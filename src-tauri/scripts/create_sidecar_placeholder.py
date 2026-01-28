"""
Create placeholder sidecar file untuk development mode.
Tauri memerlukan file sidecar yang disebutkan di externalBin, bahkan untuk dev mode.
"""
import sys
from pathlib import Path

def get_target_triple():
    """Get target triple"""
    import subprocess
    result = subprocess.run(
        ["rustc", "--print", "target-triple"],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        return result.stdout.strip()
    # Fallback
    if sys.platform == "win32":
        return "x86_64-pc-windows-msvc"
    elif sys.platform == "darwin":
        import os
        return "aarch64-apple-darwin" if "arm" in os.uname().machine else "x86_64-apple-darwin"
    else:
        return "x86_64-unknown-linux-gnu"

def create_placeholder_for_sidecar(name):
    """Create placeholder for a specific sidecar"""
    script_dir = Path(__file__).parent
    src_tauri_dir = script_dir.parent  # scripts/ -> src-tauri/
    binaries_dir = src_tauri_dir / "binaries"
    
    # Buat direktori jika belum ada
    binaries_dir.mkdir(exist_ok=True)
    
    # Get target triple
    target_triple = get_target_triple()
    
    # Create placeholder file
    placeholder_name = f"{name}-{target_triple}"
    if sys.platform == "win32":
        placeholder_name += ".exe"
    
    placeholder_path = binaries_dir / placeholder_name
    
    # Check if valid sidecar exists (not just placeholder)
    if placeholder_path.exists():
        try:
            size = placeholder_path.stat().st_size
            # Jika file > 1MB, kemungkinan adalah sidecar yang sebenarnya (bukan placeholder)
            if size > 1_000_000:
                print(f"✓ Sidecar sudah ada: {placeholder_path} ({size / (1024*1024):.2f} MB)")
                return True
            else:
                print(f"Placeholder ditemukan, akan diupdate jika perlu: {placeholder_path}")
        except Exception:
            pass
    
    # Create minimal executable placeholder
    # Untuk Windows, buat file kosong (Tauri akan skip jika tidak bisa dijalankan)
    # Atau buat file yang print message
    if sys.platform == "win32":
        # Create minimal PE executable yang hanya exit
        # Atau lebih sederhana: buat file text dengan .exe extension
        # Tapi Tauri akan error jika bukan valid executable
        # Solusi: buat file yang valid tapi hanya print message dan exit
        placeholder_content = b""  # Empty untuk sekarang, akan diisi dengan minimal exe
        # Untuk development, kita bisa skip validasi dengan membuat file dummy
        # Tapi lebih baik buat minimal executable
        
        # Create minimal Windows executable (just exit with code 0)
        # Ini adalah minimal PE header yang valid
        minimal_exe = (
            b'MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00'
            b'\xb8\x00\x00\x00\x00\x00\x00\x00@\x00\x00\x00\x00\x00\x00\x00'
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x80\x00\x00\x00'
            b'PE\x00\x00d\x86\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xf0\x00'
            b'\x0f\x01\x0b\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        )
        placeholder_path.write_bytes(minimal_exe)
    else:
        # Untuk Linux/Mac, buat shell script yang valid
        placeholder_content = f"""#!/bin/sh
# Placeholder sidecar untuk development mode
# File ini hanya untuk memenuhi requirement Tauri externalBin
# Saat runtime, aplikasi akan menggunakan Python script sebagai fallback
echo "Placeholder sidecar - using Python script instead" >&2
exit 0
"""
        placeholder_path.write_text(placeholder_content, encoding='utf-8')
        # Make executable
        import os
        os.chmod(placeholder_path, 0o755)
    
    print(f"[OK] Placeholder created: {placeholder_path}")
    return True

def create_placeholder():
    """Create placeholders for all sidecars"""
    print("Creating placeholders for all sidecars...")
    success1 = create_placeholder_for_sidecar("infer_worker")
    
    if success1:
        print("  Note: Untuk production, jalankan 'npm run build:sidecar' untuk build sidecar yang sebenarnya")
        return True
    return False

if __name__ == "__main__":
    success = create_placeholder()
    sys.exit(0 if success else 1)
