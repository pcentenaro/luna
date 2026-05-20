import aiohttp


STARTGG_API_URL = "https://api.start.gg/gql/alpha"


class StartGGError(Exception):
    """Raised when start.gg returns an error or an unexpected response."""


class StartGGClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def query(self, query: str, variables: dict | None = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {"query": query, "variables": variables or {}}

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(STARTGG_API_URL, json=payload) as response:
                data = await response.json(content_type=None)

        if "errors" in data:
            message = data["errors"][0].get("message", "Unknown start.gg error")
            raise StartGGError(message)

        if "data" not in data:
            raise StartGGError("start.gg returned an unexpected response")

        return data["data"]

    async def get_current_user(self) -> dict | None:
        data = await self.query(
            """
            query CurrentUser {
              currentUser {
                id
                slug
                name
                player {
                  id
                  gamerTag
                  prefix
                }
              }
            }
            """
        )
        return data.get("currentUser")

    async def get_player(self, player_id: int) -> dict | None:
        data = await self.query(
            """
            query Player($playerId: ID!) {
              player(id: $playerId) {
                id
                gamerTag
                prefix
              }
            }
            """,
            {"playerId": player_id},
        )
        return data.get("player")

    async def get_player_by_profile_slug(self, profile_slug: str) -> dict | None:
        data = await self.query(
            """
            query UserBySlug($slug: String!) {
              user(slug: $slug) {
                player {
                  id
                  gamerTag
                  prefix
                }
              }
            }
            """,
            {"slug": profile_slug},
        )
        user = data.get("user")
        return user.get("player") if user else None

    async def get_event_by_slug(self, event_slug: str) -> dict | None:
        data = await self.query(
            """
            query EventBySlug($slug: String) {
              event(slug: $slug) {
                id
                name
                slug
              }
            }
            """,
            {"slug": event_slug},
        )
        return data.get("event")

    async def get_event_phases(self, event_id: int) -> list[dict]:
        data = await self.query(
            """
            query EventPhases($eventId: ID!) {
              event(id: $eventId) {
                phases {
                  id
                  name
                  numSeeds
                }
              }
            }
            """,
            {"eventId": event_id},
        )
        event = data.get("event")
        return event.get("phases", []) if event else []

    async def get_phase_groups(self, phase_id: int) -> list[dict]:
        data = await self.query(
            """
            query PhaseGroups($phaseId: ID!) {
              phase(id: $phaseId) {
                phaseGroups(query: {perPage: 50}) {
                  nodes {
                    id
                    displayIdentifier
                    state
                    wave {
                      identifier
                    }
                  }
                }
              }
            }
            """,
            {"phaseId": phase_id},
        )
        phase = data.get("phase")
        phase_groups = phase.get("phaseGroups", {}) if phase else {}
        return phase_groups.get("nodes", [])

    async def get_phase_group_sets(self, phase_group_id: int) -> list[dict]:
        data = await self.query(
            """
            query PhaseGroupSets($phaseGroupId: ID!) {
              phaseGroup(id: $phaseGroupId) {
                sets(page: 1, perPage: 50) {
                  nodes {
                    id
                    fullRoundText
                    round
                    state
                    slots {
                      standing {
                        stats {
                          score {
                            value
                          }
                        }
                      }
                      entrant {
                        id
                        name
                        participants {
                          id
                          gamerTag
                          player {
                            id
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
            """,
            {"phaseGroupId": phase_group_id},
        )
        phase_group = data.get("phaseGroup")
        sets = phase_group.get("sets", {}) if phase_group else {}
        return sets.get("nodes", [])

    async def get_set(self, set_id: int) -> dict | None:
        data = await self.query(
            """
            query Set($setId: ID!) {
              set(id: $setId) {
                id
                fullRoundText
                round
                state
                slots {
                  standing {
                    stats {
                      score {
                        value
                      }
                    }
                  }
                  entrant {
                    id
                    name
                    participants {
                      id
                      gamerTag
                      player {
                        id
                      }
                    }
                  }
                }
              }
            }
            """,
            {"setId": set_id},
        )
        return data.get("set")

    async def report_set(
        self,
        set_id: int,
        winner_id: int,
        game_data: list[dict] | None = None,
    ) -> dict | None:
        data = await self.query(
            """
            mutation ReportSet($setId: ID!, $winnerId: ID!, $gameData: [BracketSetGameDataInput]) {
              reportBracketSet(setId: $setId, winnerId: $winnerId, gameData: $gameData) {
                id
                state
              }
            }
            """,
            {
                "setId": set_id,
                "winnerId": winner_id,
                "gameData": game_data,
            },
        )
        return data.get("reportBracketSet")


def format_user_display_name(user: dict) -> str:
    player = user.get("player") or {}
    gamer_tag = player.get("gamerTag")
    prefix = player.get("prefix")
    if gamer_tag and prefix:
        return f"{prefix} | {gamer_tag}"
    if gamer_tag:
        return gamer_tag

    return user.get("name") or user.get("slug") or user.get("id")
