# API AI Pack – Palm Counting AI

API Python untuk menyajikan **AI pack** (zip sidecar) dengan dukungan **pause/resume** download (Range).

## Setup

```bash
cd API-AI-PACK-PALM-COUNTING
pip install -r requirements.txt
```

## Menjalankan API

```bash
uvicorn main:app --host 0.0.0.0 --port 8765
```

- **GET /info** – Info AI pack (ukuran, available).
- **GET /download** – Download zip (mendukung `Range` untuk pause/resume).
- **POST /build** – Build sidecar + zip (lama; untuk CI/server).

## Membuat AI pack (tanpa API)

```bash
# Dari repo root
cd "Palm counting AI"
npm run build:sidecar
# install deps sekali
python -m pip install -r requirements.txt

# jalanin API
python -m uvicorn main:app --host 0.0.0.0 --port 8765
# Lalu zip
cd API-AI-PACK-PALM-COUNTING
python build_and_zip.py
# atau skip build (anggap binaries/ sudah ada):
python build_and_zip.py --skip-build
```

Output: `API-AI-PACK-PALM-COUNTING/dist/palm-counting-ai-pack-x64.zip`.

## Deploy

- Letakkan `dist/palm-counting-ai-pack-x64.zip` di server (atau jalankan `POST /build` sekali).
- Aplikasi Tauri memakai base URL API ini (mis. `http://your-server:8765`) untuk download AI pack saat pertama kali dibuka.
