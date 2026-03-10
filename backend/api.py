from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
from database.db import SessionLocal, get_engine, Base
from database import models
from backend import schemas
from backend.security import encrypt_token, decrypt_token
from backend.backup_engine import run_backup_for_all, run_backup_for_center
from backend.fortigate_client import restore_config
from backend.config import settings
from backend.auth import ensure_admin_user, authenticate_user, hash_password
from storage.file_manager import ensure_center_dir
from pathlib import Path
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


@app.get("/health")
def health():
    return {"status": "ok"}


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


@app.post("/centers", response_model=schemas.CenterOut, dependencies=[Depends(require_auth)])
def create_center(payload: schemas.CenterCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Center).filter(models.Center.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Center name already exists")

    center = models.Center(
        name=payload.name,
        location=payload.location,
        fortigate_ip=payload.fortigate_ip,
        api_token_encrypted=encrypt_token(payload.api_token),
        model=payload.model,
        status="UNKNOWN",
    )
    db.add(center)
    db.commit()
    db.refresh(center)
    ensure_center_dir(center.name)
    return center


@app.get("/centers", response_model=list[schemas.CenterOut], dependencies=[Depends(require_auth)])
def list_centers(db: Session = Depends(get_db)):
    return db.query(models.Center).all()


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
    if payload.api_token is not None:
        center.api_token_encrypted = encrypt_token(payload.api_token)

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

    token = decrypt_token(center.api_token_encrypted)
    content = path.read_bytes()
    try:
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
