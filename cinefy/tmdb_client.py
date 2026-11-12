from __future__ import annotations

import os
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any

import requests

try:
    import streamlit as st
except ImportError:  # Allows unit tests and CLI tools to use the pure matching helpers.
    st = None  # type: ignore[assignment]


def _cache_data(ttl_seconds: int):
    """Use Streamlit's in-memory cache when available; remain test/CLI friendly."""
    if st is not None and hasattr(st, "cache_data"):
        return st.cache_data(ttl=ttl_seconds, show_spinner=False)
    return lambda function: function


TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"
TMDB_WEB_BASE = "https://www.themoviedb.org/movie"


def _config_value(key: str, env_name: str = "") -> str:
    value = ""
    try:
        if st is not None:
            value = str(st.secrets.get("tmdb", {}).get(key, "") or "").strip()
    except Exception:
        pass
    if not value and env_name:
        value = os.getenv(env_name, "").strip()
    return value


def get_tmdb_config() -> dict[str, str]:
    """Read TMDB credentials from Streamlit Secrets or environment variables."""
    return {
        "bearer_token": _config_value("bearer_token", "TMDB_BEARER_TOKEN"),
        "api_key": _config_value("api_key", "TMDB_API_KEY"),
    }


def is_tmdb_configured() -> bool:
    config = get_tmdb_config()
    return bool(config["bearer_token"] or config["api_key"])


def tmdb_request(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    config = get_tmdb_config()
    if not config["bearer_token"] and not config["api_key"]:
        raise RuntimeError("TMDB não configurado. Adicione tmdb.bearer_token aos Secrets do Streamlit.")

    headers = {"accept": "application/json"}
    request_params = dict(params or {})
    if config["bearer_token"]:
        headers["Authorization"] = f"Bearer {config['bearer_token']}"
    else:
        request_params["api_key"] = config["api_key"]

    url = f"{TMDB_API_BASE}/{endpoint.lstrip('/')}"
    try:
        response = requests.get(url, headers=headers, params=request_params, timeout=25)
        if response.status_code == 401:
            raise RuntimeError("TMDB recusou a credencial. Confira o API Read Access Token nos Secrets.")
        if response.status_code == 429:
            raise RuntimeError("Limite temporário de requisições do TMDB atingido. Aguarde um pouco e tente novamente.")
        response.raise_for_status()
        return response.json()
    except requests.Timeout as exc:
        raise RuntimeError("O TMDB demorou demais para responder. Tente novamente.") from exc
    except requests.RequestException as exc:
        status = exc.response.status_code if exc.response is not None else "indisponível"
        raise RuntimeError(f"Falha ao consultar o TMDB (HTTP {status}).") from exc


def normalize_title(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _candidate_title_score(letterboxd_title: str, candidate: dict[str, Any]) -> float:
    target = normalize_title(letterboxd_title)
    choices = [candidate.get("title", ""), candidate.get("original_title", "")]
    scores = [SequenceMatcher(None, target, normalize_title(choice)).ratio() for choice in choices if choice]
    return max(scores, default=0.0)


def rank_search_results(
    title: str,
    year: int | None,
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Score TMDB candidates against Letterboxd title/year; do not auto-pick weak matches."""
    ranked: list[dict[str, Any]] = []
    for item in results:
        # Reserve 10% of the score for the release year, so exact-title remakes
        # do not tie merely because the textual similarity is already 100%.
        score = _candidate_title_score(title, item) * 0.90
        release_date = str(item.get("release_date") or "")
        candidate_year = int(release_date[:4]) if len(release_date) >= 4 and release_date[:4].isdigit() else None
        if year and candidate_year:
            delta = abs(candidate_year - int(year))
            if delta == 0:
                score += 0.10
            elif delta == 1:
                score -= 0.04
            else:
                score -= min(0.25, 0.08 * delta)
        item_copy = dict(item)
        item_copy["_cinefy_score"] = max(0.0, min(1.0, score))
        item_copy["_cinefy_year"] = candidate_year
        ranked.append(item_copy)
    return sorted(ranked, key=lambda x: x["_cinefy_score"], reverse=True)


@_cache_data(60 * 60 * 24)
def search_movies(title: str, year: int | None = None) -> list[dict[str, Any]]:
    if not str(title or "").strip():
        return []
    params: dict[str, Any] = {
        "query": str(title).strip(),
        "language": "pt-BR",
        "include_adult": "false",
        "page": 1,
    }
    if year:
        params["year"] = int(year)
    payload = tmdb_request("search/movie", params)
    results = payload.get("results", []) or []
    # Some Letterboxd exports contain the release year, while the localized search
    # can fail to find a translated title with that exact year. Retry without it.
    if not results and year:
        params.pop("year", None)
        payload = tmdb_request("search/movie", params)
        results = payload.get("results", []) or []
    return rank_search_results(str(title), year, results)


def choose_automatic_match(
    title: str,
    year: int | None,
    results: list[dict[str, Any]],
    threshold: float = 0.86,
    min_margin: float = 0.045,
) -> dict[str, Any] | None:
    ranked = rank_search_results(title, year, results)
    if not ranked or ranked[0]["_cinefy_score"] < threshold:
        return None
    if len(ranked) > 1 and ranked[0]["_cinefy_score"] - ranked[1]["_cinefy_score"] < min_margin:
        # Exact title + exact year is strong enough even when remakes share a name.
        first = ranked[0]
        exact_title = normalize_title(title) in {
            normalize_title(first.get("title", "")),
            normalize_title(first.get("original_title", "")),
        }
        if not (exact_title and year and first.get("_cinefy_year") == int(year)):
            return None
    return ranked[0]


def _image_url(path: str | None, size: str = "w500") -> str:
    return f"{TMDB_IMAGE_BASE}/{size}{path}" if path else ""


@_cache_data(60 * 60 * 24)
def get_movie_details(tmdb_id: int) -> dict[str, Any]:
    # credits is appended to the details request to avoid a separate API call.
    details = tmdb_request(f"movie/{int(tmdb_id)}", {"language": "pt-BR", "append_to_response": "credits"})
    credits = details.get("credits", {}) or {}
    crew = credits.get("crew", []) or []
    directors = list(dict.fromkeys(
        str(member.get("name", "")).strip()
        for member in crew
        if member.get("job") == "Director" and member.get("name")
    ))
    genres = [str(item.get("name", "")).strip() for item in details.get("genres", []) if item.get("name")]
    release_date = str(details.get("release_date") or "")
    year = int(release_date[:4]) if len(release_date) >= 4 and release_date[:4].isdigit() else None
    return {
        "tmdb_id": int(details["id"]),
        "tmdb_url": f"{TMDB_WEB_BASE}/{int(details['id'])}",
        "director": ", ".join(directors),
        "genres": ", ".join(genres),
        "overview": str(details.get("overview") or ""),
        "poster_url": _image_url(details.get("poster_path")),
        "backdrop_url": _image_url(details.get("backdrop_path"), "w1280"),
        "release_date": release_date,
        "tmdb_title": str(details.get("title") or details.get("original_title") or ""),
        "year": year,
        "metadata_status": "matched",
        "metadata_source": "TMDB",
    }


def find_and_enrich_movie(title: str, year: int | None) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Return details only for a confident match; otherwise return candidates for review."""
    results = search_movies(title, year)
    match = choose_automatic_match(title, year, results)
    if not match:
        return None, results[:8]
    return get_movie_details(int(match["id"])), results[:8]
