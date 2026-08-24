import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_LINKS_PATH = Path(__file__).resolve().parent.parent / "data" / "links.json"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "config.json"
DEFAULT_SCORE_TARGETS = {
    "default": 7,
    "final": 9,
    "grand_final": 10,
}


class LinkStore:
    def __init__(self):
        self.connection = sqlite3.connect("data/luna.db")
        self.connection.row_factory = lambda cursor, row: {key: value for key, value in zip([col[0] for col in cursor.description], row)}
        self.cursor = self.connection.cursor()
        self._create_tables()

    def _create_tables(self):
        queries = [(Path(__file__).parent / "queries" / "create_link_table.sql").read_text()]
        for query in queries:
           self.cursor.execute(query)

    def set_startgg_link(
        self,
        discord_user_id: int,
        startgg_player_id: int,
        gamer_tag: str | None,
        prefix: str | None,
    ):
        self.cursor.execute(f"INSERT INTO links VALUES({discord_user_id}, {startgg_player_id}, \"{gamer_tag}\", \"{prefix}\", \"{datetime.now(timezone.utc).isoformat()}\")")
        self.connection.commit()

    def get_startgg_link(self, discord_user_id: int) -> dict | None:
        self.cursor.execute(f"SELECT * FROM links WHERE discord_user_id = {discord_user_id}")
        return self.cursor.fetchone()

    def get_startgg_link_by_player_id(self, startgg_player_id: int) -> dict | None:
        self.cursor.execute(f"SELECT * FROM links WHERE startgg_player_id = {startgg_player_id}")
        return self.cursor.fetchone()

    def get_all_startgg_links(self) -> list[dict]:
        self.cursor.execute(f"SELECT * FROM links")
        return self.cursor.fetchall()

    def delete_startgg_link(self, discord_user_id: int) -> bool:
        self.cursor.execute(f"DELETE FROM links WHERE discord_user_id = {discord_user_id}")
        self.connection.commit()


class ConfigStore:
    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH):
        self.config_path = config_path
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def get_admin_role_id(self) -> int | None:
        admin_role_id = self._load().get("admin_role_id")
        return int(admin_role_id) if admin_role_id else None

    def set_admin_role_id(self, role_id: int):
        data = self._load()
        data["admin_role_id"] = str(role_id)
        self._save(data)

    def clear_admin_role_id(self) -> bool:
        data = self._load()
        removed = data.pop("admin_role_id", None)
        if removed is None:
            return False

        self._save(data)
        return True

    def get_active_event(self) -> dict | None:
        return self._load().get("active_event")

    def set_active_event(
        self,
        tournament_slug: str,
        event_slug: str,
        event_id: int,
        event_name: str,
    ):
        data = self._load()
        data["active_event"] = {
            "tournament_slug": tournament_slug,
            "event_slug": event_slug,
            "event_id": event_id,
            "event_name": event_name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save(data)

    def clear_active_event(self) -> bool:
        data = self._load()
        removed = data.pop("active_event", None)
        if removed is None:
            return False

        self._save(data)
        return True

    def get_score_targets(self) -> dict:
        score_targets = self._load().get("score_targets") or {}
        return {
            "default": int(score_targets.get("default") or DEFAULT_SCORE_TARGETS["default"]),
            "final": int(score_targets.get("final") or DEFAULT_SCORE_TARGETS["final"]),
            "grand_final": int(score_targets.get("grand_final") or DEFAULT_SCORE_TARGETS["grand_final"]),
        }

    def set_score_targets(self, default: int, final: int, grand_final: int):
        data = self._load()
        data["score_targets"] = {
            "default": int(default),
            "final": int(final),
            "grand_final": int(grand_final),
        }
        self._save(data)

    def _load(self) -> dict:
        if not self.config_path.exists():
            return {}

        with self.config_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _save(self, data: dict):
        temporary_path = self.config_path.with_suffix(".tmp")
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
            file.write("\n")

        temporary_path.replace(self.config_path)
