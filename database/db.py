from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.config import settings

_engine = None
_SessionLocal = None


class Base(DeclarativeBase):
    pass


def get_engine():
    global _engine
    if _engine is None:
        if settings.database_url.startswith("sqlite"):
            _engine = create_engine(
                settings.database_url,
                connect_args={"check_same_thread": False},
                pool_pre_ping=True,
            )
        else:
            _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def SessionLocal():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=get_engine()
        )
    return _SessionLocal()
