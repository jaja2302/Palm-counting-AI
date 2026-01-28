"""
Python sidecar untuk Tauri.
Support mode:
1. --convert: Convert .pt → .onnx (untuk backward compatibility)
2. --infer: Process folder dengan YOLO Python (legacy)
3. --infer-files: Process daftar file .tif, output per file ke folder {stem}_{model}/

Usage:
  Conversion: infer_worker.py --convert <input.pt> <output.onnx> <imgsz>
  Inference:  infer_worker.py --infer <folder> <model_path> <config_json>
  Infer files: infer_worker.py --infer-files <files_json> <model_path> <model_name> <config_json>
"""
from __future__ import annotations

import os
import re
import sys
import json
import gc
from pathlib import Path
from PIL import Image
import cv2
import geojson
from shapely.geometry import Point, mapping
import geopandas as gpd
from fastkml import kml, geometry

def safe_print(message: str) -> None:
    """Safe print function that works in both console and windowed modes"""
    try:
        print(message, file=sys.stderr, flush=True)
    except (AttributeError, OSError):
        pass

def log_error(msg: str) -> None:
    """Log error to stderr (will be captured by Rust)"""
    print(f"ERROR: {msg}", file=sys.stderr, flush=True)

def validate_and_preprocess_image(image_path):
    """Validate image and ensure consistent format (handles RGBPalette, etc.)"""
    try:
        with Image.open(image_path) as img:
            original_mode = img.mode
            width, height = img.size
            
            # Handle different image modes
            if img.mode in ['RGBA', 'LA']:
                img = img.convert('RGB')
            elif img.mode in ['L', 'P']:
                # Convert grayscale or palette to RGB (handles RGBPalette TIFF)
                img = img.convert('RGB')
            elif img.mode == 'CMYK':
                img = img.convert('RGB')
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Save the converted image temporarily for YOLO processing
            temp_path = None
            if original_mode != 'RGB':
                base_name = os.path.splitext(image_path)[0]
                temp_path = base_name + "_temp_rgb.jpg"
                img.save(temp_path, 'JPEG', quality=95)
            
            return True, width, height, img.mode, temp_path
                
    except Exception as e:
        log_error(f"Image validation failed: {e}")
        return False, 0, 0, None, None

