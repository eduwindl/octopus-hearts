import hashlib
from pathlib import Path
from datetime import datetime, timezone
from backend.config import settings


def ensure_center_dir(center_name: str) -> Path:
    safe_name = center_name.strip().lower().replace(" ", "-")
    center_dir = Path(settings.backups_root) / safe_name
    center_dir.mkdir(parents=True, exist_ok=True)
    return center_dir


def write_backup(center_name: str, content: bytes) -> tuple[Path, str, int]:
    center_dir = ensure_center_dir(center_name)
    filename = f"{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M%S')}.conf"
    file_path = center_dir / filename
    file_path.write_bytes(content)
    checksum = hashlib.sha256(content).hexdigest()
    size = len(content)
    return file_path, checksum, size


def list_backups(center_name: str) -> list[Path]:
    center_dir = ensure_center_dir(center_name)
    return sorted(center_dir.glob("*.conf"), key=lambda p: p.name, reverse=True)


def enforce_retention(center_name: str) -> list[Path]:
    backups = list_backups(center_name)
    removed: list[Path] = []
    for path in backups[settings.retention_count:]:
        path.unlink(missing_ok=True)
        removed.append(path)
    return removed
