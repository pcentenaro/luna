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

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.post(STARTGG_API_URL, json=payload) as response:
                    response.raise_for_status()
                    data = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as error:
            raise StartGGError("Could not read a valid response from start.gg") from error

        if not isinstance(data, dict):
            raise StartGGError("start.gg returned an unexpected response")
        if data.get("errors"):
            raise StartGGError("start.gg returned GraphQL errors: " + str(data["errors"]))
        if not isinstance(data.get("data"), dict):
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

    async def get_event_entrants(self, event_id: int, per_page: int = 50) -> list[dict]:
        entrants = []
        page = 1

        while True:
            data = await self.query(
                """
                query EventEntrants($eventId: ID!, $page: Int!, $perPage: Int!) {
                  event(id: $eventId) {
                    entrants(query: {page: $page, perPage: $perPage}) {
                      pageInfo {
                        page
                        totalPages
                        total
                      }
                      nodes {
                        id
                        name
                        participants {
                          id
                          gamerTag
                          player {
                            id
                            gamerTag
                            prefix
                          }
                        }
                      }
                    }
                  }
                }
                """,
                {"eventId": event_id, "page": page, "perPage": per_page},
            )
            event = data.get("event")
            if event is None:
                return []

            connection = event.get("entrants") or {}
            entrants.extend(connection.get("nodes") or [])
            page_info = connection.get("pageInfo") or {}
            total_pages = int(page_info.get("totalPages") or 1)
            if page >= total_pages:
                return entrants

            page += 1

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
        if not isinstance(event, dict) or not isinstance(event.get("phases"), list):
            raise StartGGError("start.gg did not return phases for the requested event")
        return event["phases"]

    async def get_phase_groups(self, phase_id: int) -> list[dict]:
        results = []
        page = 1
        while True:
            data = await self.query(
                """
                query PhaseGroups($phaseId: ID!, $page: Int!) {
                  phase(id: $phaseId) {
                    phaseGroups(query: {page: $page, perPage: 50}) {
                      pageInfo {
                        totalPages
                      }
                      nodes {
                        id
                        bracketType
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
                {"phaseId": phase_id, "page": page},
            )
            parent = data.get("phase")
            if not isinstance(parent, dict):
                raise StartGGError("start.gg did not return the requested phase")

            connection = parent.get("phaseGroups")
            if not isinstance(connection, dict):
                raise StartGGError("start.gg did not return phaseGroups for the requested phase")
            total_pages = (connection.get("pageInfo") or {}).get("totalPages")
            nodes = connection.get("nodes")
            if not isinstance(total_pages, int) or total_pages < 0 or not isinstance(nodes, list):
                raise StartGGError("start.gg returned invalid phaseGroups pagination data")
            if not nodes and page < total_pages:
                raise StartGGError("start.gg returned an empty page before the end of phaseGroups")
            results.extend(nodes)
            if page >= total_pages:
                return results
            page += 1

    async def get_phase_group_sets(self, phase_group_id: int) -> list[dict]:
        results = []
        page = 1
        while True:
            data = await self.query(
                """
                query PhaseGroupSets($phaseGroupId: ID!, $page: Int!) {
                  phaseGroup(id: $phaseGroupId) {
                    sets(page: $page, perPage: 50) {
                      pageInfo {
                        totalPages
                      }
                      nodes {
                        id
                        identifier
                        fullRoundText
                        round
                        state
                        winnerId
                        slots(includeByes: true) {
                          prereqId
                          prereqPlacement
                          prereqType
                          slotIndex
                          seed {
                            id
                            seedNum
                            isBye
                          }
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
                {"phaseGroupId": phase_group_id, "page": page},
            )
            parent = data.get("phaseGroup")
            if not isinstance(parent, dict):
                raise StartGGError("start.gg did not return the requested phaseGroup")

            connection = parent.get("sets")
            if not isinstance(connection, dict):
                raise StartGGError("start.gg did not return sets for the requested phaseGroup")
            total_pages = (connection.get("pageInfo") or {}).get("totalPages")
            nodes = connection.get("nodes")
            if not isinstance(total_pages, int) or total_pages < 0 or not isinstance(nodes, list):
                raise StartGGError("start.gg returned invalid sets pagination data")
            if not nodes and page < total_pages:
                raise StartGGError("start.gg returned an empty page before the end of sets")
            results.extend(nodes)
            if page >= total_pages:
                return results
            page += 1

    async def get_phase_group_standings(self, phase_group_id: int) -> list[dict]:
        data = await self.query(
            """
            query PhaseGroupStandings($phaseGroupId: ID!) {
              phaseGroup(id: $phaseGroupId) {
                standings(query: {page: 1, perPage: 100}) {
                  nodes {
                    placement
                    entrant {
                      id
                      name
                      participants {
                        player {
                          id
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
        standings = phase_group.get("standings", {}) if phase_group else {}
        return standings.get("nodes", [])

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
                  prereqId
                  prereqPlacement
                  prereqType
                  slotIndex
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
        is_dq: bool = False,
        game_data: list[dict] | None = None,
    ) -> dict | None:
        data = await self.query(
            """
            mutation ReportSet($setId: ID!, $winnerId: ID!, $isDQ: Boolean, $gameData: [BracketSetGameDataInput]) {
              reportBracketSet(setId: $setId, winnerId: $winnerId, isDQ: $isDQ, gameData: $gameData) {
                id
                state
              }
            }
            """,
            {
                "setId": set_id,
                "winnerId": winner_id,
                "isDQ": is_dq,
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
