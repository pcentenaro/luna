DROP TABLE IF EXISTS glicko_ratings;

CREATE TABLE IF NOT EXISTS glicko_ratings (
    name TEXT UNIQUE NOT NULL,
    rank INT NOT NULL,
    rating INT UNIQUE NOT NULL
);