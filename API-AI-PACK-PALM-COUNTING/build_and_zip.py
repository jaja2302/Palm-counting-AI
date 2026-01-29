"""
Build sidecar (infer_worker) dan zip ke file AI pack.
Jalankan dari repo root atau set PALM_PROJECT_ROOT.
Output: dist/palm-counting-ai-pack-x64.zip
"""
import os
import subprocess
import sys
import zipfile
from pathlib import Path

# Repo root (parent of API-AI-PACK-PALM-COUNTING)
API_DIR = Path(__file__).resolve().parent
REPO_ROOT = API_DIR.parent
SRC_TAURI = REPO_ROOT / "src-tauri"
BINARIES_DIR = SRC_TAURI / "binaries"
DIST_DIR = API_DIR / "dist"
ZIP_NAME = "palm-counting-ai-pack-x64.zip"
TARGET_TRIPLE = "x86_64-pc-windows-msvc"
SIDECAR_EXE = f"infer_worker-{TARGET_TRIPLE}.exe"


def build_sidecar() -> bool:
    """Jalankan npm run build:sidecar di repo root."""
    env = os.environ.copy()
    env["PALM_PROJECT_ROOT"] = str(REPO_ROOT)
    try:
        subprocess.run(
            ["npm", "run", "build:sidecar"],
            cwd=REPO_ROOT,
            env=env,
            check=True,
            capture_output=False,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Build sidecar gagal: {e}", file=sys.stderr)
        return False


def make_zip(skip_build: bool = False) -> Path | None:
    """
    Pastikan binaries/ berisi sidecar, lalu zip ke dist/.
    Jika skip_build=True, tidak jalankan build (anggap sudah ada).
    """
    if not skip_build:
        if not build_sidecar():
            return None
    if not BINARIES_DIR.is_dir():
        print(f"Folder tidak ada: {BINARIES_DIR}", file=sys.stderr)
        return None
    exe_path = BINARIES_DIR / SIDECAR_EXE
    if not exe_path.is_file():
        print(f"Sidecar tidak ditemukan: {exe_path}", file=sys.stderr)
        return None
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DIST_DIR / ZIP_NAME
    # Zip isi binaries/ dengan struktur: binaries/infer_worker-*.exe
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.write(exe_path, f"binaries/{SIDECAR_EXE}")
    print(f"AI pack dibuat: {zip_path}")
    return zip_path


if __name__ == "__main__":
    skip = "--skip-build" in sys.argv
    out = make_zip(skip_build=skip)
    sys.exit(0 if out else 1)
