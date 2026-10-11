"""Prepare pool statistics from shared state without Discord or network access."""

from copy import deepcopy

from images.bracket_data import build_bracket_data
from seeding import build_player_standings, is_pool_group, rank_players, split_into_brackets


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


def build_pools_summary_data(event_state: dict, event_id: int) -> dict:
    """Calculate destinations once across all pools, using the seeding rules.

    Status is unavailable, provisional, or completed (all pools finished).
    Review flags are independent: a completed calculation can still contain ties.
    Destinations are calculated assignments, not brackets published on start.gg.
    Do not split an incomplete or stale collection into misleading bracket sizes.
    """
    if event_state.get("event_id") is None or str(event_state["event_id"]) != str(event_id):
        raise ValueError("The requested event is not loaded in the shared state.")
    pools = [
        build_pool_data(event_state, event_id, int(group["id"]))
        for phase in event_state.get("phases", [])
        for group in event_state.get("phase_groups", {}).get(int(phase["id"]), [])
        if is_pool_group(phase, group)
    ]
    result = {
        "event_id": event_state["event_id"],
        "event_name": event_state.get("event_name"),
        "updated_at": event_state.get("updated_at"),
        "pools": pools, "ranked": [], "brackets": [], "destinations": {},
        "ranking_warnings": [],
        "classification_status": "unavailable",
        "requires_review": False,

    }
    if not pools:
        result["ranking_warnings"] = ["No pools are available to calculate destinations."]
        return result
    if any(pool["standings"] is None or pool["standings_error"]
           or not pool["players"] or len(pool["players"]) != len(pool["standings"])
           for pool in pools):
        result["ranking_warnings"] = ["Complete, current standings are required for all pools to calculate destinations."]
        return result
    players = [player for pool in pools for player in pool["players"]]
    if len({player.entrant_id for player in players}) != len(players):
        raise ValueError("An entrant appears in multiple pools; a unique pool stage is required.")
    ranked, warnings = rank_players(players)
    brackets = split_into_brackets(ranked)
    destinations_by_key = {}
    for bracket in brackets:
        for player in bracket.players:
            destinations_by_key.setdefault(player.competitive_key(), set()).add(bracket.name)
    tied_entrant_ids = {
        player.entrant_id for player in ranked
        if len(destinations_by_key[player.competitive_key()]) > 1
    }
    classification_status = (
        "completed" if all(str(pool["phase_group"].get("state")).casefold() in {"3", "completed"}
                           for pool in pools) else "provisional"
    )
    result.update(
        ranked=ranked, brackets=brackets, ranking_warnings=warnings,
        classification_status=classification_status, requires_review=bool(tied_entrant_ids),
        destinations={
            player.entrant_id: {
                "bracket": bracket.name, "seed": seed,
                "requires_review": player.entrant_id in tied_entrant_ids,
            }
            for bracket in brackets
            for seed, player in enumerate(bracket.players, start=1)
        },
    )
    return result
