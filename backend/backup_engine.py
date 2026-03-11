from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.config import settings
from backend.security import decrypt_token
from backend.fortigate_client import fetch_config, fetch_config_with_credentials
from database import models
from storage.file_manager import write_backup, enforce_retention
from alerts.notifier import notify_failure


def _fetch_for_center(center: models.Center) -> bytes:
    """Fetch config using the appropriate auth mode for the center."""
    if center.auth_mode == "credentials" and center.fortigate_username and center.fortigate_password_encrypted:
        password = decrypt_token(center.fortigate_password_encrypted)
        return fetch_config_with_credentials(center.fortigate_ip, center.fortigate_username, password)
    elif center.api_token_encrypted:
        token = decrypt_token(center.api_token_encrypted)
        return fetch_config(center.fortigate_ip, token)
    else:
        raise ValueError(f"Center '{center.name}' has no valid authentication configured.")


def run_backup_for_center(db: Session, center: models.Center) -> models.Backup | None:
    try:
        content = _fetch_for_center(center)
        file_path, checksum, size = write_backup(center.name, content)

        backup = models.Backup(
            center_id=center.id,
            file_path=str(file_path),
            checksum=checksum,
            size=size,
            status="OK",
        )
        db.add(backup)
        center.last_backup = datetime.now(timezone.utc)
        center.status = "OK"
        db.add(center)

        # Log success event
        event = models.Event(
            center_id=center.id,
            event_type="BACKUP_OK",
            message=f"Backup completed: {checksum[:16]}… ({size} bytes)",
        )
        db.add(event)
        db.commit()

        removed = enforce_retention(center.name)
        for path in removed:
            db.query(models.Backup).filter(models.Backup.file_path == str(path)).delete()
        db.commit()
        return backup
    except Exception as exc:
        center.status = "FAILED"
        db.add(center)
        db.commit()
        notify_failure(center.name, str(exc))
        event = models.Event(center_id=center.id, event_type="BACKUP_FAILED", message=str(exc))
        db.add(event)
        db.commit()
        return None


def run_backup_for_all(db: Session) -> dict[str, int]:
    centers = db.query(models.Center).all()
    ok = 0
    failed = 0
    for center in centers:
        result = run_backup_for_center(db, center)
        if result:
            ok += 1
        else:
            failed += 1
    return {"ok": ok, "failed": failed}


def run_backup_by_tag(db: Session, tag: str) -> dict[str, int]:
    """Run backups for all centers with a specific tag."""
    centers = db.query(models.Center).filter(models.Center.tag == tag).all()
    ok = 0
    failed = 0
    for center in centers:
        result = run_backup_for_center(db, center)
        if result:
            ok += 1
        else:
            failed += 1
    return {"ok": ok, "failed": failed, "tag": tag, "total": len(centers)}
