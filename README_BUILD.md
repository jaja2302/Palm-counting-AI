# Quick Start - Build & Deploy (Python Portable)

## TL;DR - Alur Build

```bash
# 1) Siapkan Python portable + dependencies (sekali saja)
#   - Download Python 3.11 (embeddable / portable)
#   - Extract ke: ./python/
#   - Install dependencies ke portable Python:
#       ./python/python.exe -m pip install -r src-tauri/python_ai/requirements.txt

# 2) Development
npm run tauri:dev

# 3) Production (build installer)
npm run tauri:build
```

## Detail

### Struktur folder (distribusi)

Direkomendasikan struktur akhir seperti ini (di folder hasil install):

```
your-app/
├── palm-counting-ai.exe         ← Tauri app
├── python/                      ← Python portable (runtime)
│   ├── python.exe
│   ├── DLLs/
│   ├── Lib/
│   └── Scripts/
├── python_ai/
│   ├── infer_worker.py          ← YOLO + geospatial worker
│   └── requirements.txt
└── models/                      ← YOLO models (.pt / .onnx)
```

Rust akan:
- Mencari `python_ai/infer_worker.py` di samping `palm-counting-ai.exe`.
- Jika ada, ia akan mencoba menjalankan:
  - `python/python.exe -u python_ai/infer_worker.py --infer-files ...`
  - Jika `python/python.exe` tidak ada, fallback ke `python` di PATH (untuk dev).

### Development

```bash
# 1) Pastikan dependencies ke-install (boleh pakai Python global saat dev)
cd src-tauri/python_ai
pip install -r requirements.txt

# 2) Jalanin app
cd ../../
npm run tauri:dev
```

> Di mode dev, Rust akan menjalankan `python infer_worker.py` (menggunakan Python yang ada di PATH).

### Production (bundle dengan Python portable)

1. **Download Python portable / embeddable 3.11 (x64)** dari `python.org`.
2. Extract ke folder `python/` di root project.
3. Install semua dependency ke portable Python:

```bash
./python/python.exe -m pip install -r src-tauri/python_ai/requirements.txt
```

4. Pastikan folder berikut ikut ter-bundle di installer:
   - `python/`
   - `python_ai/`
   - `models/`

5. Build Tauri:

```bash
npm run tauri:build
```

**Hasil:** Installer di `src-tauri/target/release/bundle/` yang sudah membawa:
- Runtime Python portable (`python/`)
- Script worker (`python_ai/infer_worker.py`)
- Model-model YOLO (`models/`)

## FAQ

### Q: Perlu venv?
**A: Tidak wajib.** Untuk distribusi, lebih disarankan langsung install ke Python portable (`./python/python.exe -m pip install ...`).

### Q: PC target tidak punya Python?
**A: Tidak masalah.** Aplikasi membawa Python portable sendiri di folder `python/`.

### Q: Ukuran file besar?
**A: Ya, tetap besar** karena membawa PyTorch + CUDA + dependencies geospatial. Ini normal untuk ML apps.

### Q: Error "worker not found"?
**A:**
- Development: Pastikan `src-tauri/python_ai/infer_worker.py` ada dan bisa dijalankan dengan `python`.
- Production: Pastikan folder `python_ai/` ikut terbawa di folder instalasi.

