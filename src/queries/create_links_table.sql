CREATE TABLE IF NOT EXISTS links (
    startgg_player_id TEXT PRIMARY KEY NOT NULL,
    discord_user_id TEXT UNIQUE,
    startgg_gamer_tag TEXT NOT NULL,
    startgg_prefix TEXT,
    pgrs_player_name TEXT,
    pgrs_player_id TEXT,
    updated_at TEXT NOT NULL
)
