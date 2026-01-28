//! Draw bounding boxes on images and save to annotated folder.

use crate::geo::Detection;
use imageproc::drawing::draw_hollow_rect_mut;
use imageproc::rect::Rect;
use std::path::Path;

fn class_color(class_id: i64) -> image::Rgb<u8> {
    let (r, g, b) = match class_id {
        0 => (255, 0, 0),     // red – abnormal
        1 => (0, 255, 0),     // green – normal
        2 => (0, 0, 255),     // blue
        3 => (0, 255, 255),   // cyan
        4 => (255, 0, 255),   // magenta
        5 => (255, 255, 0),   // yellow
        _ => (128, 128, 128), // gray
    };
    image::Rgb([r, g, b])
}

/// Load image, draw detections as rectangles, save to `annotated_folder/<stem>_annotated.jpg`.
/// Note: Annotated images sekarang disimpan oleh Python sidecar, fungsi ini tidak digunakan lagi.
/// Tapi tetap dipertahankan untuk backward compatibility.
pub fn save_annotated(
    image_path: &Path,
    detections: &[Detection],
    annotated_folder: &Path,
    line_width: u32,
) -> Result<std::path::PathBuf, Box<dyn std::error::Error + Send + Sync>> {
    // Load image dengan standard image::open (Python sidecar sudah handle TIFF conversion)
    let img = image::open(image_path)
        .map_err(|e| format!("open image {}: {}", image_path.display(), e))?
        .to_rgb8();
    let (w, h) = (img.width(), img.height());
    let mut im = img;

    for d in detections {
        let x1 = d.x1.round() as i32;
        let y1 = d.y1.round() as i32;
        let x2 = d.x2.round() as i32;
        let y2 = d.y2.round() as i32;
        let x_min = x1.min(x2).max(0).min(w as i32);
        let y_min = y1.min(y2).max(0).min(h as i32);
        let x_max = x1.max(x2).max(0).min(w as i32);
        let y_max = y1.max(y2).max(0).min(h as i32);
        let rw = (x_max - x_min).max(1) as u32;
        let rh = (y_max - y_min).max(1) as u32;
        let rect = Rect::at(x_min, y_min).of_size(rw, rh);
        let color = class_color(d.class_id);
        draw_hollow_rect_mut(&mut im, rect, color);
        for t in 1..(line_width as i32).min(rw as i32 / 2).min(rh as i32 / 2) {
            let rw2 = rw.saturating_sub(2 * t as u32).max(1);
            let rh2 = rh.saturating_sub(2 * t as u32).max(1);
            let inner = Rect::at(x_min + t, y_min + t).of_size(rw2, rh2);
            draw_hollow_rect_mut(&mut im, inner, color);
        }
    }

    std::fs::create_dir_all(annotated_folder)?;
    let stem = image_path
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("image");
    let mut out = annotated_folder.join(format!("{}_annotated.jpg", stem));
    let mut n = 0u32;
    while out.exists() {
        n += 1;
        out = annotated_folder.join(format!("{}_annotated_{}.jpg", stem, n));
    }
    im.save(&out)?;
    Ok(out)
}
