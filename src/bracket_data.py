"""Select an isolated bracket snapshot without importing Discord or querying start.gg."""

from copy import deepcopy


def build_bracket_data(event_state: dict, event_id: int, phase_group_id: int) -> dict:
    """Return event metadata, phase, phase_group and all sets for one cached group.

    Set/slot fields keep the start.gg shape, including null entrants, scores and
    prerequisite references. No rounds or results are inferred. The caller can
    prepare the returned data for rendering without changing the shared cache.
    """
    if event_state.get("event_id") is None or str(event_state["event_id"]) != str(event_id):
        raise ValueError("The requested event is not loaded in the shared state.")

    for phase in event_state.get("phases", []):
        for group in event_state.get("phase_groups", {}).get(int(phase["id"]), []):
            if str(group["id"]) != str(phase_group_id):
                continue
            return deepcopy({
                "event_id": event_state["event_id"],
                "event_name": event_state.get("event_name"),
                "updated_at": event_state.get("updated_at"),
                "phase": phase,
                "phase_group": group,
                "sets": [
                    match["set"] for match in event_state.get("matches", [])
                    if str(match["phase"]["id"]) == str(phase["id"])
                    and str(match["phase_group"]["id"]) == str(group["id"])
                ],
            })

    raise ValueError("The requested pool or bracket is not in the shared event state.")
