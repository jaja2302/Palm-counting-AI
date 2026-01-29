"""
Build Python sidecar untuk Tauri menggunakan PyInstaller (alternatif Nuitka).
FULL SUPPORT: YOLO + Ultralytics + GPU (CUDA)

Gunakan script ini untuk membandingkan kecepatan build & ukuran hasil vs Nuitka:
  python src-tauri/scripts/build_python_sidecar.py        # Nuitka
  python src-tauri/scripts/build_python_sidecar_pyinstaller.py  # PyInstaller
"""
import os
import sys
import subprocess
from pathlib import Path


def get_target_triple():
    """Get Rust target triple untuk platform saat ini."""
    result = subprocess.run(
        ["rustc", "--print", "target-triple"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    if sys.platform == "win32":
        return "x86_64-pc-windows-msvc"
    elif sys.platform == "darwin":
        return "aarch64-apple-darwin" if "arm" in os.uname().machine else "x86_64-apple-darwin"
    else:
        return "x86_64-unknown-linux-gnu"


def ensure_pyinstaller():
    """Ensure PyInstaller installed."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print(f"PyInstaller detected: {result.stdout.strip()}")
            return
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    print("Installing PyInstaller...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "pyinstaller"],
        check=True,
    )
    print("PyInstaller installed successfully.")


def build_sidecar_pyinstaller(script_name: str, output_name_base: str) -> bool:
    """Build Python sidecar menggunakan PyInstaller."""
    script_dir = Path(__file__).parent
    src_tauri_dir = script_dir.parent
    python_ai_dir = src_tauri_dir / "python_ai"
    out_dir = src_tauri_dir / "binaries"

    out_dir.mkdir(exist_ok=True)

    worker_script = python_ai_dir / script_name
    if not worker_script.exists():
        print(f"ERROR: {worker_script} tidak ditemukan!")
        return False

    print(f"Building Python sidecar dengan PyInstaller dari {worker_script}")

    target_triple = get_target_triple()
    output_name = f"{output_name_base}-{target_triple}"

    print(f"Target triple: {target_triple}")
    print(f"Output name: {output_name}")

    exe_suffix = ".exe" if sys.platform == "win32" else ""
    final_exe = output_name + exe_suffix

    # Base PyInstaller args — output ke binaries (terpisah dari binaries/ Nuitka)
    args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--clean",
        f"--name={output_name}",
        f"--distpath={out_dir}",
        f"--workpath={out_dir / 'build'}",
        f"--specpath={out_dir}",
    ]

    if sys.platform == "win32":
        args.append("--noconsole")

    # Hidden imports (PyTorch, Ultralytics, CV2, PIL, geo, etc.)
    hidden = [
        "torch",
        "torch.nn",
        "torch.cuda",
        "torch._C",
        "torch.backends",
        "torch.backends.cuda",
        "torch.backends.cudnn",
        "torch.utils",
        "torchvision",
        "torchvision.transforms",
        "torchvision.models",
        "ultralytics",
        "ultralytics.models",
        "ultralytics.models.yolo",
        "ultralytics.models.yolo.detect",
        "ultralytics.engine",
        "ultralytics.engine.predictor",
        "ultralytics.utils",
        "ultralytics.data",
        "ultralytics.nn",
        "cv2",
        "PIL",
        "PIL.Image",
        "numpy",
        "geojson",
        "shapely",
        "shapely.geometry",
        "shapely.geometry.point",
        "geopandas",
        "fastkml",
        "fastkml.kml",
        "fastkml.geometry",
        "yaml",
        "tqdm",
    ]
    for h in hidden:
        args.append(f"--hidden-import={h}")

    # Collect PyTorch & Ultralytics (includes CUDA DLLs, larger bundle but reliable)
    args.append("--collect-all=torch")
    args.append("--collect-all=ultralytics")

    # Optional: kurangi ukuran dengan exclude (bisa dicoba jika build terlalu besar)
    # args.append("--exclude-module=matplotlib")
    # args.append("--exclude-module=scipy")

    args.append(str(worker_script))

    print("\nRunning PyInstaller...")
    print("  ⚠️  First build: ~5–15 min (PyTorch + CUDA). Biasanya lebih cepat dari Nuitka.")
    print(f"  ℹ️  Output single-file exe di binaries/")

    debug_cmd_file = out_dir / f"pyinstaller_cmd_{output_name_base}.txt"
    debug_cmd_file.write_text(" \\\n  ".join(args), encoding="utf-8")
    print(f"  Command saved: {debug_cmd_file}\n")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    print("=" * 70)
    result = subprocess.run(args, cwd=str(python_ai_dir), env=env, check=False)
    print("=" * 70 + "\n")

    if result.returncode != 0:
        print(f"❌ PyInstaller build failed (exit {result.returncode})")
        print(f"   Debug command: {debug_cmd_file}")
        return False

    out_path = out_dir / final_exe
    if not out_path.exists():
        for candidate in [out_path, out_dir / "dist" / final_exe]:
            if candidate.exists():
                if candidate != out_path:
                    import shutil
                    shutil.move(str(candidate), str(out_path))
                break
        else:
            print(f"ERROR: Output tidak ditemukan: {out_path}")
            if out_dir.exists():
                for f in out_dir.rglob("*"):
                    if f.is_file():
                        print(f"  - {f.relative_to(out_dir)}")
            return False

    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"✓ Sidecar PyInstaller OK: {out_path}")
    print(f"  Size: {size_mb:.1f} MB")
    return True


def main():
    print("=" * 70)
    print("Building Python sidecar (infer_worker) with PyInstaller")
    print("FULL SUPPORT: YOLO + Ultralytics + GPU (CUDA)")
    print("=" * 70)

    print("\nChecking PyInstaller...")
    try:
        ensure_pyinstaller()
    except Exception as e:
        print(f"ERROR: PyInstaller install failed: {e}")
        return False

    print("\n" + "=" * 70)
    print("Building infer_worker (YOLO + GPU)...")
    print("=" * 70)
    ok = build_sidecar_pyinstaller("infer_worker.py", "infer_worker")

    if ok:
        print("\n" + "=" * 70)
        print("✓ Sidecar built with PyInstaller!")
        print("=" * 70)
        print("\n📋 Output di src-tauri/binaries/ (terpisah dari binaries/).")
        print("   Untuk dipakai app: salin exe ke binaries/ atau jalankan dari binaries/.")
        print("   Nuitka: npm run build:sidecar → binaries/")
        return True
    print("\n" + "=" * 70)
    print("✗ infer_worker PyInstaller build failed!")
    print("=" * 70)
    return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
