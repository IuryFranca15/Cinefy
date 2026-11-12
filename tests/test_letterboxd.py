from cinefy.letterboxd import parse_letterboxd_uploads


class Upload:
    def __init__(self, name, content):
        self.name = name
        self._content = content.encode("utf-8")

    def getvalue(self):
        return self._content


def make_uploads(order):
    files = {
        "diary.csv": "Date,Name,Year,Letterboxd URI,Rating,Rewatch,Tags\n2024-02-01,Amélie,2001,https://letterboxd.com/film/amelie/,4.5,No,france\n2024-03-10,Amélie,2001,https://letterboxd.com/film/amelie/,5,Yes,comfort\n",
        "ratings.csv": "Name,Year,Letterboxd URI,Rating\nAmélie,2001,https://letterboxd.com/film/amelie/,4\n",
        "watchlist.csv": "Name,Year,Letterboxd URI\nAmélie,2001,https://letterboxd.com/film/amelie/\n",
    }
    return [Upload(name, files[name]) for name in order]


def test_letterboxd_import_is_independent_of_csv_upload_order():
    first = parse_letterboxd_uploads(make_uploads(["diary.csv", "ratings.csv", "watchlist.csv"]))
    second = parse_letterboxd_uploads(make_uploads(["watchlist.csv", "ratings.csv", "diary.csv"]))
    left = first.iloc[0]
    right = second.iloc[0]
    assert left["film_key"] == right["film_key"]
    assert left["rating"] == right["rating"] == 4.0
    assert left["watched_date"] == right["watched_date"] == "2024-03-10"
    assert bool(left["is_watchlist"]) and bool(right["is_watchlist"])
    assert bool(left["is_rewatch"]) and bool(right["is_rewatch"])
    assert left["tags"] == right["tags"] == "france, comfort"



def test_partial_letterboxd_import_does_not_clear_unknown_watchlist_flag():
    imported = parse_letterboxd_uploads(make_uploads(["diary.csv"]))
    assert imported.iloc[0]["is_watchlist"] is None
