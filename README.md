# Palm Counting AI

Tauri + React + TypeScript. Inference via Python sidecar (YOLO).

## Development

```bash
conda activate yolov9
npm run tauri:dev
```

Uses `python_ai/infer_worker.py` (placeholder sidecar).

## Production build

- **Installer (~3 MB)** hanya berisi app; **AI tidak jalan** di PC user kecuali ada sidecar atau Python.
- Agar **AI jalan tanpa Python** di PC user: distribusi dua bagian (lihat BUILD.md).

```bash
npm run tauri build
```

Output: `src-tauri/target/release/bundle/nsis/palm-counting-ai_*_x64-setup.exe`.

**Untuk PC user (AI jalan tanpa Python):**  
Sediakan juga "AI pack": hasil `npm run build:sidecar` (file exe ~4–8 GB). User install app dulu, lalu salin `infer_worker-x86_64-pc-windows-msvc.exe` ke folder instalasi → subfolder `binaries/` → rename jadi `infer_worker.exe`. Detail di BUILD.md.

## Recommended IDE

- [VS Code](https://code.visualstudio.com/) + [Tauri](https://marketplace.visualstudio.com/items?itemName=tauri-apps.tauri-vscode) + [rust-analyzer](https://marketplace.visualstudio.com/items?itemName=rust-lang.rust-analyzer)
