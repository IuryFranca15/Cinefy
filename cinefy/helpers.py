"""Funções puras usadas pela interface (sem dependência de Streamlit, fáceis de testar)."""
from __future__ import annotations

import hmac
from typing import Any

import pandas as pd


def passwords_match(typed: str, expected: str) -> bool:
    """Compara senhas em tempo constante, inclusive com acentos.

    `secrets.compare_digest` com `str` só aceita ASCII e levanta TypeError nos demais
    casos; por isso a comparação é feita sobre bytes UTF-8.
    """
    return hmac.compare_digest(str(typed or "").encode("utf-8"), str(expected or "").encode("utf-8"))


def safe_poster_url(value: Any) -> str:
    """Devolve a URL do pôster apenas se for um HTTPS válido; caso contrário, string vazia."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text if text.startswith("https://") else ""


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def changed_metadata_rows(original: pd.DataFrame, edited: pd.DataFrame) -> list[dict[str, str]]:
    """Linhas cujo diretor ou gêneros mudaram de fato.

    Ambos os quadros usam as colunas film_key, director e genres. Só as linhas
    alteradas são devolvidas, para não marcar como "manual" o que veio do TMDB.
    """
    if original.empty or edited.empty:
        return []
    base = {
        str(row["film_key"]): (_clean_text(row.get("director")), _clean_text(row.get("genres")))
        for _, row in original.iterrows()
    }
    changes: list[dict[str, str]] = []
    for _, row in edited.iterrows():
        key = str(row["film_key"])
        director, genres = _clean_text(row.get("director")), _clean_text(row.get("genres"))
        if key in base and base[key] != (director, genres):
            changes.append({"film_key": key, "director": director, "genres": genres})
    return changes
