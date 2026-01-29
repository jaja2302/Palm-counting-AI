//! Orchestrate processing, emit progress/log.
//! Semua inference dilakukan di Python dengan YOLO (ultralytics).
//! Rust hanya untuk orchestration dan UI.

use crate::config::AppConfig;
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};

// Minimum exe size (bytes) untuk dianggap sidecar asli, bukan placeholder.
// Placeholder ~98 bytes; cx_Freeze launcher bisa kecil (~1 KB), Nuitka/PyInstaller lebih besar.
const MIN_SIDECAR_EXE_SIZE: u64 = 500;

/// Returns true if path is a real sidecar (not dev placeholder). Only exe size is checked.
fn is_real_sidecar(path: &std::path::Path) -> bool {
    let Ok(meta) = std::fs::metadata(path) else { return false };
    meta.len() >= MIN_SIDECAR_EXE_SIZE
}

// Helper untuk get infer_worker sidecar exe path. Hanya dari AppData Local (palm-counting-ai/binaries/).
fn get_infer_worker_path() -> std::path::PathBuf {
    #[cfg(windows)]
    let prod_names = ["infer_worker.exe", "infer_worker-x86_64-pc-windows-msvc.exe"];
    #[cfg(not(windows))]
    let prod_names: &[&str] = &[
        "infer_worker",
        "infer_worker-x86_64-unknown-linux-gnu",
        "infer_worker-aarch64-apple-darwin",
        "infer_worker-x86_64-apple-darwin",
    ];

    let app_bin = crate::config::app_data_binaries_dir();
    if app_bin.is_dir() {
        for &name in prod_names.iter() {
            let sidecar_bin = app_bin.join(name);
            if sidecar_bin.is_file() && is_real_sidecar(&sidecar_bin) {
                return sidecar_bin;
            }
        }
    }

    // Fallback dummy path untuk pesan error (exe tetap tidak ada)
    app_bin.join(prod_names[0])
}

/// Total size (bytes) of all files in dir (recursive). Public for aipack validation.
pub(crate) fn dir_total_size(path: &std::path::Path) -> u64 {
    let mut total = 0u64;
    if let Ok(entries) = path.read_dir() {
        for e in entries.flatten() {
            let p = e.path();
            if p.is_dir() {
                total += dir_total_size(&p);
            } else if let Ok(m) = std::fs::metadata(&p) {
                total += m.len();
            }
        }
    }
    total
}

/// Returns true if AI pack sudah terpasang: folder AppData binaries ada dan ada isinya (exe sidecar).
/// Jika folder tidak ada = belum download AI pack dari server.
pub fn has_ai_pack_installed() -> bool {
    let app_bin = crate::config::app_data_binaries_dir();
    if !app_bin.is_dir() {
        return false;
    }
    let path = get_infer_worker_path();
    path.is_file() && is_real_sidecar(&path)
}

/// Returns the path to the binaries folder where AI pack should be extracted.
/// Sama seperti models/ dan database.db: AppData Local palm-counting-ai/binaries/.
pub fn get_ai_pack_binaries_path() -> Option<std::path::PathBuf> {
    Some(crate::config::app_data_binaries_dir())
}

#[derive(Clone, serde::Serialize)]
pub struct ProgressPayload {
    pub processed: usize,
    pub total: usize,
    pub current_file: String,
    pub status: String,
    pub abnormal_count: u32,
    pub normal_count: u32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub output_folder: Option<String>,
}

#[derive(Clone, serde::Serialize)]
pub struct DonePayload {
    pub successful: usize,
    pub failed: usize,
    pub total: usize,
    pub total_abnormal: u32,
    pub total_normal: u32,
}

