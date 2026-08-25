CREATE TABLE IF NOT EXISTS links (
    startgg_player_id TEXT PRIMARY KEY,
    discord_user_id TEXT UNIQUE,
    startgg_gamer_tag TEXT,
    startgg_prefix TEXT,
    updated_at TEXT
)