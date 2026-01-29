"""
Zip folder src-tauri/binaries/ ke dist/. API dan Tauri satu repo → binaries di ../src-tauri/binaries.
Build sidecar manual; ini cuma zip.
"""
import sys
import zipfile
from pathlib import Path

API_DIR = Path(__file__).resolve().parent
BINARIES_DIR = API_DIR.parent / "src-tauri" / "binaries"
DIST_DIR = API_DIR / "dist"
ZIP_NAME = "palm-counting-ai-pack-x64.zip"
TARGET_TRIPLE = "x86_64-pc-windows-msvc"
SIDECAR_EXE = f"infer_worker-{TARGET_TRIPLE}.exe"


def make_zip() -> Path | None:
    """Zip seluruh isi binaries/ ke dist/. Mengembalikan path zip atau None jika gagal."""
    if not BINARIES_DIR.is_dir():
        print(f"Folder tidak ada: {BINARIES_DIR}", file=sys.stderr)
        return None
    exe_path = BINARIES_DIR / SIDECAR_EXE
    if not exe_path.is_file():
        print(f"Sidecar tidak ditemukan: {exe_path}", file=sys.stderr)
        return None
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DIST_DIR / ZIP_NAME
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for f in BINARIES_DIR.rglob("*"):
            if f.is_file():
                arcname = f"binaries/{f.relative_to(BINARIES_DIR).as_posix()}"
                zf.write(f, arcname)
    print(f"AI pack dibuat: {zip_path}")
    return zip_path


if __name__ == "__main__":
    out = make_zip()
    sys.exit(0 if out else 1)
