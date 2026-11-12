from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st
from sqlalchemy import Column, Float, Integer, MetaData, String, Table, Text, create_engine, func, inspect, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine


def _secret_database_url() -> str:
    try:
        return str(st.secrets.get("database", {}).get("url", "")).strip()
    except Exception:
        return ""


def _database_url() -> str:
    url = _secret_database_url() or os.getenv("DATABASE_URL", "").strip()
    if url:
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://") and "+psycopg" not in url:
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url
    return "sqlite:///cinefy.db"


@st.cache_resource
def get_engine() -> Engine:
    url = _database_url()
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False}, future=True)
    return create_engine(url, pool_pre_ping=True, pool_recycle=300, future=True)


metadata = MetaData()
films = Table(
    "cinefy_films",
    metadata,
    Column("film_key", String(255), primary_key=True),
    Column("title", String(500), nullable=False),
    Column("year", Integer),
    Column("letterboxd_url", Text),
    Column("watched_date", String(40)),
    Column("rating", Float),
    Column("is_rewatch", Integer, default=0),
    Column("is_watchlist", Integer, default=0),
    Column("tags", Text),
    Column("director", Text),
    Column("genres", Text),
    Column("overview", Text),
    Column("poster_url", Text),
    Column("tmdb_id", Integer),
    Column("tmdb_url", Text),
    Column("backdrop_url", Text),
    Column("release_date", String(20)),
    Column("metadata_status", String(30)),
    Column("metadata_source", String(30)),
    Column("metadata_updated_at", String(40)),
    Column("updated_at", String(40)),
)

snapshots = Table(
    "cinefy_music_snapshots",
    metadata,
    Column("snapshot_id", String(64), primary_key=True),
    Column("created_at", String(40), nullable=False),
    Column("time_range", String(30)),
    Column("payload", Text, nullable=False),
)


def init_db() -> None:
    engine = get_engine()
    metadata.create_all(engine)
    # Lightweight migration for databases created by Cinefy v1 before TMDB fields existed.
    existing = {column["name"] for column in inspect(engine).get_columns("cinefy_films")}
    migrations = {
        "tmdb_id": "INTEGER",
        "tmdb_url": "TEXT",
        "backdrop_url": "TEXT",
        "release_date": "VARCHAR(20)",
        "metadata_status": "VARCHAR(30)",
        "metadata_source": "VARCHAR(30)",
        "metadata_updated_at": "VARCHAR(40)",
    }
    with engine.begin() as connection:
        for name, sql_type in migrations.items():
            if name not in existing:
                connection.exec_driver_sql(f"ALTER TABLE cinefy_films ADD COLUMN {name} {sql_type}")


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "y", "sim", "x"}
    if value is None:
        return False
    try:
        if pd.isna(value):
            return False
    except (TypeError, ValueError):
        pass
    return bool(value)


def _normalize_film(record: dict[str, Any]) -> dict[str, Any]:
    result = dict(record)

    def number(value: Any, cast: type) -> Any:
        if value in (None, "", "nan", "NaN"):
            return None
        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
        try:
            return cast(value)
        except (TypeError, ValueError, OverflowError):
            return None

    result["year"] = number(result.get("year"), int)
    result["rating"] = number(result.get("rating"), float)
    for flag in ("is_rewatch", "is_watchlist"):
        value = result.get(flag)
        if value is None:
            result[flag] = None
        else:
            try:
                result[flag] = None if pd.isna(value) else int(_as_bool(value))
            except (TypeError, ValueError):
                result[flag] = int(_as_bool(value))
    result["updated_at"] = datetime.now(timezone.utc).isoformat()

    allowed = {column.name for column in films.columns}
    normalized = {key: value for key, value in result.items() if key in allowed}
    # A uniform set of columns allows efficient multi-row upserts and prevents
    # missing optional metadata from producing inconsistent SQL statements.
    return {column.name: normalized.get(column.name) for column in films.columns}


