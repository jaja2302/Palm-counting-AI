"""
Download AI pack zip dari API server. Jalankan langsung (tanpa Postman).
Set API_HOST / API_PORT di bawah atau lewat env/arg.
"""
import argparse
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("Butuh: pip install requests", file=sys.stderr)
    sys.exit(1)

# --- Set manual: IP server tempat uvicorn jalan (mis. 10.9.116.125 atau 192.168.1.x) ---
API_HOST = os.getenv("AI_PACK_HOST", "10.9.116.125")
API_PORT = os.getenv("AI_PACK_PORT", "8765")
BASE_URL = os.getenv("AI_PACK_BASE_URL", f"http://{API_HOST}:{API_PORT}")

CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB per chunk (lebih cepat dari 1 MB)
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT = SCRIPT_DIR / "dist" / "palm-counting-ai-pack-x64.zip"
PROGRESS_EVERY_MB = 10  # cetak progress tiap 10 MB


def get_info(base_url: str) -> dict | None:
    """GET /info → available, filename, size_bytes."""
    try:
        r = requests.get(f"{base_url}/info", timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        print(f"Gagal GET /info: {e}", file=sys.stderr)
        return None


def download_zip(base_url: str, output_path: Path, show_progress: bool = True) -> bool:
    """GET /download dan simpan ke file. Chunk 8 MB, timeout panjang untuk file besar."""
    try:
        # timeout: (connect, read) — read 2 jam untuk file ~4 GB
        r = requests.get(
            f"{base_url}/download",
            stream=True,
            timeout=(10, 7200),
            headers={"Accept": "application/zip"},
        )
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"Gagal GET /download: {e}", file=sys.stderr)
        return False

    total = 0
    content_length = r.headers.get("Content-Length")
    total_bytes = int(content_length) if content_length else None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    last_printed_mb = -1
    total_mb_val = int(total_bytes / (1024 * 1024)) if total_bytes else 0

    def show_progress_line():
        mb = total // (1024 * 1024)
        pct = min(100, total * 100 // total_bytes) if total_bytes else 0
        print(f"\r  Download {mb} / {total_mb_val} MB ({pct}%)", end="", flush=True)

    if show_progress and total_bytes:
        show_progress_line()

    with open(output_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                f.write(chunk)
                total += len(chunk)
                if show_progress and total_bytes:
                    mb = total // (1024 * 1024)
                    if mb - last_printed_mb >= PROGRESS_EVERY_MB or total >= total_bytes:
                        last_printed_mb = mb
                        show_progress_line()

    if show_progress and total_bytes:
        print()
    print(f"Saved: {output_path}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Download AI pack zip dari API server")
    parser.add_argument("--host", default=API_HOST, help=f"Host server (default: {API_HOST})")
    parser.add_argument("--port", default=API_PORT, help=f"Port (default: {API_PORT})")
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Path file output (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument("--no-progress", action="store_true", help="Sembunyikan progress")
    args = parser.parse_args()

    base = f"http://{args.host}:{args.port}"
    print(f"API: {base}")

    info = get_info(base)
    if not info:
        sys.exit(1)
    if not info.get("available"):
        print(info.get("message", "AI pack tidak tersedia."), file=sys.stderr)
        sys.exit(1)
    print(f"  Pack: {info.get('filename', '?')} ({info.get('size_mb', 0)} MB)")

    if not download_zip(base, args.output, show_progress=not args.no_progress):
        sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    main()
