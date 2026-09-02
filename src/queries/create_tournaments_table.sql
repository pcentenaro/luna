CREATE TABLE IF NOT EXISTS tournaments (
    tournament_id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    num_players INTEGER,
    url TEXT,
    game_name TEXT,
    date_timestamp INT
)