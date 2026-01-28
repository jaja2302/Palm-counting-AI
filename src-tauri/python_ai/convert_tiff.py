"""
Convert unsupported TIFF formats (RGBPalette) to standard RGB TIFF.
Sidecar untuk convert TIFF yang tidak bisa dibaca oleh Rust tiff crate.
"""
import os
import sys
from pathlib import Path
from PIL import Image

def convert_tiff_to_rgb(input_path, output_path=None):
    """
    Convert TIFF to RGB format.
    
    Args:
        input_path: Path to input TIFF file
        output_path: Path to output TIFF file (optional, defaults to input_path)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Open with PIL (supports RGBPalette)
        img = Image.open(input_path)
        original_mode = img.mode
        
        # Convert to RGB if needed
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Save as RGB TIFF
        if output_path is None:
            output_path = input_path  # Overwrite original
        
        # Save with LZW compression to keep file size reasonable
        img.save(output_path, format='TIFF', compression='lzw')
        return True
        
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    # Expected: python convert_tiff.py <input_path> [output_path]
    if len(sys.argv) < 2:
        print("Usage: convert_tiff.py <input_path> [output_path]", file=sys.stderr)
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(input_path):
        print(f"ERROR: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)
    
    success = convert_tiff_to_rgb(input_path, output_path)
    sys.exit(0 if success else 1)
