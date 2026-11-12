"""Percorre todas as páginas do app com um banco temporário e dados fictícios."""
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")
PAGES = ["Visão geral", "Letterboxd", "Spotify", "Director's Cut", "Mood Mirror", "Recomendação inversa"]

FILMS = [
    {"film_key": "https://boxd.it/a1", "title": "Filme A", "year": 2001, "rating": 4.5, "is_watchlist": False,
     "genres": "Terror, Drama", "director": "Dir A", "poster_url": "https://image.tmdb.org/t/p/w500/a.jpg", "tmdb_id": 1},
    {"film_key": "https://boxd.it/a2", "title": "Filme A", "year": 2001, "rating": 3.0, "is_watchlist": False,
     "genres": "", "director": "", "poster_url": None},
    {"film_key": "https://boxd.it/w1", "title": "Quero Ver", "year": 2020, "is_watchlist": True, "genres": "Drama, Crime"},
]

TRACKS_NO_AUDIO = [{"id": "1", "track_name": "Faixa 1", "artist_names": "Artista", "genres": ["metal"]}]  # sem uri nem métricas
TRACKS_WITH_AUDIO = [{"id": "1", "uri": "spotify:track:1", "track_name": "Faixa 1", "artist_names": "Artista",
                      "genres": ["metal"], "energy": 0.9, "valence": 0.2, "danceability": 0.4}]


def _setup(monkeypatch, tmp_path, tracks, seed_films=True):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'smoke.db'}")
    st.cache_resource.clear()
    from cinefy import database
    database.init_db()
    if seed_films:
        database.save_films(FILMS)
    if tracks is not None:
        database.save_music_snapshot({"time_range": "medium_term", "tracks": tracks, "artists": []})


@pytest.mark.parametrize("scenario", ["vazio", "sem_audio", "com_audio"])
def test_all_pages_render_without_exception(monkeypatch, tmp_path, scenario):
    tracks = {"vazio": None, "sem_audio": TRACKS_NO_AUDIO, "com_audio": TRACKS_WITH_AUDIO}[scenario]
    _setup(monkeypatch, tmp_path, tracks, seed_films=scenario != "vazio")
    at = AppTest.from_file(APP, default_timeout=30).run()
    for page in PAGES:
        at.radio(key="page").set_value(page).run()
        assert not at.exception, f"{scenario}/{page}: {[e.value for e in at.exception]}"
    st.cache_resource.clear()


def test_mood_mirror_uses_observed_audio_metrics(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, TRACKS_WITH_AUDIO)
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.radio(key="page").set_value("Mood Mirror").run()
    assert not at.exception
    assert any("Intenso e melancólico" in m.value for m in at.metric)
    st.cache_resource.clear()


def test_mood_mirror_warns_when_audio_is_missing(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, TRACKS_NO_AUDIO)
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.radio(key="page").set_value("Mood Mirror").run()
    assert not at.exception
    assert any("indisponíveis" in w.value for w in at.warning)
    st.cache_resource.clear()


def test_oauth_callback_with_invalid_state_shows_error_and_clears_params(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, None)
    at = AppTest.from_file(APP, default_timeout=30)
    at.query_params["code"] = "codigo-falso"
    at.query_params["state"] = "estado.invalido.x"
    at.run()
    assert not at.exception
    assert any("validar o retorno do Spotify" in e.value for e in at.error)
    assert "code" not in at.query_params
    st.cache_resource.clear()


def test_oauth_callback_access_denied_shows_warning(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, None)
    at = AppTest.from_file(APP, default_timeout=30)
    at.query_params["error"] = "access_denied"
    at.run()
    assert not at.exception
    assert any("cancelada" in w.value for w in at.warning)
    st.cache_resource.clear()
