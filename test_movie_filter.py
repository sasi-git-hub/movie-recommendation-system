import unittest

from movie_filter import getMoviesByRating


SAMPLE_MOVIES = [
    {"title": "G-High", "age_rating": "G", "popularity": 90},
    {"title": "G-Low", "age_rating": "G", "popularity": 10},
    {"title": "PG", "age_rating": "PG", "popularity": 80},
    {"title": "PG-13", "age_rating": "PG-13", "popularity": 70},
    {"title": "R", "age_rating": "R", "popularity": 60},
    {"title": "NC-17", "age_rating": "NC-17", "popularity": 50},
]


class TestGetMoviesByRating(unittest.TestCase):
    def test_required_g(self):
        titles = [m["title"] for m in getMoviesByRating("G", SAMPLE_MOVIES)]
        self.assertEqual(titles, ["G-High", "G-Low"])

    def test_required_pg(self):
        titles = [m["title"] for m in getMoviesByRating("PG", SAMPLE_MOVIES)]
        self.assertEqual(titles, ["G-High", "PG", "G-Low"])

    def test_required_pg_13(self):
        titles = [m["title"] for m in getMoviesByRating("PG-13", SAMPLE_MOVIES)]
        self.assertEqual(titles, ["G-High", "PG", "PG-13", "G-Low"])

    def test_required_r(self):
        titles = [m["title"] for m in getMoviesByRating("R", SAMPLE_MOVIES)]
        self.assertEqual(titles, ["G-High", "PG", "PG-13", "R", "G-Low"])

    def test_required_nc_17(self):
        titles = [m["title"] for m in getMoviesByRating("NC-17", SAMPLE_MOVIES)]
        self.assertEqual(titles, ["G-High", "PG", "PG-13", "R", "NC-17", "G-Low"])

    def test_invalid_required_rating_returns_empty(self):
        self.assertEqual(getMoviesByRating("NOT-A-RATING", SAMPLE_MOVIES), [])
        self.assertEqual(getMoviesByRating("", SAMPLE_MOVIES), [])
        self.assertEqual(getMoviesByRating(None, SAMPLE_MOVIES), [])  # type: ignore[arg-type]

    def test_ignores_unknown_movie_ratings_and_missing_ratings(self):
        movies = [
            {"title": "Unknown", "age_rating": "X", "popularity": 999},
            {"title": "Missing", "popularity": 888},
            {"title": "OK", "age_rating": "PG", "popularity": 1},
        ]
        titles = [m["title"] for m in getMoviesByRating("PG", movies)]
        self.assertEqual(titles, ["OK"])

    def test_sorting_popularity_missing_or_invalid_treated_as_zero(self):
        movies = [
            {"title": "A", "age_rating": "PG", "popularity": "not-a-number"},
            {"title": "B", "age_rating": "PG"},  # missing popularity
            {"title": "C", "age_rating": "PG", "popularity": 2},
        ]
        titles = [m["title"] for m in getMoviesByRating("PG", movies)]
        self.assertEqual(titles, ["C", "A", "B"])


if __name__ == "__main__":
    unittest.main()

