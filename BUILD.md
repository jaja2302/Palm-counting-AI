# Build Instructions - Palm Counting AI

## Alur Build untuk Production

### 1. Persiapan Dependencies

**Development (dengan Python terinstall):**
```bash
cd "Palm counting AI/src-tauri/python_ai"
pip install -r requirements.txt
```

**Production (bundle Python sebagai sidecar):**
Tidak perlu install Python di PC target! Python akan dibundle sebagai executable.

### 2. Build Python Sidecar

Python worker akan dibundle sebagai standalone executable menggunakan PyInstaller:

```bash
cd "Palm counting AI"
python scripts/build_python_sidecar.py
```

Script ini akan:
- Install PyInstaller jika belum ada
- Build `infer_worker.py` menjadi standalone executable
- Menempatkan hasil di `src-tauri/binaries/infer_worker-<target-triple>.exe`
- Auto-detect target triple (x86_64-pc-windows-msvc, dll)

**Output:** `src-tauri/binaries/infer_worker-x86_64-pc-windows-msvc.exe`

### 3. Build Tauri App

```bash
cd "Palm counting AI"
npm run tauri build
```

### Development Mode

**Cara 1: Otomatis (Recommended)**
```bash
npm run tauri:dev
```
Script ini akan:
- Otomatis build placeholder sidecar (jika belum ada)
- Menjalankan Tauri dev mode

**Cara 2: Manual**
```bash
# Build placeholder dulu (hanya sekali, atau jika dihapus)
npm run build:placeholder

# Lalu jalankan dev
npm run tauri dev
```

**Catatan:**
- Placeholder sidecar akan **otomatis dibuat** saat pertama kali run `npm run tauri:dev`
- Placeholder hanya file kecil (~1KB) untuk memenuhi requirement Tauri `externalBin`
- Untuk **production**, gunakan `npm run build:sidecar` untuk build sidecar yang sebenarnya

### 4. Hasil Build

Setelah build selesai, hasilnya ada di:
- **Windows:** `src-tauri/target/release/palm-counting-ai.exe`
- **Installer:** `src-tauri/target/release/bundle/msi/palm-counting-ai_0.1.0_x64_en-US.msi`

## Struktur Sidecar

```
src-tauri/
├── binaries/
│   └── infer_worker-x86_64-pc-windows-msvc.exe  # Python worker (PyInstaller)
├── resources/
│   ├── python_ai/
│   │   └── infer_worker.py  # Fallback untuk development
│   └── models/  # YOLO model files
└── ...
```

## Alur Runtime

### Development Mode
1. Tauri akan otomatis build placeholder sidecar saat pertama kali dev
2. Placeholder hanya untuk memenuhi requirement `externalBin` di Tauri config
3. Untuk conversion `.pt` ke `.onnx`, aplikasi akan menggunakan sidecar yang sebenarnya (jika sudah dibuild) atau fallback ke Python script
4. **Inference menggunakan Rust ONNX** - tidak perlu Python untuk inference

### Production Mode (Sidecar)
1. Rust mencari `binaries/infer_worker-<target>.exe`
2. Menjalankan executable langsung (tidak perlu Python)
3. Semua dependencies sudah dibundle di dalam executable

## Troubleshooting

### Error: "Inference worker not found"
- **Development:** Pastikan `python_ai/infer_worker.py` ada
- **Production:** Jalankan `scripts/build_python_sidecar.py` terlebih dahulu

### Error: "Python test failed"
- Install Python di sistem
- Atau gunakan sidecar (build dengan `build_python_sidecar.py`)

### Sidecar tidak ditemukan saat runtime
- Pastikan `externalBin` di `tauri.conf.json` sudah benar
- Pastikan file sidecar ada di `src-tauri/binaries/` dengan nama yang benar
- Nama harus sesuai target triple: `infer_worker-<target-triple>.exe`

## Ukuran Build

- **Python Sidecar:** ~200-500 MB (termasuk PyTorch, Ultralytics, dll)
- **Tauri App:** ~10-20 MB
- **Total:** ~250-550 MB

## Catatan Penting

1. **Tidak perlu venv** - PyInstaller akan bundle semua dependencies
2. **Tidak perlu Python di PC target** - sidecar adalah standalone executable
3. **CUDA support** - Jika build dengan CUDA, sidecar akan include CUDA libraries
4. **Cross-platform** - Build sidecar untuk setiap target platform yang berbeda

## Multi-Platform Build

Untuk build untuk platform lain:

```bash
# Linux
rustup target add x86_64-unknown-linux-gnu
python scripts/build_python_sidecar.py  # Akan auto-detect target

# macOS
rustup target add aarch64-apple-darwin
python scripts/build_python_sidecar.py
```
