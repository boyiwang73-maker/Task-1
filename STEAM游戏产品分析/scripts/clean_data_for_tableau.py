"""
Clean Steam timeline data into Tableau/HTML-friendly flat tables.

The source dashboard stores each year as nested JSON. This script standardizes
price buckets, extracts yearly metrics, normalizes repeated structures such as
genres, prices, word-cloud terms and recommended games, then writes clean CSV
files plus a SQLite database for SQL filtering.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_DIR = DATA_DIR / "tableau"
SQLITE_PATH = DATA_DIR / "steam_analysis.sqlite"

PRICE_ORDER = ["Free", "0-5", "5-10", "10-15", "15-20", "20-30", "30-50", "50+"]


def clean_price_range(value: object) -> object:
    if not isinstance(value, str):
        return value
    if value.endswith("-5") and not value[0].isdigit():
        return "0-5"
    return value


def split_price_distribution(price_distribution: dict, price_ratings: dict) -> list[dict]:
    rows = []
    for price_range, count in price_distribution.items():
        cleaned = clean_price_range(price_range)
        if cleaned == "0-5":
            # Source data only stores one mixed 0-5 bucket, so keep paid 0-5 factual
            # and expose Free as an explicit zero row instead of implying it was measured.
            rows.append({"price_range": "Free", "source_price_range": price_range, "game_count": 0, "avg_positive_ratio_pct": None})
            rows.append({"price_range": "0-5", "source_price_range": price_range, "game_count": count, "avg_positive_ratio_pct": price_ratings.get(price_range)})
        else:
            rows.append({"price_range": cleaned, "source_price_range": price_range, "game_count": count, "avg_positive_ratio_pct": price_ratings.get(price_range)})
    present = {r["price_range"] for r in rows}
    for name in PRICE_ORDER:
        if name not in present:
            rows.append({"price_range": name, "source_price_range": name, "game_count": 0, "avg_positive_ratio_pct": None})
    order = {name: idx for idx, name in enumerate(PRICE_ORDER)}
    return sorted(rows, key=lambda row: order.get(row["price_range"], 99))


def preferred_price_from_rows(price_rows: list[dict]) -> tuple[object, object]:
    eligible = [
        r for r in price_rows
        if r["game_count"] >= 20 and r["avg_positive_ratio_pct"] is not None and r["price_range"] != "Free"
    ]
    if not eligible:
        eligible = [r for r in price_rows if r["game_count"] > 0 and r["avg_positive_ratio_pct"] is not None]
    if not eligible:
        return None, None
    best = max(eligible, key=lambda r: r["avg_positive_ratio_pct"] * min(1.0, r["game_count"] / 100))
    return best["price_range"], best["avg_positive_ratio_pct"]


def load_timeline() -> dict:
    path = DATA_DIR / "timeline_data.json"
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_table(df: pd.DataFrame, name: str, conn: sqlite3.Connection) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_DIR / f"{name}.csv", index=False, encoding="utf-8-sig")
    df.to_sql(name, conn, if_exists="replace", index=False)


def normalize_timeline(data: dict) -> dict[str, pd.DataFrame]:
    yearly = data["yearly"]
    rows_yearly = []
    rows_genre = []
    rows_price = []
    rows_playtime = []
    rows_wordcloud = []
    rows_top_games = []
    rows_best_genre_games = []
    rows_trend = []
    rows_genre_trend = []

    for year_text, payload in yearly.items():
        year = int(year_text)
        metrics = payload.get("metrics", {})
        profile = payload.get("profile", {})
        price_rows_for_year = split_price_distribution(
            payload.get("price_distribution", {}),
            payload.get("price_ratings", {}),
        )
        preferred_price_range, preferred_price_rating = preferred_price_from_rows(price_rows_for_year)

        rows_yearly.append(
            {
                "year": year,
                "n_games": metrics.get("n_games"),
                "n_total_raw": metrics.get("n_total"),
                "filtered_coverage_pct": round(
                    metrics.get("n_games", 0) / metrics.get("n_total", 1) * 100, 2
                )
                if metrics.get("n_total")
                else None,
                "avg_price": metrics.get("avg_price"),
                "median_price": metrics.get("median_price"),
                "avg_positive_ratio_pct": metrics.get("avg_positive_ratio"),
                "median_positive_ratio_pct": metrics.get("median_positive_ratio"),
                "avg_playtime_hours": metrics.get("avg_playtime"),
                "median_playtime_hours": metrics.get("median_playtime"),
                "avg_reviews": metrics.get("avg_reviews"),
                "total_reviews": metrics.get("total_reviews"),
                "avg_owners": metrics.get("avg_owners"),
                "top_genre": profile.get("top_genre"),
                "top_genre_count": profile.get("top_genre_count"),
                "top_genre_pct": profile.get("top_genre_pct"),
                "preferred_price_range": preferred_price_range or clean_price_range(profile.get("preferred_price_range")),
                "preferred_price_rating_pct": preferred_price_rating or profile.get("preferred_price_rating"),
                "longest_playtime_genre": profile.get("longest_playtime_genre"),
                "longest_playtime_hours": profile.get("longest_playtime_hours"),
                "top_tag_1": (profile.get("top_tags") or [None, None, None])[0],
                "top_tag_2": (profile.get("top_tags") or [None, None, None])[1],
                "top_tag_3": (profile.get("top_tags") or [None, None, None])[2],
            }
        )

        genre_distribution = payload.get("genre_distribution", {})
        genre_ratings = payload.get("genre_ratings", {})
        for genre, game_count in genre_distribution.items():
            rating = genre_ratings.get(genre, {})
            rows_genre.append(
                {
                    "year": year,
                    "genre": genre,
                    "game_count": game_count,
                    "genre_share_pct": round(game_count / metrics.get("n_games", 1) * 100, 2)
                    if metrics.get("n_games")
                    else None,
                    "avg_positive_ratio_pct": rating.get("mean"),
                    "median_positive_ratio_pct": rating.get("median"),
                    "rating_sample_games": rating.get("n"),
                }
            )

        for price_row in price_rows_for_year:
            game_count = price_row["game_count"]
            rows_price.append(
                {
                    "year": year,
                    "price_range": price_row["price_range"],
                    "source_price_range": price_row["source_price_range"],
                    "game_count": game_count,
                    "price_share_pct": round(game_count / metrics.get("n_games", 1) * 100, 2)
                    if metrics.get("n_games")
                    else None,
                    "avg_positive_ratio_pct": price_row["avg_positive_ratio_pct"],
                }
            )

        for playtime_range, game_count in payload.get("playtime_distribution", {}).items():
            rows_playtime.append(
                {
                    "year": year,
                    "playtime_range": playtime_range,
                    "game_count": game_count,
                    "playtime_share_pct": round(game_count / metrics.get("n_games", 1) * 100, 2)
                    if metrics.get("n_games")
                    else None,
                }
            )

        for rank, item in enumerate(payload.get("wordcloud", []), start=1):
            rows_wordcloud.append(
                {
                    "year": year,
                    "rank": rank,
                    "word": item.get("word"),
                    "normalized_value": item.get("value"),
                    "raw_count": item.get("count"),
                }
            )

        for item in payload.get("top5", []):
            rows_top_games.append(
                {
                    "year": year,
                    "rank": item.get("rank"),
                    "appid": item.get("appid"),
                    "name": item.get("name"),
                    "genre": item.get("genre"),
                    "price": item.get("price"),
                    "positive_ratio_pct": item.get("positive_ratio"),
                    "reviews": item.get("reviews"),
                    "playtime_hours": item.get("playtime"),
                    "score": item.get("score"),
                }
            )

        for item in payload.get("best_by_genre", []):
            rows_best_genre_games.append(
                {
                    "year": year,
                    "appid": item.get("appid"),
                    "genre": item.get("genre"),
                    "name": item.get("name"),
                    "score": item.get("score"),
                    "positive_ratio_pct": item.get("positive_ratio"),
                    "price": item.get("price"),
                    "games_in_genre": item.get("n_in_genre"),
                }
            )

    trends = data.get("trends", {})
    years = trends.get("years", [])
    for idx, year in enumerate(years):
        rows_trend.append(
            {
                "year": year,
                "n_games": trends.get("n_games", [None] * len(years))[idx],
                "n_total_raw": trends.get("n_total", [None] * len(years))[idx],
                "median_price": trends.get("median_price", [None] * len(years))[idx],
                "median_positive_ratio_pct": trends.get(
                    "median_positive_ratio", [None] * len(years)
                )[idx],
                "avg_playtime_hours": trends.get("avg_playtime", [None] * len(years))[idx],
            }
        )

    for genre in trends.get("major_genres", []):
        counts = trends.get("genre_count_trend", {}).get(genre, [])
        ratings = trends.get("genre_rating_trend", {}).get(genre, [])
        for idx, year in enumerate(years):
            rows_genre_trend.append(
                {
                    "year": year,
                    "genre": genre,
                    "game_count": counts[idx] if idx < len(counts) else None,
                    "avg_positive_ratio_pct": ratings[idx] if idx < len(ratings) else None,
                }
            )

    return {
        "yearly_metrics": pd.DataFrame(rows_yearly),
        "genre_yearly": pd.DataFrame(rows_genre),
        "price_yearly": pd.DataFrame(rows_price),
        "playtime_yearly": pd.DataFrame(rows_playtime),
        "wordcloud_yearly": pd.DataFrame(rows_wordcloud),
        "top_games_yearly": pd.DataFrame(rows_top_games),
        "best_games_by_genre_yearly": pd.DataFrame(rows_best_genre_games),
        "trend_yearly": pd.DataFrame(rows_trend),
        "genre_trend_yearly": pd.DataFrame(rows_genre_trend),
    }


def main() -> None:
    if SQLITE_PATH.exists():
        os.remove(SQLITE_PATH)

    data = load_timeline()
    tables = normalize_timeline(data)

    with sqlite3.connect(SQLITE_PATH) as conn:
        for name, df in tables.items():
            write_table(df, name, conn)

    print(f"Exported {len(tables)} tables")
    print(f"CSV directory: {OUT_DIR}")
    print(f"SQLite database: {SQLITE_PATH}")


if __name__ == "__main__":
    main()
