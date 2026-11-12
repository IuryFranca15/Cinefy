from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd


def build_music_dataframe(tracks: list[dict[str, Any]]) -> pd.DataFrame:
    if not tracks:
        return pd.DataFrame()
    # Ignore malformed entries instead of allowing one bad API record to break the dashboard.
    valid_tracks = [item for item in tracks if isinstance(item, dict)]
    if not valid_tracks:
        return pd.DataFrame()
    frame = pd.DataFrame(valid_tracks).copy()
    for column in ["energy", "valence", "danceability", "tempo"]:
        if column not in frame.columns:
            frame[column] = np.nan
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if column in {"energy", "valence", "danceability"}:
            frame[column] = frame[column].clip(lower=0, upper=1)
        elif column == "tempo":
            frame[column] = frame[column].where(frame[column] > 0)
    if "genres" not in frame.columns:
        frame["genres"] = [[] for _ in range(len(frame))]
    return frame


def _metric_average(frame: pd.DataFrame, column: str) -> float | None:
    """Return an observed metric average; never invent a neutral fallback."""
    if frame.empty or column not in frame.columns:
        return None
    series = pd.to_numeric(frame[column], errors="coerce").dropna()
    return float(series.mean()) if not series.empty else None


def describe_music_mood(frame: pd.DataFrame) -> dict[str, Any]:
    energy = _metric_average(frame, "energy")
    valence = _metric_average(frame, "valence")
    dance = _metric_average(frame, "danceability")
    if energy is None or valence is None:
        return {
            "headline": "Métricas insuficientes",
            "description": "O Spotify não disponibilizou energia e/ou valência suficientes para estimar uma assinatura musical. Nenhum valor neutro foi presumido.",
            "energy": energy,
            "valence": valence,
            "danceability": dance,
        }
    dance_for_classification = dance if dance is not None else 0.0
    if energy >= 0.68 and valence < 0.42:
        headline = "Intenso e melancólico"
        description = "Guitarras no limite, tensão e uma certa sombra emocional. Um perfil sonoro de alta combustão e pouca euforia."
    elif energy >= 0.68 and valence >= 0.58:
        headline = "Eufórico e explosivo"
        description = "Muita energia com uma inclinação solar. Seu som parece feito para cenas em movimento."
    elif energy < 0.42 and valence < 0.42:
        headline = "Contemplativo e melancólico"
        description = "Uma paisagem mais introspectiva, com espaço para atmosfera, textura e silêncio."
    elif valence >= 0.67:
        headline = "Solar e vibrante"
        description = "Seu perfil tende ao luminoso: melodias positivas e uma atmosfera mais leve."
    elif dance_for_classification >= 0.68:
        headline = "Rítmico e magnético"
        description = "A pulsação é uma parte central do seu gosto: grooves, movimento e repetição hipnótica."
    else:
        headline = "Agridoce e alternativo"
        description = "Um equilíbrio entre intensidade e introspecção, sem depender de um único estado de espírito."
    return {"headline": headline, "description": description, "energy": energy, "valence": valence, "danceability": dance}


GENRE_MOODS: dict[str, tuple[float, float, float]] = {
    "horror": (0.78, 0.20, 0.25), "terror": (0.78, 0.20, 0.25),
    "thriller": (0.68, 0.30, 0.34), "suspense": (0.68, 0.30, 0.34),
    "crime": (0.59, 0.27, 0.31), "drama": (0.42, 0.34, 0.30),
    "romance": (0.47, 0.73, 0.56), "comedy": (0.69, 0.76, 0.72), "comédia": (0.69, 0.76, 0.72),
    "action": (0.87, 0.57, 0.62), "ação": (0.87, 0.57, 0.62),
    "science fiction": (0.62, 0.45, 0.42), "ficção científica": (0.62, 0.45, 0.42), "sci-fi": (0.62, 0.45, 0.42),
    "fantasy": (0.65, 0.67, 0.58), "fantasia": (0.65, 0.67, 0.58),
    "animation": (0.60, 0.76, 0.73), "animação": (0.60, 0.76, 0.73),
    "documentary": (0.41, 0.50, 0.36), "documentário": (0.41, 0.50, 0.36),
    "music": (0.74, 0.70, 0.79), "musical": (0.74, 0.70, 0.79),
    "war": (0.83, 0.24, 0.33), "guerra": (0.83, 0.24, 0.33),
    "history": (0.50, 0.48, 0.35), "história": (0.50, 0.48, 0.35),
    "adventure": (0.77, 0.67, 0.65), "aventura": (0.77, 0.67, 0.65),
    "mystery": (0.56, 0.30, 0.28), "mistério": (0.56, 0.30, 0.28),
    "family": (0.58, 0.78, 0.69), "família": (0.58, 0.78, 0.69),
    "western": (0.53, 0.42, 0.40),
}


