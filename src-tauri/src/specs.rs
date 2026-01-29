//! System specs (CPU, RAM) dan real-time CPU usage untuk status UI.
//! GPU tidak dideteksi di sini; AI pack (Python exe) yang mendeteksi GPU saat processing.

use serde::Serialize;
use sysinfo::{CpuRefreshKind, RefreshKind, System};

#[derive(Debug, Serialize)]
pub struct SystemSpecs {
    pub os: String,
    pub processor: String,
    pub total_ram_gb: String,
    pub available_ram_gb: String,
    pub ram_percent: String,
    pub cpu_cores: u32,
    pub cpu_threads: u32,
    pub gpu: String,
    pub gpu_memory: String,
}

fn format_bytes_gb(bytes: u64) -> String {
    format!("{:.1}", bytes as f64 / (1024.0 * 1024.0 * 1024.0))
}

pub fn get_system_specs() -> SystemSpecs {
    let mut sys = System::new_all();
    sys.refresh_all();

    let total = sys.total_memory();
    let available = sys.available_memory();
    let used = total.saturating_sub(available);
    let ram_pct = if total > 0 {
        (100.0 * used as f64 / total as f64).round()
    } else {
        0.0
    };

    let processor = sys.cpus().first().map(|c| c.brand().to_string()).unwrap_or_else(|| "Unknown".into());
    let os = match std::env::consts::OS {
        "windows" => "Windows",
        "macos" => "macOS",
        "linux" => "Linux",
        o => o,
    }
    .to_string();

    // GPU dideteksi oleh AI pack (Python exe) saat processing, tidak di sini
    let gpu = "—".to_string();
    let gpu_memory = String::new();

    SystemSpecs {
        os,
        processor,
        total_ram_gb: format_bytes_gb(total),
        available_ram_gb: format_bytes_gb(available),
        ram_percent: format!("{:.0}%", ram_pct),
        cpu_cores: sys.physical_core_count().unwrap_or(0) as u32,
        cpu_threads: sys.cpus().len() as u32,
        gpu,
        gpu_memory,
    }
}

/// Real-time CPU and GPU usage (for live monitoring in UI).
#[derive(Debug, Clone, serde::Serialize)]
pub struct RealtimeUsage {
    pub cpu_percent: f32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gpu_percent: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gpu_memory_used_mb: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gpu_memory_total_mb: Option<u64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub gpu_temp_c: Option<u32>,
}

/// Sample CPU usage (sysinfo). GPU tidak dibaca di sini; AI pack yang handle saat run.
pub fn get_realtime_usage() -> RealtimeUsage {
    let cpu_percent = {
        let mut sys = System::new_with_specifics(
            RefreshKind::new().with_cpu(CpuRefreshKind::everything()),
        );
        sys.refresh_cpu_usage();
        sys.global_cpu_usage()
    };

    RealtimeUsage {
        cpu_percent,
        gpu_percent: None,
        gpu_memory_used_mb: None,
        gpu_memory_total_mb: None,
        gpu_temp_c: None,
    }
}
