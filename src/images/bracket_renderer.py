"""Build bracket SVGs from isolated data; no network, Discord or file writes."""

from datetime import datetime, timezone
from textwrap import wrap
from xml.etree.ElementTree import Element, SubElement, tostring


MATCH_CARD_WIDTH = 360
MATCH_CARD_HEIGHT = 128
ROUND_GAP = 56
MATCH_GAP = 32


def _winners_rounds(sets: list[dict]) -> list[tuple[int, list[dict]]]:
    rounds = {}
    for match in sets:
        number = match.get("round")
        if number is None:
            continue
        number = int(number)
        label = " ".join(str(match.get("fullRoundText") or "").casefold().split())
        if number <= 0 or "grand final" in label:
            continue
        rounds.setdefault(number, []).append(match)
    return [(number, sorted(matches, key=lambda match: (
        len(str(match.get("identifier") or "")), str(match.get("identifier") or ""), str(match.get("id") or "")
    ))) for number, matches in sorted(rounds.items())]


def create_bracket_svg(data: dict, width: int = 1280, height: int = 720) -> str:
    """Draw Winners round columns. Connections, Losers and Grand Final follow later.

    Dimensions are pixels. Long headings wrap and increase the canvas height
    when necessary. Synchronization time comes from the snapshot, never now().
    """
    if type(width) is not int or type(height) is not int or width < 640 or height < 360:
        raise ValueError("The bracket canvas must be at least 640 by 360 pixels.")
    updated_at = data.get("updated_at")
    if updated_at is None:
        timestamp = "SYNC TIME UNKNOWN"
    elif isinstance(updated_at, datetime) and updated_at.utcoffset() is not None:
        timestamp = "SYNCED " + updated_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    else:
        raise ValueError("updated_at must be a timezone-aware datetime or None.")

    rounds = _winners_rounds(data.get("sets") or [])
    if rounds:
        width = max(width, 128 + len(rounds) * MATCH_CARD_WIDTH + (len(rounds) - 1) * ROUND_GAP)
    phase = data.get("phase") or {}
    group = data.get("phase_group") or {}
    group_label = group.get("displayIdentifier") or group.get("id", "?")
    title_lines = wrap(str(data.get("event_name") or "Tournament"), width=(width - 96) // 24)
    subtitle_lines = wrap(f"{phase.get('name') or 'Bracket'} / Group {group_label}", width=(width - 96) // 14)
    content_top = 98 + len(title_lines) * 36 + len(subtitle_lines) * 24 + 20
    round_labels = [wrap(matches[0].get("fullRoundText") or f"Winners Round {number}",
                         width=MATCH_CARD_WIDTH // 14) for number, matches in rounds]
    heading_height = max((len(lines) * 24 for lines in round_labels), default=0) + 32
    rows = max((len(matches) for _, matches in rounds), default=0)
    cards_height = rows * MATCH_CARD_HEIGHT + max(0, rows - 1) * MATCH_GAP
    height = max(height, content_top + 240, content_top + heading_height + cards_height + 112)
    svg = Element("svg", {
        "xmlns": "http://www.w3.org/2000/svg", "width": str(width), "height": str(height),
        "viewBox": f"0 0 {width} {height}", "role": "img",
    })
    SubElement(svg, "title").text = f"{data.get('event_name') or 'Tournament'} - {phase.get('name') or 'Bracket'} - Group {group_label}"
    SubElement(svg, "rect", {"width": str(width), "height": str(height), "fill": "#0b1020"})
    SubElement(svg, "rect", {"width": str(width), "height": "6", "fill": "#f6d54a"})
    text_group = SubElement(svg, "g", {"font-family": "'Press Start 2P'", "font-weight": "normal"})

    def text(value, y, size, color):
        SubElement(text_group, "text", {"x": "48", "y": str(y), "font-size": str(size), "fill": color}).text = value

    text("LUNA / BRACKET", 48, 12, "#f6d54a")
    y = 98
    for line in title_lines:
        text(line, y, 24, "#f3f5fb")
        y += 36
    for line in subtitle_lines:
        text(line, y, 14, "#aab6ce")
        y += 24
    SubElement(svg, "rect", {
        "x": "32", "y": str(content_top), "width": str(width - 64),
        "height": str(height - content_top - 80), "rx": "12",
        "fill": "#111a2d", "stroke": "#28344c",
    })
    content = SubElement(svg, "g", {"id": "bracket-content", "font-family": "'Press Start 2P'", "font-weight": "normal"})
    for column, ((number, matches), labels) in enumerate(zip(rounds, round_labels)):
        x = 64 + column * (MATCH_CARD_WIDTH + ROUND_GAP)
        for line_index, label in enumerate(labels):
            SubElement(content, "text", {
                "x": str(x), "y": str(content_top + 32 + line_index * 24),
                "font-size": "14", "fill": "#f6d54a",
            }).text = label
        for row, match in enumerate(matches):
            # Initial column spacing; prerequisite-based alignment belongs to the connections step.
            y = content_top + heading_height + (row + 0.5) * (cards_height + MATCH_GAP) / len(matches) - (MATCH_CARD_HEIGHT + MATCH_GAP) / 2
            card = create_match_card(match, x=x, y=round(y), width=MATCH_CARD_WIDTH)
            card.set("data-set-id", str(match.get("id", "")))
            card.set("data-round", str(number))
            content.append(card)
    text(timestamp, height - 32, 12, "#aab6ce")
    return tostring(svg, encoding="unicode")


def create_match_card(set_data: dict, x: int = 0, y: int = 0, width: int = 360) -> Element:
    """Return an SVG group for a two-player set; positioning is left to the caller.

    Rows follow slotIndex (not entrant IDs). Only an explicit seed.isBye is a
    bye; a missing entrant is TBD. Scores and prerequisite data are not changed.
    """
    if type(width) is not int or width < 320:
        raise ValueError("Match cards must be at least 320 pixels wide.")
    slots = set_data.get("slots") or []
    if len(slots) > 2:
        raise ValueError("Match cards support at most two slots.")
    ordered = sorted(enumerate(slots), key=lambda item: (
        item[1].get("slotIndex") if item[1].get("slotIndex") is not None else item[0]
    ))
    slots = [slot for _, slot in ordered]
    state = str(set_data.get("state")).casefold()
    completed = state in {"3", "completed"}
    status = {"1": "Pending", "created": "Pending", "2": "In progress", "active": "In progress",
              "3": "Completed", "completed": "Completed", "4": "Ready", "ready": "Ready",
              "5": "Invalid", "6": "Called", "7": "Queued","8" : "DQ" }.get(state, "Unknown")
    card = Element("g", {"transform": f"translate({x} {y})", "font-family": "'Press Start 2P'", "font-weight": "normal"})
    SubElement(card, "title").text = str(set_data.get("fullRoundText") or "Match")
    SubElement(card, "rect", {"width": str(width), "height": str(MATCH_CARD_HEIGHT), "rx": "8", "fill": "#1b2840", "stroke": "#3b4b67"})

    def text(value, tx, ty, size, color, limit, anchor="start"):
        full = " ".join(str(value).split())
        label = full if len(full) <= limit else full[:limit - 3] + "..."
        node = SubElement(card, "text", {"x": str(tx), "y": str(ty), "font-size": str(size), "fill": color, "text-anchor": anchor})
        node.text = label
        if label != full:
            SubElement(node, "title").text = full

    text(set_data.get("identifier") or set_data.get("id") or "?", 12, 22, 10, "#f6d54a", (width - 164) // 10)
    text(status, width - 12, 22, 10, "#aab6ce", 14, "end")
    for index in range(2):
        slot = slots[index] if index < len(slots) else {}
        entrant = slot.get("entrant") or {}
        bye = (slot.get("seed") or {}).get("isBye") is True
        name = "BYE" if bye else (entrant.get("name") or ("Unnamed" if entrant else "TBD"))
        winner = (completed and entrant.get("id") is not None and set_data.get("winnerId") is not None
                  and str(entrant["id"]) == str(set_data["winnerId"]))
        top = 32 + index * 48
        if winner:
            SubElement(card, "rect", {"x": "1", "y": str(top), "width": str(width - 2), "height": "47", "fill": "#294331"})
            text(">", 10, top + 30, 12, "#f6d54a", 1)
        SubElement(card, "line", {"x1": "1", "y1": str(top), "x2": str(width - 1), "y2": str(top), "stroke": "#3b4b67"})
        text(name, 32, top + 30, 12, "#f3f5fb" if entrant else "#aab6ce", (width - 104) // 12)
        score = (((slot.get("standing") or {}).get("stats") or {}).get("score") or {}).get("value")
        text(score if score is not None else "—", width - 16, top + 30, 14, "#f6d54a" if winner else "#f3f5fb", 4, "end")
    return card
