"""Render a pool summary from the same isolated snapshot as the bracket."""

from textwrap import wrap
from xml.etree.ElementTree import Element, SubElement, tostring


POOL_CARD_WIDTH = 800
POOL_CARD_HEIGHT = 300
POOL_ROW_HEIGHT = 40
BRACKET_COLORS = {
    "Maestro": "#ff8585", "Avanzado": "#67c8ff",
    "Intermedio": "#f6d54a", "Principiante": "#88dc9b",
    "Principal": "#ff8585", "Secundario": "#67c8ff", "Final": "#ff8585",
}


def create_pool_card(data: dict, x: int = 0, y: int = 0, *, summary: dict | None = None) -> Element:
    """Return a pool card whose height grows with its standings table."""
    group = data.get("phase_group") or {}
    phase = data.get("phase") or {}
    players = sorted(data.get("players") or [], key=lambda player: (
        player.placement, player.name.casefold(), player.entrant_id
    ))
    table_bottom = POOL_CARD_HEIGHT + max(1, len(players)) * POOL_ROW_HEIGHT
    height = table_bottom + (96 if summary is not None else 0)
    classification = (summary or {}).get("classification_status", "unavailable")
    destinations = (summary or {}).get("destinations", {}) if classification in {"provisional", "completed"} else {}
    if data.get("standings_error"):
        classification, destinations = "unavailable", {}
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
    for heading, tx in (("Pos", 24), ("Player", 80), ("Sets W-L", 388), ("Points +/-", 500), ("Destination", 640)):
        text(heading, tx, 248, 10, "#aab6ce", 11)
    for index, player in enumerate(players):
        top = 260 + index * POOL_ROW_HEIGHT
        SubElement(card, "line", {"x1": "24", "y1": str(top), "x2": str(POOL_CARD_WIDTH - 24),
                                  "y2": str(top), "stroke": "#28344c"})
        text(player.placement, 24, top + 26, 10, "#f6d54a", 4)
        destination = destinations.get(player.entrant_id, {})
        bracket = destination.get("bracket")
        player_color = BRACKET_COLORS.get(bracket, "#f3f5fb")
        text(player.name, 80, top + 26, 10, player_color, 28)
        destination_label = (bracket + ("*" if destination.get("requires_review") else "")) if bracket else "—"
        text(destination_label, 640, top + 26, 10, player_color, 13)
        text(f"{player.match_wins}-{player.match_losses}", 388, top + 26, 10, "#f3f5fb", 9)
        text(f"{player.points_for}-{player.points_against}", 500, top + 26, 10, "#f3f5fb", 11)
    if not players:
        message = "Standings unavailable" if data.get("standings") is None else "No ranked players"
        text(message, 24, 286, 10, "#aab6ce", 59)
    if summary is not None:
        classification_label = {
            "provisional": "Provisional destinations - pools still open",
            "completed": "Calculated destinations - pools completed",
        }.get(classification, "Destinations unavailable")
        text(classification_label, 24, table_bottom, 10, "#aab6ce", 75)
        if classification != "unavailable":
            for index, bracket in enumerate(summary.get("brackets", [])):
                text(bracket.name, 24 + index * 188, table_bottom + 28, 10,
                     BRACKET_COLORS.get(bracket.name, "#f3f5fb"), 17)
            if summary.get("requires_review"):
                text("* Unresolved tie - manual review required", 24, table_bottom + 52, 10, "#f6d54a", 75)
    if data.get("standings_error"):
        note = "Standings outdated" if data.get("standings") is not None else "Standings unavailable"
        text(note, 24, height - 16, 10, "#f6d54a", 59)
    return card


def create_pools_svg(summary: dict) -> str:
    """Arrange prepared pools in two columns, preserving their supplied order."""
    pools = summary.get("pools") or []
    margin, gap = 32, 32
    columns = min(2, max(1, len(pools)))
    width = margin * 2 + columns * POOL_CARD_WIDTH + (columns - 1) * gap
    title = " ".join(str(summary.get("event_name") or "Tournament").split()) or "Tournament"
    title_lines = wrap(title, width=(width - margin * 2) // 24)
    cards_top = 98 + len(title_lines) * 36 + 24
    content = Element("g", {"id": "pool-grid"})
    y = cards_top
    for start in range(0, len(pools), columns):
        cards = []
        for column, pool in enumerate(pools[start:start + columns]):
            card = create_pool_card(pool, x=margin + column * (POOL_CARD_WIDTH + gap),
                                    y=y, summary=summary)
            card.set("data-pool-id", str((pool.get("phase_group") or {}).get("id", "")))
            content.append(card)
            cards.append(card)
        y += max(int(card.find("rect").get("height")) for card in cards) + gap
    height = y if pools else cards_top + 80
    svg = Element("svg", {"xmlns": "http://www.w3.org/2000/svg",
                         "width": str(width), "height": str(height),
                         "viewBox": f"0 0 {width} {height}", "role": "img"})
    SubElement(svg, "title").text = f"{title} - Pool standings"
    SubElement(svg, "rect", {"width": str(width), "height": str(height), "fill": "#0b1020"})
    SubElement(svg, "rect", {"width": str(width), "height": "6", "fill": "#f6d54a"})
    heading = SubElement(svg, "g", {"font-family": "'Press Start 2P'", "font-weight": "normal"})
    SubElement(heading, "text", {"x": str(margin), "y": "48", "font-size": "12",
                                 "fill": "#f6d54a"}).text = "LUNA / POOLS"
    for index, line in enumerate(title_lines):
        SubElement(heading, "text", {"x": str(margin), "y": str(98 + index * 36),
                                     "font-size": "24", "fill": "#f3f5fb"}).text = line
    if not pools:
        SubElement(heading, "text", {"x": str(margin), "y": str(cards_top + 24),
                                     "font-size": "12", "fill": "#aab6ce"}).text = "No pools available"
    svg.append(content)
    return tostring(svg, encoding="unicode")
