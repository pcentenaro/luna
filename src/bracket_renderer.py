"""Build bracket SVGs from isolated data; no network, Discord or file writes."""

from datetime import datetime, timezone
from textwrap import wrap
from xml.etree.ElementTree import Element, SubElement, tostring


def create_bracket_svg(data: dict, width: int = 1280, height: int = 720) -> str:
    """Create the canvas only. Match cards and connections are added in later steps.

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

    phase = data.get("phase") or {}
    group = data.get("phase_group") or {}
    group_label = group.get("displayIdentifier") or group.get("id", "?")
    title_lines = wrap(str(data.get("event_name") or "Tournament"), width=(width - 96) // 24)
    subtitle_lines = wrap(f"{phase.get('name') or 'Bracket'} / Group {group_label}", width=(width - 96) // 14)
    content_top = 98 + len(title_lines) * 36 + len(subtitle_lines) * 24 + 20
    height = max(height, content_top + 240)
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
    SubElement(svg, "g", {"id": "bracket-content"})
    text(timestamp, height - 32, 12, "#aab6ce")
    return tostring(svg, encoding="unicode")
