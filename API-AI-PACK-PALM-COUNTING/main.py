"""
API untuk download AI pack Palm Counting AI.
Hanya menyajikan zip; tidak ada build. Build sidecar manual di server, lalu zip folder binaries/.
- GET /info   -> info ukuran, versi
- GET /download -> file zip (Accept-Ranges untuk pause/resume)
- POST /zip   -> (opsional) buat ulang zip dari folder binaries/
"""
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from build_and_zip import DIST_DIR, ZIP_NAME, make_zip

app = FastAPI(title="Palm Counting AI - AI Pack API", version="1.0.0")

PACK_PATH = DIST_DIR / ZIP_NAME

API_HOST = os.getenv("AI_PACK_HOST", "0.0.0.0")
API_PORT = int(os.getenv("AI_PACK_PORT", os.getenv("PORT", "8765")))


def ensure_pack() -> Path | None:
    """Zip ada → pakai. Belum ada → coba buat dari ../src-tauri/binaries/."""
    if PACK_PATH.is_file():
        return PACK_PATH
    if make_zip():
        return PACK_PATH
    return None


@app.get("/info")
def info():
    """Info AI pack: size, exists, version."""
    path = ensure_pack()
    if path is None:
        return JSONResponse(
            status_code=404,
            content={
                "available": False,
                "message": "AI pack belum tersedia. Di server: zip folder binaries/ dengan python build_and_zip.py",
            },
        )
    size = path.stat().st_size
    return {
        "available": True,
        "filename": ZIP_NAME,
        "size_bytes": size,
        "size_mb": round(size / (1024 * 1024), 2),
        "version": "1.0",
    }


@app.get("/download")
def download(request: Request):
    """
    Download file zip. Mendukung Range header untuk pause/resume.
    """
    path = ensure_pack()
    if path is None:
        return JSONResponse(status_code=404, content={"detail": "AI pack not found"})
    size = path.stat().st_size
    range_header = request.headers.get("range")
    if range_header:
        # Parse "bytes=start-end" or "bytes=start-"
        try:
            unit, part = range_header.strip().split("=", 1)
            if unit.lower() != "bytes":
                return Response(status_code=416, content=b"Invalid range unit")
            parts = part.split("-", 1)
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if len(parts) > 1 and parts[1] else size - 1
            if start >= size or start > end:
                return Response(
                    status_code=416,
                    content=b"Range not satisfiable",
                    headers={"Content-Range": f"bytes */{size}"},
                )
            end = min(end, size - 1)
            content_length = end - start + 1
            with open(path, "rb") as f:
                f.seek(start)
                body = f.read(content_length)
            return Response(
                status_code=206,
                content=body,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(len(body)),
                    "Content-Type": "application/zip",
                },
                media_type="application/zip",
            )
        except (ValueError, IndexError):
            return Response(status_code=400, content=b"Invalid Range header")
    # Full file (tetap kirim Accept-Ranges agar client bisa resume)
    return FileResponse(
        path,
        filename=ZIP_NAME,
        media_type="application/zip",
        headers={"Accept-Ranges": "bytes"},
    )


@app.post("/zip")
def zip_pack():
    """Buat ulang zip dari folder binaries/ (tanpa build). Berguna setelah kamu update binaries/ di server."""
    try:
        out = make_zip()
        if out is None:
            return JSONResponse(status_code=500, content={"detail": "Zip gagal. Pastikan folder src-tauri/binaries/ ada dan berisi sidecar exe."})
        return {"ok": True, "path": str(out), "filename": ZIP_NAME}
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT)