def get_film_mood_target(genres: str) -> dict[str, Any]:
    normalized = _split_genres(genres)
    selected = [GENRE_MOODS[g] for g in normalized if g in GENRE_MOODS]
    if not selected:
        values = (0.58, 0.48, 0.46)
        label = "Atmosfera cinematográfica equilibrada"
    else:
        values = tuple(float(np.mean([x[i] for x in selected])) for i in range(3))
        if values[0] > 0.68 and values[1] < 0.40:
            label = "Tenso, sombrio e intenso"
        elif values[1] > 0.65:
            label = "Solar, caloroso e expansivo"
        elif values[0] < 0.48:
            label = "Contemplativo e atmosférico"
        else:
            label = "Dramático e pulsante"
    return {"energy": values[0], "valence": values[1], "danceability": values[2], "label": label}


def rank_tracks_for_film(music: pd.DataFrame, genres: str) -> pd.DataFrame:
    if music.empty:
        return music.copy()

    frame = music.copy().reset_index(drop=True)
    target = get_film_mood_target(genres)
    metric_columns = ["energy", "valence", "danceability"]
    weights = {"energy": 0.40, "valence": 0.35, "danceability": 0.25}

    for column in metric_columns:
        if column not in frame.columns:
            frame[column] = np.nan
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        if column in {"energy", "valence", "danceability"}:
            frame[column] = frame[column].where(frame[column].between(0, 1))

    observed = frame[metric_columns].notna()
    if not observed.any().any():
        # No score is fabricated when the API did not provide audio features.
        frame["match_score"] = np.nan
        frame["match_available"] = False
        return frame

    weighted_distance = pd.Series(0.0, index=frame.index, dtype=float)
    available_weight = pd.Series(0.0, index=frame.index, dtype=float)
    for column in metric_columns:
        valid = frame[column].notna()
        weight = weights[column]
        weighted_distance.loc[valid] += (frame.loc[valid, column] - target[column]).abs() * weight
        available_weight.loc[valid] += weight

    distance = weighted_distance.div(available_weight.where(available_weight > 0))
    frame["match_score"] = (1 - distance).clip(0, 1)
    frame["match_available"] = frame["match_score"].notna()
    return frame.sort_values("match_score", ascending=False, na_position="last", kind="stable").reset_index(drop=True)


GENRE_ALIASES = {
    "acao": "action", "comedia": "comedy", "ficcao cientifica": "science fiction",
    "ficcao-cientifica": "science fiction", "sci fi": "science fiction", "sci-fi": "science fiction",
    "animacao": "animation", "documentario": "documentary", "guerra": "war",
    "historia": "history", "aventura": "adventure", "misterio": "mystery",
    "familia": "family", "musica": "music", "romance": "romance", "drama": "drama",
    "terror": "horror", "suspense": "thriller", "crime": "crime", "western": "western",
    "fantasia": "fantasy", "musical": "musical",
}


def _canonical_genre(value: Any) -> str:
    """Normalize English/Portuguese TMDB genre labels to comparable keys."""
    import unicodedata

    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    text = re.sub(r"\s+", " ", text.replace("_", " ")).strip()
    return GENRE_ALIASES.get(text, text)


