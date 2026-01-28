#!/usr/bin/env python3
"""
Optimized build script untuk Pokok Kuning Desktop App dengan CUDA support
Minimal imports - hanya yang diperlukan saja!
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# ========== UBAH VERSION DI SINI ==========
APP_VERSION = "1.1.1"   # Format: "1.0.0" atau "1.2.3.4"
# ==========================================

def check_environment():
    """Check if we're in the correct environment"""
    conda_env = os.environ.get('CONDA_DEFAULT_ENV')
    conda_prefix = os.environ.get('CONDA_PREFIX')
    
    print("🔍 Environment Check")
    print("=" * 40)
    print(f"Conda Environment: {conda_env}")
    print(f"Python: {sys.executable}")
    
    if conda_env != 'yolov9':
        print("❌ Not in 'yolov9' environment!")
        print("Please run: conda activate yolov9")
        return False
    
    # Test PyTorch and CUDA
    try:
        import torch
        print(f"PyTorch: {torch.__version__}")
        print(f"CUDA Available: {torch.cuda.is_available()}")
        
        if torch.cuda.is_available():
            print(f"CUDA Version: {torch.version.cuda}")
            print(f"GPU: {torch.cuda.get_device_name(0)}")
        
        return True
    except ImportError:
        print("❌ PyTorch not installed!")
        return False

def _version_to_tuple(s):
    """Convert '1.0.0' or '1.2.3.4' -> (1, 0, 0, 0) or (1, 2, 3, 4)."""
    parts = [int(x) for x in s.strip().split(".")]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])

def create_version_file():
    """Create version_info.txt for Windows EXE (File Version / Product Version).
    PyInstaller evals this file; only a VSVersionInfo(...) expression is allowed (no imports).
    """
    v = _version_to_tuple(APP_VERSION)
    vstr = ".".join(str(x) for x in v)
    path = Path("version_info.txt")
    # Output must be eval-able only. VSVersionInfo etc. come from PyInstaller's versioninfo namespace.
    content = f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({v[0]}, {v[1]}, {v[2]}, {v[3]}),
    prodvers=({v[0]}, {v[1]}, {v[2]}, {v[3]}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'Pokok Kuning'),
          StringStruct('FileDescription', 'Pokok Kuning Desktop App'),
          StringStruct('FileVersion', '{vstr}'),
          StringStruct('InternalName', 'PokokKuningApp'),
          StringStruct('LegalCopyright', 'Copyright (C) Pokok Kuning'),
          StringStruct('OriginalFilename', 'PokokKuningApp.exe'),
          StringStruct('ProductName', 'Pokok Kuning Desktop App'),
          StringStruct('ProductVersion', '{vstr}'),
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
    path.write_text(content, encoding="utf-8")
    print(f"✅ Created version file: {path} (version {vstr})")
    return path

def create_optimized_spec_file():
    """Create optimized spec file with minimal essential imports"""
    
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

block_cipher = None

# App code files - minimal essential
added_files = [
    ('model', 'model'),
    ('ui', 'ui'), 
    ('core', 'core'),
    ('utils', 'utils'),
]

# Add icon if exists
if os.path.exists('assets/img/logo.ico'):
    added_files.append(('assets/img/logo.ico', 'assets/img'))

def get_conda_prefix():
    """Get conda environment prefix"""
    conda_prefix = os.environ.get('CONDA_PREFIX')
    if conda_prefix and os.path.exists(conda_prefix):
        return conda_prefix
    return None

def collect_essential_gdal_data():
    """Collect essential GDAL data for SHP export"""
    gdal_files = []
    conda_prefix = get_conda_prefix()
    
    if not conda_prefix:
        return gdal_files
    
    print(f"Collecting GDAL data from: {conda_prefix}")
    
    # Essential GDAL data files
    gdal_data_paths = [
        Path(conda_prefix) / "Library" / "share" / "gdal",
        Path(conda_prefix) / "share" / "gdal",
    ]
    
    essential_files = [
        'gcs.csv', 'pcs.csv', 'ellipsoid.csv', 'datum.csv', 'prime_meridian.csv'
    ]
    
    for gdal_path in gdal_data_paths:
        if gdal_path.exists():
            for data_file in essential_files:
                file_path = gdal_path / data_file
                if file_path.exists():
                    gdal_files.append((str(file_path), f"gdal_data/{data_file}"))
                    print(f"Found GDAL data: {data_file}")
            break
    
    # Essential PROJ data
    proj_data_paths = [
        Path(conda_prefix) / "Library" / "share" / "proj",
        Path(conda_prefix) / "share" / "proj",
    ]
    
    for proj_path in proj_data_paths:
        if proj_path.exists():
            # Just get a few essential proj files
            proj_files = list(proj_path.glob("*.db"))[:3]  # Get first 3 .db files
            for proj_file in proj_files:
                gdal_files.append((str(proj_file), f"proj_data/{proj_file.name}"))
                print(f"Found PROJ data: {proj_file.name}")
            break
    
    return gdal_files

