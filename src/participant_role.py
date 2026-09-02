import discord

import config


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
    user_ids = get_registered_discord_user_ids(entrants, config.link_store.get_all_startgg_links())
    if discord_user_id is not None:
        user_ids &= {discord_user_id}

    result = {"matched": len(user_ids), "assigned": 0, "already": 0, "missing": 0, "failed": 0}
    for user_id in user_ids:
        member = guild.get_member(user_id)
        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except discord.NotFound:
                result["missing"] += 1
                continue

        if role in member.roles:
            result["already"] += 1
            continue

        try:
            await member.add_roles(role, reason=f"Registered for {active_event['event_name']} on start.gg")
            result["assigned"] += 1
        except (discord.Forbidden, discord.HTTPException):
            result["failed"] += 1

    return result