def _split_genres(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_values = list(value)
    else:
        try:
            if pd.isna(value):
                return []
        except (TypeError, ValueError):
            pass
        raw_values = re.split(r"[,;/|]", str(value))
    return list(dict.fromkeys(g for item in raw_values if (g := _canonical_genre(item))))


MUSIC_TO_FILM: dict[str, set[str]] = {
    "metal": {"Horror", "Thriller", "Drama", "Crime"},
    "sludge metal": {"Horror", "Thriller", "Drama", "Crime"},
    "doom metal": {"Horror", "Mystery", "Drama"},
    "post-punk": {"Drama", "Crime", "Thriller", "Mystery"},
    "punk": {"Action", "Comedy", "Drama"},
    "punk rock": {"Action", "Comedy", "Drama"},
    "indie rock": {"Drama", "Comedy", "Romance"},
    "alternative rock": {"Drama", "Science Fiction", "Thriller"},
    "shoegaze": {"Romance", "Drama", "Fantasy"},
    "dream pop": {"Romance", "Fantasy", "Drama"},
    "synth-pop": {"Science Fiction", "Thriller", "Drama"},
    "electropop": {"Science Fiction", "Comedy", "Romance"},
    "pop": {"Comedy", "Romance", "Musical"},
    "hip hop": {"Crime", "Drama", "Comedy"},
    "rap": {"Crime", "Drama", "Comedy"},
    "jazz": {"Crime", "Drama", "Mystery"},
    "classical": {"Drama", "History", "Fantasy"},
    "ambient": {"Science Fiction", "Drama", "Mystery"},
    "electronic": {"Science Fiction", "Action", "Thriller"},
    "house": {"Comedy", "Romance", "Action"},
    "disco": {"Comedy", "Musical", "Romance"},
    "folk": {"Drama", "Adventure", "History"},
    "country": {"Drama", "Romance", "Western"},
}


def _top_music_genres(music: pd.DataFrame) -> list[str]:
    counts: dict[str, int] = {}
    for genres in music.get("genres", pd.Series(dtype=object)):
        if isinstance(genres, list):
            values = genres
        else:
            values = str(genres).split(",") if genres else []
        for genre in values:
            genre = str(genre).strip().lower()
            if genre:
                counts[genre] = counts.get(genre, 0) + 1
    return [genre for genre, _ in sorted(counts.items(), key=lambda x: x[1], reverse=True)]


def inverse_recommendations(music: pd.DataFrame, watchlist: pd.DataFrame) -> pd.DataFrame:
    if music.empty or watchlist.empty:
        return pd.DataFrame()

    top_genres = _top_music_genres(music)
    preferred_film_genres: set[str] = set()
    for music_genre in top_genres:
        normalized_music_genre = _canonical_genre(music_genre)
        for known, film_genres in MUSIC_TO_FILM.items():
            known_normalized = _canonical_genre(known)
            if known_normalized in normalized_music_genre or normalized_music_genre in known_normalized:
                preferred_film_genres.update(_canonical_genre(g) for g in film_genres)
                break

    if not preferred_film_genres:
        # Mood fallback is only possible when the required observed metrics exist.
        mood = describe_music_mood(music)
        energy, valence = mood.get("energy"), mood.get("valence")
        if energy is not None and valence is not None:
            if energy > 0.65 and valence < 0.45:
                preferred_film_genres.update({"thriller", "crime", "horror", "drama"})
            elif valence > 0.62:
                preferred_film_genres.update({"comedy", "romance", "musical", "adventure"})
            else:
                preferred_film_genres.update({"drama", "mystery", "science fiction"})

    if not preferred_film_genres:
        return pd.DataFrame()

    records: list[dict[str, Any]] = []
    for _, film in watchlist.iterrows():
        genres = set(_split_genres(film.get("genres")))
        matches = sorted(genres.intersection(preferred_film_genres))
        if genres and matches:
            # Filmes com correspondência ficam sempre acima dos sem correspondência
            # (0,15) e dos sem gênero (0,05); três gêneros em comum já dão 100%.
            score = 0.30 + 0.70 * min(1.0, len(matches) / 3)
            reason = f"Combina com suas referências musicais: {', '.join(matches[:3])}."
        elif genres:
            reason = "Uma escolha fora do eixo dominante do seu som — boa para variar a sessão."
            score = 0.15
        else:
            reason = "Adicione os gêneros deste filme para uma recomendação mais precisa."
            score = 0.05
        records.append({**film.to_dict(), "match_score": float(max(0.0, min(1.0, score))), "reason": reason})

    result = pd.DataFrame(records)
    if result.empty:
        return result
    if "rating" not in result.columns:
        result["rating"] = np.nan
    result["rating"] = pd.to_numeric(result["rating"], errors="coerce")
    result = result.sort_values(["match_score", "rating"], ascending=[False, False], na_position="last", kind="stable").reset_index(drop=True)
    result["rank"] = result.index + 1
    return result


def make_mood_mirror_text(music_mood: dict[str, Any], genre_counts: dict[str, int]) -> str:
    dominant = sorted(genre_counts.items(), key=lambda x: x[1], reverse=True)[:3]
    film_genres = ", ".join(g for g, _ in dominant)
    energy = music_mood.get("energy")
    valence = music_mood.get("valence")
    if energy is None or valence is None:
        return "Ainda não há métricas de áudio suficientes no Spotify para comparar quantitativamente o perfil musical com a filmografia."
    if energy > 0.65 and valence < 0.45:
        if any(g.lower() in {"comedy", "comédia", "romance", "animation", "animação"} for g, _ in dominant):
            return f"Seu som puxa para a intensidade e a melancolia, enquanto sua filmografia recente se inclina para {film_genres}. Existe um contraste interessante: talvez você esteja buscando no cinema um ritmo diferente daquele que escuta."
        return f"Música e cinema parecem conversar na mesma frequência: energia alta, atmosferas densas e alguma tensão. Seus gêneros mais frequentes são {film_genres}."
    if valence > 0.62:
        return f"Sua assinatura sonora tem uma inclinação luminosa, e os filmes que mais aparecem são {film_genres}. Seu repertório parece alternar entre prazer imediato e curiosidade por outras atmosferas."
    return f"Seu perfil musical é mais agridoce e sua filmografia se concentra em {film_genres}. Há espaço para contemplação, tensão e narrativas que ficam ecoando depois dos créditos."
