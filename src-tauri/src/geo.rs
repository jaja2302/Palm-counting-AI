//! Geospatial operations: GeoJSON, KML, Shapefile generation, TFW parsing.
//! Moved from Python to reduce dependencies.

use serde::{Deserialize, Serialize};
use std::path::Path;

/// Detection result from YOLO inference
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Detection {
    pub x1: f64,
    pub y1: f64,
    pub x2: f64,
    pub y2: f64,
    pub class_id: i64,
    pub conf: f64,
}

/// TFW (World File) parameters for georeferencing
/// Rotation terms (lines 2 and 3) diabaikan karena tidak digunakan.
#[derive(Debug, Clone)]
pub struct TfwParams {
    pub pixel_size_x: f64,
    pub pixel_size_y: f64,
    pub upper_left_x: f64,
    pub upper_left_y: f64,
}

/// Read TFW file and parse parameters
pub fn read_tfw(tfw_path: &Path) -> Result<TfwParams, Box<dyn std::error::Error + Send + Sync>> {
    let content = std::fs::read_to_string(tfw_path)?;
    let lines: Vec<&str> = content.lines().take(6).collect();
    
    if lines.len() < 6 {
        return Err("TFW file must have at least 6 lines".into());
    }
    
    Ok(TfwParams {
        pixel_size_x: lines[0].trim().parse()?,
        // lines[1] dan [2] adalah rotasi, di-skip
        pixel_size_y: lines[3].trim().parse()?,
        upper_left_x: lines[4].trim().parse()?,
        upper_left_y: lines[5].trim().parse()?,
    })
}

/// Convert pixel coordinates to map coordinates using TFW parameters
pub fn pixel_to_map(x: f64, y: f64, tfw: &TfwParams) -> (f64, f64) {
    let map_x = tfw.upper_left_x + x * tfw.pixel_size_x;
    let map_y = tfw.upper_left_y + y * tfw.pixel_size_y;
    (map_x, map_y)
}

/// Generate GeoJSON from detections
pub fn generate_geojson(
    detections: &[Detection],
    class_names: &std::collections::HashMap<i64, String>,
    tfw: &TfwParams,
) -> geojson::FeatureCollection {
    let mut features = Vec::new();
    
    for det in detections {
        let center_x = (det.x1 + det.x2) / 2.0;
        let center_y = (det.y1 + det.y2) / 2.0;
        let (map_x, map_y) = pixel_to_map(center_x, center_y, tfw);
        
        let point = geojson::Geometry::new(geojson::Value::Point(vec![map_x, map_y]));
        let class_name = class_names
            .get(&det.class_id)
            .cloned()
            .unwrap_or_else(|| format!("class_{}", det.class_id));
        
        let mut properties = geojson::JsonObject::new();
        properties.insert("label".to_string(), serde_json::Value::String(class_name));
        properties.insert("confidence".to_string(), serde_json::Value::Number(
            serde_json::Number::from_f64(det.conf).unwrap_or(serde_json::Number::from(0))
        ));
        properties.insert("class_id".to_string(), serde_json::Value::Number(
            serde_json::Number::from(det.class_id)
        ));
        
        features.push(geojson::Feature {
            bbox: None,
            geometry: Some(point),
            id: None,
            properties: Some(properties),
            foreign_members: None,
        });
    }
    
    geojson::FeatureCollection {
        bbox: None,
        features,
        foreign_members: None,
    }
}

/// Save GeoJSON to file with duplicate handling
pub fn save_geojson(
    geojson: &geojson::FeatureCollection,
    output_path: &Path,
) -> Result<std::path::PathBuf, Box<dyn std::error::Error + Send + Sync>> {
    let mut final_path = output_path.to_path_buf();
    let mut counter = 1;
    
    while final_path.exists() {
        let stem = output_path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("output");
        let parent = output_path.parent().unwrap_or(Path::new("."));
        let ext = output_path.extension().and_then(|s| s.to_str()).unwrap_or("geojson");
        final_path = parent.join(format!("{}_{}.{}", stem, counter, ext));
        counter += 1;
    }
    
    let json_string = serde_json::to_string_pretty(geojson)?;
    std::fs::write(&final_path, json_string)?;
    Ok(final_path)
}