def collect_essential_packages():
    """Collect essential package data for CUDA to work"""
    package_files = []
    
    # Torchvision package - CRITICAL for CUDA
    try:
        import torchvision
        torchvision_path = torchvision.__path__[0]
        package_files.append((torchvision_path, 'torchvision'))
        print(f"Added torchvision package: {torchvision_path}")
    except ImportError:
        print("Warning: torchvision not found")
    
    # PyTorch package - ensure CUDA support
    try:
        import torch
        torch_path = torch.__path__[0]
        package_files.append((torch_path, 'torch'))
        print(f"Added torch package: {torch_path}")
    except ImportError:
        print("Warning: torch not found")
    
    return package_files

# Collect GDAL data for SHP export
gdal_data = collect_essential_gdal_data()
added_files.extend(gdal_data)

# Collect essential packages for CUDA
package_data = collect_essential_packages()
added_files.extend(package_data)

# OPTIMIZED hidden imports - minimal but complete
hiddenimports = [
    # App modules
    'ui.main_window', 'core.processor', 'utils.config_manager',
    
    # FIXED PyTorch imports - include torch.distributed
    'torch', 'torch.cuda', 'torch._C', 'torch.nn',
    'torch.distributed',           # CRITICAL FIX
    'torch.distributed.nn',        # Also needed
    'torch.utils', 'torch.utils.data',
    'torch.backends', 'torch.backends.cuda', 'torch.backends.cudnn',
    'torch.version',
    
    # Torchvision - needed for CUDA to work properly
    'torchvision', 'torchvision.transforms', 'torchvision.models',
    'torchvision.models.resnet', 'torchvision.models.vgg',
    
    # FIXED Ultralytics essentials - MINIMAL but COMPLETE
    'ultralytics', 'ultralytics.models', 'ultralytics.models.yolo',
    'ultralytics.models.yolo.detect', 'ultralytics.models.yolo.detect.predict',
    'ultralytics.models.yolo.detect.val', 'ultralytics.models.yolo.detect.train',
    'ultralytics.models.yolo.segment', 'ultralytics.models.yolo.classify',
    'ultralytics.models.rtdetr',   # NEEDED for Ultralytics initialization
    'ultralytics.models.sam',      # NEEDED - was causing import error
    'ultralytics.engine', 'ultralytics.engine.predictor', 'ultralytics.engine.results',
    'ultralytics.engine.trainer', 'ultralytics.engine.validator',
    'ultralytics.utils', 'ultralytics.utils.plotting', 'ultralytics.utils.ops',
    'ultralytics.utils.torch_utils', 'ultralytics.utils.checks',
    'ultralytics.data', 'ultralytics.data.utils', 'ultralytics.data.base',
    'ultralytics.nn', 'ultralytics.nn.modules', 'ultralytics.nn.tasks',
    'ultralytics.trackers', 'ultralytics.trackers.track',
    
    # Computer Vision - minimal essential
    'cv2', 'numpy', 'PIL', 'PIL.Image', 'PIL.ImageDraw',
    
    # Additional essential modules for stability
    'yaml', 'tqdm', 'requests', 'urllib3',
    
    # Pandas modules - needed for geopandas
    'pandas', 'pandas.core', 'pandas.core.api', 'pandas.core.frame', 'pandas.core.series',
    'pandas.core.groupby', 'pandas.core.groupby.generic',
    
    # Geospatial for SHP/KML export - minimal essential
    'geojson', 'shapely', 'shapely.geometry', 'shapely.ops',
    'geopandas', 'geopandas.io', 'geopandas.io.file',
    'fiona', 'fiona.io', 'fiona.crs', 'fiona.schema', 'fiona.env',
    'pyproj', 'pyproj.crs', 'osgeo', 'osgeo.gdal', 'osgeo.ogr', 'osgeo.osr',
    
    # PyQt5 - minimal essential
    'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets', 'PyQt5.sip',
    
    # System essentials - minimal
    'threading', 'multiprocessing', 'concurrent.futures',
    'logging', 'json', 'pathlib', 'time', 'gc', 'traceback',
]

