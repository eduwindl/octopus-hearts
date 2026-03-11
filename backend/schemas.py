from datetime import datetime
from pydantic import BaseModel, Field


class CenterBase(BaseModel):
    name: str
    location: str | None = None
    fortigate_ip: str
    model: str | None = None


class CenterCreate(CenterBase):
    api_token: str = Field(..., min_length=10)


class CenterUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    fortigate_ip: str | None = None
    model: str | None = None
    api_token: str | None = None


class CenterOut(CenterBase):
    id: int
    last_backup: datetime | None = None
    status: str

    class Config:
        from_attributes = True


class BackupOut(BaseModel):
    id: int
    center_id: int
    backup_date: datetime
    file_path: str
    checksum: str
    size: int
    status: str

    class Config:
        from_attributes = True


class EventOut(BaseModel):
    id: int
    center_id: int
    event_type: str
    message: str
    timestamp: datetime

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    password: str = Field(..., min_length=6)
    role: str = "operator"


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PasswordUpdate(BaseModel):
    new_password: str = Field(..., min_length=6)


class DiffResponse(BaseModel):
    center_id: int
    from_backup_id: int
    to_backup_id: int
    diff: str
