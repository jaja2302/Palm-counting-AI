//! SQLite config and YOLO model library.

use rusqlite::Connection;
use std::path::{Path, PathBuf};

fn app_dir() -> PathBuf {
    dirs::data_local_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("palm-counting-ai")
}

fn db_path() -> PathBuf {
    app_dir().join("database.db")
}

fn models_dir() -> PathBuf {
    app_dir().join("models")
}

fn open_db() -> Result<Connection, rusqlite::Error> {
    let p = db_path();
    std::fs::create_dir_all(p.parent().unwrap()).ok();
    let conn = Connection::open(&p)?;
    conn.execute_batch("PRAGMA foreign_keys = ON;")?;
    Ok(conn)
}

pub fn setup_db() -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let conn = open_db()?;
    conn.execute(
        r#"
        CREATE TABLE IF NOT EXISTS configuration (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model TEXT,
            imgsz TEXT,
            iou TEXT,
            conf TEXT,
            convert_shp TEXT,
            convert_kml TEXT,
            max_det TEXT,
            line_width TEXT,
            show_labels TEXT,
            show_conf TEXT,
            status_blok TEXT,
            save_annotated TEXT,
            last_folder_path TEXT,
            device TEXT,
            active_model_id INTEGER
        )
        "#,
        [],
    )?;

    conn.execute(
        r#"
        CREATE TABLE IF NOT EXISTS yolo_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            path TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
        "#,
        [],
    )?;

    conn.execute(
        r#"
        CREATE TABLE IF NOT EXISTS tiff_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
        "#,
        [],
    )?;

    // Add columns if missing (migrations)
    let add_col = |name: &str, sql: &str| -> Result<(), rusqlite::Error> {
        let exists: bool = conn.query_row(
            "SELECT COUNT(1) FROM pragma_table_info('configuration') WHERE name = ?1",
            [name],
            |r| r.get(0),
        )?;
        if !exists {
            conn.execute(sql, [])?;
        }
        Ok(())
    };
    add_col("device", "ALTER TABLE configuration ADD COLUMN device TEXT DEFAULT 'auto'")?;
    add_col("active_model_id", "ALTER TABLE configuration ADD COLUMN active_model_id INTEGER")?;

    let count: i64 = conn.query_row("SELECT COUNT(*) FROM configuration", [], |r| r.get(0))?;
    if count == 0 {
        conn.execute(
            r#"
            INSERT INTO configuration (
                model, imgsz, iou, conf, convert_shp, convert_kml,
                max_det, line_width, show_labels, show_conf, status_blok, save_annotated,
                last_folder_path, device, active_model_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            "#,
            rusqlite::params![
                "",
                "12800",
                "0.2",
                "0.2",
                "true",
                "false",
                "10000",
                "3",
                "true",
                "false",
                "Full Blok",
                "true",
                None::<String>,
                "auto",
                None::<i64>,
            ],
        )?;
    }
    Ok(())
}

#[derive(Debug, serde::Serialize, serde::Deserialize)]
pub struct AppConfig {
    pub model: Option<String>,
    pub imgsz: String,
    pub iou: String,
    pub conf: String,
    pub convert_shp: String,
    pub convert_kml: String,
    pub max_det: String,
    pub line_width: String,
    pub show_labels: String,
    pub show_conf: String,
    pub status_blok: String,
    pub save_annotated: String,
    pub last_folder_path: Option<String>,
    pub device: String,
    pub active_model_id: Option<i64>,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            model: None,
            imgsz: "12800".into(),
            iou: "0.2".into(),
            conf: "0.2".into(),
            convert_shp: "true".into(),
            convert_kml: "false".into(),
            max_det: "10000".into(),
            line_width: "3".into(),
            show_labels: "true".into(),
            show_conf: "false".into(),
            status_blok: "Full Blok".into(),
            save_annotated: "true".into(),
            last_folder_path: None,
            device: "auto".into(),
            active_model_id: None,
        }
    }
}

