# Analisis: Full Rust vs Hybrid Python+Rust untuk YOLO Inference

## TL;DR

**Bisa full Rust, tapi ada trade-off:**
- ✅ **ONNX Runtime (ort)** - Paling cepat, perlu convert `.pt` → `.onnx`
- ⚠️ **Candle-rs** - Native Rust, bisa load `.pt`, tapi lebih lambat
- ❌ **Tidak ada** Rust equivalent Ultralytics langsung

## Opsi Rust untuk YOLO

### 1. **ONNX Runtime (ort) - RECOMMENDED** ⭐

**Crates:**
- `ort` - ONNX Runtime binding untuk Rust
- `yolo-rs` - Wrapper khusus YOLO dengan ort
- `usls` - Comprehensive YOLO library (YOLOv5-v13)

**Pros:**
- ✅ **Paling cepat** - ~7ms per image (RTX 3060) vs PyTorch ~5.5ms
- ✅ **Production-ready** - Mature, banyak digunakan
- ✅ **Multi-backend** - CPU, CUDA, TensorRT, CoreML, OpenVINO
- ✅ **Tidak perlu Python** - Full Rust
- ✅ **Ukuran kecil** - Tidak perlu bundle PyTorch

**Cons:**
- ❌ **Perlu convert model** - `.pt` → `.onnx` (sekali saja)
- ❌ **Tidak 100% compatible** - Beberapa ops mungkin tidak support

**Implementasi:**
```rust
// Cargo.toml
[dependencies]
ort = { version = "2", features = ["cuda"] }
image = "0.24"

// infer.rs
use ort::{Session, Value, inputs};
use image::DynamicImage;

pub fn load_yolo_model(onnx_path: &str) -> Session {
    Session::builder()
        .unwrap()
        .with_execution_providers([ort::ExecutionProvider::CUDA(Default::default())])
        .unwrap()
        .commit_from_file(onnx_path)
        .unwrap()
}

pub fn predict(model: &Session, img: DynamicImage, imgsz: u32) -> Vec<Detection> {
    // Preprocess image
    let input = preprocess_image(img, imgsz);
    
    // Run inference
    let outputs = model.run(inputs!["images" => input]?).unwrap();
    
    // Post-process (NMS, filter by conf)
    post_process(outputs, conf_threshold, iou_threshold)
}
```

**Model Conversion:**
```python
# Convert sekali saja
from ultralytics import YOLO
model = YOLO("yolov8n-pokok-kuning.pt")
model.export(format="onnx", imgsz=1280, simplify=True)
# Output: yolov8n-pokok-kuning.onnx
```

---

### 2. **Candle-rs (Hugging Face)** 

**Crates:**
- `candle-core`, `candle-nn` - ML framework
- `candle-transformers` - Pre-trained models

**Pros:**
- ✅ **Native Rust** - No external dependencies
- ✅ **Bisa load .pt** - Langsung dari PyTorch format (via SafeTensors)
- ✅ **WASM support** - Bisa run di browser
- ✅ **No conversion needed** - Pakai model langsung

**Cons:**
- ❌ **Lebih lambat** - ~55ms vs ~7ms (ONNX) atau ~5.5ms (PyTorch)
- ❌ **Limited ops** - Tidak semua PyTorch ops support
- ❌ **Less mature** - Masih development
- ❌ **CUDA support terbatas** - Performance gap besar

**Implementasi:**
```rust
// Cargo.toml
[dependencies]
candle-core = "0.5"
candle-nn = "0.5"
candle-transformers = "0.5"

// infer.rs
use candle_core::{Device, Tensor};
use candle_nn::VarBuilder;

pub fn load_yolo_model(pt_path: &str) -> YOLO {
    let device = Device::Cuda(0);
    let vb = VarBuilder::from_pth(pt_path, DType::F32, &device)?;
    // Load model architecture + weights
}
```

---

### 3. **yolo-rust-ort** (Community)

**Crates:**
- `yolo-rust-ort` - YOLOv8/v10 dengan ONNX

**Pros:**
- ✅ Simple API
- ✅ ONNX-based (cepat)

**Cons:**
- ❌ Less maintained
- ❌ Limited to YOLOv8/v10

---

## Perbandingan Performance

| Solution | Inference Time (RTX 3060) | Model Format | CUDA Support | Maturity |
|----------|---------------------------|--------------|--------------|----------|
| **PyTorch (current)** | ~5.5ms | `.pt` | ✅ Excellent | ✅ Mature |
| **ONNX Runtime (ort)** | ~7ms | `.onnx` | ✅ Excellent | ✅ Mature |
| **Candle-rs** | ~55ms | `.pt` / SafeTensors | ⚠️ Limited | ⚠️ Beta |
| **Python sidecar** | ~5.5ms + overhead | `.pt` | ✅ Excellent | ✅ Mature |

