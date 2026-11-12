import numpy as np
import pandas as pd
import pytest

from cinefy import tmdb_client as tm
from cinefy.analytics import build_music_dataframe, describe_music_mood, inverse_recommendations, rank_tracks_for_film


def test_inverse_recommendations_matching_film_always_beats_non_matching():
    music = pd.DataFrame([{"genres": ["metal", "shoegaze", "electronic", "jazz", "pop"]}])
    watchlist = pd.DataFrame([
        {"title": "Sem relação", "genres": "Western", "rating": 5.0},
        {"title": "Um gênero", "genres": "Fantasia", "rating": 1.0},
        {"title": "Sem gênero", "genres": "", "rating": 5.0},
    ])
    result = inverse_recommendations(music, watchlist)
    assert result.iloc[0]["title"] == "Um gênero"
    assert result.iloc[-1]["title"] == "Sem gênero"
    assert result["match_score"].between(0, 1).all()


@pytest.mark.parametrize("tracks", [
    [{"track_name": "x"}],
    [{"track_name": "x", "energy": None, "valence": "abc", "danceability": float("nan")}],
    [{"track_name": "x", "energy": 7, "valence": -3, "danceability": 0.5}],
    ["lixo", None, 3],
])
def test_music_pipeline_survives_null_or_malformed_metrics(tracks):
    frame = build_music_dataframe(tracks)
    mood = describe_music_mood(frame)
    assert "headline" in mood
    ranked = rank_tracks_for_film(frame, "Drama")
    if not ranked.empty and "match_score" in ranked:
        assert ranked["match_score"].dropna().between(0, 1).all()
    assert not np.isinf(ranked.select_dtypes("number").to_numpy(dtype=float, na_value=0)).any() if not ranked.empty else True


class FakeResponse:
    def __init__(self, status=200, payload=None, headers=None, json_error=False):
        self.status_code, self._payload, self.headers, self._json_error = status, payload, headers or {}, json_error

    def json(self):
        if self._json_error:
            raise ValueError("json inválido")
        return self._payload


@pytest.fixture
def tmdb_config(monkeypatch):
    monkeypatch.setattr(tm, "get_tmdb_config", lambda: {"bearer_token": "token-example-fake", "api_key": ""})
    monkeypatch.setattr(tm.time, "sleep", lambda *_: None)


def test_tmdb_401_aborts_batch(monkeypatch, tmdb_config):
    monkeypatch.setattr(tm.requests, "get", lambda *a, **k: FakeResponse(401))
    with pytest.raises(tm.TMDBAbortError):
        tm.tmdb_request("search/movie")


def test_tmdb_429_retries_once_then_aborts(monkeypatch, tmdb_config):
    calls = []
    monkeypatch.setattr(tm.requests, "get", lambda *a, **k: calls.append(1) or FakeResponse(429, headers={"Retry-After": "1"}))
    with pytest.raises(tm.TMDBAbortError):
        tm.tmdb_request("search/movie")
    assert len(calls) == 2


def test_tmdb_429_recovers_after_retry(monkeypatch, tmdb_config):
    answers = iter([FakeResponse(429, headers={"Retry-After": "1"}), FakeResponse(200, {"results": []})])
    monkeypatch.setattr(tm.requests, "get", lambda *a, **k: next(answers))
    assert tm.tmdb_request("search/movie") == {"results": []}


def test_tmdb_network_error_and_bad_json_are_friendly(monkeypatch, tmdb_config):
    def boom(*a, **k):
        raise tm.requests.ConnectionError("sem rede")
    monkeypatch.setattr(tm.requests, "get", boom)
    with pytest.raises(RuntimeError, match="TMDB"):
        tm.tmdb_request("x")
    monkeypatch.setattr(tm.requests, "get", lambda *a, **k: FakeResponse(200, json_error=True))
    with pytest.raises(RuntimeError, match="ilegível"):
        tm.tmdb_request("x")


def test_movie_details_without_id_raises_runtime_error(monkeypatch):
    monkeypatch.setattr(tm, "tmdb_request", lambda *a, **k: {})
    with pytest.raises(RuntimeError):
        tm.get_movie_details.__wrapped__(1) if hasattr(tm.get_movie_details, "__wrapped__") else tm.get_movie_details(1)


def test_search_ignores_malformed_results(monkeypatch):
    monkeypatch.setattr(tm, "tmdb_request", lambda *a, **k: {"results": ["lixo", None, {"title": "sem id"}, {"id": 1, "title": "Dune", "release_date": "2021-09-15"}]})
    fn = tm.search_movies.__wrapped__ if hasattr(tm.search_movies, "__wrapped__") else tm.search_movies
    results = fn("Dune", 2021)
    assert [item["id"] for item in results] == [1]
