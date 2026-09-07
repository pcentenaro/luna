import discord

import config
from pgrs import fetch_pgrs_entries, normalize_pgrs_name


def get_registered_discord_user_ids(entrants: list[dict], links: list[dict]) -> set[int]:
    player_ids = {
        str(player["id"])
        for entrant in entrants
        for participant in entrant.get("participants") or []
        if (player := participant.get("player")) and player.get("id") is not None
    }
    return {
        int(link["discord_user_id"])
        for link in links
        if str(link.get("startgg_player_id")) in player_ids
    }


def get_pgrs_registered_discord_user_ids(entries: list[dict], links: list[dict]) -> set[int]:
    entries_by_id = {str(entry["player_id"]): entry for entry in entries}
    entries_by_name = {}
    for entry in entries:
        entries_by_name.setdefault(normalize_pgrs_name(entry["player_name"]), []).append(entry)

    registered_user_ids = set()
    for link in links:
        player_id = link.get("pgrs_player_id")
        entry = entries_by_id.get(str(player_id)) if player_id else None
        player_name = (link.get("pgrs_player_name") or "").strip()
        if not player_id and player_name:
            matches = entries_by_name.get(normalize_pgrs_name(player_name), [])
            if len(matches) == 1:
                entry = matches[0]
                config.link_store.set_pgrs_link(
                    int(link["discord_user_id"]),
                    player_name,
                    entry["player_id"],
                )
        if entry:
            registered_user_ids.add(int(link["discord_user_id"]))
    return registered_user_ids


async def sync_participant_role(
    guild: discord.Guild | None,
    discord_user_id: int | None = None,
) -> dict | None:
    active_event = config.config_store.get_active_event()
    role_id = config.config_store.get_participant_role_id()
    if guild is None or active_event is None or role_id is None or config.startgg_client is None:
        return None

    role = guild.get_role(role_id)
    if role is None:
        return None

    entrants = await config.startgg_client.get_event_entrants(active_event["event_id"])
    links = config.link_store.get_all_startgg_links()
    registered_user_ids = get_registered_discord_user_ids(entrants, links)
    pgrs_competition_id = active_event.get("pgrs_competition_id")
    if pgrs_competition_id:
        pgrs_entries = await fetch_pgrs_entries(pgrs_competition_id)
        registered_user_ids &= get_pgrs_registered_discord_user_ids(pgrs_entries, links)
    if discord_user_id is not None:
        user_ids = {discord_user_id}
        registered_user_ids &= user_ids
    else:
        user_ids = {int(link["discord_user_id"]) for link in links}

    result = {
        "matched": len(registered_user_ids),
        "assigned": 0,
        "already": 0,
        "removed": 0,
        "missing": 0,
        "failed": 0,
    }
    for user_id in user_ids:
        member = guild.get_member(user_id)
        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except discord.NotFound:
                if user_id in registered_user_ids:
                    result["missing"] += 1
                continue
            except (discord.Forbidden, discord.HTTPException):
                result["failed"] += 1
                continue

        if user_id not in registered_user_ids:
            if role in member.roles:
                try:
                    await member.remove_roles(
                        role,
                        reason=f"Registration incomplete for {active_event['event_name']}",
                    )
                    result["removed"] += 1
                except (discord.Forbidden, discord.HTTPException):
                    result["failed"] += 1
            continue

        if role in member.roles:
            result["already"] += 1
            continue

        try:
            source = "start.gg and PGRS" if pgrs_competition_id else "start.gg"
            await member.add_roles(role, reason=f"Registered for {active_event['event_name']} on {source}")
            result["assigned"] += 1
        except (discord.Forbidden, discord.HTTPException):
            result["failed"] += 1

    return result


async def remove_participant_roles(guild: discord.Guild | None) -> dict | None:
    active_event = config.config_store.get_active_event()
    role_id = config.config_store.get_participant_role_id()
    if guild is None or active_event is None or role_id is None or config.startgg_client is None:
        return None

    role = guild.get_role(role_id)
    if role is None:
        return None

    entrants = await config.startgg_client.get_event_entrants(active_event["event_id"])
    user_ids = get_registered_discord_user_ids(entrants, config.link_store.get_all_startgg_links())
    result = {"matched": len(user_ids), "removed": 0, "absent": 0, "missing": 0, "failed": 0}

    for user_id in user_ids:
        member = guild.get_member(user_id)
        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except discord.NotFound:
                result["missing"] += 1
                continue
            except (discord.Forbidden, discord.HTTPException):
                result["failed"] += 1
                continue

        if role not in member.roles:
            result["absent"] += 1
            continue

        try:
            await member.remove_roles(role, reason=f"Cleared {active_event['event_name']} start.gg event")
            result["removed"] += 1
        except (discord.Forbidden, discord.HTTPException):
            result["failed"] += 1

    return result
