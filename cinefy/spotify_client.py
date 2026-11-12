from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets as _secrets
import time
from typing import Any
from urllib.parse import urlencode

import requests
import streamlit as st

API_BASE = "https://api.spotify.com/v1"
AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
SCOPES = ["user-top-read", "playlist-modify-private"]
# O Spotify não aceita mais "localhost"; em HTTP só endereços de loopback (IP literal).
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8501"
STATE_MAX_AGE_SECONDS = 10 * 60


class SpotifyTemporaryError(RuntimeError):
    """Falha transitória (rede, timeout, 5xx): a sessão não deve ser descartada."""


def _state_key() -> bytes:
    config = get_spotify_config()
    key = f"cinefy-oauth-state:{config['client_secret']}"
    return key.encode("utf-8")


def make_state(now: float | None = None) -> str:
    """Gera um `state` OAuth assinado (HMAC), que não depende de st.session_state.

    O redirect do Spotify abre uma sessão Streamlit nova, então o estado não pode
    ficar guardado na sessão: ele precisa ser verificável apenas pela assinatura.
    """
    issued = int(now if now is not None else time.time())
    payload = f"{issued}.{_secrets.token_urlsafe(12)}"
    signature = hmac.new(_state_key(), payload.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    return f"{payload}.{signature}"


def verify_state(state: str | None, now: float | None = None) -> bool:
    if not state or not isinstance(state, str):
        return False
    parts = state.split(".")
    if len(parts) != 3:
        return False
    issued_text, nonce, signature = parts
    if not issued_text.isdigit() or not nonce:
        return False
    expected = hmac.new(_state_key(), f"{issued_text}.{nonce}".encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(signature.encode("utf-8"), expected.encode("utf-8")):
        return False
    age = (now if now is not None else time.time()) - int(issued_text)
    return -30 <= age <= STATE_MAX_AGE_SECONDS


def get_spotify_config() -> dict[str, str]:
    try:
        section = st.secrets.get("spotify", {})
    except Exception:
        section = {}
    return {
        "client_id": str(section.get("client_id", "") or os.getenv("SPOTIFY_CLIENT_ID", "")).strip(),
        "client_secret": str(section.get("client_secret", "") or os.getenv("SPOTIFY_CLIENT_SECRET", "")).strip(),
        "redirect_uri": str(section.get("redirect_uri", "") or os.getenv("SPOTIFY_REDIRECT_URI", DEFAULT_REDIRECT_URI)).strip(),
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
    try:
        response = requests.post(
            TOKEN_URL,
            data=data,
            headers={"Authorization": _basic_auth_header(), "Content-Type": "application/x-www-form-urlencoded"},
            timeout=25,
        )
    except requests.Timeout as exc:
        raise SpotifyTemporaryError("O Spotify demorou demais para responder. Tente novamente.") from exc
    except requests.RequestException as exc:
        raise SpotifyTemporaryError("Não foi possível falar com o Spotify. Verifique sua conexão.") from exc
    if response.status_code >= 500 or response.status_code == 429:
        raise SpotifyTemporaryError(f"O Spotify está indisponível no momento (HTTP {response.status_code}).")
    if response.status_code >= 400:
        try:
            detail = response.json().get("error_description") or response.json().get("error") or ""
        except ValueError:
            detail = ""
        raise RuntimeError(f"O Spotify recusou a autorização (HTTP {response.status_code}). {detail}".strip())
    try:
        result = response.json()
    except ValueError as exc:
        raise SpotifyTemporaryError("Resposta inválida do Spotify ao autenticar.") from exc
    if not isinstance(result, dict) or not result.get("access_token"):
        raise SpotifyTemporaryError("O Spotify não devolveu um token de acesso.")
    try:
        expires_in = int(result.get("expires_in", 3600))
    except (TypeError, ValueError):
        expires_in = 3600
    result["expires_at"] = time.time() + expires_in
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
    """Renova o token.

    Devolve None quando a sessão não pode mais ser renovada (refresh token ausente
    ou recusado). Falhas transitórias levantam `SpotifyTemporaryError`, para que o
    chamador mantenha o token atual em vez de desconectar o usuário.
    """
    refresh = token.get("refresh_token")
    if not refresh:
        return None
    try:
        refreshed = _token_request({"grant_type": "refresh_token", "refresh_token": str(refresh), "client_id": get_spotify_config()["client_id"]})
    except SpotifyTemporaryError:
        raise
    except RuntimeError:
        return None
    if "refresh_token" not in refreshed:
        refreshed["refresh_token"] = refresh
    return refreshed


class SpotifyHTTPError(RuntimeError):
    """Erro HTTP da API do Spotify, já com mensagem em português."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def _http_error_message(status: int) -> str:
    if status in (403, 404):
        return f"Spotify respondeu HTTP {status}. Verifique as permissões e as regras atuais do modo de desenvolvimento do Spotify (usuário autorizado no painel, escopos e recursos descontinuados)."
    if status == 401:
        return "Spotify respondeu HTTP 401. Sua sessão expirou; conecte novamente."
    if status == 429:
        return "Limite de requisições do Spotify atingido."
    if status >= 500:
        return f"O Spotify está instável no momento (HTTP {status}). Tente novamente em instantes."
    return f"Spotify respondeu HTTP {status}."


def _send(method: str, url: str, access_token: str, params: dict[str, Any] | None, json: dict[str, Any] | None) -> requests.Response:
    try:
        return requests.request(
            method,
            url,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            params=params,
            json=json,
            timeout=35,
        )
    except requests.Timeout as exc:
        raise SpotifyTemporaryError("O Spotify demorou demais para responder. Tente novamente.") from exc
    except requests.RequestException as exc:
        raise SpotifyTemporaryError("Não foi possível falar com o Spotify. Verifique sua conexão.") from exc


def spotify_request(method: str, endpoint: str, *, params: dict[str, Any] | None = None, json: dict[str, Any] | None = None) -> dict[str, Any]:
    token = st.session_state.get("spotify_token")
    if not token:
        raise RuntimeError("Conecte o Spotify primeiro.")
    if float(token.get("expires_at", 0) or 0) <= time.time() + 45:
        renewed = refresh_access_token(token)  # SpotifyTemporaryError sobe sem apagar o token
        if not renewed:
            st.session_state.pop("spotify_token", None)
            raise RuntimeError("Sua sessão Spotify expirou. Conecte novamente.")
        token = renewed
        st.session_state["spotify_token"] = token

    url = endpoint if endpoint.startswith("http") else f"{API_BASE}{endpoint}"
    response = _send(method, url, token["access_token"], params, json)
    if response.status_code == 401:
        refreshed = refresh_access_token(token)
        if refreshed:
            st.session_state["spotify_token"] = refreshed
            response = _send(method, url, refreshed["access_token"], params, json)
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "alguns")
        raise SpotifyHTTPError(429, f"Limite de requisições do Spotify atingido. Tente novamente em {retry_after} segundos.")
    if response.status_code >= 400:
        raise SpotifyHTTPError(response.status_code, _http_error_message(response.status_code))
    if not response.content:
        return {}
    try:
        payload = response.json()
    except ValueError as exc:
        raise SpotifyTemporaryError("Resposta inválida do Spotify.") from exc
    return payload if isinstance(payload, dict) else {}


def spotify_get(endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    return spotify_request("GET", endpoint, params=params)


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
    top_tracks = [t for t in (spotify_get("/me/top/tracks", {"limit": 50, "time_range": time_range}).get("items") or []) if isinstance(t, dict)]
    top_artists = [a for a in (spotify_get("/me/top/artists", {"limit": 50, "time_range": time_range}).get("items") or []) if isinstance(a, dict)]

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
