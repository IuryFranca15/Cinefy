from __future__ import annotations

import base64
import os
import time
from typing import Any
from urllib.parse import urlencode

import requests
import streamlit as st

API_BASE = "https://api.spotify.com/v1"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
SCOPES = ["user-top-read", "playlist-modify-private"]


def get_spotify_config() -> dict[str, str]:
    try:
        section = st.secrets.get("spotify", {})
    except Exception:
        section = {}
    return {
        "client_id": str(section.get("client_id", "") or os.getenv("SPOTIFY_CLIENT_ID", "")).strip(),
        "client_secret": str(section.get("client_secret", "") or os.getenv("SPOTIFY_CLIENT_SECRET", "")).strip(),
        "redirect_uri": str(section.get("redirect_uri", "") or os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8501")).strip(),
    }


def is_spotify_configured() -> bool:
    config = get_spotify_config()
    return bool(config["client_id"] and config["client_secret"] and config["redirect_uri"])


def build_authorize_url(state: str) -> str:
    config = get_spotify_config()
    params = {
        "client_id": config["client_id"],
        "response_type": "code",
        "redirect_uri": config["redirect_uri"],
        "scope": " ".join(SCOPES),
        "state": state,
        "show_dialog": "true",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def _basic_auth_header() -> str:
    config = get_spotify_config()
    token = base64.b64encode(f"{config['client_id']}:{config['client_secret']}".encode()).decode()
    return f"Basic {token}"


def _token_request(data: dict[str, str]) -> dict[str, Any]:
    response = requests.post(
        TOKEN_URL,
        data=data,
        headers={"Authorization": _basic_auth_header(), "Content-Type": "application/x-www-form-urlencoded"},
        timeout=25,
    )
    response.raise_for_status()
    result = response.json()
    result["expires_at"] = time.time() + int(result.get("expires_in", 3600))
    return result


def exchange_code(code: str) -> dict[str, Any]:
    config = get_spotify_config()
    return _token_request({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config["redirect_uri"],
        "client_id": config["client_id"],
    })


def refresh_access_token(token: dict[str, Any]) -> dict[str, Any] | None:
    refresh = token.get("refresh_token")
    if not refresh:
        return None
    try:
        refreshed = _token_request({"grant_type": "refresh_token", "refresh_token": str(refresh), "client_id": get_spotify_config()["client_id"]})
        if "refresh_token" not in refreshed:
            refreshed["refresh_token"] = refresh
        return refreshed
    except requests.RequestException:
        return None


def spotify_request(method: str, endpoint: str, *, params: dict[str, Any] | None = None, json: dict[str, Any] | None = None) -> dict[str, Any]:
    token = st.session_state.get("spotify_token")
    if not token:
        raise RuntimeError("Conecte o Spotify primeiro.")
    if float(token.get("expires_at", 0)) <= time.time() + 45:
        token = refresh_access_token(token)
        if not token:
            st.session_state.pop("spotify_token", None)
            raise RuntimeError("Sua sessão Spotify expirou. Conecte novamente.")
        st.session_state["spotify_token"] = token

    url = endpoint if endpoint.startswith("http") else f"{API_BASE}{endpoint}"
    response = requests.request(
        method,
        url,
        headers={"Authorization": f"Bearer {token['access_token']}", "Content-Type": "application/json"},
        params=params,
        json=json,
        timeout=35,
    )
    if response.status_code == 401:
        refreshed = refresh_access_token(token)
        if refreshed:
            st.session_state["spotify_token"] = refreshed
            response = requests.request(
                method, url,
                headers={"Authorization": f"Bearer {refreshed['access_token']}", "Content-Type": "application/json"},
                params=params, json=json, timeout=35,
            )
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "alguns segundos")
        raise RuntimeError(f"Limite de requisições do Spotify atingido. Tente novamente em {retry_after} segundos.")
    response.raise_for_status()
    return response.json() if response.content else {}


def spotify_get(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        return spotify_request("GET", endpoint, params=params)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "desconhecido"
        detail = "Verifique as permissões e as regras atuais do modo de desenvolvimento do Spotify." if status in (403, 404) else str(exc)
        raise RuntimeError(f"Spotify respondeu HTTP {status}. {detail}") from exc


def _audio_features(track_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not track_ids:
        return {}
    try:
        payload = spotify_get("/audio-features", {"ids": ",".join(track_ids[:100])})
        return {item["id"]: item for item in payload.get("audio_features", []) if item and item.get("id")}
    except Exception:
        # Spotify may deny specific endpoints for certain app modes/accounts.
        return {}


def sync_top_music(time_range: str = "medium_term") -> dict[str, Any]:
    if time_range not in {"short_term", "medium_term", "long_term"}:
        raise ValueError("Período inválido.")
    top_tracks = spotify_get("/me/top/tracks", {"limit": 50, "time_range": time_range}).get("items", [])
    top_artists = spotify_get("/me/top/artists", {"limit": 50, "time_range": time_range}).get("items", [])

    artist_genres: dict[str, list[str]] = {}
    for artist in top_artists:
        artist_genres[artist.get("id", "")] = artist.get("genres", []) or []

    ids = [track.get("id") for track in top_tracks if track.get("id")]
    features = _audio_features(ids)
    normalized_tracks: list[dict[str, Any]] = []
    for track in top_tracks:
        artists = track.get("artists", []) or []
        genres: list[str] = []
        for artist in artists:
            genres.extend(artist_genres.get(artist.get("id", ""), []))
        unique_genres = sorted(set(genres))
        audio = features.get(track.get("id", ""), {})
        normalized_tracks.append({
            "id": track.get("id"),
            "uri": track.get("uri"),
            "track_name": track.get("name"),
            "artist_names": ", ".join(a.get("name", "") for a in artists),
            "artist_ids": [a.get("id") for a in artists if a.get("id")],
            "album_name": (track.get("album") or {}).get("name", ""),
            "album_image": ((track.get("album") or {}).get("images") or [{}])[0].get("url"),
            "spotify_url": (track.get("external_urls") or {}).get("spotify", ""),
            "genres": unique_genres,
            "energy": audio.get("energy"),
            "valence": audio.get("valence"),
            "danceability": audio.get("danceability"),
            "tempo": audio.get("tempo"),
        })

    return {
        "time_range": time_range,
        "tracks": normalized_tracks,
        "artists": [
            {"id": a.get("id"), "name": a.get("name"), "genres": a.get("genres", []) or [],
             "spotify_url": (a.get("external_urls") or {}).get("spotify", "")}
            for a in top_artists
        ],
    }


def create_playlist(name: str, description: str, track_uris: list[str]) -> dict[str, Any]:
    if not track_uris:
        raise ValueError("Não há faixas suficientes para montar a playlist.")
    # Current Spotify Web API uses POST /me/playlists and POST /playlists/{id}/items.
    playlist = spotify_request("POST", "/me/playlists", json={
        "name": name[:100],
        "description": description[:300],
        "public": False,
    })
    playlist_id = playlist.get("id")
    if not playlist_id:
        raise RuntimeError("O Spotify não retornou o identificador da playlist.")
    for start in range(0, len(track_uris), 100):
        batch = track_uris[start:start + 100]
        spotify_request("POST", f"/playlists/{playlist_id}/items", json={"uris": batch})
    return playlist
