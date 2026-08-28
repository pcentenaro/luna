CREATE TABLE IF NOT EXISTS tournament_standings (
    tournament_id TEXT NOT NULL,
    phase_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    standing_id TEXT NOT NULL PRIMARY KEY,
    placement INT NOT NULL,
    player_id TEXT NOT NULL,
    FOREIGN KEY(tournament_id) REFERENCES tournaments(tournament_id),
    FOREIGN KEY(phase_id) REFERENCES tournament_phases(phase_id),
    FOREIGN KEY(player_id) REFERENCES links(startgg_player_id) 
)