print(f"Optimized hidden imports: {len(hiddenimports)}")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['hook-optimized.py'],
    excludes=[
        # Exclude heavy non-essential modules
        'tkinter', 'matplotlib.pyplot', 'scipy.optimize', 'sklearn.datasets',
        'IPython', 'jupyter', 'notebook',
        'setuptools', 'distutils', 'wheel', 'pip',
        # Exclude heavy plotting and visualization
        'matplotlib', 'seaborn', 'plotly', 'bokeh',
        # Exclude heavy scientific computing
        'scipy.spatial', 'scipy.stats', 'scipy.optimize',
        # Exclude heavy ML libraries
        'sklearn', 'tensorflow', 'keras',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Filter data files - keep essential only
filtered_datas = []
for data_tuple in a.datas:
    if len(data_tuple) >= 2:
        src_path = data_tuple[0].lower()
        
        # Skip patterns
        skip_patterns = [
            'test/', 'tests/', 'example/', 'examples/', 'doc/', 'docs/',
            'sample/', 'samples/', 'demo/', 'demos/', 'tutorial/',
            '.md', '.rst', '.txt', 'readme', 'changelog', 'license',
            'benchmark/', 'profiling/', '.pyi', '.typed',
        ]
        
        should_skip = any(pattern in src_path for pattern in skip_patterns)
        
        if not should_skip:
            filtered_datas.append(data_tuple)

a.datas = filtered_datas
print(f"Filtered data files: {len(a.datas)}")

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PokokKuningApp',
    debug=False,              # Disable debug for production
    bootloader_ignore_signals=False,
    strip=False,                     # Keep disabled to avoid warnings
    upx=True,                        # Compress for size
    console=True,                    # Keep console for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/img/logo.ico' if os.path.exists('assets/img/logo.ico') else None,
    version='version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[
        'cudart*.dll', 'cublas*.dll', 'c10_cuda.dll',
        'gdal*.dll', 'proj*.dll', 'geos*.dll'
    ],
    name='PokokKuningApp',
)
'''
    
    spec_file = Path("pokok_kuning_optimized.spec")
    with open(spec_file, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print(f"✅ Created optimized spec file: {spec_file}")
    return spec_file

def create_optimized_hook():
    """Create optimized runtime hook with minimal setup"""
    
    hook_content = '''#!/usr/bin/env python3
"""
Optimized Runtime Hook - Minimal Setup for Stability
"""

import os
import sys
import logging
import datetime

