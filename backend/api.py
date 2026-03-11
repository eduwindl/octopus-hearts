from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database.db import SessionLocal, get_engine, Base
from database import models
from backend import schemas
from backend.security import encrypt_token, decrypt_token
from backend.backup_engine import run_backup_for_all, run_backup_for_center, run_backup_by_tag
from backend.fortigate_client import restore_config, restore_config_with_credentials
from backend.config import settings
from backend.auth import ensure_admin_user, authenticate_user, hash_password
from storage.file_manager import ensure_center_dir
from pathlib import Path
import os
import difflib
import secrets


app = FastAPI(title="FortiGate Backup Manager")
security = HTTPBasic()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"] ,
    allow_headers=["*"] ,
)

import sys

def _find_static_dir():
    """Find the frontend/dashboard static directory, checking multiple locations."""
    # 1. Explicit env var (set by desktop_app.py)
    env_dir = os.getenv("FGBM_STATIC_DIR")
    if env_dir and Path(env_dir).exists():
        return Path(env_dir)
    # 2. PyInstaller bundle directory (_MEIPASS)
    if getattr(sys, "frozen", False):
        meipass = Path(sys._MEIPASS) / "frontend" / "dashboard"
        if meipass.exists():
            return meipass
    # 3. Relative to source file (dev mode)
    src = Path(__file__).resolve().parent.parent / "frontend" / "dashboard"
    if src.exists():
        return src
    return None

_static = _find_static_dir()
if _static:
    app.mount("/ui", StaticFiles(directory=_static, html=True), name="ui")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_auth(
    credentials: HTTPBasicCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> models.User | None:
    if not settings.auth_enabled:
        return None
    user = authenticate_user(db, credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user


def require_admin(user: models.User = Depends(require_auth)) -> models.User:
    if user is None or user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=get_engine())
    db = SessionLocal()
    try:
        ensure_admin_user(db)
    finally:
        db.close()


@app.get("/")
def root():
    if _static and (_static / "index.html").exists():
        return FileResponse(_static / "index.html")
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok"}


# ═══════════════════════════════════════════
# Users
# ═══════════════════════════════════════════

@app.post("/users", response_model=schemas.UserOut, dependencies=[Depends(require_admin)])
def create_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    user = models.User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/users", response_model=list[schemas.UserOut], dependencies=[Depends(require_admin)])
def list_users(db: Session = Depends(get_db)):
    return db.query(models.User).order_by(models.User.created_at.desc()).all()


@app.put("/users/{user_id}/disable", response_model=schemas.UserOut, dependencies=[Depends(require_admin)])
def disable_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.put("/users/{user_id}/password", response_model=schemas.UserOut)
def update_password(
    user_id: int,
    payload: schemas.PasswordUpdate,
    db: Session = Depends(get_db),
    current: models.User = Depends(require_auth),
):
    if current.role != "admin" and current.id != user_id:
        raise HTTPException(status_code=403, detail="Not allowed")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(require_auth)):
    return user


# ═══════════════════════════════════════════
# Centers
# ═══════════════════════════════════════════

