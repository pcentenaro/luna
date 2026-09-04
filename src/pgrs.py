from html.parser import HTMLParser

import aiohttp


PGRS_BASE_URL = "https://puyopuyo-global-ranking-series.j-cg.com"


class PGRSError(Exception):
    """Raised when PGRS cannot be read or returns an unexpected page."""


class _EntriesParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.entries = []
        self.found_table = False
        self._field = None
        self._value = []
        self._player_name = None

    def handle_starttag(self, tag, attrs):
        classes = (dict(attrs).get("class") or "").split()
        if "participants-table__body" in classes:
            self.found_table = True
        if "player-name" in classes:
            self._field = "name"
            self._value = []
        elif "player-username" in classes:
            self._field = "id"
            self._value = []

    def handle_data(self, data):
        if self._field:
            self._value.append(data)

    def handle_endtag(self, tag):
        if tag != "div" or self._field is None:
            return

        value = " ".join("".join(self._value).split())
        if self._field == "name":
            self._player_name = value
        else:
            player_id = value.removeprefix("#")
            if self._player_name and player_id.isdigit():
                self.entries.append({"player_id": player_id, "player_name": self._player_name})
            self._player_name = None
        self._field = None
        self._value = []


async def fetch_pgrs_entries(competition_id: str) -> list[dict]:
    url = f"{PGRS_BASE_URL}/competition/{competition_id}/entries"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url) as response:
                if response.status == 404:
                    raise PGRSError("PGRS competition not found")
                response.raise_for_status()
                page = await response.text()
    except (aiohttp.ClientError, TimeoutError) as error:
        raise PGRSError(f"Could not read PGRS entries: {error}") from error

    parser = _EntriesParser()
    parser.feed(page)
    if not parser.found_table:
        raise PGRSError("PGRS returned an unexpected entries page")
    return parser.entries
