#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

use tauri::Manager;

struct BackendState {
    child: Mutex<Option<Child>>,
}

fn spawn_backend() -> Result<Child, String> {
    let backend_cmd = std::env::var("TC_SNIPER_BACKEND_CMD").ok();
    if let Some(command) = backend_cmd {
        let mut parts = command.split_whitespace();
        let executable = parts.next().ok_or("TC_SNIPER_BACKEND_CMD is empty")?;
        let args: Vec<String> = parts.map(|part| part.to_string()).collect();
        return Command::new(executable)
            .args(args)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|err| err.to_string());
    }

    #[cfg(debug_assertions)]
    {
        return Command::new("python")
            .args(["..\\run_tc_sniper_api.py"])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|err| err.to_string());
    }

    #[cfg(not(debug_assertions))]
    {
        Command::new("run_tc_sniper_api.exe")
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|err| err.to_string())
    }
}

#[tauri::command]
fn ensure_backend(state: tauri::State<'_, BackendState>) -> Result<(), String> {
    let mut child = state.child.lock().map_err(|_| "Backend lock failed".to_string())?;
    if child.is_none() {
        *child = Some(spawn_backend()?);
    }
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .manage(BackendState {
            child: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![ensure_backend])
        .setup(|app| {
            let window = app.get_webview_window("main").ok_or("Missing main window")?;
            let state = app.state::<BackendState>();
            ensure_backend(state).map_err(|err| -> Box<dyn std::error::Error> { err.into() })?;
            window.emit("backend-started", true)?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
