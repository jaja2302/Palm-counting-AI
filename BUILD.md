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

Python worker dibundle sebagai standalone executable. Tiga opsi:

**Opsi A – Nuitka (default):**
```bash
npm run build:sidecar
# atau: python src-tauri/scripts/build_python_sidecar.py
```
- Compile ke native; build lama (~20–30 min pertama), hasil bisa lebih kecil/cepat runtime.

**Opsi B – PyInstaller:**
```bash
npm run build:sidecar:pyinstaller
# atau: python src-tauri/scripts/build_python_sidecar_pyinstaller.py
```
- Bundle dengan PyInstaller; build biasanya lebih cepat (~5–15 min).

**Opsi C – cx_Freeze:**
```bash
npm run build:sidecar:cxfreeze
# atau: python src-tauri/scripts/build_python_sidecar_cxfreeze.py
```
- Folder output (exe + deps); startup sering lebih cepat dari PyInstaller.
- **Catatan:** cx_Freeze + PyTorch/Ultralytics kadang `RecursionError`. Jika gagal, pakai Nuitka atau PyInstaller.

- **Nuitka** → `src-tauri/binaries/infer_worker-<target-triple>.exe`
- **PyInstaller** → `src-tauri/binaries_pyinstaller/` (single-file exe)
- **cx_Freeze** → `src-tauri/binaries_cxfreeze/` (folder exe + dll; untuk dipakai app, salin isi ke `binaries/` atau rename folder)

### 3. Build Tauri App

Sidecar di-include sesuai [Tauri doc](https://v2.tauri.app/develop/building/sidecar/): `externalBin: ["binaries/infer_worker"]` di `tauri.conf.json`. Karena file sidecar asli ~4–8 GB, **NSIS gagal** saat bundle; jadi untuk **build installer** pakai **placeholder** dulu (exe kecil):

```bash
cd "Palm counting AI"
npm run build:placeholder   # buat binaries/infer_worker-<target>.exe (kecil)
npm run tauri build
```

Atau satu perintah: `npm run tauri:build` (placeholder lalu tauri build).

- **Installer:** berisi app + resources + **sidecar placeholder** (~beberapa KB). Di PC user, **AI tidak jalan** sampai salah satu di bawah.

**Agar AI jalan di PC user (tanpa Python di PC):**
1. Build sidecar sekali: `npm run build:sidecar` (atau PyInstaller/cx_Freeze).
2. Distribusi dua bagian:
   - **Installer:** `bundle/nsis/palm-counting-ai_*_x64-setup.exe` (~3 MB) — user install seperti biasa.
   - **AI pack:** file `infer_worker-x86_64-pc-windows-msvc.exe` (hasil build:sidecar, ~4–8 GB). Host terpisah (Google Drive, release GitHub, dll).
3. Di PC user: setelah install app, buat folder `binaries` di folder instalasi (satu tingkat dengan `palm-counting-ai.exe`), salin `infer_worker-x86_64-pc-windows-msvc.exe` ke dalamnya, lalu **rename** jadi `infer_worker.exe`. Setelah itu fitur AI jalan tanpa perlu Python.

**Alternatif (dengan Python di PC user):**  
Installer sudah bawa `python_ai/*.py`. User install Python + `pip install -r requirements.txt` dari folder resources app; app akan pakai skrip Python sebagai fallback (jika sidecar tidak ada).

**Download AI pack dari dalam aplikasi (first-run):**  
Saat aplikasi pertama kali dibuka, jika AI pack belum terpasang akan muncul banner dengan URL API. User bisa download langsung dari app (dengan progress, Jeda, Lanjutkan). API disediakan di folder `API-AI-PACK-PALM-COUNTING` (Python FastAPI): build sidecar + zip, lalu serve dengan dukungan **Range** untuk pause/resume. Lihat `API-AI-PACK-PALM-COUNTING/README.md`.

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
- Placeholder sidecar akan **otomatis dibuat** saat pertama kali run `npm run tauri:dev` (untuk dev, app cari sidecar di `binaries/` atau fallback Python).
- Untuk **production**, sidecar tidak ikut di installer; gunakan `npm run build:sidecar` lalu distribusi terpisah atau salin ke folder instalasi.

### 4. Hasil Build

Setelah build selesai, hasilnya ada di:
- **Windows:** `src-tauri/target/release/palm-counting-ai.exe`
- **Installer (NSIS):** `src-tauri/target/release/bundle/nsis/palm-counting-ai_1.1.23_x64-setup.exe`

## Struktur Sidecar

```
src-tauri/
├── binaries/
│   └── infer_worker-x86_64-pc-windows-msvc.exe  # Nuitka (build:sidecar)
├── binaries_pyinstaller/
│   └── infer_worker-x86_64-pc-windows-msvc.exe  # PyInstaller (build:sidecar:pyinstaller)
├── binaries_cxfreeze/
│   ├── infer_worker-x86_64-pc-windows-msvc.exe  # cx_Freeze (build:sidecar:cxfreeze)
│   └── ... (dll/deps)
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
1. Rust mencari `infer_worker.exe` di folder exe atau `binaries/` (jika user sudah menyalin sidecar ke sana).
2. Jika tidak ada, fallback ke skrip Python di resources (`python_ai/infer_worker.py`) jika Python terinstall.
3. Sidecar tidak lagi dibundle di installer karena ukuran (~4 GB); distribusi terpisah atau salin manual.

## Troubleshooting

### Error: "Inference worker not found"
- **Development:** Pastikan `python_ai/infer_worker.py` ada
- **Production:** Jalankan `scripts/build_python_sidecar.py` terlebih dahulu

### Error: "Python test failed"
- Install Python di sistem
- Atau gunakan sidecar (build dengan `build_python_sidecar.py`)

### Sidecar tidak ditemukan saat runtime
- **Dev:** file sidecar di `src-tauri/binaries/` (nama: `infer_worker-<target-triple>.exe`) atau gunakan fallback Python.
- **Production:** salin hasil `build:sidecar` ke folder instalasi (subfolder `binaries/` atau sama folder dengan exe), atau andalkan fallback Python.

### Error: "failed to run light.exe" (MSI / WiX)
Jika Anda build **MSI** (`"targets": "msi"` atau `"all"`) dan dapat error ini, menurut [Tauri Windows Installer doc](https://v2.tauri.app/develop/building/windows/): build MSI membutuhkan **VBScript** di Windows. Aktifkan lewat: **Settings → Apps → Optional features → More Windows features** → centang **Windows Script Host** / VBScript. Setelah itu coba `npm run tauri build` lagi.  
Proyek ini memakai **NSIS** saja (`"targets": ["nsis"]`) agar build selalu jalan; MSI juga bisa gagal jika sidecar terlalu besar (~4 GB).

## Ukuran Build

- **Python Sidecar:** ~200-500 MB (termasuk PyTorch, Ultralytics, dll)
- **Tauri App:** ~10-20 MB
- **Total:** ~250-550 MB

## Catatan Penting

1. **Tidak perlu venv** - Nuitka/PyInstaller/cx_Freeze akan bundle semua dependencies
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
