# API AI Pack – Palm Counting AI

API hanya **menyajikan zip** untuk download. **Tidak ada build** di API. Build sidecar manual di server, lalu zip folder `binaries/`, jalankan API.

## Setup

```bash
cd API-AI-PACK-PALM-COUNTING
pip install -r requirements.txt
```

## Menjalankan API

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8765
```

Atau: `python main.py` (baca env `AI_PACK_HOST` / `AI_PACK_PORT` atau `PORT`).

- **GET /info** – Info AI pack (ukuran, available). 404 jika zip belum ada.
- **GET /download** – Download zip (Range untuk pause/resume).
- **POST /zip** – Buat ulang zip dari folder `src-tauri/binaries/` (opsional).

## Alur di server (simple)

1. **Build sidecar manual** (sekali, dari repo root):
   - cx_Freeze: `python src-tauri/scripts/build_python_sidecar_cxfreeze.py`
   - atau Nuitka: `npm run build:sidecar`
   - atau PyInstaller: `python src-tauri/scripts/build_python_sidecar_pyinstaller.py`  
   Hasil di `src-tauri/binaries/` (exe + DLL/deps).

2. **Zip folder binaries** (sekali, atau setelah update binaries):
   ```bash
   cd API-AI-PACK-PALM-COUNTING
   python build_and_zip.py
   ```
   Hasil: `dist/palm-counting-ai-pack-x64.zip`.

3. **Jalankan API** – hanya menyajikan zip untuk GET /info dan GET /download.

## Deploy

- Di server: build sidecar manual → zip dengan `python build_and_zip.py` → jalankan API.
- Aplikasi Tauri pakai base URL API ini untuk download AI pack saat pertama buka.
