from cinefy.tmdb_client import choose_automatic_match, normalize_title, rank_search_results


def test_normalize_title_removes_accents_and_punctuation():
    assert normalize_title("O Fabuloso Destino de Amélie Poulain!") == "o fabuloso destino de amelie poulain"


def test_rank_search_results_uses_year_to_distinguish_remakes():
    results = [
        {"id": 2, "title": "The Thing", "original_title": "The Thing", "release_date": "2011-10-12"},
        {"id": 1, "title": "The Thing", "original_title": "The Thing", "release_date": "1982-06-25"},
    ]
    ranked = rank_search_results("The Thing", 1982, results)
    assert ranked[0]["id"] == 1


def test_automatic_match_does_not_accept_weak_title_similarity():
    results = [{"id": 10, "title": "A Completely Different Movie", "original_title": "A Completely Different Movie", "release_date": "2001-01-01"}]
    assert choose_automatic_match("The Matrix", 1999, results) is None


def test_automatic_match_accepts_exact_title_and_year():
    results = [
        {"id": 2, "title": "Dune", "original_title": "Dune", "release_date": "1984-12-14"},
        {"id": 1, "title": "Dune", "original_title": "Dune", "release_date": "2021-09-15"},
    ]
    match = choose_automatic_match("Dune", 2021, results)
    assert match is not None
    assert match["id"] == 1
