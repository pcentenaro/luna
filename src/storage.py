import json
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
    def __init__(self, links_path: Path = DEFAULT_LINKS_PATH):
        self.links_path = links_path
        self.links_path.parent.mkdir(parents=True, exist_ok=True)

    def set_startgg_link(
        self,
        discord_user_id: int,
        startgg_player_id: int,
        gamer_tag: str | None,
        prefix: str | None,
    ):
        data = self._load()
        data[str(discord_user_id)] = {
            "discord_user_id": discord_user_id,
            "startgg_player_id": startgg_player_id,
            "startgg_gamer_tag": gamer_tag,
            "startgg_prefix": prefix,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save(data)

    def get_startgg_link(self, discord_user_id: int) -> dict | None:
        return self._load().get(str(discord_user_id))

    def get_startgg_link_by_player_id(self, startgg_player_id: int) -> dict | None:
        for link in self._load().values():
            if str(link.get("startgg_player_id")) == str(startgg_player_id):
                return link
        return None

    def delete_startgg_link(self, discord_user_id: int) -> bool:
        data = self._load()
        removed = data.pop(str(discord_user_id), None)
        if removed is None:
            return False

        self._save(data)
        return True

    def _load(self) -> dict:
        if not self.links_path.exists():
            return {}

        with self.links_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _save(self, data: dict):
        temporary_path = self.links_path.with_suffix(".tmp")
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
            file.write("\n")

        temporary_path.replace(self.links_path)


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