pub fn load_config() -> Result<AppConfig, Box<dyn std::error::Error + Send + Sync>> {
    setup_db()?;
    let conn = open_db()?;
    let mut stmt = conn.prepare(
        "SELECT model, imgsz, iou, conf, convert_shp, convert_kml, max_det, line_width,
                show_labels, show_conf, status_blok, save_annotated, last_folder_path, device, active_model_id
         FROM configuration ORDER BY id DESC LIMIT 1",
    )?;
    let row = stmt.query_row([], |r| {
        Ok(AppConfig {
            model: r.get(0).ok(),
            imgsz: r.get::<_, String>(1).unwrap_or_else(|_| "12800".into()),
            iou: r.get::<_, String>(2).unwrap_or_else(|_| "0.2".into()),
            conf: r.get::<_, String>(3).unwrap_or_else(|_| "0.2".into()),
            convert_shp: r.get::<_, String>(4).unwrap_or_else(|_| "true".into()),
            convert_kml: r.get::<_, String>(5).unwrap_or_else(|_| "false".into()),
            max_det: r.get::<_, String>(6).unwrap_or_else(|_| "10000".into()),
            line_width: r.get::<_, String>(7).unwrap_or_else(|_| "3".into()),
            show_labels: r.get::<_, String>(8).unwrap_or_else(|_| "true".into()),
            show_conf: r.get::<_, String>(9).unwrap_or_else(|_| "false".into()),
            status_blok: r.get::<_, String>(10).unwrap_or_else(|_| "Full Blok".into()),
            save_annotated: r.get::<_, String>(11).unwrap_or_else(|_| "true".into()),
            last_folder_path: r.get(12).ok(),
            device: r.get::<_, String>(13).unwrap_or_else(|_| "auto".into()),
            active_model_id: r.get(14).ok(),
        })
    });

    match row {
        Ok(c) => Ok(c),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(AppConfig::default()),
        Err(e) => Err(e.into()),
    }
}

pub fn save_config(c: &AppConfig) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    setup_db()?;
    let conn = open_db()?;
    conn.execute(
        r#"
        INSERT INTO configuration (
            model, imgsz, iou, conf, convert_shp, convert_kml,
            max_det, line_width, show_labels, show_conf, status_blok, save_annotated,
            last_folder_path, device, active_model_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        "#,
        rusqlite::params![
            c.model.as_deref().unwrap_or(""),
            &c.imgsz,
            &c.iou,
            &c.conf,
            &c.convert_shp,
            &c.convert_kml,
            &c.max_det,
            &c.line_width,
            &c.show_labels,
            &c.show_conf,
            &c.status_blok,
            &c.save_annotated,
            c.last_folder_path.as_deref(),
            &c.device,
            c.active_model_id,
        ],
    )?;
    Ok(())
}

#[derive(Debug, serde::Serialize)]
pub struct YoloModel {
    pub id: i64,
    pub name: String,
    pub path: String,
    pub is_active: bool,
}

pub fn list_models() -> Result<Vec<YoloModel>, Box<dyn std::error::Error + Send + Sync>> {
    setup_db()?;
    let conn = open_db()?;
    let active: Option<i64> = conn
        .query_row("SELECT active_model_id FROM configuration ORDER BY id DESC LIMIT 1", [], |r| {
            r.get(0)
        })
        .ok()
        .and_then(|x: Option<i64>| x);

    let mut stmt = conn.prepare("SELECT id, name, path FROM yolo_models ORDER BY id")?;
    let rows = stmt.query_map([], |r| {
        let id: i64 = r.get(0)?;
        let name: String = r.get(1)?;
        let path: String = r.get(2)?;
        Ok(YoloModel {
            id,
            name,
            path,
            is_active: active == Some(id),
        })
    })?;
    let out: Result<Vec<_>, _> = rows.collect();
    Ok(out?)
}

