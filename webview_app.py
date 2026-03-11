import base64
import secrets
import threading
import time
import os
import sys
from pathlib import Path

import requests
import uvicorn
import webview
import tkinter as tk
from tkinter import messagebox


APP_TITLE = "FortiGate Backup Manager"


def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_storage_dir(app_dir: Path) -> Path:
    try:
        test_file = app_dir / ".write_test"
        test_file.write_text("ok")
        test_file.unlink(missing_ok=True)
        return app_dir
    except Exception:
        local_app_data = Path(os.environ.get("LOCALAPPDATA", str(app_dir)))
        return local_app_data / "FGBM"


def ensure_dirs(storage_dir: Path) -> tuple[Path, Path, Path]:
    data_dir = storage_dir / "data"
    backups_dir = storage_dir / "backups"
    data_dir.mkdir(parents=True, exist_ok=True)
    backups_dir.mkdir(parents=True, exist_ok=True)
    return data_dir, backups_dir, data_dir / "secret.key"


def load_or_create_secret(secret_file: Path) -> str:
    if secret_file.exists():
        return secret_file.read_text().strip()
    secret = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
    secret_file.write_text(secret)
    return secret


def init_environment(base_dir: Path) -> None:
    storage_dir = get_storage_dir(base_dir)
    data_dir, backups_dir, secret_file = ensure_dirs(storage_dir)
    secret = load_or_create_secret(secret_file)
    os.environ.setdefault("TOKEN_ENCRYPTION_KEY", secret)
    db_path = data_dir / "fgbm.db"
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    os.environ.setdefault("BACKUPS_ROOT", str(backups_dir))
    os.environ.setdefault("FGBM_STATIC_DIR", str(base_dir / "frontend" / "dashboard"))


def start_api():
    config = uvicorn.Config("backend.api:app", host="127.0.0.1", port=8000, log_level="warning")
    server = uvicorn.Server(config)
    server.run()


def wait_for_api(timeout: int = 20) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            res = requests.get("http://127.0.0.1:8000/health", timeout=1)
            if res.ok:
                return True
        except requests.RequestException:
            time.sleep(0.5)
    return False


def main():
    base_dir = get_app_dir()
    init_environment(base_dir)

    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()

    if not wait_for_api():
        raise RuntimeError("API did not start")

    webview.create_window(APP_TITLE, "http://127.0.0.1:8000/ui", width=1200, height=800)
    webview.start()


def write_log(app_dir: Path, message: str) -> Path:
    try:
        log_path = app_dir / "fgbm-error.txt"
        log_path.write_text(message)
        return log_path
    except Exception:
        storage_dir = get_storage_dir(app_dir)
        storage_dir.mkdir(parents=True, exist_ok=True)
        log_path = storage_dir / "fgbm-error.txt"
        log_path.write_text(message)
        return log_path


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        app_dir = get_app_dir()
        log_path = write_log(app_dir, str(exc))
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Fatal error", f"Application failed to start.\n\nLog: {log_path}")
