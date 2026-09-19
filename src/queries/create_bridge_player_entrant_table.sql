CREATE TABLE IF NOT EXISTS bridge_player_entrant (
    tournament_id TEXT NOT NULL,
    entrant_id TEXT NOT NULL,
    player_id TEXT NOT NULL,
    substituted_player_id TEXT,
    tournament_specific_gamer_tag TEXT NOT NULL,
    FOREIGN KEY(tournament_id) REFERENCES tournaments(tournament_id),
    FOREIGN KEY(player_id) REFERENCES links(player_id),
    FOREIGN KEY(substituted_player_id) REFERENCES links(player_id),
    PRIMARY KEY(tournament_id, entrant_id, player_id)
)