"""Render a pool summary from the same isolated snapshot as the bracket."""

from xml.etree.ElementTree import Element, SubElement


POOL_CARD_WIDTH = 480
POOL_CARD_HEIGHT = 240


def create_pool_card(data: dict, x: int = 0, y: int = 0) -> Element:
    """Return a fixed-size SVG group; counts describe cached sets, not standings."""
    group = data.get("phase_group") or {}
    phase = data.get("phase") or {}
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
    SubElement(card, "rect", {"width": str(POOL_CARD_WIDTH), "height": str(POOL_CARD_HEIGHT),
                              "rx": "12", "fill": "#111a2d", "stroke": "#3b4b67"})

    def text(value, tx, ty, size, fill, limit):
        full = " ".join(str(value).split())
        node = SubElement(card, "text", {"x": str(tx), "y": str(ty),
                                         "font-size": str(size), "fill": fill})
        node.text = full if len(full) <= limit else full[:limit - 3] + "..."
        if node.text != full:
            SubElement(node, "title").text = full

    text(label, 24, 36, 16, "#f6d54a", 27)
    text(phase.get("name") or "Bracket", 24, 64, 12, "#aab6ce", 36)
    text(status, 24, 94, 12, color, 36)
    SubElement(card, "line", {"x1": "24", "y1": "112", "x2": "456", "y2": "112",
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
    return card
