import sys
import types

from sqlalchemy import create_engine, select

# Database tests do not need a real Streamlit server. Supply only the decorator
# and secrets interface used during module import when Streamlit is not installed.
try:
    import streamlit  # noqa: F401
except ImportError:
    fake_streamlit = types.ModuleType("streamlit")
    fake_streamlit.cache_resource = lambda function: function
    fake_streamlit.secrets = {}
    sys.modules["streamlit"] = fake_streamlit

from cinefy import database


def test_save_films_uses_batch_upsert_and_preserves_existing_metadata(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", future=True)
    database.metadata.create_all(engine)
    monkeypatch.setattr(database, "get_engine", lambda: engine)

    database.save_films([
        {"film_key": "film:1", "title": "Filme A", "year": 2001, "rating": 4.5,
         "genres": "Drama", "is_watchlist": True},
        {"film_key": "film:2", "title": "Filme B", "year": 2020, "rating": 3.0,
         "genres": "Ação", "is_watchlist": True},
    ])
    database.save_films([
        {"film_key": "film:1", "title": "Filme A", "rating": None, "genres": ""},
    ])

    with engine.connect() as connection:
        rows = connection.execute(select(database.films).order_by(database.films.c.film_key)).mappings().all()
    assert len(rows) == 2
    assert rows[0]["rating"] == 4.5
    assert rows[0]["genres"] == "Drama"
    assert rows[0]["is_watchlist"] == 1
    assert rows[1]["title"] == "Filme B"
    engine.dispose()
