import pandas as pd

from cinefy.analytics import build_music_dataframe, describe_music_mood, get_film_mood_target, rank_tracks_for_film


def test_build_music_dataframe():
    frame = build_music_dataframe([{"track_name": "Track", "energy": 0.8, "valence": 0.2, "danceability": 0.5}])
    assert len(frame) == 1
    assert frame.iloc[0]["energy"] == 0.8


def test_describe_music_mood():
    frame = pd.DataFrame({"energy": [0.8, 0.9], "valence": [0.2, 0.3], "danceability": [0.4, 0.5]})
    mood = describe_music_mood(frame)
    assert mood["headline"] == "Intenso e melancólico"


def test_get_film_mood_target():
    target = get_film_mood_target("Horror, Thriller")
    assert target["energy"] > 0.6
    assert target["valence"] < 0.4


def test_rank_tracks_for_film():
    frame = pd.DataFrame([
        {"track_name": "A", "energy": 0.8, "valence": 0.2, "danceability": 0.3, "uri": "spotify:track:a"},
        {"track_name": "B", "energy": 0.1, "valence": 0.9, "danceability": 0.9, "uri": "spotify:track:b"},
    ])
    ranked = rank_tracks_for_film(frame, "Horror")
    assert ranked.iloc[0]["track_name"] == "A"



def test_missing_audio_features_do_not_become_neutral_scores():
    frame = build_music_dataframe([{"track_name": "Sem métricas", "energy": None, "valence": None}])
    mood = describe_music_mood(frame)
    ranked = rank_tracks_for_film(frame, "Terror")
    assert mood["energy"] is None
    assert mood["valence"] is None
    assert mood["headline"] == "Métricas insuficientes"
    assert pd.isna(ranked.iloc[0]["match_score"])


def test_portuguese_tmdb_genres_are_normalized_for_film_mood():
    target = get_film_mood_target("Terror, Ficção científica")
    assert target["energy"] < 0.78
    assert target["valence"] > 0.20


def test_inverse_recommendations_normalize_languages_and_cap_score():
    from cinefy.analytics import inverse_recommendations

    music = pd.DataFrame([{"genres": ["metal", "shoegaze", "electronic"]}])
    watchlist = pd.DataFrame([
        {"title": "Match", "genres": "Terror, Suspense, Drama, Crime, Romance, Fantasia, Ficção científica, Ação", "rating": 4.5},
        {"title": "Lower rated", "genres": "Terror, Drama", "rating": 2.0},
    ])
    result = inverse_recommendations(music, watchlist)
    assert result.iloc[0]["title"] == "Match"
    assert result.iloc[0]["match_score"] == 1.0
    assert result["match_score"].between(0, 1).all()
