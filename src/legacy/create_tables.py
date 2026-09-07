import sqlite3
from pathlib import Path

queries = [
    (Path(__file__).resolve().parent.parent / "queries" / "create_links_table.sql").read_text(),
    (Path(__file__).resolve().parent.parent / "queries" / "create_tournaments_table.sql").read_text(),
    (Path(__file__).resolve().parent.parent / "queries" / "create_tournament_phases_table.sql").read_text(),
    (Path(__file__).resolve().parent.parent / "queries" / "create_tournament_sets_table.sql").read_text(),
    (Path(__file__).resolve().parent.parent / "queries" / "create_tournament_standings_table.sql").read_text(),
    (Path(__file__).resolve().parent.parent / "queries" / "create_bridge_player_entrant_table.sql").read_text()
]
connection = sqlite3.connect("data/luna.db")
cursor = connection.cursor()
for query in queries:
    cursor.execute(query)
connection.commit()