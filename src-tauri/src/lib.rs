mod config;
mod infer;
mod specs;
// mod yolo_onnx;  // Tidak digunakan lagi - semua inference di Python

use tauri::Emitter;

use config::{
    add_model as config_add_model,
    add_tiff_paths,
    get_active_model_path,
    list_models,
    list_tiff_paths,
    load_config,
    remove_model as config_remove_model,
    remove_tiff_path,
    save_config,
    set_active_model,
    AppConfig,
};
use specs::{get_realtime_usage, get_system_specs};
use std::sync::atomic::AtomicBool;

#[tauri::command]
fn get_specs() -> Result<specs::SystemSpecs, String> {
    Ok(get_system_specs())
}

#[tauri::command]
fn get_realtime_usage_cmd() -> Result<specs::RealtimeUsage, String> {
    Ok(get_realtime_usage())
}

#[tauri::command]
fn load_config_cmd() -> Result<AppConfig, String> {
    load_config().map_err(|e| e.to_string())
}

#[tauri::command]
fn save_config_cmd(c: AppConfig) -> Result<(), String> {
    save_config(&c).map_err(|e| e.to_string())
}

#[tauri::command]
fn list_models_cmd() -> Result<Vec<config::YoloModel>, String> {
    list_models().map_err(|e| e.to_string())
}

#[tauri::command]
async fn add_model_cmd(
    window: tauri::Window,
    source_path: String,
    name: Option<String>,
) -> Result<config::YoloModel, String> {
    let path = std::path::Path::new(&source_path).to_path_buf();
    let name = name.unwrap_or_else(|| {
        path.file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("model")
            .to_string()
    });
    
    // Check if conversion is needed
    let needs_conversion = path.extension()
        .and_then(|e| e.to_str())
        .map(|e| e.eq_ignore_ascii_case("pt"))
        .unwrap_or(false);
    
    if needs_conversion {
        // Emit conversion start event
        let _ = window.emit("model-conversion-start", &format!("Converting {} to ONNX...", name));
    }
    
    // Run in background thread to avoid blocking UI
    let window_clone = window.clone();
    let name_clone = name.clone();
    let path_clone = path.clone();
    
    // Use async runtime to wait for thread result
    let (tx, rx) = std::sync::mpsc::channel();
    
    std::thread::spawn(move || {
        let result = config_add_model(name_clone.clone(), &path_clone);
        let _ = tx.send(result);
    });
    
    // Wait for result - this will block the async task but not the UI thread
    // Tauri's async runtime will handle this properly
    let result = rx.recv().map_err(|e| format!("Thread error: {}", e))?;
    
    match result {
        Ok(model) => {
            if needs_conversion {
                let _ = window_clone.emit("model-conversion-done", &format!("Successfully converted {}", name));
            }
            Ok(model)
        }
        Err(e) => {
            if needs_conversion {
                let _ = window_clone.emit("model-conversion-error", &format!("Conversion failed: {}", e));
            }
            Err(e.to_string())
        }
    }
}

#[tauri::command]
async fn add_models_cmd(
    window: tauri::Window,
    source_paths: Vec<String>,
) -> Result<Vec<config::YoloModel>, String> {
    let total = source_paths.len();
    let mut results = Vec::new();
    let mut success_count = 0;
    let mut failed_count = 0;
    
    // Emit start event for multiple models
    if total > 1 {
        let _ = window.emit("model-conversion-start", &format!("Adding {} models...", total));
    }
    
    for (index, source_path) in source_paths.iter().enumerate() {
        let path = std::path::Path::new(source_path).to_path_buf();
        let name = path.file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("model")
            .to_string();
        
        // Check if conversion is needed
        let needs_conversion = path.extension()
            .and_then(|e| e.to_str())
            .map(|e| e.eq_ignore_ascii_case("pt"))
            .unwrap_or(false);
        
        // Emit progress for current file
        if total > 1 {
            let progress_msg = if needs_conversion {
                format!("[{}/{}] Converting {} to ONNX...", index + 1, total, name)
            } else {
                format!("[{}/{}] Adding {}...", index + 1, total, name)
            };
            let _ = window.emit("model-conversion-start", &progress_msg);
        } else if needs_conversion {
            let _ = window.emit("model-conversion-start", &format!("Converting {} to ONNX...", name));
        }
        
        // Run in background thread
        let name_clone = name.clone();
        let path_clone = path.clone();
        let (tx, rx) = std::sync::mpsc::channel();
        
        std::thread::spawn(move || {
            let result = config_add_model(name_clone.clone(), &path_clone);
            let _ = tx.send(result);
        });
        
        // Wait for result
        let result = rx.recv().map_err(|e| format!("Thread error: {}", e))?;
        
        match result {
            Ok(model) => {
                results.push(model);
                success_count += 1;
                if needs_conversion {
                    let _ = window.emit("model-conversion-done", &format!("[{}/{}] Successfully converted {}", index + 1, total, name));
                }
            }
            Err(e) => {
                failed_count += 1;
                let error_msg = format!("[{}/{}] Failed to add {}: {}", index + 1, total, name, e);
                let _ = window.emit("model-conversion-error", &error_msg);
                // Continue with next file instead of returning error immediately
            }
        }
    }
    
    // Emit final summary
    if total > 1 {
        let summary = format!("Completed: {} successful, {} failed out of {}", success_count, failed_count, total);
        if failed_count == 0 {
            let _ = window.emit("model-conversion-done", &summary);
        } else {
            let _ = window.emit("model-conversion-error", &summary);
        }
    }
    
    if results.is_empty() {
        Err(format!("Failed to add any models. {} failed out of {}", failed_count, total))
    } else {
        Ok(results)
    }
}

