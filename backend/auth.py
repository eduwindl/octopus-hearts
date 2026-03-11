from passlib.hash import pbkdf2_sha256
from sqlalchemy.orm import Session
from database import models


def hash_password(password: str) -> str:
    return pbkdf2_sha256.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pbkdf2_sha256.verify(password, password_hash)


def ensure_admin_user(db: Session, username: str = "admin", password: str = "changeme") -> models.User:
    existing = db.query(models.User).first()
    if existing:
        return existing

    user = models.User(
        username=username,
        password_hash=hash_password(password),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> models.User | None:
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
