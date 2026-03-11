"""FortiGate Backup Manager – Desktop App (pywebview + FastAPI)

Launches a native window with full minimize/maximize/close controls that
renders the premium HTML/CSS/JS dashboard through an embedded FastAPI server.
Everything self-contained, no external dependencies at runtime.
"""

import base64
import secrets
import threading
import logging
import time
import sys
import os
from pathlib import Path

APP_TITLE = "FortiGate Backup Manager"
VERSION = "1.2.0"

# ════════════════════════════════════════════════════════════════════════
# Path helpers
# ════════════════════════════════════════════════════════════════════════

def get_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_bundle_dir() -> Path:
    """Return the directory where PyInstaller extracted bundled data files.
    For frozen apps this is sys._MEIPASS; for dev it's the source root."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
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


def ensure_dirs(storage_dir: Path) -> tuple:
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

    # Critical: tell the API where to find the bundled frontend files
    bundle_dir = get_bundle_dir()
    static_dir = bundle_dir / "frontend" / "dashboard"
    if static_dir.exists():
        os.environ["FGBM_STATIC_DIR"] = str(static_dir)


# ════════════════════════════════════════════════════════════════════════
# API server
# ════════════════════════════════════════════════════════════════════════

def start_api_server(port: int = 8787):
    try:
        # CRITICAL: When PyInstaller builds with console=False, sys.stdout and
        # sys.stderr are None.  Uvicorn's logging formatter calls
        # sys.stderr.isatty() which crashes.  Redirect to devnull first.
        if sys.stdout is None:
            sys.stdout = open(os.devnull, "w")
        if sys.stderr is None:
            sys.stderr = open(os.devnull, "w")

        import uvicorn
        from backend.api import app
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
        )
    except BaseException as e:
        import traceback

        err_path = get_storage_dir(get_app_dir()) / "api-error.log"
        err_path.write_text("API Thread Exception / BaseException:\n" + traceback.format_exc() + f"\nError type: {type(e)}")


def wait_for_api(port: int, timeout: int = 20) -> bool:
    """Block until the API is responding or timeout."""
    import requests
    url = f"http://127.0.0.1:{port}/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


# ════════════════════════════════════════════════════════════════════════
# Scheduler
# ════════════════════════════════════════════════════════════════════════

def start_scheduler():
    from backend.config import settings
    if not settings.scheduler_enabled:
        return None
    from apscheduler.schedulers.background import BackgroundScheduler
    from backend.backup_engine import run_backup_for_all
    from database.db import SessionLocal

    scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)

    def job():
        db = SessionLocal()
        try:
            run_backup_for_all(db)
        finally:
            db.close()

    scheduler.add_job(job, "cron", hour=18, minute=0)
    scheduler.start()
    return scheduler


# ════════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════════

def main():
    # Fix None streams for windowed PyInstaller apps (console=False)
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    log = logging.getLogger("fgbm")

    base_dir = get_app_dir()
    log.info("Base dir: %s", base_dir)

    init_environment(base_dir)

    # Init database
    from database import models  # noqa: F401
    from database.db import SessionLocal, get_engine, Base
    Base.metadata.create_all(bind=get_engine())

    # Ensure admin user
    from backend.auth import ensure_admin_user
    db = SessionLocal()
    try:
        ensure_admin_user(db)
    finally:
        db.close()

    # Start scheduler
    scheduler = start_scheduler()

    # Get free dynamic port
    import socket
    def get_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]
            
    port = get_free_port()
    api_thread = threading.Thread(target=start_api_server, args=(port,), daemon=True)
    api_thread.start()
    log.info("Waiting for API on port %d...", port)

    if not wait_for_api(port):
        log.error("API server failed to start")
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Error", "API server failed to start.\nCheck the log for details.")
        except Exception:
            pass
        return

    log.info("API ready – launching window")

    # Launch webview window
    import webview
    window = webview.create_window(
        APP_TITLE,
        url=f"http://127.0.0.1:{port}/ui/",
        width=1280,
        height=820,
        min_size=(900, 600),
        background_color="#06080f",
        text_select=True,
    )
    webview.start(gui="edgechromium")

    # Cleanup
    if scheduler:
        scheduler.shutdown(wait=False)
    log.info("Application closed")


def run():
    try:
        main()
    except Exception as exc:
        import traceback
        storage_dir = get_storage_dir(get_app_dir())
        storage_dir.mkdir(parents=True, exist_ok=True)
        log_path = storage_dir / "fgbm-error.txt"
        try:
            log_path.write_text(traceback.format_exc())
        except Exception:
            pass
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Fatal error",
                                  f"Application failed to start.\n\n{exc}\n\nLog: {log_path}")
        except Exception:
            pass


if __name__ == "__main__":
    run()
