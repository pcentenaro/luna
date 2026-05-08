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
