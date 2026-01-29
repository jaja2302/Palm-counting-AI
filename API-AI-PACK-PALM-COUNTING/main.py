"""
API untuk download AI pack Palm Counting AI.
- GET /info  -> info ukuran, versi, dll
- GET /download -> file zip (Accept-Ranges untuk pause/resume)
- POST /build -> (opsional) build sidecar + zip
"""
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from build_and_zip import DIST_DIR, ZIP_NAME, make_zip

app = FastAPI(title="Palm Counting AI - AI Pack API", version="1.0.0")

PACK_PATH = DIST_DIR / ZIP_NAME


def ensure_pack() -> Path | None:
    """Pastikan file zip ada; kalau belum, coba build (skip build, hanya zip jika binaries ada)."""
    if PACK_PATH.is_file():
        return PACK_PATH
    # Coba zip saja dulu (tanpa build) kalau binaries sudah ada
    if make_zip(skip_build=True):
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
                "message": "AI pack belum tersedia. Jalankan POST /build atau build_and_zip.py dulu.",
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


@app.post("/build")
def build():
    """Build sidecar + zip (lama, untuk dijalankan manual atau CI)."""
    try:
        out = make_zip(skip_build=False)
        if out is None:
            return JSONResponse(status_code=500, content={"detail": "Build or zip failed"})
        return {"ok": True, "path": str(out), "filename": ZIP_NAME}
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8765)
