from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database.db import SessionLocal, get_engine, Base
from database import models
from backend import schemas
from backend.security import encrypt_token
from backend.backup_engine import run_backup_for_all, run_backup_for_center
from storage.file_manager import ensure_center_dir
from pathlib import Path
import difflib


app = FastAPI(title="FortiGate Backup Manager")

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


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=get_engine())


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/centers", response_model=schemas.CenterOut)
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


@app.get("/centers", response_model=list[schemas.CenterOut])
def list_centers(db: Session = Depends(get_db)):
    return db.query(models.Center).all()


@app.get("/centers/{center_id}", response_model=schemas.CenterOut)
def get_center(center_id: int, db: Session = Depends(get_db)):
    center = db.query(models.Center).filter(models.Center.id == center_id).first()
    if not center:
        raise HTTPException(status_code=404, detail="Center not found")
    return center


@app.put("/centers/{center_id}", response_model=schemas.CenterOut)
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


@app.delete("/centers/{center_id}")
def delete_center(center_id: int, db: Session = Depends(get_db)):
    center = db.query(models.Center).filter(models.Center.id == center_id).first()
    if not center:
        raise HTTPException(status_code=404, detail="Center not found")
    db.delete(center)
    db.commit()
    return {"deleted": True}


@app.post("/backups/run")
def run_backups(db: Session = Depends(get_db)):
    result = run_backup_for_all(db)
    return result


@app.post("/backups/run/{center_id}")
def run_backup_one(center_id: int, db: Session = Depends(get_db)):
    center = db.query(models.Center).filter(models.Center.id == center_id).first()
    if not center:
        raise HTTPException(status_code=404, detail="Center not found")
    backup = run_backup_for_center(db, center)
    if not backup:
        raise HTTPException(status_code=500, detail="Backup failed")
    return {"backup_id": backup.id}


@app.get("/backups", response_model=list[schemas.BackupOut])
def list_backups(center_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Backup)
    if center_id is not None:
        query = query.filter(models.Backup.center_id == center_id)
    return query.order_by(models.Backup.backup_date.desc()).all()


@app.get("/events", response_model=list[schemas.EventOut])
def list_events(center_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(models.Event)
    if center_id is not None:
        query = query.filter(models.Event.center_id == center_id)
    return query.order_by(models.Event.timestamp.desc()).all()


@app.post("/restore/{backup_id}")
def restore_backup(backup_id: int, db: Session = Depends(get_db)):
    backup = db.query(models.Backup).filter(models.Backup.id == backup_id).first()
    if not backup:
        raise HTTPException(status_code=404, detail="Backup not found")

    path = Path(backup.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Backup file missing")

    # Placeholder: production restore would push config via FortiOS API.
    return {"restored": True, "file": str(path)}


@app.get("/diff", response_model=schemas.DiffResponse)
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
