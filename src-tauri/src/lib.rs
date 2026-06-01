use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use tauri::Manager;
use tauri_plugin_shell::ShellExt;

#[derive(Debug, Serialize, Deserialize)]
pub struct ScrapeOptions {
    pub url: String,
    pub output_dir: String,
    pub workers: u32,
    pub timeout: u32,
    pub formats: Vec<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ScrapeResult {
    pub success: bool,
    pub message: String,
    pub artifacts: std::collections::HashMap<String, String>,
}

/// Invoke the bundled Python CLI to scrape an index URL.
#[tauri::command]
async fn scrape_index(app: tauri::AppHandle, opts: ScrapeOptions) -> Result<ScrapeResult, String> {
    let formats: Vec<String> = opts.formats.iter().flat_map(|f| vec!["--format".into(), f.clone()]).collect();

    let mut cli_args = vec![
        opts.url.clone(),
        "-o".into(), opts.output_dir.clone(),
        "--workers".into(), opts.workers.to_string(),
        "--timeout".into(), opts.timeout.to_string(),
    ];
    cli_args.extend(formats);

    let output = if let Ok(sidecar_cmd) = app.shell().sidecar("llmscrap-cli") {
        sidecar_cmd
            .args(&cli_args)
            .output()
            .await
            .map_err(|e| e.to_string())?
    } else {
        let python = resolve_python(&app)?;
        let mut python_args = vec!["-m".into(), "llmscrap".into()];
        python_args.extend(cli_args);

        let mut command = app.shell().command(&python);
        if let Some(py_root) = resolve_python_module_root(&app) {
            let py_root = py_root.to_string_lossy().into_owned();
            let pythonpath = match std::env::var("PYTHONPATH") {
                Ok(existing) if !existing.trim().is_empty() => format!("{py_root};{existing}"),
                _ => py_root,
            };
            command = command.env("PYTHONPATH", pythonpath);
        }

        command
            .args(&python_args)
            .output()
            .await
            .map_err(|e| e.to_string())?
    };

    if output.status.success() {
        let stdout = String::from_utf8_lossy(&output.stdout).to_string();
        // Parse simple artifact paths from stdout lines like "[>]  json  : path"
        let mut artifacts = std::collections::HashMap::new();
        for line in stdout.lines() {
            if line.trim_start().starts_with("[>]") {
                let parts: Vec<&str> = line.splitn(2, ':').collect();
                if parts.len() == 2 {
                    let key = parts[0].replace("[>]", "").trim().to_string();
                    let val = parts[1].trim().to_string();
                    artifacts.insert(key, val);
                }
            }
        }
        Ok(ScrapeResult { success: true, message: stdout, artifacts })
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        Err(stderr)
    }
}

/// Read the .progress.json file from an output directory.
#[tauri::command]
fn read_progress(output_dir: String) -> Result<String, String> {
    let path = PathBuf::from(&output_dir).join(".progress.json");
    std::fs::read_to_string(&path).map_err(|e| e.to_string())
}

/// Open a folder in the system file explorer.
#[tauri::command]
async fn reveal_folder(app: tauri::AppHandle, path: String) -> Result<(), String> {
    use tauri_plugin_opener::OpenerExt;
    app.opener().reveal_item_in_dir(&path).map_err(|e| e.to_string())
}

/// Resolve path to Python interpreter (bundled resource or system fallback).
fn resolve_python(app: &tauri::AppHandle) -> Result<String, String> {
    // Try bundled sidecar first
    let resource_path = app
        .path()
        .resource_dir()
        .map(|p| p.join("llmscrap-cli"))
        .ok();

    if let Some(p) = resource_path {
        if p.exists() {
            return Ok(p.to_string_lossy().into_owned());
        }
    }

    // Fall back to system Python
    Ok("python".into())
}

/// Resolve the local folder that contains the `llmscrap` Python package.
fn resolve_python_module_root(app: &tauri::AppHandle) -> Option<PathBuf> {
    let mut candidates = Vec::new();

    if let Ok(cwd) = std::env::current_dir() {
        candidates.push(cwd.join("python"));
    }

    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            candidates.push(dir.join("..").join("..").join("..").join("python"));
            candidates.push(
                dir.join("..")
                    .join("..")
                    .join("..")
                    .join("..")
                    .join("python"),
            );
        }
    }

    if let Ok(resource_dir) = app.path().resource_dir() {
        candidates.push(resource_dir.join("python"));
    }

    candidates.into_iter().find(|candidate| {
        candidate
            .join("llmscrap")
            .join("__main__.py")
            .exists()
    })
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .invoke_handler(tauri::generate_handler![
            scrape_index,
            read_progress,
            reveal_folder,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
