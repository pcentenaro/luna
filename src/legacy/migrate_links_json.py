# Migrates links.json to SQLite3

import json
import sqlite3
from pathlib import Path

links_file_path = Path(__file__).resolve().parent.parent.parent / "data" / "links.json"
with open(links_file_path) as links_file:
    links = json.load(links_file)
connection = sqlite3.connect("data/luna.db")
cursor = connection.cursor()

for key in links:
    row = links[key]
    cursor.execute(f"INSERT INTO links VALUES({row["startgg_player_id"]}, {row["discord_user_id"]}, \"{row["startgg_gamer_tag"]}\", \"{row["startgg_prefix"]}\", \"{row["updated_at"]}\")")
    connection.commit()