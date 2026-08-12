-- Steam Tableau/HTML CSV export SQL
-- Usage:
--   cd github_release
--   python scripts/clean_data_for_tableau.py
--   sqlite3 data/steam_analysis.sqlite ".read sql/export_tableau_csv.sql"
--
-- This script keeps only the filtered and chart-ready fields used by the
-- dashboard. Output CSV files are written to data/tableau/.

.headers on
.mode csv

-- 1. Year KPI cards and yearly overview table.
.once data/tableau/yearly_metrics.csv
SELECT
  year,
  n_games,
  n_total_raw,
  filtered_coverage_pct,
  ROUND(median_price, 2) AS median_price,
  ROUND(median_positive_ratio_pct, 2) AS median_positive_ratio_pct,
  ROUND(avg_playtime_hours, 2) AS avg_playtime_hours,
  total_reviews,
  top_genre,
  top_genre_count,
  top_genre_pct,
  preferred_price_range,
  preferred_price_rating_pct,
  longest_playtime_genre,
  longest_playtime_hours,
  top_tag_1,
  top_tag_2,
  top_tag_3
FROM yearly_metrics
WHERE year BETWEEN 2006 AND 2025
ORDER BY year;

-- 2. Genre distribution bar chart.
.once data/tableau/genre_yearly.csv
SELECT
  year,
  genre,
  game_count,
  genre_share_pct,
  avg_positive_ratio_pct,
  median_positive_ratio_pct,
  rating_sample_games
FROM genre_yearly
WHERE year BETWEEN 2006 AND 2025
  AND game_count > 0
ORDER BY year, game_count DESC;

-- 3. Price bucket chart.
.once data/tableau/price_yearly.csv
SELECT
  year,
  price_range,
  source_price_range,
  game_count,
  price_share_pct,
  avg_positive_ratio_pct
FROM price_yearly
WHERE year BETWEEN 2006 AND 2025
ORDER BY
  year,
  CASE price_range
    WHEN 'Free' THEN 0
    WHEN '0-5' THEN 1
    WHEN '5-10' THEN 2
    WHEN '10-15' THEN 3
    WHEN '15-20' THEN 4
    WHEN '20-30' THEN 5
    WHEN '30-50' THEN 6
    WHEN '50+' THEN 7
    ELSE 99
  END;

-- 4. Playtime distribution chart.
.once data/tableau/playtime_yearly.csv
SELECT
  year,
  playtime_range,
  game_count,
  playtime_share_pct
FROM playtime_yearly
WHERE year BETWEEN 2006 AND 2025
ORDER BY year, game_count DESC;

-- 5. Keyword block / word cloud.
.once data/tableau/wordcloud_yearly.csv
SELECT
  year,
  rank,
  word,
  normalized_value,
  raw_count
FROM wordcloud_yearly
WHERE year BETWEEN 2006 AND 2025
  AND rank <= 60
ORDER BY year, rank;

-- 6. Recommended games TOP 5.
.once data/tableau/top_games_yearly.csv
SELECT
  year,
  rank,
  appid,
  name,
  genre,
  price,
  positive_ratio_pct,
  reviews,
  playtime_hours,
  score
FROM top_games_yearly
WHERE year BETWEEN 2006 AND 2025
  AND rank <= 5
ORDER BY year, rank;

-- 7. Best game by each genre.
.once data/tableau/best_games_by_genre_yearly.csv
SELECT
  year,
  appid,
  genre,
  name,
  score,
  positive_ratio_pct,
  price,
  games_in_genre
FROM best_games_by_genre_yearly
WHERE year BETWEEN 2006 AND 2025
ORDER BY year, score DESC;

-- 8. Long-term trend lines.
.once data/tableau/trend_yearly.csv
SELECT
  year,
  n_games,
  n_total_raw,
  ROUND(median_price, 2) AS median_price,
  ROUND(median_positive_ratio_pct, 2) AS median_positive_ratio_pct,
  ROUND(avg_playtime_hours, 2) AS avg_playtime_hours
FROM trend_yearly
WHERE year BETWEEN 2006 AND 2025
ORDER BY year;

-- 9. Major genre trend stacked/line charts.
.once data/tableau/genre_trend_yearly.csv
SELECT
  year,
  genre,
  game_count,
  avg_positive_ratio_pct
FROM genre_trend_yearly
WHERE year BETWEEN 2006 AND 2025
ORDER BY year, genre;
