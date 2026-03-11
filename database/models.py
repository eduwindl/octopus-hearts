from sqlalchemy import String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from database.db import Base


VALID_TAGS = ("minerd", "transi", "unphu", "lanco")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="admin")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Center(Base):
    __tablename__ = "centers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    location: Mapped[str | None] = mapped_column(String(200))
    fortigate_ip: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    api_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    fortigate_username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fortigate_password_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_mode: Mapped[str] = mapped_column(String(20), default="token")  # "token" or "credentials"
    model: Mapped[str | None] = mapped_column(String(100))
    tag: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    last_backup: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(50), default="UNKNOWN")

    backups: Mapped[list["Backup"]] = relationship("Backup", back_populates="center")
    events: Mapped[list["Event"]] = relationship("Event", back_populates="center")


class Backup(Base):
    __tablename__ = "backups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    center_id: Mapped[int] = mapped_column(ForeignKey("centers.id"))
    backup_date: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    file_path: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String(128))
    size: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default="OK")

    center: Mapped[Center] = relationship("Center", back_populates="backups")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    center_id: Mapped[int] = mapped_column(ForeignKey("centers.id"))
    event_type: Mapped[str] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text)
    timestamp: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    center: Mapped[Center] = relationship("Center", back_populates="events")