/// Generate KML from GeoJSON FeatureCollection (manual XML generation)
pub fn generate_kml(
    geojson: &geojson::FeatureCollection,
    output_path: &Path,
) -> Result<std::path::PathBuf, Box<dyn std::error::Error + Send + Sync>> {
    let mut xml = String::from("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n");
    xml.push_str("<kml xmlns=\"http://www.opengis.net/kml/2.2\">\n");
    xml.push_str("  <Document>\n");
    xml.push_str("    <name>doc name</name>\n");
    xml.push_str("    <description>doc description</description>\n");
    
    for (_idx, feature) in geojson.features.iter().enumerate() {
        if let Some(geom) = &feature.geometry {
            if let geojson::Value::Point(coords) = &geom.value {
                if coords.len() >= 2 {
                    let label = feature
                        .properties
                        .as_ref()
                        .and_then(|p| p.get("label"))
                        .and_then(|v| v.as_str())
                        .unwrap_or("Unnamed");
                    let desc = format!(
                        "Confidence: {:.2}, Class ID: {}",
                        feature
                            .properties
                            .as_ref()
                            .and_then(|p| p.get("confidence"))
                            .and_then(|v| v.as_f64())
                            .unwrap_or(0.0),
                        feature
                            .properties
                            .as_ref()
                            .and_then(|p| p.get("class_id"))
                            .and_then(|v| v.as_i64())
                            .unwrap_or(0)
                    );
                    
                    xml.push_str("    <Placemark>\n");
                    xml.push_str(&format!("      <name>{}</name>\n", escape_xml(label)));
                    xml.push_str(&format!("      <description>{}</description>\n", escape_xml(&desc)));
                    xml.push_str("      <Point>\n");
                    xml.push_str(&format!("        <coordinates>{},{},0</coordinates>\n", coords[0], coords[1]));
                    xml.push_str("      </Point>\n");
                    xml.push_str("    </Placemark>\n");
                }
            }
        }
    }
    
    xml.push_str("  </Document>\n");
    xml.push_str("</kml>\n");
    
    let mut final_path = output_path.to_path_buf();
    let mut counter = 1;
    while final_path.exists() {
        let stem = output_path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("output");
        let parent = output_path.parent().unwrap_or(Path::new("."));
        final_path = parent.join(format!("{}_{}.kml", stem, counter));
        counter += 1;
    }
    
    std::fs::write(&final_path, xml)?;
    Ok(final_path)
}

fn escape_xml(s: &str) -> String {
    s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\"", "&quot;")
        .replace("'", "&apos;")
}

/// Generate Shapefile from GeoJSON FeatureCollection
/// Menghasilkan satu set lengkap file Shapefile: .shp, .shx, .dbf
pub fn generate_shapefile(
    geojson: &geojson::FeatureCollection,
    output_path: &Path,
) -> Result<std::path::PathBuf, Box<dyn std::error::Error + Send + Sync>> {
    use shapefile::dbase::{FieldName, FieldValue, TableWriterBuilder};
    use shapefile::{Point, Writer};

    let base_path = output_path.parent().unwrap_or(Path::new("."));
    let stem = output_path
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("output");

    // Handle duplicates
    let mut shp_path = base_path.join(format!("{}.shp", stem));
    let mut counter = 1;
    while shp_path.exists() {
        shp_path = base_path.join(format!("{}_{}.shp", stem, counter));
        counter += 1;
    }

    // DBF schema: label (text), class_id (numeric), confidence (float)
    let table_builder = TableWriterBuilder::new()
        .add_character_field(FieldName::try_from("label")?, 64)
        .add_numeric_field(FieldName::try_from("class_id")?, 10, 0)
        .add_float_field(FieldName::try_from("confidence")?, 10, 4);

    let mut writer = Writer::from_path(&shp_path, table_builder)?;

    for feature in &geojson.features {
        if let Some(geom) = &feature.geometry {
            if let geojson::Value::Point(coords) = &geom.value {
                if coords.len() >= 2 {
                    let point = Point::new(coords[0], coords[1]);

                    // Ambil properti dari GeoJSON
                    let props = feature.properties.as_ref();
                    let label = props
                        .and_then(|p| p.get("label"))
                        .and_then(|v| v.as_str())
                        .unwrap_or("Unnamed")
                        .to_string();
                    let class_id = props
                        .and_then(|p| p.get("class_id"))
                        .and_then(|v| v.as_i64())
                        .unwrap_or(0);
                    let confidence = props
                        .and_then(|p| p.get("confidence"))
                        .and_then(|v| v.as_f64())
                        .unwrap_or(0.0);

                    // Bangun record DBF
                    let mut record = shapefile::dbase::Record::default();
                    record.insert("label".to_string(), FieldValue::Character(Some(label)));
                    record.insert(
                        "class_id".to_string(),
                        FieldValue::Numeric(Some(class_id as f64)),
                    );
                    record.insert(
                        "confidence".to_string(),
                        FieldValue::Numeric(Some(confidence)),
                    );

                    writer.write_shape_and_record(&point, &record)?;
                }
            }
        }
    }

    // Writer akan menutup dan flush semua file (shp, shx, dbf) saat drop
    Ok(shp_path)
}
