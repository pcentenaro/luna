import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_LINKS_PATH = Path(__file__).resolve().parent.parent / "data" / "links.json"


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
