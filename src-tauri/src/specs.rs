//! System specs (CPU, RAM, GPU) and real-time CPU/GPU usage for status UI.

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

    let (gpu, gpu_mem) = gpu_info();

    SystemSpecs {
        os,
        processor,
        total_ram_gb: format_bytes_gb(total),
        available_ram_gb: format_bytes_gb(available),
        ram_percent: format!("{:.0}%", ram_pct),
        cpu_cores: sys.physical_core_count().unwrap_or(0) as u32,
        cpu_threads: sys.cpus().len() as u32,
        gpu,
        gpu_memory: gpu_mem,
    }
}

fn gpu_info() -> (String, String) {
    #[cfg(target_os = "windows")]
    {
        gpu_info_nvidia_smi()
    }
    #[cfg(not(target_os = "windows"))]
    {
        gpu_info_nvidia_smi()
    }
}

fn gpu_info_nvidia_smi() -> (String, String) {
    let out = std::process::Command::new("nvidia-smi")
        .args(["--query-gpu=name,memory.total", "--format=csv,noheader,nounits"])
        .output();
    match out {
        Ok(o) if o.status.success() => {
            let s = String::from_utf8_lossy(&o.stdout);
            let line = s.lines().next().unwrap_or("").trim();
            if line.is_empty() {
                return ("No GPU".into(), "".into());
            }
            let parts: Vec<&str> = line.split(',').map(|x| x.trim()).collect();
            let name = parts.first().unwrap_or(&"").to_string();
            let mem = parts.get(1).unwrap_or(&"").to_string();
            let mem = if mem.is_empty() { mem } else { format!("{} MB", mem) };
            (name, mem)
        }
        _ => ("No CUDA GPU".into(), "".into()),
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

/// Sample CPU usage (sysinfo) and GPU utilization/memory/temp (nvidia-smi).
/// Call every 1–2 s for live stats. First CPU read may be low; subsequent calls improve.
pub fn get_realtime_usage() -> RealtimeUsage {
    let cpu_percent = {
        let mut sys = System::new_with_specifics(
            RefreshKind::new().with_cpu(CpuRefreshKind::everything()),
        );
        std::thread::sleep(sysinfo::MINIMUM_CPU_UPDATE_INTERVAL);
        sys.refresh_cpu_usage();
        sys.global_cpu_usage()
    };

    let (gpu_percent, gpu_mem_used, gpu_mem_total, gpu_temp) = gpu_realtime_nvidia_smi();

    RealtimeUsage {
        cpu_percent,
        gpu_percent,
        gpu_memory_used_mb: gpu_mem_used,
        gpu_memory_total_mb: gpu_mem_total,
        gpu_temp_c: gpu_temp,
    }
}

fn gpu_realtime_nvidia_smi() -> (Option<u32>, Option<u64>, Option<u64>, Option<u32>) {
    let out = std::process::Command::new("nvidia-smi")
        .args([
            "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
            "--format=csv,noheader,nounits",
        ])
        .output();
    match out {
        Ok(o) if o.status.success() => {
            let s = String::from_utf8_lossy(&o.stdout);
            let line = s.lines().next().unwrap_or("").trim();
            if line.is_empty() {
                return (None, None, None, None);
            }
            let parts: Vec<&str> = line.split(',').map(|x| x.trim()).collect();
            let pct = parts.get(0).and_then(|x| x.parse::<u32>().ok());
            let used = parts.get(1).and_then(|x| x.parse::<u64>().ok());
            let total = parts.get(2).and_then(|x| x.parse::<u64>().ok());
            let temp = parts.get(3).and_then(|x| x.parse::<u32>().ok());
            (pct, used, total, temp)
        }
        _ => (None, None, None, None),
    }
}
