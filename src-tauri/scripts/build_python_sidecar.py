"""
Build Python sidecar untuk Tauri.
Menggunakan PyInstaller untuk bundle infer_worker.py sebagai standalone executable.
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
    # Fallback untuk Windows
    if sys.platform == "win32":
        return "x86_64-pc-windows-msvc"
    elif sys.platform == "darwin":
        return "aarch64-apple-darwin" if "arm" in os.uname().machine else "x86_64-apple-darwin"
    else:
        return "x86_64-unknown-linux-gnu"

def build_sidecar(script_name, output_name_base):
    """Build a single Python sidecar script"""
    script_dir = Path(__file__).parent
    src_tauri_dir = script_dir.parent  # scripts/ -> src-tauri/
    python_ai_dir = src_tauri_dir / "python_ai"  # python_ai sekarang di src-tauri/
    binaries_dir = src_tauri_dir / "binaries"
    
    # Buat direktori binaries jika belum ada
    binaries_dir.mkdir(exist_ok=True)
    
    # Path ke script
    worker_script = python_ai_dir / script_name
    if not worker_script.exists():
        print(f"ERROR: {worker_script} tidak ditemukan!")
        return False
    
    print(f"Building Python sidecar dari {worker_script}")
    
    # Install PyInstaller jika belum ada
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # Build dengan PyInstaller
    target_triple = get_target_triple()
    output_name = f"{output_name_base}-{target_triple}"
    
    print(f"Target triple: {target_triple}")
    print(f"Output name: {output_name}")
    
    # PyInstaller command
    # Note: --collect-all akan bundle semua submodules, penting untuk PyTorch/CUDA
    # WARNING: --collect-all ultralytics causes crash (exit code 3221226505) on Windows
    # Solution: Use specific --hidden-import instead of --collect-all for ultralytics
    # Gunakan --workpath dan --distpath untuk mengarahkan artifacts ke temp location
    # Ini membantu mencegah Tauri watch mode dari mendeteksi perubahan
    import tempfile
    temp_build_dir = Path(tempfile.gettempdir()) / "pyinstaller_build" / f"infer_worker_{os.getpid()}"
    temp_build_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine hidden imports based on script
    hidden_imports = []
    collect_all = []
    
    if script_name == "infer_worker.py":
        # For model conversion, need PyTorch/Ultralytics
        # NOTE: --collect-all ultralytics causes crash (exit code 3221226505)
        # Use specific hidden imports instead of collect-all for ultralytics
        hidden_imports = [
            "--hidden-import", "ultralytics",
            "--hidden-import", "ultralytics.models",
            "--hidden-import", "ultralytics.models.yolo",
            "--hidden-import", "ultralytics.models.yolo.detect",
            "--hidden-import", "ultralytics.utils",
            "--hidden-import", "torch",
            "--hidden-import", "torchvision",
            "--hidden-import", "PIL",
            "--hidden-import", "PIL.Image",
            "--hidden-import", "numpy",
            "--hidden-import", "cv2",
            "--hidden-import", "geojson",
            "--hidden-import", "shapely",
            "--hidden-import", "shapely.geometry",
            "--hidden-import", "geopandas",
            "--hidden-import", "fastkml",
        ]
        # Only collect-all for torch/torchvision (ultralytics removed to prevent crash)
        collect_all = [
            "--collect-all", "torch",
            "--collect-all", "torchvision",
        ]
    elif script_name == "convert_tiff.py":
        # For TIFF conversion, only need PIL
        hidden_imports = [
            "--hidden-import", "PIL",
            "--hidden-import", "PIL.Image",
        ]
        collect_all = []
    
    pyinstaller_cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", output_name_base,
        "--workpath", str(temp_build_dir / "build"),  # Build artifacts ke temp
        "--distpath", str(temp_build_dir / "dist"),   # Dist artifacts ke temp
        "--specpath", str(temp_build_dir),            # Spec file ke temp (PENTING: cegah Tauri watch mode)
        *hidden_imports,
        *[item for sublist in [[f"--collect-all", mod] for mod in [x for i, x in enumerate(collect_all) if i % 2 == 1]] for item in sublist],
        "--noconsole",  # Hide console window (optional, bisa dihapus untuk debugging)
        str(worker_script)
    ]
    
    print(f"Running: {' '.join(pyinstaller_cmd)}")
    
    # Run PyInstaller
    result = subprocess.run(
        pyinstaller_cmd,
        cwd=python_ai_dir,
        check=False
    )
    
    if result.returncode != 0:
        print("ERROR: PyInstaller build failed!")
        return False
    
    # Move hasil build ke binaries directory
    # Build output sekarang di temp directory
    temp_dist_dir = temp_build_dir / "dist"
    if sys.platform == "win32":
        build_output = temp_dist_dir / f"{output_name_base}.exe"
    else:
        build_output = temp_dist_dir / output_name_base
    
    if not build_output.exists():
        print(f"ERROR: Build output tidak ditemukan: {build_output}")
        print(f"  Dist directory contents: {list(temp_dist_dir.iterdir()) if temp_dist_dir.exists() else 'not found'}")
        # Cleanup temp directory
        try:
            shutil.rmtree(temp_build_dir)
        except:
            pass
        return False
    
    # Rename sesuai target triple
    final_output = binaries_dir / output_name
    if sys.platform == "win32" and not final_output.suffix:
        final_output = final_output.with_suffix(".exe")
    
    print(f"Copying {build_output} -> {final_output}")
    shutil.copy2(build_output, final_output)
    
    # Cleanup PyInstaller artifacts IMMEDIATELY to prevent Tauri watch mode from detecting changes
    # Hapus .spec file terlebih dahulu (ini yang paling sering trigger rebuild)
    # Note: Dengan --specpath, spec file seharusnya sudah di temp, tapi cek juga di python_ai_dir untuk safety
    spec_file = python_ai_dir / f"{output_name_base}.spec"
    if spec_file.exists():
        try:
            spec_file.unlink()
            print(f"Cleaned up {output_name_base}.spec from python_ai directory")
        except Exception as e:
            print(f"Warning: Could not remove spec file: {e}")
    
    # Cleanup temp build directory
    try:
        shutil.rmtree(temp_build_dir)
        print("Cleaned up temp build directory")
    except Exception as e:
        print(f"Warning: Could not remove temp build directory: {e}")
    
    # Juga cleanup jika ada build/dist di python_ai_dir (untuk safety)
    build_dir = python_ai_dir / "build"
    if build_dir.exists():
        try:
            shutil.rmtree(build_dir)
            print("Cleaned up build directory in python_ai")
        except Exception as e:
            print(f"Warning: Could not remove build directory: {e}")
    
    dist_dir = python_ai_dir / "dist"
    if dist_dir.exists():
        try:
            shutil.rmtree(dist_dir)
            print("Cleaned up dist directory in python_ai")
        except Exception as e:
            print(f"Warning: Could not remove dist directory: {e}")
    
    print(f"✓ Python sidecar berhasil dibuild: {final_output}")
    print(f"  Size: {final_output.stat().st_size / (1024*1024):.2f} MB")
    
    return True

def build_python_sidecar():
    """Build all Python sidecars"""
    print("=" * 60)
    print("Building Python sidecars...")
    print("=" * 60)
    
    # Build infer_worker (model conversion)
    print("\n[1/2] Building infer_worker (model conversion)...")
    success1 = build_sidecar("infer_worker.py", "infer_worker")
    
    # Build convert_tiff (TIFF RGBPalette conversion)
    print("\n[2/2] Building convert_tiff (TIFF conversion)...")
    success2 = build_sidecar("convert_tiff.py", "convert_tiff")
    
    if success1 and success2:
        print("\n" + "=" * 60)
        print("✓ All sidecars built successfully!")
        print("=" * 60)
        return True
    else:
        print("\n" + "=" * 60)
        print("✗ Some sidecars failed to build!")
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = build_python_sidecar()
    sys.exit(0 if success else 1)
