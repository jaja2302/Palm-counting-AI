//! Image validation and preprocessing utilities.
//! Moved from Python to reduce dependencies.

use image::GenericImageView;
use std::path::Path;

/// Image validation result
#[derive(Debug, Clone)]
pub struct ImageValidation {
    pub is_valid: bool,
    pub width: u32,
    pub height: u32,
    pub mode: String,
    pub temp_path: Option<std::path::PathBuf>,
}

/// Validate and preprocess image (handles different color modes, converts to RGB)
pub fn validate_and_preprocess_image(
    image_path: &Path,
) -> Result<ImageValidation, Box<dyn std::error::Error + Send + Sync>> {
    use image::DynamicImage;
    
    let img = image::open(image_path)?;
    let (width, height) = (img.width(), img.height());
    
    // Check if already RGB
    if let DynamicImage::ImageRgb8(_) = img {
        return Ok(ImageValidation {
            is_valid: true,
            width,
            height,
            mode: "RGB".to_string(),
            temp_path: None,
        });
    }
    
    // Convert to RGB
    let rgb_img = img.to_rgb8();
    
    // Save temporary RGB image
    let base_name = image_path
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("image");
    let parent = image_path.parent().unwrap_or(Path::new("."));
    let temp_path = parent.join(format!("{}_temp_rgb.jpg", base_name));
    
    rgb_img.save(&temp_path)?;
    
    Ok(ImageValidation {
        is_valid: true,
        width,
        height,
        mode: "RGB".to_string(),
        temp_path: Some(temp_path),
    })
}

/// Cleanup temporary file if it exists
pub fn cleanup_temp_file(temp_path: &Path) {
    if temp_path.exists() {
        let _ = std::fs::remove_file(temp_path);
    }
}
