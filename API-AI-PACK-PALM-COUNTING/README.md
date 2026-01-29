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

## Download zip dari PC lain (tanpa Postman)

Salin folder `API-AI-PACK-PALM-COUNTING` ke PC lain (atau minimal file `download_zip.py` + `pip install requests`). Set **IP server** tempat uvicorn jalan:

1. **Edit di script**: buka `download_zip.py`, ubah baris `API_HOST = "10.9.116.125"` ke IP server (mis. `192.168.1.5`).
2. Atau lewat arg: `python download_zip.py --host 192.168.1.5 --port 8765`
3. Jalankan: `python download_zip.py`

File zip tersimpan di `API-AI-PACK-PALM-COUNTING/dist/palm-counting-ai-pack-x64.zip`. Kecepatan tergantung jaringan; script pakai chunk 8 MB dan timeout 2 jam untuk file besar.

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
