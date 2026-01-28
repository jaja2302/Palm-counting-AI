# Quick Start - Build & Deploy

## TL;DR - Alur Build

```bash
# Development (otomatis create placeholder)
npm run tauri:dev

# Production (build sidecar + app)
npm run build:sidecar    # Build Python sidecar
npm run tauri:build      # Build Tauri app

# Atau build sekaligus:
npm run build:full
```

## Detail

### Development (dengan Python terinstall)

```bash
# Install Python dependencies
cd python_ai
pip install -r requirements.txt

# Run development
npm run tauri:dev
```

**Tidak perlu build sidecar** - akan menggunakan Python script langsung.

### Production (bundle untuk distribusi)

```bash
# 1. Build Python sidecar (PyInstaller)
npm run build:sidecar

# 2. Build Tauri app
npm run tauri:build
```

**Hasil:** Installer di `src-tauri/target/release/bundle/`

## FAQ

### Q: Perlu venv?
**A: Tidak!** PyInstaller akan bundle semua dependencies. Tidak perlu venv.

### Q: PC target tidak punya Python?
**A: Tidak masalah!** Sidecar adalah standalone executable, tidak perlu Python.

### Q: Ukuran file besar?
**A: Ya, ~200-500 MB** karena include PyTorch + CUDA libraries. Ini normal untuk ML apps.

### Q: Bisa build untuk Linux/Mac?
**A: Ya!** Build sidecar di platform target masing-masing:
```bash
# Di Linux
npm run build:sidecar
npm run tauri:build

# Di Mac
npm run build:sidecar  
npm run tauri:build
```

### Q: Error "worker not found"?
**A:** 
- Development: Pastikan `python_ai/infer_worker.py` ada
- Production: Jalankan `npm run build:sidecar` dulu

## Struktur Build

```
src-tauri/
├── binaries/
│   └── infer_worker-<target-triple>.exe  ← Python sidecar (PyInstaller)
├── resources/
│   ├── python_ai/infer_worker.py         ← Fallback (dev only)
│   └── models/                            ← YOLO models
└── target/release/
    └── palm-counting-ai.exe              ← Tauri app
```

Lihat [BUILD.md](./BUILD.md) untuk detail lengkap.
