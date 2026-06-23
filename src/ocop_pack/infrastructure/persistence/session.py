from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from ocop_pack.infrastructure.persistence.models import Base


def make_engine(db_url: str = "sqlite:///data/ocop_packaging.db") -> Engine:
    if db_url.startswith("sqlite:///") and db_url != "sqlite:///:memory:":
        Path(db_url.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(db_url, future=True)

    @event.listens_for(engine, "connect")
    def _fk(dbapi_connection: Any, _connection_record: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
