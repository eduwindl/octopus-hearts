import os
from pathlib import Path
import threading
import webbrowser
import uvicorn


def main():
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data"
    backups_dir = base_dir / "backups"
    data_dir.mkdir(parents=True, exist_ok=True)
    backups_dir.mkdir(parents=True, exist_ok=True)

    static_dir = base_dir / "frontend" / "dashboard"
    os.environ.setdefault("FGBM_STATIC_DIR", str(static_dir))

    os.environ.setdefault("DATABASE_URL", "sqlite:///./data/fgbm.db")
    os.environ.setdefault("BACKUPS_ROOT", "./backups")

    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:8000")).start()
    uvicorn.run("backend.api:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
