CREATE TABLE IF NOT EXISTS tournament_sets (
    tournament_id TEXT NOT NULL,
    phase_id TEXT NOT NULL,
    group_id TEXT NOT NULL,
    match_id TEXT NOT NULL,
    player1_id TEXT NOT NULL,
    player2_id TEXT NOT NULL,
    player1_score INT,
    player2_score INT,
    player1_standing INT,
    player2_standing INT,
    FOREIGN KEY(tournament_id) REFERENCES tournaments(tournament_id),
    FOREIGN KEY(phase_id) REFERENCES tournament_phases(phase_id),
    PRIMARY KEY(tournament_id, phase_id, group_id, match_id)
)