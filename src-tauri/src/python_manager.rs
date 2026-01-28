use std::path::PathBuf;
use std::process::Command;

pub struct PythonManager {
    python_exe: PathBuf,
    requirements_path: PathBuf,
    marker_file: PathBuf,
}

impl PythonManager {
    pub fn new(_app_handle: &tauri::AppHandle) -> Result<Self, String> {
        // Folder tempat executable berada (install dir)
        let exe_dir = std::env::current_exe()
            .map_err(|e| format!("Failed to get current_exe: {}", e))?
            .parent()
            .ok_or("Failed to get exe directory")?
            .to_path_buf();

        // Python portable yang dibundel: ./python/python.exe (Windows) atau ./python/python
        let python_exe = if cfg!(target_os = "windows") {
            exe_dir.join("python").join("python.exe")
        } else {
            exe_dir.join("python").join("python")
        };

        // requirements.txt dibundel di samping app: ./python_ai/requirements.txt
        let requirements_path = exe_dir.join("python_ai").join("requirements.txt");

        // Marker bahwa environment sudah pernah di-setup, simpan di subfolder lokal
        let app_dir = exe_dir.join("data");
        let marker_file = app_dir.join("python_env_ready.txt");

        Ok(Self {
            python_exe,
            requirements_path,
            marker_file,
        })
    }

    pub fn is_ready(&self) -> bool {
        self.marker_file.exists()
    }

    /// Setup environment sekali (first run): pip install -r requirements.txt
    pub fn setup<F>(&self, progress: F) -> Result<(), String>
    where
        F: Fn(String),
    {
        if self.is_ready() {
            progress("Python environment already initialized.".to_string());
            return Ok(());
        }

        if !self.python_exe.exists() {
            return Err(format!(
                "Bundled Python not found at: {}",
                self.python_exe.display()
            ));
        }

        if !self.requirements_path.exists() {
            return Err(format!(
                "requirements.txt not found at: {}",
                self.requirements_path.display()
            ));
        }

        progress(format!(
            "Using Python at: {}",
            self.python_exe.display()
        ));
        progress("Installing AI dependencies (this may take a while, especially torch + CUDA)...".to_string());

        let output = Command::new(&self.python_exe)
            .arg("-m")
            .arg("pip")
            .arg("install")
            .arg("-r")
            .arg(&self.requirements_path)
            .output()
            .map_err(|e| format!("Failed to start pip: {}", e))?;

        if !output.status.success() {
            let stderr = String::from_utf8_lossy(&output.stderr);
            return Err(format!("pip install failed: {}", stderr));
        }

        // Simpan marker supaya tidak install ulang tiap kali
        if let Some(parent) = self.marker_file.parent() {
            std::fs::create_dir_all(parent)
                .map_err(|e| format!("Failed to create app data dir: {}", e))?;
        }
        std::fs::write(&self.marker_file, "ok")
            .map_err(|e| format!("Failed to write marker file: {}", e))?;

        progress("Python environment setup complete.".to_string());
        Ok(())
    }

    pub fn get_python_executable(&self) -> PathBuf {
        self.python_exe.clone()
    }
}

