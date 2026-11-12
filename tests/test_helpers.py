import pandas as pd

from cinefy.helpers import changed_metadata_rows, passwords_match, safe_poster_url


def test_passwords_match_with_accents():
    assert passwords_match("sênha-ção", "sênha-ção")
    assert not passwords_match("senha", "sênha")
    assert not passwords_match("", "x")


def test_safe_poster_url_rejects_nan_and_http():
    assert safe_poster_url(float("nan")) == ""
    assert safe_poster_url(None) == ""
    assert safe_poster_url("http://exemplo.com/a.jpg") == ""
    assert safe_poster_url("https://image.tmdb.org/t/p/w500/a.jpg") == "https://image.tmdb.org/t/p/w500/a.jpg"


def test_changed_metadata_rows_only_returns_edits_and_cleans_nan():
    original = pd.DataFrame([
        {"film_key": "a", "director": "Ana", "genres": "Drama"},
        {"film_key": "b", "director": None, "genres": None},
        {"film_key": "c", "director": "Caio", "genres": "Terror"},
    ])
    edited = original.copy()
    edited.loc[1, "genres"] = "Comédia"
    edited.loc[2, "director"] = float("nan")
    changes = changed_metadata_rows(original, edited)
    assert changes == [
        {"film_key": "b", "director": "", "genres": "Comédia"},
        {"film_key": "c", "director": "", "genres": "Terror"},
    ]


def test_changed_metadata_rows_empty_inputs():
    assert changed_metadata_rows(pd.DataFrame(), pd.DataFrame()) == []