/// Process daftar file .tif; output per file ke folder {stem}_{model_name}/.
pub fn run_processing_files(
    files: &[String],
    model_path: &str,
    model_name: &str,
    config: &AppConfig,
    cancel: &AtomicBool,
    mut on_log: impl FnMut(&str) + Send + 'static,
    mut on_progress: impl FnMut(&ProgressPayload),
    mut on_done: impl FnMut(&DonePayload),
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    use std::io::{BufRead, BufReader};
    use std::process::{Command, Stdio};

    if files.is_empty() {
        return Err("No files to process".into());
    }
    let model_path_buf = Path::new(model_path);
    if !model_path_buf.is_file() {
        return Err(format!("Model file not found: {}", model_path).into());
    }
    let app_bin = crate::config::app_data_binaries_dir();
    if !app_bin.is_dir() {
        return Err(
            "AI pack belum didownload dari server. Download AI pack terlebih dahulu dari aplikasi."
                .into(),
        );
    }
    let worker_path = get_infer_worker_path();
    if !worker_path.exists() {
        #[cfg(windows)]
        let exe_name = "infer_worker-x86_64-pc-windows-msvc.exe";
        #[cfg(not(windows))]
        let exe_name = "infer_worker (sesuai target triple)";
        return Err(format!(
            "infer_worker tidak ditemukan di {}. Pastikan AI pack berisi file {} (bukan placeholder).",
            app_bin.display(),
            exe_name
        )
        .into());
    }

    eprintln!("[palm-counting-ai] Starting processing with infer_worker (sidecar)...");
    on_log("Starting processing with infer_worker (sidecar)...");
    let worker_path_display = worker_path.display().to_string();
    eprintln!("[palm-counting-ai] Using sidecar exe: {}", worker_path_display);
    on_log(&format!("Using sidecar exe: {}", worker_path_display));
    let config_json = serde_json::json!({
        "imgsz": config.imgsz,
        "conf": config.conf,
        "iou": config.iou,
        "max_det": config.max_det,
        "device": config.device,
        "convert_kml": config.convert_kml,
        "convert_shp": config.convert_shp,
        "save_annotated": config.save_annotated,
        "line_width": config.line_width,
        "show_labels": config.show_labels,
        "show_conf": config.show_conf,
    });
    let files_json = serde_json::to_string(files)
        .map_err(|e| format!("Failed to serialize files: {}", e))?;

    // Wajib pakai sidecar executable (tanpa fallback Python).
    let mut cmd = Command::new(&worker_path);
    cmd.arg("--infer-files")
        .arg(&files_json)
        .arg(model_path)
        .arg(model_name)
        .arg(config_json.to_string())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    let mut child = cmd.spawn().map_err(|e| {
        let msg = format!("Failed to start infer_worker: {}", e);
        if e.raw_os_error() == Some(216) {
            format!(
                "{} (Error 216: exe tidak kompatibel—mungkin file placeholder. Build dengan: npm run build:sidecar:cxfreeze lalu salin isi folder src-tauri/binaries ke AppData Local palm-counting-ai/binaries)",
                msg
            )
        } else {
            msg
        }
    })?;
    let stdout = child.stdout.take().ok_or("Failed to capture stdout")?;
    let stderr = child.stderr.take().ok_or("Failed to capture stderr")?;
    let stdout_reader = BufReader::new(stdout);
    let stderr_reader = BufReader::new(stderr);

    let mut successful = 0_usize;
    let mut failed = 0_usize;
    let mut total_abnormal = 0_u32;
    let mut total_normal = 0_u32;
    let mut total = 0_usize;

    use std::sync::{Arc, Mutex};
    let on_log_shared = Arc::new(Mutex::new(on_log));
    let on_log_clone = on_log_shared.clone();
    let stderr_reader_clone = stderr_reader;
    std::thread::spawn(move || {
        let mut lines = stderr_reader_clone.lines();
        while let Some(Ok(line)) = lines.next() {
            if !line.trim().is_empty() {
                eprintln!("[infer_worker] {}", line);
                if let Ok(mut log_fn) = on_log_clone.lock() {
                    log_fn(&line);
                }
            }
        }
    });

    let mut stdout_lines = stdout_reader.lines();
    loop {
        if cancel.load(Ordering::Relaxed) {
            let _ = child.kill();
            eprintln!("[palm-counting-ai] Cancelled.");
            if let Ok(mut log_fn) = on_log_shared.lock() {
                log_fn("Cancelled.");
            }
            break;
        }
        let line = match stdout_lines.next() {
            Some(Ok(line)) => line,
            Some(Err(_)) | None => break,
        };
        if line.trim().is_empty() {
            continue;
        }
        if let Ok(progress) = serde_json::from_str::<serde_json::Value>(&line) {
            if progress.get("done").and_then(|v| v.as_bool()).unwrap_or(false) {
                successful = progress.get("successful").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
                failed = progress.get("failed").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
                total = progress.get("total").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
                total_abnormal = progress.get("total_abnormal").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
                total_normal = progress.get("total_normal").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
                break;
            } else {
                let processed = progress.get("processed").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
                total = progress.get("total").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
                let current_file = progress.get("current_file").and_then(|v| v.as_str()).unwrap_or("").to_string();
                let status = progress.get("status").and_then(|v| v.as_str()).unwrap_or("").to_string();
                let abnormal_count = progress.get("abnormal_count").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
                let normal_count = progress.get("normal_count").and_then(|v| v.as_u64()).unwrap_or(0) as u32;
                successful = progress.get("successful").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
                failed = progress.get("failed").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
                let output_folder = progress
                    .get("output_folder")
                    .and_then(|v| v.as_str())
                    .filter(|s| !s.is_empty())
                    .map(String::from);
                on_progress(&ProgressPayload {
                    processed,
                    total,
                    current_file,
                    status,
                    abnormal_count,
                    normal_count,
                    output_folder,
                });
            }
        }
    }

    let _ = child.wait();
    let done_msg = format!("Done. {} succeeded, {} failed.", successful, failed);
    eprintln!("[palm-counting-ai] {}", done_msg);
    if let Ok(mut log_fn) = on_log_shared.lock() {
        log_fn(&done_msg);
    }
    on_done(&DonePayload {
        successful,
        failed,
        total,
        total_abnormal,
        total_normal,
    });
    Ok(())
}