@app.post("/centers", response_model=schemas.CenterOut, dependencies=[Depends(require_auth)])
def create_center(payload: schemas.CenterCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Center).filter(models.Center.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Center name already exists")

    center = models.Center(
        name=payload.name,
        location=payload.location,
        fortigate_ip=payload.fortigate_ip,
        model=payload.model,
        tag=payload.tag,
        auth_mode=payload.auth_mode,
        status="UNKNOWN",
    )

    if payload.auth_mode == "token" and payload.api_token:
        center.api_token_encrypted = encrypt_token(payload.api_token)
    elif payload.auth_mode == "credentials" and payload.fortigate_username and payload.fortigate_password:
        center.fortigate_username = payload.fortigate_username
        center.fortigate_password_encrypted = encrypt_token(payload.fortigate_password)

    db.add(center)
    db.commit()
    db.refresh(center)
    ensure_center_dir(center.name)
    return center


@app.get("/centers", response_model=list[schemas.CenterOut], dependencies=[Depends(require_auth)])
def list_centers(tag: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Center)
    if tag:
        query = query.filter(models.Center.tag == tag)
    return query.all()


@app.get("/centers/{center_id}", response_model=schemas.CenterOut, dependencies=[Depends(require_auth)])
def get_center(center_id: int, db: Session = Depends(get_db)):
    center = db.query(models.Center).filter(models.Center.id == center_id).first()
    if not center:
        raise HTTPException(status_code=404, detail="Center not found")
    return center


@app.put("/centers/{center_id}", response_model=schemas.CenterOut, dependencies=[Depends(require_auth)])
def update_center(center_id: int, payload: schemas.CenterUpdate, db: Session = Depends(get_db)):
    center = db.query(models.Center).filter(models.Center.id == center_id).first()
    if not center:
        raise HTTPException(status_code=404, detail="Center not found")

    if payload.name is not None:
        center.name = payload.name
    if payload.location is not None:
        center.location = payload.location
    if payload.fortigate_ip is not None:
        center.fortigate_ip = payload.fortigate_ip
    if payload.model is not None:
        center.model = payload.model
    if payload.tag is not None:
        center.tag = payload.tag
    if payload.auth_mode is not None:
        center.auth_mode = payload.auth_mode
    if payload.api_token is not None:
        center.api_token_encrypted = encrypt_token(payload.api_token)
    if payload.fortigate_username is not None:
        center.fortigate_username = payload.fortigate_username
    if payload.fortigate_password is not None:
        center.fortigate_password_encrypted = encrypt_token(payload.fortigate_password)

    db.add(center)
    db.commit()
    db.refresh(center)
    return center


@app.delete("/centers/{center_id}", dependencies=[Depends(require_auth)])
def delete_center(center_id: int, db: Session = Depends(get_db)):
    center = db.query(models.Center).filter(models.Center.id == center_id).first()
    if not center:
        raise HTTPException(status_code=404, detail="Center not found")
    db.delete(center)
    db.commit()
    return {"deleted": True}


# ═══════════════════════════════════════════
# Bulk Import
# ═══════════════════════════════════════════

@app.post("/centers/bulk", dependencies=[Depends(require_auth)])
def bulk_import_centers(payload: schemas.BulkImportRequest, db: Session = Depends(get_db)):
    created = 0
    skipped = 0
    errors = []
    for item in payload.centers:
        existing = db.query(models.Center).filter(
            (models.Center.name == item.name) | (models.Center.fortigate_ip == item.fortigate_ip)
        ).first()
        if existing:
            skipped += 1
            continue
        try:
            center = models.Center(
                name=item.name,
                location=item.location,
                fortigate_ip=item.fortigate_ip,
                model=item.model,
                tag=item.tag,
                auth_mode=item.auth_mode,
                status="UNKNOWN",
            )
            if item.auth_mode == "token" and item.api_token:
                center.api_token_encrypted = encrypt_token(item.api_token)
            elif item.auth_mode == "credentials" and item.fortigate_username and item.fortigate_password:
                center.fortigate_username = item.fortigate_username
                center.fortigate_password_encrypted = encrypt_token(item.fortigate_password)

            db.add(center)
            db.commit()
            ensure_center_dir(center.name)
            created += 1
        except Exception as exc:
            db.rollback()
            errors.append({"name": item.name, "error": str(exc)})

    return {"created": created, "skipped": skipped, "errors": errors}


# ═══════════════════════════════════════════
# Tags
# ═══════════════════════════════════════════

@app.get("/tags", dependencies=[Depends(require_auth)])
def list_tags(db: Session = Depends(get_db)):
    """Return available tags and count of centers per tag."""
    from sqlalchemy import func
    results = db.query(models.Center.tag, func.count(models.Center.id)).group_by(models.Center.tag).all()
    return [{"tag": tag or "untagged", "count": count} for tag, count in results]


# ═══════════════════════════════════════════
# Bulk Credential Assignment
# ═══════════════════════════════════════════

class CredentialApplyRequest(schemas.BaseModel):
    auth_mode: str = "credentials"       # "credentials" or "token"
    fortigate_username: str | None = None
    fortigate_password: str | None = None
    api_token: str | None = None
    tag: str | None = None               # apply to all centers with this tag
    center_ids: list[int] | None = None   # or apply to specific center IDs


@app.post("/credentials/apply", dependencies=[Depends(require_admin)])
def apply_credentials(payload: CredentialApplyRequest, db: Session = Depends(get_db)):
    """Apply credentials to all centers matching a tag or specific center IDs."""
    query = db.query(models.Center)
    if payload.tag:
        query = query.filter(models.Center.tag == payload.tag)
    elif payload.center_ids:
        query = query.filter(models.Center.id.in_(payload.center_ids))
    else:
        raise HTTPException(status_code=400, detail="Provide a tag or center_ids")

    centers = query.all()
    if not centers:
        raise HTTPException(status_code=404, detail="No matching centers found")

    updated = 0
    for center in centers:
        center.auth_mode = payload.auth_mode
        if payload.auth_mode == "credentials":
            if payload.fortigate_username:
                center.fortigate_username = payload.fortigate_username
            if payload.fortigate_password:
                center.fortigate_password_encrypted = encrypt_token(payload.fortigate_password)
        elif payload.auth_mode == "token":
            if payload.api_token:
                center.api_token_encrypted = encrypt_token(payload.api_token)
        db.add(center)
        updated += 1

    db.commit()
    return {"updated": updated, "tag": payload.tag, "auth_mode": payload.auth_mode}


# ═══════════════════════════════════════════
# Backups
# ═══════════════════════════════════════════

@app.post("/backups/run", dependencies=[Depends(require_auth)])
def run_backups(db: Session = Depends(get_db)):
    result = run_backup_for_all(db)
    return result


@app.post("/backups/run/{center_id}", dependencies=[Depends(require_auth)])
def run_backup_one(center_id: int, db: Session = Depends(get_db)):
    center = db.query(models.Center).filter(models.Center.id == center_id).first()
    if not center:
        raise HTTPException(status_code=404, detail="Center not found")
    backup = run_backup_for_center(db, center)
    if not backup:
        raise HTTPException(status_code=500, detail="Backup failed")
    return {"backup_id": backup.id}


@app.post("/backups/run-by-tag/{tag}", dependencies=[Depends(require_auth)])
def run_backups_by_tag(tag: str, db: Session = Depends(get_db)):
    result = run_backup_by_tag(db, tag)
    return result


@app.get("/backups", response_model=list[schemas.BackupOut], dependencies=[Depends(require_auth)])
def list_backups(center_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Backup)
    if center_id is not None:
        query = query.filter(models.Backup.center_id == center_id)
    return query.order_by(models.Backup.backup_date.desc()).all()


@app.get("/events", response_model=list[schemas.EventOut], dependencies=[Depends(require_auth)])
def list_events(center_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Event)
    if center_id is not None:
        query = query.filter(models.Event.center_id == center_id)
    return query.order_by(models.Event.timestamp.desc()).all()


@app.post("/restore/{backup_id}", dependencies=[Depends(require_auth)])
def restore_backup(backup_id: int, db: Session = Depends(get_db)):
    backup = db.query(models.Backup).filter(models.Backup.id == backup_id).first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    center = db.query(models.Center).filter(models.Center.id == backup.center_id).first()
    if not center:
        raise HTTPException(status_code=404, detail="Center not found")

    path = Path(backup.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Backup file missing")

    content = path.read_bytes()
    try:
        if center.auth_mode == "credentials" and center.fortigate_username and center.fortigate_password_encrypted:
            password = decrypt_token(center.fortigate_password_encrypted)
            restore_config_with_credentials(center.fortigate_ip, center.fortigate_username, password, content)
        else:
            token = decrypt_token(center.api_token_encrypted)
            restore_config(center.fortigate_ip, token, content)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Restore failed: {exc}") from exc

    return {"restored": True, "file": str(path), "center": center.name}


@app.get("/diff", response_model=schemas.DiffResponse, dependencies=[Depends(require_auth)])
def diff_backups(center_id: int, from_backup_id: int, to_backup_id: int, db: Session = Depends(get_db)):
    from_backup = db.query(models.Backup).filter(models.Backup.id == from_backup_id).first()
    to_backup = db.query(models.Backup).filter(models.Backup.id == to_backup_id).first()
    if not from_backup or not to_backup:
        raise HTTPException(status_code=404, detail="Backup not found")
    if from_backup.center_id != center_id or to_backup.center_id != center_id:
        raise HTTPException(status_code=400, detail="Backups do not belong to center")

    from_text = Path(from_backup.file_path).read_text(errors="ignore").splitlines()
    to_text = Path(to_backup.file_path).read_text(errors="ignore").splitlines()

    diff = "\n".join(difflib.unified_diff(from_text, to_text, fromfile=str(from_backup.file_path), tofile=str(to_backup.file_path)))
    return schemas.DiffResponse(
        center_id=center_id,
        from_backup_id=from_backup_id,
        to_backup_id=to_backup_id,
        diff=diff,
    )
