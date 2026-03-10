from datetime import datetime, timezone
from sqlalchemy.orm import Session
from backend.config import settings
from backend.security import decrypt_token
from backend.fortigate_client import fetch_config
from database import models
from storage.file_manager import write_backup, enforce_retention
from alerts.notifier import notify_failure

def run_backup_for_center(db: Session, center: models.Center) -> models.Backup | None:
    token = decrypt_token(center.api_token_encrypted)
    try:
        content = fetch_config(center.fortigate_ip, token)
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
