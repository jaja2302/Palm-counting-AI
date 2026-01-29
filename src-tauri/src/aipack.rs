//! Download AI pack dari API dengan dukungan pause/resume (Range) dan unzip.

use std::io::Write;
use std::sync::atomic::{AtomicBool, Ordering};

use tauri::Emitter;

static DOWNLOAD_CANCEL: AtomicBool = AtomicBool::new(false);

const PARTIAL_NAME: &str = "palm-ai-pack-download.partial";
const ZIP_NAME: &str = "palm-ai-pack-download.zip";

fn temp_partial_path() -> std::path::PathBuf {
    std::env::temp_dir().join(PARTIAL_NAME)
}

fn temp_zip_path() -> std::path::PathBuf {
    std::env::temp_dir().join(ZIP_NAME)
}

async fn do_download(window: &tauri::Window, base_url: &str) -> Result<(), String> {
    DOWNLOAD_CANCEL.store(false, Ordering::Relaxed);
    let client = reqwest::Client::new();
    let info_url = format!("{}/info", base_url.trim_end_matches('/'));
    let download_url = format!("{}/download", base_url.trim_end_matches('/'));

    let info: serde_json::Value = client
        .get(&info_url)
        .send()
        .await
        .map_err(|e| e.to_string())?
        .error_for_status()
        .map_err(|e| e.to_string())?
        .json()
        .await
        .map_err(|e| e.to_string())?;

    let total = info
        .get("size_bytes")
        .and_then(|v| v.as_u64())
        .unwrap_or(0) as u64;

    if total == 0 {
        return Err("AI pack tidak tersedia (size 0)".to_string());
    }

    let partial_path = temp_partial_path();
    let zip_path = temp_zip_path();
    let mut start: u64 = 0;
    if partial_path.exists() {
        start = std::fs::metadata(&partial_path)
            .map(|m| m.len())
            .unwrap_or(0) as u64;
        if start >= total {
            std::fs::remove_file(&partial_path).ok();
            start = 0;
        }
    }

    let mut request = client.get(&download_url);
    if start > 0 {
        request = request.header("Range", format!("bytes={}-", start));
    }

    let response = request.send().await.map_err(|e| e.to_string())?;
    let status = response.status();
    if !status.is_success() && status.as_u16() != 206 {
        return Err(format!("Download gagal: {}", status));
    }

    let _content_length = response
        .content_length()
        .or_else(|| {
            response
                .headers()
                .get("Content-Range")
                .and_then(|v| v.to_str().ok())
                .and_then(|s| s.split('/').nth(1))
                .and_then(|s| s.parse::<u64>().ok())
        })
        .unwrap_or(total);

    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .write(true)
        .append(start > 0)
        .open(&partial_path)
        .map_err(|e| e.to_string())?;

    let mut stream = response.bytes_stream();
    let mut downloaded = start;

    use futures_util::StreamExt;
    while let Some(chunk) = stream.next().await {
        if DOWNLOAD_CANCEL.load(Ordering::Relaxed) {
            let _ = window.emit(
                "ai-pack-paused",
                serde_json::json!({ "downloaded": downloaded, "total": total }),
            );
            return Ok(());
        }
        let chunk = chunk.map_err(|e| e.to_string())?;
        file.write_all(&chunk).map_err(|e| e.to_string())?;
        downloaded += chunk.len() as u64;
        let percent = if total > 0 {
            (downloaded as f64 / total as f64 * 100.0).min(100.0)
        } else {
            0.0
        };
        let _ = window.emit(
            "ai-pack-progress",
            serde_json::json!({
                "downloaded": downloaded,
                "total": total,
                "percent": percent.round()
            }),
        );
    }

    drop(file);
    std::fs::rename(&partial_path, &zip_path).map_err(|e| e.to_string())?;

    let binaries_path = crate::infer::get_ai_pack_binaries_path()
        .ok_or_else(|| "Tidak dapat menentukan folder binaries".to_string())?;
    std::fs::create_dir_all(&binaries_path).map_err(|e| e.to_string())?;

    let zip_file = std::fs::File::open(&zip_path).map_err(|e| e.to_string())?;
    let mut archive = zip::ZipArchive::new(zip_file).map_err(|e| e.to_string())?;
    let total_entries = archive.len();
    let _ = window.emit(
        "ai-pack-extracting",
        serde_json::json!({ "total": total_entries }),
    );
    let mut extracted = 0_usize;
    for i in 0..total_entries {
        let mut entry = archive.by_index(i).map_err(|e| e.to_string())?;
        let name = entry.name().replace('\\', "/");
        let name_trim = name
            .trim_start_matches("binaries/")
            .trim_start_matches("binaries\\");
        if name_trim.is_empty() || name_trim.ends_with('/') {
            continue;
        }
        let out_path = binaries_path.join(name_trim);
        if entry.is_dir() {
            std::fs::create_dir_all(&out_path).map_err(|e| e.to_string())?;
        } else {
            if let Some(p) = out_path.parent() {
                std::fs::create_dir_all(p).map_err(|e| e.to_string())?;
            }
            let mut out = std::fs::File::create(&out_path).map_err(|e| e.to_string())?;
            std::io::copy(&mut entry, &mut out).map_err(|e| e.to_string())?;
        }
        extracted += 1;
        if extracted % 50 == 0 || extracted == total_entries {
            let _ = window.emit(
                "ai-pack-extract-progress",
                serde_json::json!({
                    "current": extracted,
                    "total": total_entries,
                    "percent": if total_entries > 0 { (extracted as f64 / total_entries as f64 * 100.0).round() } else { 100.0 }
                }),
            );
        }
    }
    std::fs::remove_file(&zip_path).ok();

    // Validasi folder yang benar-benar kita ekstrak (bukan path lain yang dipakai has_ai_pack_installed di dev).
    const MIN_SIZE_BYTES: u64 = 5_000_000; // 5 MB
    #[cfg(windows)]
    let exe_names = ["infer_worker.exe", "infer_worker-x86_64-pc-windows-msvc.exe"];
    #[cfg(not(windows))]
    let exe_names = ["infer_worker", "infer_worker-x86_64-unknown-linux-gnu", "infer_worker-aarch64-apple-darwin", "infer_worker-x86_64-apple-darwin"];

    let extracted_size = crate::infer::dir_total_size(&binaries_path);
    let exe_found = exe_names
        .iter()
        .any(|name| binaries_path.join(name).is_file());

    let path_str = binaries_path.display().to_string();
    let size_mb = extracted_size as f64 / 1_000_000.0;
    let _ = window.emit(
        "ai-pack-log",
        serde_json::json!({
            "message": format!(
                "Validasi: folder={}, ukuran={} bytes ({:.2} MB), exe_ada={}, minimum=5 MB",
                path_str, extracted_size, size_mb, exe_found
            ),
            "path": path_str,
            "size_bytes": extracted_size,
            "size_mb": size_mb,
            "threshold_mb": 5,
            "exe_found": exe_found,
        }),
    );

    let valid = extracted_size > MIN_SIZE_BYTES && exe_found;
    if !valid {
        let reason = if !exe_found {
            "infer_worker exe tidak ditemukan di folder extract"
        } else {
            "ukuran folder extract di bawah 5 MB"
        };
        let detail = format!(
            "Folder: {} | Ukuran: {} bytes ({:.2} MB) | Minimum: 5 MB | Penyebab: {}",
            path_str, extracted_size, size_mb, reason
        );
        let _ = window.emit("ai-pack-log", serde_json::json!({ "message": detail }));
        return Err(format!(
            "File yang didownload bukan AI pack valid. {}",
            detail
        ));
    }

    let _ = window.emit("ai-pack-done", ());
    Ok(())
}

#[tauri::command]
pub async fn start_download_ai_pack(window: tauri::Window, base_url: String) -> Result<(), String> {
    let url = base_url.trim_end_matches('/').to_string();
    tauri::async_runtime::spawn(async move {
        if let Err(e) = do_download(&window, &url).await {
            let _ = window.emit("ai-pack-error", &e);
        }
    });
    Ok(())
}

#[tauri::command]
pub fn pause_download_ai_pack() {
    DOWNLOAD_CANCEL.store(true, Ordering::Relaxed);
}

#[tauri::command]
pub fn check_ai_pack_installed() -> bool {
    crate::infer::has_ai_pack_installed()
}

#[tauri::command]
pub fn get_ai_pack_path() -> Option<String> {
    crate::infer::get_ai_pack_binaries_path().map(|p| p.to_string_lossy().to_string())
}
