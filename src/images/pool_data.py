"""Prepare pool statistics from shared state without Discord or network access."""

from copy import deepcopy

from images.bracket_data import build_bracket_data
from seeding import build_player_standings, is_pool_group


def build_pool_data(event_state: dict, event_id: int, phase_group_id: int) -> dict:
    """Keep standings freshness separate from the sets' snapshot time.

    Missing standings remain None; a successfully loaded empty list stays [].
    Players use the seeding calculation, without assigning destination brackets.
    """
    data = build_bracket_data(event_state, event_id, phase_group_id)
    group = data["phase_group"]
    if not is_pool_group(data["phase"], group):
        raise ValueError("The requested group is not a pool.")
    group_id = int(group["id"])
    data["standings"] = deepcopy(event_state.get("standings", {}).get(group_id))
    data["standings_updated_at"] = event_state.get("standings_updated_at", {}).get(group_id)
    data["standings_error"] = event_state.get("standings_errors", {}).get(group_id)
    data["players"] = build_player_standings(
        pool_id=group_id,
        pool_name=f"Pool {group.get('displayIdentifier') or group_id}",
        standings=data["standings"] or [],
        sets=data["sets"],
    )
    return data
