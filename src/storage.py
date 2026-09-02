import csv
import json
import os
import sqlite3
from datetime import datetime, timezone
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from pathlib import Path
from time import sleep


DEFAULT_LINKS_PATH = Path(__file__).resolve().parent.parent / "data" / "links.json"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "config.json"
DEFAULT_SCORE_TARGETS = {
    "default": 7,
    "final": 9,
    "grand_final": 10,
}


class LinkStore:
    def __init__(self):
        self.connection = sqlite3.connect("data/luna.db")
        self.connection.row_factory = lambda cursor, row: {key: value for key, value in zip([col[0] for col in cursor.description], row)}
        self.cursor = self.connection.cursor()
        self._create_tables()

    def _create_tables(self):
        queries = [(Path(__file__).parent / "queries" / "create_links_table.sql").read_text()]
        for query in queries:
           self.cursor.execute(query)

    def set_startgg_link(
        self,
        discord_user_id: int,
        startgg_player_id: int,
        gamer_tag: str | None,
        prefix: str | None,
    ):
        self.cursor.execute(f"""
            INSERT INTO links
                VALUES({discord_user_id}, {startgg_player_id}, \"{gamer_tag}\", \"{prefix}\", \"{datetime.now(timezone.utc).isoformat()}\")
                ON CONFLICT(startgg_player_id) DO NOTHING
                ON CONFLICT(discord_user_id) DO UPDATE SET
                    startgg_player_id = excluded.startgg_player_id,
                    startgg_gamer_tag = excluded.startgg_gamer_tag,
                    startgg_prefix = excluded.startgg_prefix,
                    updated_at = excluded.updated_at
                WHERE startgg_player_id NOT IN ({startgg_player_id})
            """
        )
        self.connection.commit()

    def get_startgg_link(self, discord_user_id: int) -> dict | None:
        self.cursor.execute(f"SELECT * FROM links WHERE discord_user_id = {discord_user_id}")
        return self.cursor.fetchone()

    def get_startgg_link_by_player_id(self, startgg_player_id: int) -> dict | None:
        self.cursor.execute(f"SELECT * FROM links WHERE startgg_player_id = {startgg_player_id}")
        return self.cursor.fetchone()

    def get_all_startgg_links(self) -> list[dict]:
        self.cursor.execute(f"SELECT * FROM links")
        return self.cursor.fetchall()

    def delete_startgg_link(self, discord_user_id: int) -> bool:
        self.cursor.execute(f"DELETE FROM links WHERE discord_user_id = {discord_user_id}")
        self.connection.commit()


class ConfigStore:
    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH):
        self.config_path = config_path
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

    def get_admin_role_id(self) -> int | None:
        admin_role_id = self._load().get("admin_role_id")
        return int(admin_role_id) if admin_role_id else None

    def set_admin_role_id(self, role_id: int):
        data = self._load()
        data["admin_role_id"] = str(role_id)
        self._save(data)

    def clear_admin_role_id(self) -> bool:
        data = self._load()
        removed = data.pop("admin_role_id", None)
        if removed is None:
            return False

        self._save(data)
        return True

    def get_active_event(self) -> dict | None:
        return self._load().get("active_event")

    def set_active_event(
        self,
        tournament_slug: str,
        event_slug: str,
        event_id: int,
        event_name: str,
    ):
        data = self._load()
        data["active_event"] = {
            "tournament_slug": tournament_slug,
            "event_slug": event_slug,
            "event_id": event_id,
            "event_name": event_name,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save(data)

    def clear_active_event(self) -> bool:
        data = self._load()
        removed = data.pop("active_event", None)
        if removed is None:
            return False

        self._save(data)
        return True

    def get_score_targets(self) -> dict:
        score_targets = self._load().get("score_targets") or {}
        return {
            "default": int(score_targets.get("default") or DEFAULT_SCORE_TARGETS["default"]),
            "final": int(score_targets.get("final") or DEFAULT_SCORE_TARGETS["final"]),
            "grand_final": int(score_targets.get("grand_final") or DEFAULT_SCORE_TARGETS["grand_final"]),
        }

    def set_score_targets(self, default: int, final: int, grand_final: int):
        data = self._load()
        data["score_targets"] = {
            "default": int(default),
            "final": int(final),
            "grand_final": int(grand_final),
        }
        self._save(data)

    def _load(self) -> dict:
        if not self.config_path.exists():
            return {}

        with self.config_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _save(self, data: dict):
        temporary_path = self.config_path.with_suffix(".tmp")
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2, ensure_ascii=False)
            file.write("\n")

        temporary_path.replace(self.config_path)


