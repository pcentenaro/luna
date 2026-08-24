CREATE TABLE IF NOT EXISTS links (
    discord_user_id INTEGER UNIQUE,
    startgg_player_id INTEGER UNIQUE,
    startgg_gamer_tag TEXT,
    startgg_prefix TEXT,
    updated_at TEXT,
    PRIMARY KEY (discord_user_id, startgg_player_id)
)