import os
import sqlite3
from datetime import datetime, timezone
from dotenv import load_dotenv
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport


class EventDataStore:
    def __init__(self, database_path):
        self.tournament_slugs = []
        self.tournament_ids = []
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
        self.gql_client.close_sync()


    def load_all_tournament_ids_from_database(self):
        self.cursor.execute("SELECT tournament_id FROM tournaments")
        rows = self.cursor.fetchall()
        self.tournament_ids = [row["tournament_id"] for row in rows]


    def store_general_tournament_data(self):
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
        self.connection.commit()


    def store_player_data(self):
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
        self.connection.commit()


    def store_tournament_phases(self):
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
        self.connection.commit()


    def store_tournament_sets(self):
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
        self.connection.commit()


    def store_tournament_standings(self):
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
        self.connection.commit()