def convert_mode() -> None:
    """Conversion mode: convert .pt to .onnx"""
    if len(sys.argv) < 4:
        log_error("Usage: infer_worker.py --convert <input.pt> <output.onnx> <imgsz>")
        sys.exit(1)
    
    pt_path = sys.argv[2]
    onnx_path = sys.argv[3]
    imgsz = int(sys.argv[4]) if len(sys.argv) > 4 else 640
    
    try:
        from ultralytics import YOLO
        import torch
        
        # WAJIB GPU - tidak ada fallback ke CPU
        if not torch.cuda.is_available():
            log_error("GPU (CUDA) is REQUIRED for model conversion!")
            sys.exit(1)
        
        device = 'cuda:0'
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / (1024**3)
        safe_print(f"Using GPU: {gpu_name} ({gpu_memory:.1f} GB)")
        
    except ImportError as e:
        log_error(f"Failed to import: {e}")
        sys.exit(1)
    except Exception as e:
        log_error(f"GPU detection failed: {e}")
        sys.exit(1)
    
    try:
        safe_print(f"Loading model: {pt_path}")
        model = YOLO(pt_path)
        model.to(device)
        safe_print(f"Model moved to device: {device}")
        
        # Verify GPU dengan dummy forward pass
        try:
            test_size = min(640, imgsz)
            dummy_input = torch.zeros(1, 3, test_size, test_size).to(device)
            _ = model.model(dummy_input)
            safe_print(f"GPU verification successful")
            del dummy_input
            torch.cuda.empty_cache()
        except Exception as gpu_test_err:
            log_error(f"GPU verification failed: {gpu_test_err}")
            sys.exit(1)
        
        safe_print(f"Exporting to ONNX: {onnx_path} (imgsz={imgsz}, device={device})")
        model.export(
            format="onnx",
            imgsz=imgsz,
            simplify=True,
            opset=12,
            dynamic=False,
            half=False,
            device=device,
        )
        
        # Move exported file
        exported_path = os.path.splitext(pt_path)[0] + ".onnx"
        if os.path.exists(exported_path) and exported_path != onnx_path:
            import shutil
            shutil.move(exported_path, onnx_path)
            safe_print(f"Moved {exported_path} -> {onnx_path}")
        
        if not os.path.exists(onnx_path):
            possible_paths = [
                os.path.splitext(pt_path)[0] + ".onnx",
                os.path.join(os.path.dirname(onnx_path), os.path.basename(os.path.splitext(pt_path)[0] + ".onnx")),
            ]
            for pp in possible_paths:
                if os.path.exists(pp):
                    import shutil
                    shutil.move(pp, onnx_path)
                    safe_print(f"Found and moved: {pp} -> {onnx_path}")
                    break
        
        if os.path.exists(onnx_path):
            size_mb = os.path.getsize(onnx_path) / (1024 * 1024)
            safe_print(f"✓ Conversion successful: {onnx_path} ({size_mb:.2f} MB)")
            sys.exit(0)
        else:
            log_error(f"ONNX file not found at {onnx_path}")
            sys.exit(1)
            
    except Exception as e:
        log_error(f"Conversion failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def infer_mode() -> None:
    """Inference mode: process folder dengan YOLO Python"""
    if len(sys.argv) < 4:
        log_error("Usage: infer_worker.py --infer <folder> <model_path> <config_json>")
        sys.exit(1)
    
    folder_path = sys.argv[2]
    model_path = sys.argv[3]
    config_json = sys.argv[4]
    
    try:
        config = json.loads(config_json)
    except Exception as e:
        log_error(f"Failed to parse config JSON: {e}")
        sys.exit(1)
    
    # Parse config
    imgsz = int(config.get("imgsz", 12800))
    conf = float(config.get("conf", 0.2))
    iou = float(config.get("iou", 0.2))
    max_det = int(config.get("max_det", 10000))
    device_pref = config.get("device", "auto").lower()
    convert_kml = config.get("convert_kml", "false").lower() == "true"
    convert_shp = config.get("convert_shp", "false").lower() == "true"
    save_annotated = config.get("save_annotated", "true").lower() == "true"
    line_width = int(config.get("line_width", 3))
    show_labels = config.get("show_labels", "true").lower() == "true"
    show_conf = config.get("show_conf", "false").lower() == "true"

    try:
        from ultralytics import YOLO
        import torch
        
        # Device selection
        if device_pref == "cpu":
            device = "cpu"
            safe_print(f"Using CPU (user selection)")
        elif device_pref == "cuda":
            if torch.cuda.is_available():
                device = "cuda"
                safe_print(f"Using CUDA: {torch.cuda.get_device_name(0)}")
            else:
                device = "cpu"
                safe_print(f"CUDA requested but not available, using CPU")
        else:  # auto
            if torch.cuda.is_available():
                device = "cuda"
                safe_print(f"Auto-detected CUDA: {torch.cuda.get_device_name(0)}")
            else:
                device = "cpu"
                safe_print(f"CUDA not available, using CPU")
        
        # Load model
        safe_print(f"Loading YOLO model: {model_path}")
        model = YOLO(model_path)
        
        if device == "cuda":
            try:
                torch.cuda.empty_cache()
                model.to(device)
                # Test CUDA
                test_tensor = torch.zeros(1, device='cuda')
                del test_tensor
                torch.cuda.synchronize()
                safe_print(f"Model loaded on GPU successfully")
            except Exception as e:
                safe_print(f"CUDA error, falling back to CPU: {e}")
                device = "cpu"
                model = YOLO(model_path)
        else:
            safe_print(f"Model loaded on CPU")
    except Exception as e:
        log_error(f"Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Get image files — hanya TIFF ( .tif / .tiff ); abaikan .jpg (termasuk _temp_rgb.jpg dari preprocessing)
    image_extensions = ('.tif', '.tiff')
    image_files = [f for f in os.listdir(folder_path) if f.lower().endswith(image_extensions)]
    total_files = len(image_files)
    
    if total_files == 0:
        log_error("No image files found in folder")
        sys.exit(1)
    
    safe_print(f"Found {total_files} image file(s) to process")
    
    successful = 0
    failed = 0
    total_abnormal = 0
    total_normal = 0
    annotated_dir = os.path.join(folder_path, "annotated")
    
    for index, image_file in enumerate(image_files):
        image_path = os.path.join(folder_path, image_file)
        safe_print(f"Processing [{index+1}/{total_files}]: {image_file}")
        
        try:
            # Validate and preprocess image (handles RGBPalette, etc.)
            is_valid, width, height, mode, temp_path = validate_and_preprocess_image(image_path)
            if not is_valid:
                safe_print(f"  ✗ Invalid image")
                failed += 1
                continue
            
            # Use temp RGB image if created
            processing_path = temp_path if temp_path else image_path
            
            # Run YOLO prediction
            try:
                results = model.predict(
                    source=processing_path,
                    imgsz=imgsz,
                    conf=conf,
                    iou=iou,
                    max_det=max_det,
                    device=device,
                    verbose=False,
                    save=False
                )
            except Exception as pred_error:
                safe_print(f"  ⚠️  Prediction failed: {pred_error}")
                if device == "cuda":
                    safe_print(f"  Retrying on CPU...")
                    results = model.predict(
                        source=processing_path,
                        imgsz=imgsz,
                        conf=conf,
                        iou=iou,
                        max_det=max_det,
                        device="cpu",
                        verbose=False,
                        save=False
                    )
                else:
                    raise pred_error

            # Count detections
            abnormal_count = 0
            normal_count = 0
            detections_list = []
            
            for result in results:
                if result.boxes is not None:
                    for detection in result.boxes:
                        class_id = int(detection.cls)
                        if class_id == 0:
                            abnormal_count += 1
                        elif class_id == 1:
                            normal_count += 1
                        
                        # Store detection for GeoJSON
                        x1, y1, x2, y2 = detection.xyxy[0].cpu().numpy()
                        detections_list.append({
                            'x1': float(x1),
                            'y1': float(y1),
                            'x2': float(x2),
                            'y2': float(y2),
                            'class_id': int(class_id),
                            'conf': float(detection.conf.cpu().numpy())
                        })
            
            total_abnormal += abnormal_count
            total_normal += normal_count
            
            # Read .tfw file (optional)
            base_name = os.path.splitext(image_path)[0]
            tfw_file = base_name + ".tfw"
            tfw_params = None
            if os.path.exists(tfw_file):
                try:
                    with open(tfw_file) as f:
                        params = f.readlines()
                    tfw_params = [float(p.strip()) for p in params[:6]]
                except Exception:
                    pass
            
            # Create and save GeoJSON/KML/Shapefile only when .tfw exists
            if tfw_params and detections_list:
                labels = model.names
                pixel_size_x, rotation_x, rotation_y, pixel_size_y, upper_left_x, upper_left_y = tfw_params
                features = []
                for det in detections_list:
                    try:
                        center_x = (det['x1'] + det['x2']) / 2
                        center_y = (det['y1'] + det['y2']) / 2
                        map_x = upper_left_x + center_x * pixel_size_x
                        map_y = upper_left_y + center_y * pixel_size_y
                        point = Point(map_x, map_y)
                        class_id = det['class_id']
                        label = labels.get(class_id, f"class_{class_id}")
                        feature = geojson.Feature(
                            geometry=mapping(point),
                            properties={
                                "label": label,
                                "confidence": det['conf'],
                                "class_id": class_id
                            }
                        )
                        features.append(feature)
                    except Exception:
                        continue
                if features:
                    fc = geojson.FeatureCollection(features)
                    geojson_path = os.path.join(folder_path, os.path.splitext(image_file)[0] + ".geojson")
                    
                    # Handle duplicates
                    counter = 1
                    while os.path.exists(geojson_path):
                        geojson_path = os.path.join(folder_path, f"{os.path.splitext(image_file)[0]}_{counter}.geojson")
                        counter += 1
                    
                    with open(geojson_path, "w") as f:
                        geojson.dump(fc, f)
                    safe_print(f"  ✓ GeoJSON saved: {os.path.basename(geojson_path)}")
                    
                    # Convert to KML if requested
                    if convert_kml:
                        try:
                            kml_path = geojson_path.replace('.geojson', '.kml')
                            k = kml.KML()
                            ns = '{http://www.opengis.net/kml/2.2}'
                            d = kml.Document(ns, 'docid', 'doc name', 'doc description')
                            k.append(d)
                            
                            for feature in fc['features']:
                                coords = feature['geometry']['coordinates']
                                properties = feature['properties']
                                p = kml.Placemark(ns, 'id', properties.get('label', 'Unnamed'), 'description')
                                p.geometry = geometry.Point(coords[0], coords[1])
                                d.append(p)
                            
                            with open(kml_path, 'w') as f:
                                f.write(k.to_string(prettyprint=True))
                            safe_print(f"  ✓ KML saved: {os.path.basename(kml_path)}")
                        except Exception as e:
                            safe_print(f"  ✗ KML conversion failed: {e}")
                    
                    # Convert to Shapefile if requested
                    if convert_shp:
                        try:
                            shp_path = geojson_path.replace('.geojson', '.shp')
                            gdf = gpd.read_file(geojson_path)
                            if not gdf.empty:
                                base_shp_path = os.path.splitext(shp_path)[0]
                                gdf.to_file(base_shp_path, driver='ESRI Shapefile')
                                safe_print(f"  ✓ Shapefile saved: {os.path.basename(base_shp_path)}.shp")
                        except Exception as e:
                            safe_print(f"  ✗ Shapefile conversion failed: {e}")
            elif not tfw_params:
                safe_print(
                    "  Shapefile, KML, and GeoJSON require a .tfw file next to the TIFF "
                    "(same base name, e.g. UPE.tfw for UPE.tif). Skipping geospatial output."
                )
            elif not detections_list:
                safe_print("  No detections; skipping geospatial output.")
            # Save annotated image if requested
            if save_annotated and results:
                try:
                    os.makedirs(annotated_dir, exist_ok=True)
                    image = cv2.imread(image_path)
                    if image is not None:
                        colors = {
                            0: (0, 0, 255),    # Red for abnormal
                            1: (0, 255, 0),    # Green for normal
                            2: (255, 0, 0),    # Blue
                        }
                        
                        for result in results:
                            if result.boxes is not None:
                                for detection in result.boxes:
                                    x1, y1, x2, y2 = detection.xyxy[0].cpu().numpy().astype(int)
                                    class_id = int(detection.cls)
                                    color = colors.get(class_id, (128, 128, 128))
                                    
                                    cv2.rectangle(image, (x1, y1), (x2, y2), color, line_width)
                                    
                                    if show_labels or show_conf:
                                        confidence = float(detection.conf)
                                        class_name = model.names.get(class_id, f"class_{class_id}")
                                        
                                        if show_labels and show_conf:
                                            label = f"{class_name}: {confidence:.2f}"
                                        elif show_labels:
                                            label = class_name
                                        else:
                                            label = f"{confidence:.2f}"
                                        
                                        (text_width, text_height), baseline = cv2.getTextSize(
                                            label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
                                        )
                                        cv2.rectangle(
                                            image,
                                            (x1, y1 - text_height - 10),
                                            (x1 + text_width, y1),
                                            color,
                                            -1
                                        )
                                        cv2.putText(
                                            image,
                                            label,
                                            (x1, y1 - 5),
                                            cv2.FONT_HERSHEY_SIMPLEX,
                                            0.6,
                                            (255, 255, 255),
                                            2
                                        )
                        
                        base_name = os.path.splitext(os.path.basename(image_path))[0]
                        output_path = os.path.join(annotated_dir, f"{base_name}_annotated.jpg")
                        
                        counter = 1
                        while os.path.exists(output_path):
                            output_path = os.path.join(annotated_dir, f"{base_name}_annotated_{counter}.jpg")
                            counter += 1
                        
                        cv2.imwrite(output_path, image)
                        safe_print(f"  ✓ Annotated image saved: {os.path.basename(output_path)}")
                except Exception as e:
                    safe_print(f"  ✗ Failed to save annotated image: {e}")
            
            # Cleanup temp file
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            
            safe_print(f"  ✓ Detection: {abnormal_count} abnormal, {normal_count} normal")
            successful += 1
            
            # Memory cleanup
            if (index + 1) % 5 == 0:
                gc.collect()
                if device == "cuda":
                    torch.cuda.empty_cache()
            
            # Output progress as JSON (for Rust to parse)
            progress = {
                "processed": index + 1,
                "total": total_files,
                "current_file": image_file,
                "status": "OK",
                "abnormal_count": abnormal_count,
                "normal_count": normal_count,
                "successful": successful,
                "failed": failed
            }
            print(json.dumps(progress), flush=True)
            
        except Exception as e:
            safe_print(f"  ❌ Error processing {image_file}: {e}")
            failed += 1
            progress = {
                "processed": index + 1,
                "total": total_files,
                "current_file": image_file,
                "status": f"Error: {e}",
                "abnormal_count": 0,
                "normal_count": 0,
                "successful": successful,
                "failed": failed
            }
            print(json.dumps(progress), flush=True)
    
    # Final summary
    summary = {
        "done": True,
        "successful": successful,
        "failed": failed,
        "total": total_files,
        "total_abnormal": total_abnormal,
        "total_normal": total_normal
    }
    print(json.dumps(summary), flush=True)
    
    sys.exit(0 if successful > 0 else 1)


def _sanitize_model_name(name: str) -> str:
    """Safe folder name from model name (no path chars)."""
    s = re.sub(r'[<>:"/\\|?*]', '_', name)
    return s.strip() or "model"


def infer_files_mode() -> None:
    """Process daftar file .tif; output per file ke folder {stem}_{model_name}/."""
    if len(sys.argv) < 6:
        log_error("Usage: infer_worker.py --infer-files <files_json> <model_path> <model_name> <config_json>")
        sys.exit(1)
    files_json = sys.argv[2]
    model_path = sys.argv[3]
    model_name = sys.argv[4]
    config_json = sys.argv[5]
    model_name_safe = _sanitize_model_name(model_name)
    try:
        file_paths = json.loads(files_json)
    except Exception as e:
        log_error(f"Failed to parse files JSON: {e}")
        sys.exit(1)
    if not isinstance(file_paths, list) or not file_paths:
        log_error("files_json must be a non-empty array of .tif paths")
        sys.exit(1)
    image_extensions = ('.tif', '.tiff')
    image_files = [p for p in file_paths if isinstance(p, str) and p.lower().endswith(image_extensions)]
    if not image_files:
        log_error("No .tif/.tiff paths in files_json")
        sys.exit(1)
    try:
        config = json.loads(config_json)
    except Exception as e:
        log_error(f"Failed to parse config JSON: {e}")
        sys.exit(1)
    imgsz = int(config.get("imgsz", 12800))
    conf = float(config.get("conf", 0.2))
    iou = float(config.get("iou", 0.2))
    max_det = int(config.get("max_det", 10000))
    device_pref = config.get("device", "auto").lower()
    convert_kml = config.get("convert_kml", "false").lower() == "true"
    convert_shp = config.get("convert_shp", "false").lower() == "true"
    save_annotated = config.get("save_annotated", "true").lower() == "true"
    line_width = int(config.get("line_width", 3))
    show_labels = config.get("show_labels", "true").lower() == "true"
    show_conf = config.get("show_conf", "false").lower() == "true"
    try:
        from ultralytics import YOLO
        import torch
        
        # Device selection
        if device_pref == "cpu":
            device = "cpu"
            safe_print(f"Using CPU (user selection)")
        elif device_pref == "cuda":
            if torch.cuda.is_available():
                device = "cuda"
                safe_print(f"Using CUDA: {torch.cuda.get_device_name(0)}")
            else:
                device = "cpu"
                safe_print(f"CUDA requested but not available, using CPU")
        else:  # auto
            if torch.cuda.is_available():
                device = "cuda"
                safe_print(f"Auto-detected CUDA: {torch.cuda.get_device_name(0)}")
            else:
                device = "cpu"
                safe_print(f"CUDA not available, using CPU")
        
        # Load model
        safe_print(f"Loading YOLO model: {model_path}")
        model = YOLO(model_path)
        
        if device == "cuda":
            try:
                torch.cuda.empty_cache()
                model.to(device)
                safe_print("Model loaded on GPU successfully")
            except Exception as e:
                safe_print(f"CUDA error, falling back to CPU: {e}")
                device = "cpu"
                model = YOLO(model_path)
        else:
            safe_print(f"Model loaded on CPU")
    except Exception as e:
        log_error(f"Failed to load model: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    total_files = len(image_files)
    safe_print(f"Found {total_files} image file(s) to process")
    successful = 0
    failed = 0
    total_abnormal = 0
    total_normal = 0
    for index, image_path in enumerate(image_files):
        if not os.path.isfile(image_path):
            safe_print(f"  ✗ Not a file: {image_path}")
            failed += 1
            print(json.dumps({
                "processed": index + 1, "total": total_files, "current_file": image_path,
                "status": "Error: not a file", "abnormal_count": 0, "normal_count": 0,
                "successful": successful, "failed": failed, "output_folder": None
            }), flush=True)
            continue
        parent_dir = os.path.dirname(image_path)
        stem = os.path.splitext(os.path.basename(image_path))[0]
        output_dir = os.path.join(parent_dir, f"{stem}_{model_name_safe}")
        os.makedirs(output_dir, exist_ok=True)
        image_file = os.path.basename(image_path)
        safe_print(f"Processing [{index + 1}/{total_files}]: {image_file}")
        try:
            safe_print("  [1/4] Validating image...")
            is_valid, width, height, mode, temp_path = validate_and_preprocess_image(image_path)
            if not is_valid:
                safe_print("  ✗ Invalid image")
                failed += 1
                print(json.dumps({
                    "processed": index + 1, "total": total_files, "current_file": image_path,
                    "status": "Invalid image", "abnormal_count": 0, "normal_count": 0,
                    "successful": successful, "failed": failed, "output_folder": None
                }), flush=True)
                continue
            processing_path = temp_path if temp_path else image_path
            def _emit_inference_progress(batch_num: int) -> None:
                safe_print(f"  [2/4] Inference batch {batch_num}...")
                print(
                    json.dumps(
                        {
                            "processed": index,
                            "total": total_files,
                            "current_file": image_path,
                            "status": f"Inference batch {batch_num}...",
                            "abnormal_count": 0,
                            "normal_count": 0,
                            "successful": successful,
                            "failed": failed,
                            "output_folder": None,
                        }
                    ),
                    flush=True,
                )

            safe_print("  [2/4] Running YOLO inference... (large images may take several minutes)")
            results = []
            for batch_num, r in enumerate(
                model.predict(
                    source=processing_path,
                    imgsz=imgsz,
                    conf=conf,
                    iou=iou,
                    max_det=max_det,
                    device=device,
                    verbose=False,
                    save=False,
                    stream=True,
                ),
                1,
            ):
                results.append(r)
                _emit_inference_progress(batch_num)
            safe_print("  [3/4] Inference done. Generating GeoJSON & outputs...")
            print(
                json.dumps(
                    {
                        "processed": index,
                        "total": total_files,
                        "current_file": image_path,
                        "status": "Generating GeoJSON & outputs...",
                        "abnormal_count": 0,
                        "normal_count": 0,
                        "successful": successful,
                        "failed": failed,
                        "output_folder": None,
                    }
                ),
                flush=True,
            )
            abnormal_count = 0
            normal_count = 0
            detections_list = []
            for result in results:
                if result.boxes is None:
                    continue
                for detection in result.boxes:
                    class_id = int(detection.cls)
                    if class_id == 0:
                        abnormal_count += 1
                    elif class_id == 1:
                        normal_count += 1
                    x1, y1, x2, y2 = detection.xyxy[0].cpu().numpy()
                    detections_list.append({
                        "x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2),
                        "class_id": int(class_id), "conf": float(detection.conf.cpu().numpy()),
                    })
            total_abnormal += abnormal_count
            total_normal += normal_count
            base_name = os.path.splitext(image_path)[0]
            tfw_file = base_name + ".tfw"
            tfw_params = None
            if os.path.exists(tfw_file):
                try:
                    with open(tfw_file) as f:
                        params = f.readlines()
                    tfw_params = [float(p.strip()) for p in params[:6]]
                except Exception:
                    pass
            if tfw_params and detections_list:
                labels = model.names
                pixel_size_x, _, _, pixel_size_y, upper_left_x, upper_left_y = tfw_params
                features = []
                for det in detections_list:
                    try:
                        cx = (det["x1"] + det["x2"]) / 2
                        cy = (det["y1"] + det["y2"]) / 2
                        map_x = upper_left_x + cx * pixel_size_x
                        map_y = upper_left_y + cy * pixel_size_y
                        point = Point(map_x, map_y)
                        class_id = det["class_id"]
                        label = labels.get(class_id, f"class_{class_id}")
                        features.append(geojson.Feature(
                            geometry=mapping(point),
                            properties={"label": label, "confidence": det["conf"], "class_id": class_id},
                        ))
                    except Exception:
                        continue
                if features:
                    fc = geojson.FeatureCollection(features)
                    geojson_path = os.path.join(output_dir, stem + ".geojson")
                    counter = 1
                    while os.path.exists(geojson_path):
                        geojson_path = os.path.join(output_dir, f"{stem}_{counter}.geojson")
                        counter += 1
                    with open(geojson_path, "w") as f:
                        geojson.dump(fc, f)
                    safe_print(f"  ✓ GeoJSON saved: {os.path.basename(geojson_path)}")
                    if convert_kml:
                        try:
                            kml_path = geojson_path.replace(".geojson", ".kml")
                            k = kml.KML()
                            ns = "{http://www.opengis.net/kml/2.2}"
                            d = kml.Document(ns, "docid", "doc name", "doc description")
                            k.append(d)
                            for feature in fc["features"]:
                                coords = feature["geometry"]["coordinates"]
                                props = feature["properties"]
                                p = kml.Placemark(ns, "id", props.get("label", "Unnamed"), "description")
                                p.geometry = geometry.Point(coords[0], coords[1])
                                d.append(p)
                            with open(kml_path, "w") as f:
                                f.write(k.to_string(prettyprint=True))
                            safe_print(f"  ✓ KML saved: {os.path.basename(kml_path)}")
                        except Exception as e:
                            safe_print(f"  ✗ KML conversion failed: {e}")
                    if convert_shp:
                        try:
                            shp_path = geojson_path.replace(".geojson", ".shp")
                            gdf = gpd.read_file(geojson_path)
                            if not gdf.empty:
                                base_shp_path = os.path.splitext(shp_path)[0]
                                gdf.to_file(base_shp_path, driver="ESRI Shapefile")
                                safe_print(f"  ✓ Shapefile saved: {os.path.basename(base_shp_path)}.shp")
                        except Exception as e:
                            safe_print(f"  ✗ Shapefile conversion failed: {e}")
            elif not tfw_params:
                safe_print(
                    "  Shapefile, KML, and GeoJSON require a .tfw file next to the TIFF "
                    "(same base name, e.g. UPE.tfw for UPE.tif). Skipping geospatial output."
                )
            elif not detections_list:
                safe_print("  No detections; skipping geospatial output.")
            if save_annotated and results:
                try:
                    img = cv2.imread(image_path)
                    if img is not None:
                        colors = {0: (0, 0, 255), 1: (0, 255, 0), 2: (255, 0, 0)}
                        for result in results:
                            if result.boxes is None:
                                continue
                            for detection in result.boxes:
                                x1, y1, x2, y2 = detection.xyxy[0].cpu().numpy().astype(int)
                                cid = int(detection.cls)
                                color = colors.get(cid, (128, 128, 128))
                                cv2.rectangle(img, (x1, y1), (x2, y2), color, line_width)
                                if show_labels or show_conf:
                                    cf = float(detection.conf)
                                    cn = model.names.get(cid, f"class_{cid}")
                                    lbl = f"{cn}: {cf:.2f}" if (show_labels and show_conf) else (cn if show_labels else f"{cf:.2f}")
                                    (tw, th), _ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                                    cv2.rectangle(img, (x1, y1 - th - 10), (x1 + tw, y1), color, -1)
                                    cv2.putText(img, lbl, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                        out_path = os.path.join(output_dir, f"{stem}_annotated.jpg")
                        c = 1
                        while os.path.exists(out_path):
                            out_path = os.path.join(output_dir, f"{stem}_annotated_{c}.jpg")
                            c += 1
                        cv2.imwrite(out_path, img)
                        safe_print(f"  ✓ Annotated image saved: {os.path.basename(out_path)}")
                except Exception as e:
                    safe_print(f"  ✗ Failed to save annotated image: {e}")
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            safe_print(f"  ✓ Detection: {abnormal_count} abnormal, {normal_count} normal")
            successful += 1
            out_abs = os.path.abspath(output_dir)
            print(json.dumps({
                "processed": index + 1, "total": total_files, "current_file": image_path,
                "status": "OK", "abnormal_count": abnormal_count, "normal_count": normal_count,
                "successful": successful, "failed": failed, "output_folder": out_abs
            }), flush=True)
        except Exception as e:
            safe_print(f"  ❌ Error processing {image_file}: {e}")
            failed += 1
            print(json.dumps({
                "processed": index + 1, "total": total_files, "current_file": image_path,
                "status": str(e), "abnormal_count": 0, "normal_count": 0,
                "successful": successful, "failed": failed, "output_folder": None
            }), flush=True)
        if (index + 1) % 5 == 0:
            gc.collect()
            if device == "cuda":
                torch.cuda.empty_cache()
    summary = {
        "done": True, "successful": successful, "failed": failed, "total": total_files,
        "total_abnormal": total_abnormal, "total_normal": total_normal,
    }
    print(json.dumps(summary), flush=True)
    sys.exit(0 if successful > 0 else 1)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--convert":
            convert_mode()
        elif sys.argv[1] == "--infer":
            infer_mode()
        elif sys.argv[1] == "--infer-files":
            infer_files_mode()
        else:
            log_error("Unknown mode. Use --convert, --infer, or --infer-files")
            sys.exit(1)
    else:
        log_error("Usage:")
        log_error("  Conversion: infer_worker.py --convert <input.pt> <output.onnx> <imgsz>")
        log_error("  Inference:  infer_worker.py --infer <folder> <model_path> <config_json>")
        log_error("  Infer files: infer_worker.py --infer-files <files_json> <model_path> <model_name> <config_json>")
        sys.exit(1)