pub fn add_model(name: String, source_path: &Path) -> Result<YoloModel, Box<dyn std::error::Error + Send + Sync>> {
    setup_db()?;
    std::fs::create_dir_all(models_dir())?;
    
    // Support .pt dan .onnx langsung (tidak perlu convert)
    // Python sidecar akan handle inference untuk kedua format
    let base = source_path
        .file_name()
        .and_then(|s| s.to_str())
        .unwrap_or("model");
    let dest = models_dir().join(base);
    let dest = unique_path(&dest);
    std::fs::copy(source_path, &dest)?;
    let final_path = dest.to_string_lossy().into_owned();

    let conn = open_db()?;
    conn.execute("INSERT INTO yolo_models (name, path) VALUES (?1, ?2)", [&name, &final_path])?;
    let id = conn.last_insert_rowid();
    let active: Option<i64> = conn
        .query_row("SELECT active_model_id FROM configuration ORDER BY id DESC LIMIT 1", [], |r| {
            r.get(0)
        })
        .ok()
        .and_then(|x: Option<i64>| x);
    Ok(YoloModel {
        id,
        name,
        path: final_path,
        is_active: active == Some(id),
    })
}

fn unique_path(p: &PathBuf) -> PathBuf {
    if !p.exists() {
        return p.clone();
    }
    let stem = p.file_stem().and_then(|s| s.to_str()).unwrap_or("model");
    let ext = p.extension().and_then(|s| s.to_str()).unwrap_or("pt");
    let parent = p.parent().unwrap();
    for n in 1..10000 {
        let candidate = parent.join(format!("{}_{}.{}", stem, n, ext));
        if !candidate.exists() {
            return candidate;
        }
    }
    parent.join(format!("{}_{}.{}", stem, 0, ext))
}

pub fn remove_model(id: i64) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    setup_db()?;
    let conn = open_db()?;
    let path: Option<String> = conn.query_row("SELECT path FROM yolo_models WHERE id = ?1", [id], |r| r.get(0))?;
    conn.execute("DELETE FROM yolo_models WHERE id = ?1", [id])?;
    if let Some(p) = path {
        let _ = std::fs::remove_file(&p);
    }
    Ok(())
}

pub fn set_active_model(id: i64) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let mut c = load_config()?;
    c.active_model_id = Some(id);
    save_config(&c)
}

pub fn get_active_model_path() -> Result<Option<String>, Box<dyn std::error::Error + Send + Sync>> {
    let c = load_config()?;
    let aid = match c.active_model_id {
        Some(x) => x,
        None => return Ok(None),
    };
    let conn = open_db()?;
    let path: Option<String> = conn.query_row("SELECT path FROM yolo_models WHERE id = ?1", [aid], |r| r.get(0))?;
    Ok(path)
}

/// Simpan daftar path TIFF ke SQLite (local). Duplikat di-ignore.
pub fn add_tiff_paths(paths: Vec<String>) -> Result<usize, Box<dyn std::error::Error + Send + Sync>> {
    setup_db()?;
    let conn = open_db()?;
    let mut added = 0_usize;
    for p in paths {
        if p.trim().is_empty() {
            continue;
        }
        match conn.execute("INSERT OR IGNORE INTO tiff_files (path) VALUES (?1)", [&p]) {
            Ok(1) => added += 1,
            _ => {}
        }
    }
    Ok(added)
}

/// Ambil daftar path TIFF dari SQLite (urutan created_at).
pub fn list_tiff_paths() -> Result<Vec<String>, Box<dyn std::error::Error + Send + Sync>> {
    setup_db()?;
    let conn = open_db()?;
    let mut stmt = conn.prepare("SELECT path FROM tiff_files ORDER BY created_at ASC")?;
    let rows = stmt.query_map([], |r| r.get::<_, String>(0))?;
    let out: Result<Vec<_>, _> = rows.collect();
    Ok(out?)
}

/// Hapus satu path TIFF dari daftar.
pub fn remove_tiff_path(path: &str) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    setup_db()?;
    let conn = open_db()?;
    conn.execute("DELETE FROM tiff_files WHERE path = ?1", [path])?;
    Ok(())
}
