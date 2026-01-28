from __future__ import annotations

from typing import Any, Iterable


_MPAA_ORDER: dict[str, int] = {
    "G": 0,
    "PG": 1,
    "PG-13": 2,
    "R": 3,
    "NC-17": 4,
}


def _as_rating(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    v = value.strip().upper()
    # Normalize common variants
    v = v.replace("PG13", "PG-13").replace("NC17", "NC-17")
    return v


def getMoviesByRating(requiredRating: str, movieData: Iterable[dict[str, Any]]):
    """
    Filter movies by MPAA rating.

    Includes movies whose rating is <= requiredRating in restrictiveness
    (e.g. requiredRating='PG-13' includes 'G', 'PG', 'PG-13').

    Expects each movie dict to contain an MPAA rating under the key 'age_rating'
    (matches this codebase's Movie model/seed shape).

    Sorting:
    - Results are sorted by 'popularity' descending (missing/invalid popularity treated as 0).

    Invalid input handling:
    - If requiredRating is not a known MPAA rating, returns an empty list.
    """
    req = _as_rating(requiredRating)
    if req is None or req not in _MPAA_ORDER:
        return []

    req_level = _MPAA_ORDER[req]

    def rating_ok(movie: dict[str, Any]) -> bool:
        movie_rating = _as_rating(movie.get("age_rating"))
        if movie_rating is None:
            return False
        level = _MPAA_ORDER.get(movie_rating)
        if level is None:
            return False
        return level <= req_level

    def popularity(movie: dict[str, Any]) -> float:
        val = movie.get("popularity", 0)
        try:
            return float(val)
        except (TypeError, ValueError):
            return 0.0

    filtered = [m for m in movieData if rating_ok(m)]
    filtered.sort(key=popularity, reverse=True)
    return filtered