def save_films(records: list[dict[str, Any]]) -> None:
    """Persist film imports in batches and one transaction per batch."""
    if not records:
        return

    deduplicated: dict[str, dict[str, Any]] = {}
    for raw in records:
        if not isinstance(raw, dict):
            continue
        record = _normalize_film(raw)
        if not record.get("film_key") or not record.get("title"):
            continue
        key = str(record["film_key"])
        prior = deduplicated.get(key)
        if prior:
            # Keep the latest non-empty metadata when the same film appears
            # more than once in a single import payload.
            for field, value in record.items():
                if field in {"is_watchlist", "is_rewatch"} and value is not None:
                    prior[field] = int(bool(prior.get(field)) or bool(value))
                elif value not in (None, "") or field == "updated_at":
                    prior[field] = value
        else:
            deduplicated[key] = record

    rows = list(deduplicated.values())
    if not rows:
        return

    engine = get_engine()
    preserve_when_missing = {
        "year", "letterboxd_url", "watched_date", "rating", "tags", "director",
        "genres", "overview", "poster_url", "tmdb_id", "tmdb_url", "backdrop_url",
        "release_date", "metadata_status", "metadata_source", "metadata_updated_at",
        "is_rewatch", "is_watchlist",
    }
    batch_size = 200

    for start in range(0, len(rows), batch_size):
        batch = rows[start:start + batch_size]
        with engine.begin() as connection:
            if engine.dialect.name in {"sqlite", "postgresql"}:
                insert_factory = sqlite_insert if engine.dialect.name == "sqlite" else pg_insert
                statement = insert_factory(films).values(batch)
                mutable: dict[str, Any] = {}
                for column in films.columns:
                    name = column.name
                    if name == "film_key":
                        continue
                    incoming = getattr(statement.excluded, name)
                    if name in preserve_when_missing:
                        if isinstance(column.type, (String, Text)):
                            incoming = func.nullif(incoming, "")
                        mutable[name] = func.coalesce(incoming, getattr(films.c, name))
                    else:
                        mutable[name] = incoming
                statement = statement.on_conflict_do_update(
                    index_elements=["film_key"], set_=mutable
                )
                connection.execute(statement)
            else:
                for record in batch:
                    existing = connection.execute(
                        select(films.c.film_key).where(films.c.film_key == record["film_key"])
                    ).first()
                    if existing:
                        values = {k: v for k, v in record.items() if k != "film_key"}
                        connection.execute(update(films).where(films.c.film_key == record["film_key"]).values(**values))
                    else:
                        connection.execute(films.insert().values(**record))


def get_films() -> pd.DataFrame:
    with get_engine().connect() as connection:
        frame = pd.read_sql(select(films).order_by(films.c.title), connection)
    if frame.empty:
        return pd.DataFrame(columns=[column.name for column in films.columns] + ["is_watchlist_bool"])
    for flag in ("is_watchlist", "is_rewatch"):
        frame[flag] = pd.to_numeric(frame[flag], errors="coerce").fillna(0).astype(bool)
    return frame


def _text_or_empty(value: Any) -> str:
    """Converte NaN/None em texto vazio, evitando gravar 'nan' ou NaN no banco."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def update_film_metadata(records: list[dict[str, Any]]) -> int:
    """Atualiza diretor e gêneros editados manualmente. Retorna quantas linhas foram gravadas."""
    written = 0
    if not records:
        return written
    with get_engine().begin() as connection:
        for record in records:
            key = record.get("film_key")
            if not key:
                continue
            result = connection.execute(
                update(films)
                .where(films.c.film_key == str(key))
                .values(director=_text_or_empty(record.get("director")),
                        genres=_text_or_empty(record.get("genres")),
                        metadata_source="manual",
                        updated_at=datetime.now(timezone.utc).isoformat())
            )
            written += result.rowcount or 0
    return written


def update_tmdb_metadata(film_key: str, details: dict[str, Any]) -> None:
    allowed = {
        "tmdb_id", "tmdb_url", "backdrop_url", "release_date", "director", "genres",
        "overview", "poster_url", "metadata_status", "metadata_source", "metadata_updated_at",
    }
    values = {key: value for key, value in details.items() if key in allowed}
    values["metadata_updated_at"] = datetime.now(timezone.utc).isoformat()
    values["updated_at"] = datetime.now(timezone.utc).isoformat()
    with get_engine().begin() as connection:
        connection.execute(update(films).where(films.c.film_key == film_key).values(**values))


def save_music_snapshot(payload: dict[str, Any]) -> None:
    import uuid

    snapshot = {
        "snapshot_id": str(uuid.uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "time_range": payload.get("time_range", "medium_term"),
        "payload": json.dumps(payload, ensure_ascii=False),
    }
    with get_engine().begin() as connection:
        connection.execute(snapshots.insert().values(**snapshot))


def get_latest_snapshot() -> dict[str, Any] | None:
    with get_engine().connect() as connection:
        row = connection.execute(select(snapshots).order_by(snapshots.c.created_at.desc()).limit(1)).mappings().first()
    if not row:
        return None
    result = dict(row)
    try:
        payload = json.loads(result.pop("payload", "{}") or "{}")
    except (TypeError, json.JSONDecodeError):
        payload = {}
    result["tracks"] = payload.get("tracks", []) if isinstance(payload, dict) else []
    result["artists"] = payload.get("artists", []) if isinstance(payload, dict) else []
    result["time_range"] = row["time_range"]
    return result


def get_snapshots() -> pd.DataFrame:
    with get_engine().connect() as connection:
        return pd.read_sql(select(snapshots).order_by(snapshots.c.created_at.desc()), connection)
