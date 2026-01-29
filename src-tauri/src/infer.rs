//! Orchestrate processing, emit progress/log.
//! Semua inference dilakukan di Python dengan YOLO (ultralytics).
//! Rust hanya untuk orchestration dan UI.

use crate::config::AppConfig;
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};

// Helper untuk get infer_worker sidecar path (mirip get_converter_path di config.rs)
fn get_infer_worker_path() -> (std::path::PathBuf, bool) {
    // Try sidecar executable first
    if let Ok(exe) = std::env::current_exe() {
        if let Some(exe_dir) = exe.parent() {
            // Check in src-tauri/binaries/ (dev mode)
            if let Some(target_dir) = exe_dir.parent() {
                if let Some(src_tauri_dir) = target_dir.parent() {
                    let sidecar_bin = src_tauri_dir.join("binaries").join("infer_worker-x86_64-pc-windows-msvc.exe");
                    if sidecar_bin.exists() {
                        if let Ok(metadata) = std::fs::metadata(&sidecar_bin) {
                            if metadata.len() > 1_000_000 {
                                return (sidecar_bin, false);
                            }
                        }
                    }
                }
            }
            
            // Check in same directory as executable (production – Tauri bundle)
            #[cfg(windows)]
            let prod_names = ["infer_worker.exe", "infer_worker-x86_64-pc-windows-msvc.exe"];
            #[cfg(not(windows))]
            let prod_names: &[&str] = &["infer_worker", "infer_worker-x86_64-unknown-linux-gnu", "infer_worker-aarch64-apple-darwin", "infer_worker-x86_64-apple-darwin"];
            for &name in prod_names.iter() {
                let sidecar = exe_dir.join(name);
                if sidecar.exists() {
                    if let Ok(metadata) = std::fs::metadata(&sidecar) {
                        if metadata.len() > 1_000_000 {
                            return (sidecar, false);
                        }
                    }
                }
            }
            // Check in subdirectory binaries (production – Tauri bundle)
            let binaries_dir = exe_dir.join("binaries");
            if binaries_dir.is_dir() {
                for &name in prod_names.iter() {
                    let sidecar_bin = binaries_dir.join(name);
                    if sidecar_bin.exists() {
                        if let Ok(metadata) = std::fs::metadata(&sidecar_bin) {
                            if metadata.len() > 1_000_000 {
                                return (sidecar_bin, false);
                            }
                        }
                    }
                }
            }
        }
    }
    
    // Fallback to Python script for dev mode
    if let Ok(exe) = std::env::current_exe() {
        if let Some(exe_dir) = exe.parent() {
            let possible_paths = vec![
                exe_dir.parent().and_then(|p| p.parent()).map(|p| p.join("python_ai").join("infer_worker.py")),
            ];
            
            for path_opt in possible_paths {
                if let Some(path) = path_opt {
                    if path.exists() {
                        return (path, true);
                    }
                }
            }
        }
    }
    
    // Fallback from CWD
    if let Ok(cwd) = std::env::current_dir() {
        let fallback1 = cwd.join("src-tauri").join("python_ai").join("infer_worker.py");
        if fallback1.exists() {
            return (fallback1, true);
        }
        let fallback2 = cwd.join("python_ai").join("infer_worker.py");
        if fallback2.exists() {
            return (fallback2, true);
        }
    }
    
    // Default path
    (std::path::PathBuf::from("src-tauri/python_ai/infer_worker.py"), true)
}

/// Returns true if a real AI pack sidecar (size > 1MB) is installed.
pub fn has_ai_pack_installed() -> bool {
    let (path, use_python) = get_infer_worker_path();
    if use_python {
        return false;
    }
    path.exists()
        && std::fs::metadata(&path).map(|m| m.len() > 1_000_000).unwrap_or(false)
}

/// Returns the path to the binaries folder where AI pack should be extracted (for production).
pub fn get_ai_pack_binaries_path() -> Option<std::path::PathBuf> {
    std::env::current_exe()
        .ok()
        .and_then(|exe| exe.parent().map(|p| p.join("binaries")))
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
    let (worker_path, use_python) = get_infer_worker_path();
    if !worker_path.exists() {
        return Err(format!(
            "infer_worker sidecar not found. Run 'npm run build:sidecar' to build it."
        )
        .into());
    }

    on_log("Starting processing with Python YOLO...");
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

    let mut cmd = if use_python {
        let mut c = Command::new("python");
        c.arg("-u").arg(&worker_path);
        c.env("PYTHONUNBUFFERED", "1");
        c
    } else {
        Command::new(&worker_path)
    };
    cmd.arg("--infer-files")
        .arg(&files_json)
        .arg(model_path)
        .arg(model_name)
        .arg(config_json.to_string())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    let mut child = cmd
        .spawn()
        .map_err(|e| format!("Failed to start infer_worker: {}", e))?;
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
    if let Ok(mut log_fn) = on_log_shared.lock() {
        log_fn(&format!("Done. {} succeeded, {} failed.", successful, failed));
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

