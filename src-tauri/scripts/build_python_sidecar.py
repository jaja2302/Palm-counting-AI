"""
Build Python sidecar untuk Tauri menggunakan Nuitka.
FULL SUPPORT: YOLO + Ultralytics + GPU (CUDA)
FIX: Completely disable anti-bloat plugin via environment variable
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

def get_target_triple():
    """Get Rust target triple untuk platform saat ini"""
    result = subprocess.run(
        ["rustc", "--print", "target-triple"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        return result.stdout.strip()
    if sys.platform == "win32":
        return "x86_64-pc-windows-msvc"
    elif sys.platform == "darwin":
        return "aarch64-apple-darwin" if "arm" in os.uname().machine else "x86_64-apple-darwin"
    else:
        return "x86_64-unknown-linux-gnu"

def ensure_nuitka():
    """Ensure Nuitka installed"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "nuitka", "--version"],
            capture_output=True,
            text=True
        )
        print(f"Nuitka detected: {result.stdout.strip()}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Installing Nuitka...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "nuitka"],
            check=True
        )
        print("Nuitka installed successfully")

def get_package_data_dir(package_name):
    """Get the data directory for a package"""
    try:
        import importlib.util
        spec = importlib.util.find_spec(package_name)
        if spec and spec.origin:
            return str(Path(spec.origin).parent)
    except:
        pass
    return None

def build_sidecar_nuitka(script_name, output_name_base):
    """Build a single Python sidecar script using Nuitka"""
    script_dir = Path(__file__).parent
    src_tauri_dir = script_dir.parent
    python_ai_dir = src_tauri_dir / "python_ai"
    binaries_dir = src_tauri_dir / "binaries"
    
    binaries_dir.mkdir(exist_ok=True)
    
    worker_script = python_ai_dir / script_name
    if not worker_script.exists():
        print(f"ERROR: {worker_script} tidak ditemukan!")
        return False
    
    print(f"Building Python sidecar dengan Nuitka dari {worker_script}")
    
    target_triple = get_target_triple()
    output_name = f"{output_name_base}-{target_triple}"
    
    print(f"Target triple: {target_triple}")
    print(f"Output name: {output_name}")
    
    # Nuitka build command - Base options
    nuitka_cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",  # Create standalone distribution
        "--onefile",  # Create single executable
        "--assume-yes-for-downloads",  # Auto-download dependencies
        "--output-filename=" + (output_name + ".exe" if sys.platform == "win32" else output_name),
        "--output-dir=" + str(binaries_dir),
        
        # ============================================
        # CRITICAL: Disable ALL plugins to avoid subprocess crashes
        # ============================================
        "--plugin-no-detection",  # Disable automatic plugin detection
    ]
    
    # Windows-specific options
    if sys.platform == "win32":
        nuitka_cmd.extend([
            "--windows-console-mode=disable",  # No console window
        ])
    
    # Script-specific options
    if script_name == "infer_worker.py":
        print("  Configuring for YOLO + Ultralytics + GPU (CUDA)...")
        print("  ⚠️  Disabling ALL plugins to avoid subprocess crash with path spaces")
        
        nuitka_cmd.extend([
            # ============================================
            # PyTorch + CUDA Support (CRITICAL for GPU)
            # ============================================
            "--include-package=torch",
            "--include-package=torch.nn",
            "--include-package=torch.cuda",
            "--include-package=torch._C",  # C extensions (CRITICAL!)
            "--include-package=torch.backends",
            "--include-package=torch.backends.cuda",
            "--include-package=torch.backends.cudnn",  # cuDNN support
            "--include-package=torch.distributed",
            "--include-package=torch.utils",
            "--include-package=torch.utils.data",
            "--include-package=torch.autograd",
            "--include-package=torch.nn.functional",
            
            # TorchVision
            "--include-package=torchvision",
            "--include-package=torchvision.transforms",
            "--include-package=torchvision.models",
            
            # ============================================
            # Ultralytics + YOLO (CRITICAL)
            # ============================================
            "--include-package=ultralytics",
            "--include-package=ultralytics.models",
            "--include-package=ultralytics.models.yolo",
            "--include-package=ultralytics.models.yolo.detect",
            "--include-package=ultralytics.models.yolo.segment",
            "--include-package=ultralytics.engine",
            "--include-package=ultralytics.engine.predictor",
            "--include-package=ultralytics.engine.results",
            "--include-package=ultralytics.utils",
            "--include-package=ultralytics.data",
            "--include-package=ultralytics.nn",
            
            # ============================================
            # Image Processing
            # ============================================
            "--include-package=PIL",
            "--include-package=cv2",
            "--include-package=numpy",
            
            # ============================================
            # Geo Libraries
            # ============================================
            "--include-package=geojson",
            "--include-package=shapely",
            "--include-package=geopandas",
            "--include-package=fastkml",
            
            # ============================================
            # Utilities
            # ============================================
            "--include-package=yaml",
            "--include-package=tqdm",
            "--include-package=pathlib",
            
            # ============================================
            # Follow Imports (Auto-detect submodules)
            # ============================================
            "--follow-import-to=torch",
            "--follow-import-to=torchvision",
            "--follow-import-to=ultralytics",
            "--follow-import-to=numpy",
            "--follow-import-to=cv2",
            "--follow-import-to=PIL",
        ])
        
        # ============================================
        # CRITICAL: Include Ultralytics Data Files
        # ============================================
        ultralytics_dir = get_package_data_dir("ultralytics")
        if ultralytics_dir:
            print(f"  Found ultralytics at: {ultralytics_dir}")
            nuitka_cmd.extend([
                f"--include-data-dir={ultralytics_dir}=ultralytics",
            ])
        
        # ============================================
        # CRITICAL: Include PyTorch CUDA DLLs (Windows)
        # ============================================
        if sys.platform == "win32":
            torch_dir = get_package_data_dir("torch")
            if torch_dir:
                torch_lib = Path(torch_dir) / "lib"
                if torch_lib.exists():
                    print(f"  Found PyTorch CUDA libs at: {torch_lib}")
                    # Include semua DLL dari torch/lib
                    dll_count = 0
                    for dll_file in torch_lib.glob("*.dll"):
                        nuitka_cmd.append(f"--include-data-files={dll_file}=torch/lib/{dll_file.name}")
                        dll_count += 1
                    print(f"  Including {dll_count} CUDA DLLs")
    else:
        # Unknown script
        print(f"  WARNING: Unknown script {script_name}, using default Nuitka options")
    
    # Add the script at the end
    nuitka_cmd.append(str(worker_script))
    
    print(f"\nRunning Nuitka...")
    if script_name == "infer_worker.py":
        print(f"  ⚠️  First build: 20-30 minutes (PyTorch + CUDA + no plugin optimizations)")
        print(f"  ⚠️  File size may be larger (~600MB-1.2GB)")
        print(f"  ℹ️  Plugin disabled to avoid subprocess crash")
    else:
        print(f"  Expected time: 2-5 minutes...")
    
    print(f"\n  Full command saved for debugging...")
    debug_cmd_file = binaries_dir / f"nuitka_cmd_{output_name_base}.txt"
    debug_cmd_file.write_text(' \\\n  '.join(nuitka_cmd), encoding='utf-8')
    print(f"  Command file: {debug_cmd_file}")
    
    # Set environment for better output
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    
    # ============================================
    # CRITICAL: Disable anti-bloat via environment variable
    # ============================================
    env["NUITKA_PLUGIN_ANTI_BLOAT_DISABLE"] = "1"
    
    # Run Nuitka
    print("\n" + "="*70)
    result = subprocess.run(
        nuitka_cmd,
        cwd=str(python_ai_dir),
        env=env,
        check=False
    )
    print("="*70 + "\n")
    
    if result.returncode != 0:
        print(f"\n❌ ERROR: Nuitka build failed with return code {result.returncode}!")
        print("\nThis is a known issue with Nuitka + Python path containing spaces.")
        print("\n🔧 ULTIMATE SOLUTION:")
        print("   Install Python in a path without spaces:")
        print("   1. Download Python from python.org")
        print("   2. Custom installation to: C:\\Python311")
        print("   3. Install dependencies: pip install -r requirements.txt")
        print("   4. Build from that Python: C:\\Python311\\python.exe src-tauri/scripts/build_python_sidecar.py")
        print(f"\nDebug command saved to: {debug_cmd_file}")
        return False
    
    # Check if output exists
    if sys.platform == "win32":
        final_output = binaries_dir / f"{output_name}.exe"
    else:
        final_output = binaries_dir / output_name
    
    if not final_output.exists():
        print(f"ERROR: Build output tidak ditemukan: {final_output}")
        print(f"  Expected: {final_output}")
        if binaries_dir.exists():
            print(f"  Binaries dir contents:")
            for item in binaries_dir.iterdir():
                print(f"    - {item.name} ({item.stat().st_size / (1024*1024):.1f} MB)")
        return False
    
    print(f"✓ Python sidecar berhasil dibuild dengan Nuitka: {final_output}")
    print(f"  Size: {final_output.stat().st_size / (1024*1024):.2f} MB")
    
    return True

