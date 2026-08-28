import os
import sqlite3
from dotenv import load_dotenv
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from pathlib import Path

load_dotenv()
connection = sqlite3.connect("data/luna.db")
cursor = connection.cursor()
transport = AIOHTTPTransport(
    url="https://api.start.gg/gql/alpha",
    headers={"Authorization": f"Bearer {os.getenv("STARTGG_API_KEY")}"})
client = Client(transport=transport)

slugs = [
    "tournament/copa-luna-1/event/puyo-singles",
    "tournament/copa-luna-2/event/puyo-singles",
    "tournament/copa-luna-3/event/puyo-singles",
    "tournament/copa-luna-4/event/puyo-singles",
    "tournament/copa-luna-5/event/puyo-singles",
    "tournament/copa-luna-6/event/puyo-singles",
    "tournament/copa-luna-7/event/puyo-singles",
    "tournament/copa-luna-8/event/puyo-singles",
    "tournament/copa-luna-9/event/puyo-singles",
    "tournament/copa-luna-10/event/puyo-singles",
    "tournament/copa-luna-11/event/puyo-singles",
    "tournament/copa-luna-12/event/puyo-singles",
    "tournament/copa-luna-13-aniversario-edition/event/puyo-singles",
    "tournament/copa-luna-14-1/event/puyo-singles",
    "tournament/copa-luna-15/event/puyo-singles",
    "tournament/copa-luna-16/event/puyo-singles",
    "tournament/copa-luna-17/event/puyo-singles",
    "tournament/copa-luna-rumbo-al-pgrs-mes-1/event/puyo-singles",
    "tournament/copa-luna-rumbo-al-pgrs-mes-2/event/puyo-singles",
    "tournament/copa-luna-rumbo-al-pgrs-mes-3/event/puyo-singles",
    "tournament/copa-luna-rumbo-al-pgrs-edici-n-final/event/puyo-singles"
]

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

for slug in slugs:
    result = client.execute(gql_query, variable_values={"slug": slug})
    result = result["event"]
    cursor.execute(
        f"""
        INSERT INTO tournaments
        VALUES(
            \"{result["id"]}\",
            \"{result["tournament"]["name"]}\",
            \"{result["slug"]}",
            {result["entrants"]["pageInfo"]["total"]},
            \"{result["tournament"]["url"]}\",
            \"{result["videogame"]["name"]}\",
            \"{result["tournament"]["registrationClosesAt"]}\")
        """
    )

connection.commit()