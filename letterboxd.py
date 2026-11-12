from __future__ import annotations

import hashlib
import io
import re
from typing import Any

import pandas as pd


def _truthy(value: Any) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes", "y", "sim", "x"}


def _clean(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _key(uri: str, title: str, year: Any) -> str:
    if uri:
        return uri.rstrip("/")
    # Keep the legacy fallback key format so old local rows remain addressable.
    base = f"{str(title or '').lower()}::{year or ''}"
    return "local:" + hashlib.sha1(base.encode("utf-8")).hexdigest()


def _read_csv(upload: Any) -> pd.DataFrame:
    """Read a Letterboxd CSV upload while preserving literal values and accents."""
    if hasattr(upload, "getvalue"):
        raw = upload.getvalue()
    elif hasattr(upload, "read"):
        raw = upload.read()
    elif isinstance(upload, (bytes, bytearray)):
        raw = bytes(upload)
    else:
        raise TypeError("Formato de arquivo enviado não é suportado.")

    if not raw:
        return pd.DataFrame()
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(raw), dtype=str, keep_default_na=False, encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeError("Não foi possível decodificar o CSV do Letterboxd.")


def _parse_year(value: Any) -> int | None:
    text = _clean(value)
    if not text:
        return None
    try:
        year = int(float(text))
        return year if 1870 <= year <= 2200 else None
    except (TypeError, ValueError, OverflowError):
        return None


def _latest_date(current: str, incoming: str) -> str:
    if not incoming:
        return current
    if not current:
        return incoming
    current_date = pd.to_datetime(current, errors="coerce", utc=True)
    incoming_date = pd.to_datetime(incoming, errors="coerce", utc=True)
    if pd.isna(current_date):
        return incoming
    if pd.isna(incoming_date):
        return current
    return incoming if incoming_date >= current_date else current


def parse_letterboxd_uploads(uploads: list[Any]) -> pd.DataFrame:
    """Merge diary, ratings and watchlist CSVs independent of upload order.

    Watchlist membership is treated as a positive fact: a row in watchlist.csv
    marks the movie as watchlisted, while rows in diary.csv/ratings.csv do not
    clear that flag simply because of the order in which files were selected.
    """
    merged: dict[str, dict[str, Any]] = {}
    has_watchlist_upload = any("watchlist" in str(getattr(upload, "name", "")).casefold() for upload in uploads)

    for upload in uploads:
        df = _read_csv(upload)
        if df.empty:
            continue

        lower_columns = {str(column).strip().casefold(): column for column in df.columns}
        name_col = lower_columns.get("name") or lower_columns.get("film") or lower_columns.get("title")
        if not name_col:
            continue

        filename = str(getattr(upload, "name", "")).casefold()
        is_watchlist_file = "watchlist" in filename
        is_ratings_file = "ratings" in filename
        is_diary_file = "diary" in filename

        for _, row in df.iterrows():
            title = _clean(row.get(name_col))
            if not title:
                continue

            year_value = _parse_year(row.get(lower_columns.get("year")))
            uri = _clean(row.get(lower_columns.get("letterboxd uri")))
            film_key = _key(uri, title, year_value)
            record = merged.setdefault(film_key, {
                "film_key": film_key,
                "title": title,
                "year": year_value,
                "letterboxd_url": uri,
                "watched_date": "",
                "rating": None,
                "is_rewatch": None,
                "is_watchlist": False if has_watchlist_upload else None,
                "tags": "",
                "director": "",
                "genres": "",
                "overview": "",
                "poster_url": "",
            })

            # Fill metadata regardless of which CSV was selected first.
            if not record.get("year") and year_value:
                record["year"] = year_value
            if not record.get("letterboxd_url") and uri:
                record["letterboxd_url"] = uri

            rating_col = lower_columns.get("rating")
            rating_text = _clean(row.get(rating_col)) if rating_col else ""
            if rating_text:
                try:
                    rating = float(rating_text)
                    if 0 <= rating <= 5:
                        # ratings.csv is the authoritative aggregate; otherwise keep
                        # the first non-empty value and make no file-order assumption.
                        if is_ratings_file or record["rating"] is None:
                            record["rating"] = rating
                except (TypeError, ValueError):
                    pass

            date_col = lower_columns.get("watched date") or lower_columns.get("date")
            date_text = _clean(row.get(date_col)) if date_col else ""
            if date_text and (is_diary_file or not record["watched_date"]):
                record["watched_date"] = _latest_date(record["watched_date"], date_text)

            rewatch_col = lower_columns.get("rewatch")
            if rewatch_col:
                current_rewatch = record.get("is_rewatch")
                record["is_rewatch"] = bool(current_rewatch) or _truthy(row.get(rewatch_col))

            tags_col = lower_columns.get("tags")
            tags_text = _clean(row.get(tags_col)) if tags_col else ""
            if tags_text:
                tag_values = [tag.strip() for tag in re.split(r"[,;|]", tags_text) if tag.strip()]
                existing = [tag.strip() for tag in re.split(r"[,;|]", record["tags"]) if tag.strip()]
                record["tags"] = ", ".join(dict.fromkeys(existing + tag_values))

            if is_watchlist_file:
                record["is_watchlist"] = True

    if not merged:
        return pd.DataFrame()
    return pd.DataFrame(list(merged.values()))