def build_python_sidecar():
    """Build all Python sidecars using Nuitka"""
    print("=" * 70)
    print("Building Python sidecars with Nuitka")
    print("FULL SUPPORT: YOLO + Ultralytics + GPU (CUDA)")
    print("=" * 70)
    
    # Ensure Nuitka installed
    print("\nChecking Nuitka installation...")
    try:
        ensure_nuitka()
    except Exception as e:
        print(f"ERROR: Failed to install Nuitka: {e}")
        return False
    
    # Build infer_worker (long build due to PyTorch + CUDA)
    print("\n" + "=" * 70)
    print("[1/1] Building infer_worker (YOLO + GPU)...")
    print("=" * 70)
    success1 = build_sidecar_nuitka("infer_worker.py", "infer_worker")
    
    if success1:
        print("\n" + "=" * 70)
        print("✓ Sidecar built successfully with Nuitka!")
        print("=" * 70)
        print("\n📋 Important Notes:")
        print("  • Executable includes CUDA support for GPU inference")
        print("  • File size may be large due to disabled optimizations")
        print("  • Executable will auto-detect GPU on target PC")
        return True
    else:
        print("\n" + "=" * 70)
        print("✗ Sidecar build failed!")
        print("  - infer_worker: FAILED")
        print("\n💡 Recommendation: Install Python in C:\\Python311 (no spaces)")
        print("=" * 70)
        return False

if __name__ == "__main__":
    success = build_python_sidecar()
    sys.exit(0 if success else 1)