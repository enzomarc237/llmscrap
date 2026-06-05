use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use tauri::Manager;
use tauri_plugin_shell::ShellExt;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct PreviewLink {
    pub title: String,
    pub url: String,
    #[serde(default)]
    pub section: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ScrapeOptions {
    pub url: String,
    pub output_dir: String,
    pub workers: u32,
    pub timeout: u32,
    pub formats: Vec<String>,
    #[serde(default)]
    pub selected_links: Vec<PreviewLink>,
    #[serde(default)]
    pub allow_external: bool,
    #[serde(default)]
    pub recursive_depth: u32,
    #[serde(default)]
    pub request_delay: f64,
    #[serde(default = "default_user_agent")]
    pub user_agent: String,
    #[serde(default)]
    pub polite: bool,
}

fn default_user_agent() -> String {
    "llmscrap/0.2".into()
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ScrapeResult {
    pub success: bool,
    pub message: String,
    pub artifacts: HashMap<String, String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct PreviewResult {
    pub index_url: String,
    pub errors: Vec<String>,
    pub links: Vec<PreviewLink>,
}

fn cancel_file_path(output_dir: &str) -> PathBuf {
    PathBuf::from(output_dir).join(".cancel")
}

fn write_selected_links_file(output_dir: &str, links: &[PreviewLink]) -> Result<Option<PathBuf>, String> {
    if links.is_empty() {
        return Ok(None);
    }
    let path = PathBuf::from(output_dir).join(".selected_links.json");
    std::fs::create_dir_all(PathBuf::from(output_dir)).map_err(|e| e.to_string())?;
    let payload = serde_json::to_string(links).map_err(|e| e.to_string())?;
    std::fs::write(&path, payload).map_err(|e| e.to_string())?;
    Ok(Some(path))
}

async fn execute_scraper(
    app: &tauri::AppHandle,
    cli_args: &[String],
) -> Result<(bool, String, String), String> {
    let output = if let Ok(sidecar_cmd) = app.shell().sidecar("llmscrap-cli") {
        sidecar_cmd
            .args(cli_args)
            .output()
            .await
            .map_err(|e| e.to_string())?
    } else {
        let python = resolve_python(app)?;
        let mut python_args = vec!["-m".into(), "llmscrap".into()];
        python_args.extend(cli_args.iter().cloned());

        let mut command = app.shell().command(&python);
        if let Some(py_root) = resolve_python_module_root(app) {
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

    let success = output.status.success();
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    Ok((success, stdout, stderr))
}

fn parse_artifacts(stdout: &str) -> HashMap<String, String> {
    let mut artifacts = HashMap::new();
    for line in stdout.lines() {
        let trimmed = line.trim_start();
        if !trimmed.starts_with("[>]") {
            continue;
        }
        let parts: Vec<&str> = trimmed.splitn(2, ':').collect();
        if parts.len() != 2 {
            continue;
        }
        let key = parts[0]
            .trim_start_matches("[>]")
            .split_whitespace()
            .next()
            .unwrap_or_default()
            .to_string();
        let value = parts[1].trim().to_string();
        if !key.is_empty() && !value.is_empty() {
            artifacts.insert(key, value);
        }
    }
    artifacts
}

fn append_common_args(cli_args: &mut Vec<String>, opts: &ScrapeOptions) {
    cli_args.extend(vec![
        opts.url.clone(),
        "-o".into(),
        opts.output_dir.clone(),
        "--workers".into(),
        opts.workers.to_string(),
        "--timeout".into(),
        opts.timeout.to_string(),
        "--recursive-depth".into(),
        opts.recursive_depth.to_string(),
        "--request-delay".into(),
        opts.request_delay.to_string(),
        "--user-agent".into(),
        opts.user_agent.clone(),
    ]);

    if opts.allow_external {
        cli_args.push("--allow-external".into());
    }
    if opts.polite {
        cli_args.push("--polite".into());
    }
    for fmt in &opts.formats {
        cli_args.push("--format".into());
        cli_args.push(fmt.clone());
    }
}

/// Preview links from an index URL before downloading.
#[tauri::command]
async fn preview_index(app: tauri::AppHandle, opts: ScrapeOptions) -> Result<PreviewResult, String> {
    let mut cli_args = Vec::<String>::new();
    append_common_args(&mut cli_args, &opts);
    cli_args.push("--preview-json".into());

    let (success, stdout, stderr) = execute_scraper(&app, &cli_args).await?;
    let output = if success { stdout } else { format!("{stdout}\n{stderr}") };
    serde_json::from_str::<PreviewResult>(output.trim()).map_err(|e| format!("Failed to parse preview output: {e}. Raw: {output}"))
}

/// Invoke the bundled Python CLI to scrape an index URL.
#[tauri::command]
async fn scrape_index(app: tauri::AppHandle, opts: ScrapeOptions) -> Result<ScrapeResult, String> {
    let cancel_file = cancel_file_path(&opts.output_dir);
    if cancel_file.exists() {
        let _ = std::fs::remove_file(&cancel_file);
    }

    let mut cli_args = Vec::<String>::new();
    append_common_args(&mut cli_args, &opts);
    cli_args.push("--cancel-file".into());
    cli_args.push(cancel_file.to_string_lossy().into_owned());

    let links_file = write_selected_links_file(&opts.output_dir, &opts.selected_links)?;
    if let Some(path) = links_file.as_ref() {
        cli_args.push("--links-file".into());
        cli_args.push(path.to_string_lossy().into_owned());
    }

    let (success, stdout, stderr) = execute_scraper(&app, &cli_args).await?;

    if let Some(path) = links_file {
        let _ = std::fs::remove_file(path);
    }

    if success {
        Ok(ScrapeResult {
            success: true,
            message: stdout.clone(),
            artifacts: parse_artifacts(&stdout),
        })
    } else {
        Err(format!("{stdout}\n{stderr}").trim().to_string())
    }
}

#[tauri::command]
async fn retry_failed(app: tauri::AppHandle, opts: ScrapeOptions, manifest_path: String) -> Result<ScrapeResult, String> {
    let cancel_file = cancel_file_path(&opts.output_dir);
    if cancel_file.exists() {
        let _ = std::fs::remove_file(&cancel_file);
    }

    let mut cli_args = Vec::<String>::new();
    append_common_args(&mut cli_args, &opts);
    cli_args.push("--retry-failed-from".into());
    cli_args.push(manifest_path);
    cli_args.push("--cancel-file".into());
    cli_args.push(cancel_file.to_string_lossy().into_owned());

    let (success, stdout, stderr) = execute_scraper(&app, &cli_args).await?;

    if success {
        Ok(ScrapeResult {
            success: true,
            message: stdout.clone(),
            artifacts: parse_artifacts(&stdout),
        })
    } else {
        Err(format!("{stdout}\n{stderr}").trim().to_string())
    }
}

#[tauri::command]
fn cancel_scrape(output_dir: String) -> Result<(), String> {
    let path = cancel_file_path(&output_dir);
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    std::fs::write(path, b"cancel").map_err(|e| e.to_string())
}

/// Read the .progress.json file from an output directory.
#[tauri::command]
fn read_progress(output_dir: String) -> Result<String, String> {
    let path = PathBuf::from(&output_dir).join(".progress.json");
    std::fs::read_to_string(&path).map_err(|e| e.to_string())
}

/// Read a UTF-8 file for local preview.
#[tauri::command]
fn read_text_file(path: String) -> Result<String, String> {
    std::fs::read_to_string(PathBuf::from(path)).map_err(|e| e.to_string())
}

/// Open a file/folder in the system shell.
#[tauri::command]
async fn open_path(app: tauri::AppHandle, path: String) -> Result<(), String> {
    use tauri_plugin_opener::OpenerExt;
    app.opener().open_path(path, None::<&str>).map_err(|e| e.to_string())
}

/// Open folder containing path in system file explorer.
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
            preview_index,
            scrape_index,
            retry_failed,
            cancel_scrape,
            read_progress,
            read_text_file,
            open_path,
            reveal_folder,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
