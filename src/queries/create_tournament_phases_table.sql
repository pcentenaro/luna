CREATE TABLE IF NOT EXISTS tournament_phases (
    tournament_id TEXT NOT NULL,
    phase_id TEXT NOT NULL,
    phase_order INT NOT NULL,
    phase_type TEXT NOT NULL,
    phase_name TEXT NOT NULL,
    num_players INT NOT NULL,
    FOREIGN KEY(tournament_id) REFERENCES tournaments(tournament_id),
    PRIMARY KEY(phase_id, tournament_id)
)