---

## Rekomendasi

### **Opsi A: Full Rust dengan ONNX** ⭐ RECOMMENDED

**Alasan:**
1. Performance hampir sama dengan PyTorch (~7ms vs ~5.5ms)
2. Tidak perlu Python dependency
3. Ukuran bundle lebih kecil
4. Production-ready

**Workflow:**
1. Convert model `.pt` → `.onnx` (sekali, saat add model)
2. Bundle `.onnx` file (lebih kecil dari PyTorch)
3. Rust load `.onnx` dengan `ort`
4. Inference langsung di Rust

**Effort:**
- Medium (2-3 hari)
- Perlu implementasi preprocess/postprocess
- Perlu NMS (Non-Max Suppression) manual

---

### **Opsi B: Tetap Hybrid (Current)**

**Alasan:**
1. Sudah working
2. Tidak perlu convert model
3. Compatible 100% dengan Ultralytics
4. Easy maintenance

**Trade-off:**
- Perlu bundle Python sidecar (~200-500 MB)
- Atau require Python di system

---

### **Opsi C: Candle-rs (Full Rust, Native)**

**Alasan:**
1. True native Rust
2. Bisa load `.pt` langsung

**Trade-off:**
- **10x lebih lambat** (55ms vs 5.5ms)
- Less mature
- Limited CUDA support

**Tidak direkomendasikan** untuk production karena performance gap terlalu besar.

---

## Implementasi Full Rust dengan ONNX

### Step 1: Model Conversion

```python
# Conversion via sidecar Python worker
# python_ai/infer_worker.py --convert model.pt model.onnx 1280
# Atau otomatis saat add model via UI
```

### Step 2: Rust Implementation

```rust
// src-tauri/Cargo.toml
[dependencies]
ort = { version = "2", features = ["cuda"] }
image = "0.24"
ndarray = "0.15"

// src-tauri/src/infer.rs
use ort::{Session, Value, inputs};
use image::DynamicImage;

pub struct YOLOInference {
    session: Session,
    imgsz: u32,
}

impl YOLOInference {
    pub fn new(onnx_path: &str, imgsz: u32) -> Result<Self> {
        let session = Session::builder()
            .unwrap()
            .with_execution_providers([
                ort::ExecutionProvider::CUDA(Default::default()),
                ort::ExecutionProvider::CPU(Default::default()),
            ])
            .unwrap()
            .commit_from_file(onnx_path)?;
        
        Ok(Self { session, imgsz })
    }
    
    pub fn predict(&self, img: DynamicImage, conf: f32, iou: f32) -> Vec<Detection> {
        // 1. Preprocess
        let input_tensor = self.preprocess(img);
        
        // 2. Inference
        let outputs = self.session.run(inputs!["images" => input_tensor]?)?;
        
        // 3. Post-process (NMS, filter)
        self.post_process(outputs, conf, iou)
    }
    
    fn preprocess(&self, img: DynamicImage) -> Tensor {
        // Resize, normalize, convert to tensor
        // Similar to Ultralytics preprocessing
    }
    
    fn post_process(&self, outputs: Value, conf: f32, iou: f32) -> Vec<Detection> {
        // Extract boxes, apply NMS, filter by confidence
    }
}
```

### Step 3: Update Model Library

```rust
// Saat add model, auto-convert ke ONNX
pub fn add_model(pt_path: &str) -> Result<Model> {
    // 1. Copy .pt ke models/
    // 2. Convert .pt -> .onnx
    // 3. Save both (atau hanya .onnx)
    // 4. Insert ke DB
}
```

---

## Kesimpulan

### **Untuk Production: ONNX Runtime (ort)** ⭐

**Pros:**
- ✅ Full Rust, no Python
- ✅ Performance excellent (~7ms)
- ✅ Bundle size kecil
- ✅ Production-ready

**Cons:**
- ⚠️ Perlu convert model (sekali)
- ⚠️ Perlu implementasi preprocess/postprocess

### **Untuk Development: Tetap Hybrid**

**Pros:**
- ✅ Sudah working
- ✅ Tidak perlu convert
- ✅ Compatible 100%

**Cons:**
- ❌ Perlu Python/sidecar
- ❌ Bundle size besar

---

## Next Steps (Jika mau full Rust)

1. **Implementasi ONNX inference** (2-3 hari)
   - Preprocess image
   - Post-process dengan NMS
   - CUDA support

2. **Model conversion** (1 hari)
   - Auto-convert saat add model
   - Store .onnx di models/

3. **Testing** (1 hari)
   - Compare dengan PyTorch
   - Verify accuracy

**Total effort: ~1 minggu**

Apakah mau saya implementasikan full Rust dengan ONNX?