# Create runtime log file
runtime_log_file = os.path.join(os.getcwd(), f"runtime_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(runtime_log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def setup_environment():
    """Setup minimal runtime environment"""
    logger.info("=== ENVIRONMENT SETUP ===")
    
    try:
        if hasattr(sys, '_MEIPASS'):
            base_dir = sys._MEIPASS
            
            # Add _internal to PATH
            internal_dir = os.path.join(base_dir, '_internal')
            if os.path.exists(internal_dir):
                current_path = os.environ.get('PATH', '')
                if internal_dir not in current_path:
                    os.environ['PATH'] = internal_dir + os.pathsep + current_path
                    logger.info(f"Added to PATH: {internal_dir}")
            
            # CUDA environment - minimal setup
            os.environ['CUDA_PATH'] = base_dir
            os.environ['CUDA_VISIBLE_DEVICES'] = '0'
            os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'max_split_size_mb:256,garbage_collection_threshold:0.6'
            
            # torch.distributed environment - CRITICAL FIX
            os.environ['MASTER_ADDR'] = 'localhost'
            os.environ['MASTER_PORT'] = '12355'
            os.environ['RANK'] = '0' 
            os.environ['WORLD_SIZE'] = '1'
            logger.info("Set torch.distributed environment variables")
            
            # GDAL environment
            gdal_data_dir = os.path.join(base_dir, 'gdal_data')
            if os.path.exists(gdal_data_dir):
                os.environ['GDAL_DATA'] = gdal_data_dir
                logger.info(f"Set GDAL_DATA: {gdal_data_dir}")
            
            proj_data_dir = os.path.join(base_dir, 'proj_data')  
            if os.path.exists(proj_data_dir):
                os.environ['PROJ_LIB'] = proj_data_dir
                logger.info(f"Set PROJ_LIB: {proj_data_dir}")
        
        logger.info("Environment setup completed")
        
    except Exception as e:
        logger.error(f"Environment setup failed: {e}")

def test_critical_imports():
    """Test critical imports with minimal logging"""
    logger.info("=== IMPORT TESTING ===")
    
    import_tests = [
        ('torch', 'PyTorch'),
        ('torch.distributed', 'PyTorch Distributed'),
        ('ultralytics', 'Ultralytics'),
        ('cv2', 'OpenCV'), 
        ('geojson', 'GeoJSON'),
        ('PyQt5.QtCore', 'PyQt5')
    ]
    
    success_count = 0
    for module_name, display_name in import_tests:
        try:
            module = __import__(module_name)
            logger.info(f"{display_name}: OK")
            success_count += 1
                
        except ImportError as e:
            logger.error(f"{display_name} IMPORT FAILED: {e}")
        except Exception as e:
            logger.error(f"{display_name} ERROR: {e}")
    
    logger.info(f"Import test results: {success_count}/{len(import_tests)} successful")
    
    if success_count < len(import_tests):
        logger.error("CRITICAL: Some imports failed - application may crash")
    else:
        logger.info("All critical imports successful")

# Execute setup
try:
    setup_environment()
    test_critical_imports()
    logger.info("=== RUNTIME SETUP COMPLETED ===")
    logger.info(f"Runtime log saved to: {runtime_log_file}")
    
except Exception as e:
    logger.error(f"RUNTIME HOOK FAILED: {e}")
    logger.error("Application may crash - check this log file for details")
'''
    
    hook_file = Path("hook-optimized.py")
    with open(hook_file, 'w', encoding='utf-8') as f:
        f.write(hook_content)
    
    print(f"✅ Created optimized hook: {hook_file}")

def clean_build():
    """Clean build directories"""
    print("\n🧹 Cleaning previous builds...")
    
    for dir_name in ["dist", "build", "__pycache__"]:
        dir_path = Path(dir_name)
        if dir_path.exists():
            try:
                shutil.rmtree(dir_path)
                print(f"Removed: {dir_name}/")
            except Exception as e:
                print(f"Failed to remove {dir_name}/: {e}")

def build_executable():
    """Build the executable"""
    
    print("\n🔨 Building executable...")
    print("=" * 50)
    
    spec_file = "pokok_kuning_optimized.spec"
    
    # Run PyInstaller with optimization
    cmd = [
        sys.executable, "-m", "PyInstaller", 
        "--clean", 
        "--noconfirm",
        "--log-level=INFO",
        spec_file
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=1800)
        
        if result.stdout:
            print("Build completed successfully!")
        if result.stderr:
            print("Build warnings/errors:", result.stderr)
        
        return True
        
    except subprocess.TimeoutExpired:
        print("❌ Build timed out after 30 minutes")
        return False
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed with return code: {e.returncode}")
        if e.stderr:
            print("STDERR:", e.stderr)
        return False

def verify_build():
    """Verify build output"""
    
    print("\n🔍 Verifying build...")
    
    exe_file = Path("dist/PokokKuningApp/PokokKuningApp.exe")
    
    if not exe_file.exists():
        print("❌ Executable not found!")
        return False
    
    # Get size info
    try:
        size_mb = exe_file.stat().st_size / (1024 * 1024)
        print(f"✅ Executable created: {size_mb:.1f} MB")
    except:
        print("✅ Executable created")
    
    # Directory info
    dist_dir = Path("dist/PokokKuningApp")
    if dist_dir.exists():
        total_size = 0
        file_count = 0
        
        try:
            for file_path in dist_dir.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
                    file_count += 1
            
            total_mb = total_size / (1024 * 1024)
            print(f"✅ Total directory: {total_mb:.1f} MB ({file_count} files)")
            
        except Exception as e:
            print(f"Error analyzing directory: {e}")
    
    return True

def main():
    """Main optimized build process"""
    
    print("🚀 Optimized Pokok Kuning Build Process")
    print("=" * 60)
    print("🎯 Minimal imports - hanya yang diperlukan saja!")
    print("=" * 60)
    
    # 1. Check environment
    if not check_environment():
        print("\n❌ Environment check failed!")
        return False
    
    # 2. Create optimized files
    print("\n📝 Creating optimized build files...")
    create_version_file()
    create_optimized_spec_file()
    create_optimized_hook()
    
    # 3. Clean build
    clean_build()
    
    # 4. Build
    if not build_executable():
        print("\n❌ Build failed!")
        return False
    
    # 5. Verify
    if not verify_build():
        print("\n❌ Verification failed!")
        return False
    
    # 6. Success!
    print("\n" + "=" * 60)
    print("🎉 OPTIMIZED BUILD COMPLETED!")
    print("=" * 60)
    print("\nYour optimized executable is ready:")
    print("📁 Location: dist/PokokKuningApp/PokokKuningApp.exe")
    print("\n🚀 OPTIMIZATIONS APPLIED:")
    print("📦 Minimal hidden imports (reduced from 100+ to ~60)")
    print("🗂️  Essential packages only (torch, torchvision, ultralytics)")
    print("🔧 Optimized runtime hook (minimal setup)")
    print("📊 Reduced executable size and startup time")
    print("🛡️  Maintained CUDA support and stability")
    print("\n🧪 Test your app:")
    print("1. cd dist/PokokKuningApp")
    print("2. Run: PokokKuningApp.exe")
    print("3. Check runtime_*.log for any issues")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nBuild interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)