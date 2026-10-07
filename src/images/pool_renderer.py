"""Render a pool summary from the same isolated snapshot as the bracket."""

from xml.etree.ElementTree import Element, SubElement


POOL_CARD_WIDTH = 640
POOL_CARD_HEIGHT = 300
POOL_ROW_HEIGHT = 40


def create_pool_card(data: dict, x: int = 0, y: int = 0) -> Element:
    """Return a pool card whose height grows with its standings table."""
    group = data.get("phase_group") or {}
    phase = data.get("phase") or {}
    players = sorted(data.get("players") or [], key=lambda player: (
        player.placement, player.name.casefold(), player.entrant_id
    ))
    height = POOL_CARD_HEIGHT + max(1, len(players)) * POOL_ROW_HEIGHT
    sets = data.get("sets") or []
    states = [str(match.get("state")).casefold() for match in sets]
    state = str(group.get("state")).casefold()
    status, color = {
        "1": ("Pending", "#aab6ce"), "created": ("Pending", "#aab6ce"),
        "2": ("In progress", "#67c8ff"), "active": ("In progress", "#67c8ff"),
        "3": ("Completed", "#88dc9b"), "completed": ("Completed", "#88dc9b"),
    }.get(state, ("Unknown", "#aab6ce"))
    label = f"Pool {group.get('displayIdentifier') or group.get('id', '?')}"
    card = Element("g", {"transform": f"translate({x} {y})",
                         "font-family": "'Press Start 2P'", "font-weight": "normal"})
    SubElement(card, "title").text = f"{phase.get('name') or 'Bracket'} / {label}"
    SubElement(card, "rect", {"width": str(POOL_CARD_WIDTH), "height": str(height),
                              "rx": "12", "fill": "#111a2d", "stroke": "#3b4b67"})

    def text(value, tx, ty, size, fill, limit):
        full = " ".join(str(value).split())
        node = SubElement(card, "text", {"x": str(tx), "y": str(ty),
                                         "font-size": str(size), "fill": fill})
        node.text = full if len(full) <= limit else full[:limit - 3] + "..."
        if node.text != full:
            SubElement(node, "title").text = full

    text(label, 24, 36, 16, "#f6d54a", 37)
    text(phase.get("name") or "Bracket", 24, 64, 12, "#aab6ce", 49)
    text(status, 24, 94, 12, color, 36)
    SubElement(card, "line", {"x1": "24", "y1": "112", "x2": str(POOL_CARD_WIDTH - 24), "y2": "112",
                              "stroke": "#28344c"})
    counts = (
        ("Completed", sum(value in {"3", "completed"} for value in states)),
        ("Ready", sum(value in {"4", "ready"} for value in states)),
        ("In play", sum(value in {"2", "active"} for value in states)),
    )
    for column, (name, count) in enumerate(counts):
        tx = 24 + column * 144
        text(count, tx, 151, 20, "#f3f5fb", 6)
        text(name, tx, 176, 10, "#aab6ce", 13)
    text(f"Cached sets: {len(sets)}", 24, 216, 10, "#aab6ce", 43)
    for heading, tx in (("Pos", 24), ("Player", 80), ("Sets W-L", 388), ("Points +/-", 500)):
        text(heading, tx, 248, 10, "#aab6ce", 11)
    for index, player in enumerate(players):
        top = 260 + index * POOL_ROW_HEIGHT
        SubElement(card, "line", {"x1": "24", "y1": str(top), "x2": str(POOL_CARD_WIDTH - 24),
                                  "y2": str(top), "stroke": "#28344c"})
        text(player.placement, 24, top + 26, 10, "#f6d54a", 4)
        text(player.name, 80, top + 26, 10, "#f3f5fb", 28)
        text(f"{player.match_wins}-{player.match_losses}", 388, top + 26, 10, "#f3f5fb", 9)
        text(f"{player.points_for}-{player.points_against}", 500, top + 26, 10, "#f3f5fb", 11)
    if not players:
        message = "Standings unavailable" if data.get("standings") is None else "No ranked players"
        text(message, 24, 286, 10, "#aab6ce", 59)
    if data.get("standings_error"):
        note = "Standings outdated" if data.get("standings") is not None else "Standings unavailable"
        text(note, 24, height - 16, 10, "#f6d54a", 59)
    return card