class EventDataStore:
    def __init__(self, database_path):
        self.tournament_slugs = []
        self.tournament_ids = set()
        self.connection = sqlite3.connect(database_path)
        self.connection.row_factory = lambda cursor, row: {key: value for key, value in zip([col[0] for col in cursor.description], row)}
        self.cursor = self.connection.cursor()
        self.transport = AIOHTTPTransport(
            url="https://api.start.gg/gql/alpha",
            headers={"Authorization": f"Bearer {os.getenv("STARTGG_API_KEY")}"})
        self.gql_client = Client(transport=self.transport,
                        fetch_schema_from_transport=False)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close_connection()

    def set_tournament_slugs(self, slugs):
        self.tournament_slugs = slugs

    def close_connection(self):
        self.cursor.close()
        self.connection.close()

    def load_all_tournament_ids_from_database(self):
        self.cursor.execute("SELECT tournament_id FROM tournaments")
        rows = self.cursor.fetchall()
        self.tournament_ids = {row["tournament_id"] for row in rows}

    def store_glicko_ratings(self, csv_path):
        query = Path("queries/create_glicko_ratings_table.sql").read_text()
        self.cursor.executescript(query)
        with Path(csv_path).open() as glicko_data:
            csv_reader = csv.DictReader(glicko_data)
            next(csv_reader)
            for row in csv_reader:
                self.cursor.execute(
                    """
                    INSERT INTO glicko_ratings
                    VALUES(?, ?, ?)
                    """,
                    (
                        row["Player"],
                        row["Rank"],
                        row["Points"]
                    )
                )
        self.connection.commit()


    def store_general_tournament_data(self, cooldown_secs = 5):
        gql_query = gql(
            """
            query ExampleQuery($slug: String!) {
                event(slug: $slug) {
                    tournament {
                        name
                        registrationClosesAt
                        url
                    }
                    id
                    entrants {
                        pageInfo {
                            total
                        }
                    }
                    videogame {
                        name
                    }
                    slug
                }
            }
            """
        )

        for slug in self.tournament_slugs:
            result = self.gql_client.execute(gql_query, variable_values={"slug": slug})
            result = result["event"]
            self.cursor.execute(
                f"""
                INSERT INTO tournaments
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result["id"],
                    result["tournament"]["name"],
                    result["slug"],
                    result["entrants"]["pageInfo"]["total"],
                    result["tournament"]["url"],
                    result["videogame"]["name"],
                    result["tournament"]["registrationClosesAt"]
                )
            )
            self.tournament_ids.add(result["id"])
            sleep(cooldown_secs)
        self.connection.commit()

    def store_player_data(self, cooldown_secs = 5):
        query = gql(
            """
            query Query($id: ID!) {
                event(id: $id) {
                    entrants {
                        nodes {
                            participants {
                            gamerTag
                                player {
                                    id
                                    gamerTag
                                    prefix
                                }
                            }
                            id
                        }
                    }
                }
            }
            """
        )

        for tournament_id in self.tournament_ids:
            result = self.gql_client.execute(query, variable_values={"id": tournament_id})
            result = result["event"]["entrants"]["nodes"]
            # Updates player link information based on latest event.
            # If player is already registered, preserves their Discord ID.
            for entrant in result:
                participant = entrant["participants"][0]
                player = participant["player"]
                self.cursor.execute(
                    f"""
                    INSERT INTO links
                        VALUES(?, ?, ?, ?, ?)
                        ON CONFLICT(startgg_player_id) DO UPDATE SET
                            startgg_gamer_tag = excluded.startgg_gamer_tag,
                            startgg_prefix = excluded.startgg_prefix,
                            updated_at = excluded.updated_at
                    """,
                    (
                        player["id"],
                        None,
                        player["gamerTag"],
                        player["prefix"],
                        datetime.now(timezone.utc).isoformat()
                    )
                )
                self.connection.commit()

                self.cursor.execute(
                    """
                    INSERT INTO bridge_player_entrant
                        VALUES(?, ?, ?, ?, ?)
                        ON CONFLICT DO NOTHING
                    """,
                    (tournament_id, entrant["id"], player["id"], None, participant["gamerTag"])
                )
                self.connection.commit()
            sleep(cooldown_secs)
        self.connection.commit()

    def store_tournament_phases(self, cooldown_secs = 5):
        query = gql(
            """
            query Query($id: ID!) {
                event(id: $id) {
                    phases {
                        id
                        name
                        numSeeds
                        phaseOrder
                        phaseGroups {
                            nodes {
                                bracketType
                            }
                        }
                    }
                }
            }
            """
        )

        for tournament_id in self.tournament_ids:        
            result = self.gql_client.execute(query, variable_values={"id": tournament_id})
            result = result["event"]["phases"]
            for phase in result:
                bracket_type = phase["phaseGroups"]["nodes"][0]["bracketType"]
                self.cursor.execute(
                    f"""
                    INSERT OR REPLACE INTO tournament_phases
                        VALUES(?, ?, ?, ?, ?, ?)
                    """,
                    (
                        tournament_id,
                        phase["id"],
                        phase["phaseOrder"],
                        bracket_type,
                        phase["name"],
                        phase["numSeeds"]
                    )
                )
            sleep(cooldown_secs)
        self.connection.commit()

    def store_tournament_sets(self, cooldown_secs = 5):
        phase_id_query = gql(
            """
            query Query($id: ID!) {
                event(id: $id) {
                    phases {
                        id
                    }
                }
            }
            """
        )

        tournament_sets_query = gql(
            """
            query Query($phaseId: ID!) {
                phase(id: $phaseId) {
                    id
                    phaseGroups {
                        pageInfo {
                            totalPages
                        }
                        nodes {
                            id
                            sets {
                                nodes {
                                    id
                                    slots {
                                        entrant {
                                            id
                                        }
                                        standing {
                                            stats {
                                                score {
                                                    value
                                                }
                                            }
                                            placement
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            """
        )

        for tournament_id in self.tournament_ids:
            results = self.gql_client.execute(phase_id_query, variable_values={"id": tournament_id})
            phases = results["event"]["phases"]

            for phase in phases:
                result = self.gql_client.execute(tournament_sets_query, variable_values={"id": tournament_id, "phaseId": phase["id"]})
                phase = result["phase"]
                for group_node in phase["phaseGroups"]["nodes"]:
                    for set_node in group_node["sets"]["nodes"]:
                        slots = set_node["slots"]
                        self.cursor.execute(
                            f"""
                            INSERT OR REPLACE INTO tournament_sets
                                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                tournament_id,
                                phase["id"],
                                group_node["id"],
                                set_node["id"],
                                slots[0]["entrant"]["id"],
                                slots[1]["entrant"]["id"],
                                slots[0]["standing"]["stats"]["score"]["value"],
                                slots[1]["standing"]["stats"]["score"]["value"],
                                slots[0]["standing"]["placement"],
                                slots[1]["standing"]["placement"]
                            )
                        )
            sleep(cooldown_secs)
        self.connection.commit()

    def store_tournament_standings(self, cooldown_secs = 5):
        query = gql(
            """
            query Query($id: ID!) {
                event(id: $id) {
                    phases {
                    id
                        phaseGroups {
                            nodes {
                                id
                                standings {
                                    nodes {
                                        id
                                        placement
                                        entrant {
                                            id
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
            """
        )

        for tournament_id in self.tournament_ids:
            result = self.gql_client.execute(query, variable_values={"id": tournament_id})
            result = result["event"]["phases"]
            for phase in result:
                for group_node in phase["phaseGroups"]["nodes"]:
                    for standings_node in group_node["standings"]["nodes"]:
                        self.cursor.execute(
                            f"""
                            INSERT OR REPLACE INTO tournament_standings
                                VALUES(?, ?, ?, ?, ?, ?)
                            """,
                            (
                                tournament_id,
                                phase["id"],
                                group_node["id"],
                                standings_node["id"],
                                standings_node["placement"],
                                standings_node["entrant"]["id"]
                            )
                        )
            sleep(cooldown_secs)
        self.connection.commit()

    def get_player_podium_summary(self, discord_id):
        self.cursor.execute(
            f"""
            WITH
                tournament_info AS (
                    SELECT
                        t.tournament_id,
                        MAX(p.phase_order) AS max_phase_order
                    FROM tournaments AS t
                    INNER JOIN tournament_phases AS p
                        ON t.tournament_id = p.tournament_id
                    GROUP BY t.tournament_id
                ),

                player_standings AS (
                    SELECT
                        s.placement,
                        s.tournament_id,
                        p.phase_order,
                        i.max_phase_order
                    FROM tournament_standings AS s
                    INNER JOIN tournament_phases AS p
                        ON s.tournament_id = p.tournament_id
                        AND s.phase_id = p.phase_id
                    INNER JOIN bridge_player_entrant AS b
                        ON s.entrant_id = b.entrant_id
                    INNER JOIN links AS l
                        ON b.player_id = l.startgg_player_id
                    INNER JOIN tournament_info AS i
                        ON s.tournament_id = i.tournament_id
                    WHERE
                        p.phase_type = "DOUBLE_ELIMINATION"
                        AND l.discord_user_id = ?
                ),

                standings AS (
                    SELECT
                        COUNT(placement = 1 OR NULL) AS relative_first_places,
                        COUNT(placement = 2 OR NULL) AS relative_second_places,
                        COUNT(placement = 3 OR NULL) AS relative_third_places,
                        COUNT(placement > 3 OR NULL) AS relative_other_places,
                        COUNT((placement = 1 AND phase_order = max_phase_order) OR NULL) AS absolute_first_places,
                        COUNT((placement = 2 AND phase_order = max_phase_order) OR NULL) AS absolute_second_places,
                        COUNT((placement = 3 AND phase_order = max_phase_order) OR NULL) AS absolute_third_places,
                        COUNT(phase_order < max_phase_order OR NULL) + COUNT((phase_order = max_phase_order AND placement > 3) OR NULL) AS absolute_other_places
                    FROM player_standings
                )
            
            SELECT *
            FROM standings
            """,
            [str(discord_id)]
        )
        return self.cursor.fetchone()

    def get_player_set_summary(self, discord_id):
        self.cursor.execute(
            """
            WITH
                player_sets AS (
                    SELECT
                        entrant1_id,
                        entrant2_id,
                        entrant1_score,
                        entrant2_score,
                        entrant1_standing,
                        entrant2_standing,
                        (entrant1_id = b.entrant_id) AS is_entrant1
                    FROM tournament_sets AS s
                    INNER JOIN bridge_player_entrant AS b
                        ON s.tournament_id = b.tournament_id
                        AND (s.entrant1_id = b.entrant_id OR s.entrant2_id = b.entrant_id)
                    INNER JOIN links AS l
                        ON l.startgg_player_id = b.player_id
                    WHERE
                        l.discord_user_id = ?
                        AND entrant1_score >= 0
                        AND entrant2_score >= 0
                ),

                set_summary AS (
                    SELECT
                        COUNT(*) AS set_count,
                        100.0 * COUNT(
                            CASE
                                WHEN
                                    (is_entrant1 IS TRUE AND entrant1_standing = 2)
                                    OR (is_entrant1 IS FALSE AND entrant1_standing = 1)
                                    THEN NULL
                                ELSE 1
                            END
                        ) / COUNT(*) AS pct_set_win_rate,
                        SUM(entrant1_score + entrant2_score) AS round_count,
                        100.0 * SUM(
                            CASE
                                WHEN is_entrant1 THEN entrant1_score
                                ELSE entrant2_score
                            END
                        ) / SUM(entrant1_score + entrant2_score) AS pct_round_win_rate
                    FROM player_sets
                )

            SELECT *
            FROM set_summary
            """,
            [str(discord_id)]
        )
        return self.cursor.fetchone()

    def get_player_glicko_rating(self, discord_id):
        self.cursor.execute(
            """
            SELECT
                rating,
                rank
            FROM glicko_ratings as g
            INNER JOIN links as l
                ON g.name = l.startgg_gamer_tag
                OR g.name = l.startgg_prefix || " | " || l.startgg_gamer_tag
            WHERE l.discord_user_id = ?
            """,
            [str(discord_id)]
        )
        return self.cursor.fetchone()