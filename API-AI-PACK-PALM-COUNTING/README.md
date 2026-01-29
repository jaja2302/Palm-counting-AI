# API AI Pack – Palm Counting AI

API Python untuk menyajikan **AI pack** (zip sidecar) dengan dukungan **pause/resume** download (Range).

## Setup

```bash
cd API-AI-PACK-PALM-COUNTING
pip install -r requirements.txt
```

## Menjalankan API

```bash
# Pakai env untuk host/port (opsional)
# AI_PACK_HOST=0.0.0.0  AI_PACK_PORT=8765
python -m uvicorn main:app --host 0.0.0.0 --port 8765
```

Atau langsung: `python main.py` (baca `AI_PACK_HOST` / `AI_PACK_PORT` atau `PORT`).

- **GET /info** – Info AI pack (ukuran, available). 404 jika pack belum ada.
- **GET /download** – Download zip (mendukung `Range` untuk pause/resume).
- **POST /build** – Build sidecar + zip (lama; untuk CI/server).

## Membuat AI pack di server

Di server, AI pack **harus dibuat sekali** sebelum `/info` dan `/download` bisa dipakai.

**Opsi A – Lewat API (setelah API jalan):**

```bash
curl -X POST http://localhost:8765/build
```

API akan jalankan `npm run build:sidecar` di repo lalu zip ke `dist/`. Lama (~5–15 menit+ tergantung mesin).

**Opsi B – Manual dari CLI (sebelum atau tanpa API):**

```bash
# Dari repo root
npm run build:sidecar
# atau PyInstaller: npm run build:sidecar:pyinstaller
# lalu salin exe ke src-tauri/binaries/ jika perlu

cd API-AI-PACK-PALM-COUNTING
python build_and_zip.py --skip-build
```

Hasil: `dist/palm-counting-ai-pack-x64.zip`. Setelah itu jalankan API; GET /info dan GET /download akan melayani file ini.

## Deploy

- Di server: buat AI pack sekali (lihat **Membuat AI pack di server** di atas), lalu jalankan API.
- Aplikasi Tauri memakai base URL API ini (mis. `http://your-server:8765`) untuk download AI pack saat pertama kali dibuka.
