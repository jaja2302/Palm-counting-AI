# Palm Counting AI

Tauri + React + TypeScript. Inference via Python sidecar (YOLO).

## Development

```bash
npm run tauri:dev
```

Uses `python_ai/infer_worker.py` (placeholder sidecar).

## Production build

**Sidecar Python harus di-build dulu**, lalu Tauri bundle:

```bash
npm run build:prod
```

Atau step manual:

1. `npm run build:sidecar` — PyInstaller bundle `infer_worker.py` + `convert_tiff.py` ke `src-tauri/binaries/`
2. `npm run tauri build` — build app + bundle sidecar

Output installer: `src-tauri/target/release/bundle/`.

## Recommended IDE

- [VS Code](https://code.visualstudio.com/) + [Tauri](https://marketplace.visualstudio.com/items?itemName=tauri-apps.tauri-vscode) + [rust-analyzer](https://marketplace.visualstudio.com/items?itemName=rust-lang.rust-analyzer)
