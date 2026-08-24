CREATE TABLE IF NOT EXISTS links (
    discord_user_id INTEGER PRIMARY KEY,
    startgg_user_id INTEGER NOT NULL,
    startgg_gamer_tag TEXT,
    startgg_prefix TEXT,
    updated_at TEXT
)