#[tauri::command]
fn remove_model_cmd(id: i64) -> Result<(), String> {
    config_remove_model(id).map_err(|e| e.to_string())
}

#[tauri::command]
fn set_active_model_cmd(id: i64) -> Result<(), String> {
    set_active_model(id).map_err(|e| e.to_string())
}

#[tauri::command]
fn list_tiff_paths_cmd() -> Result<Vec<String>, String> {
    list_tiff_paths().map_err(|e| e.to_string())
}

#[tauri::command]
fn add_tiff_paths_cmd(paths: Vec<String>) -> Result<usize, String> {
    add_tiff_paths(paths).map_err(|e| e.to_string())
}

#[tauri::command]
fn remove_tiff_path_cmd(path: String) -> Result<(), String> {
    remove_tiff_path(&path).map_err(|e| e.to_string())
}

static PROCESSING_CANCEL: AtomicBool = AtomicBool::new(false);

#[tauri::command]
fn run_processing_cmd(
    window: tauri::Window,
    files: Vec<String>,
    model_name: String,
) -> Result<(), String> {
    let model_path = get_active_model_path()
        .map_err(|e| e.to_string())?
        .ok_or("No active model. Add and select a YOLO model first.")?;
    let config = load_config().map_err(|e| e.to_string())?;
    let cancel = &PROCESSING_CANCEL;
    cancel.store(false, std::sync::atomic::Ordering::Relaxed);

    std::thread::spawn(move || {
        let window_log = window.clone();
        let window_progress = window.clone();
        let window_done = window.clone();
        let on_log = move |s: &str| {
            let _ = window_log.emit("processing-log", s);
        };
        let on_progress = move |p: &infer::ProgressPayload| {
            let _ = window_progress.emit("processing-progress", p);
        };
        let on_done = move |d: &infer::DonePayload| {
            let _ = window_done.emit("processing-done", d);
        };
        if let Err(e) = infer::run_processing_files(
            &files,
            &model_path,
            &model_name,
            &config,
            cancel,
            on_log,
            on_progress,
            on_done,
        ) {
            let _ = window.emit("processing-log", &format!("Error: {}", e));
            let _ = window.emit(
                "processing-done",
                &infer::DonePayload {
                    successful: 0,
                    failed: 0,
                    total: 0,
                    total_abnormal: 0,
                    total_normal: 0,
                },
            );
        }
    });
    Ok(())
}

#[tauri::command]
fn cancel_processing() {
    PROCESSING_CANCEL.store(true, std::sync::atomic::Ordering::Relaxed);
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_notification::init())
        .invoke_handler(tauri::generate_handler![
            get_specs,
            get_realtime_usage_cmd,
            load_config_cmd,
            save_config_cmd,
            list_models_cmd,
            add_model_cmd,
            add_models_cmd,
            remove_model_cmd,
            set_active_model_cmd,
            list_tiff_paths_cmd,
            add_tiff_paths_cmd,
            remove_tiff_path_cmd,
            run_processing_cmd,
            cancel_processing,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
