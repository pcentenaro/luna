import unittest

from participant_role import get_registered_discord_user_ids


class ParticipantRoleTest(unittest.TestCase):
    def test_matches_linked_players_registered_in_event(self):
        entrants = [
            {
                "participants": [
                    {"player": {"id": "10"}},
                    {"player": None},
                ]
            },
            {"participants": [{"player": {"id": 20}}]},
        ]
        links = [
            {"discord_user_id": "1", "startgg_player_id": 10},
            {"discord_user_id": 2, "startgg_player_id": "20"},
            {"discord_user_id": 3, "startgg_player_id": 30},
        ]

        self.assertEqual(get_registered_discord_user_ids(entrants, links), {1, 2})


class ParticipantRoleViewTest(unittest.IsolatedAsyncioTestCase):
    async def test_builds_native_role_selector(self):
        from cogs.views.admin_panel import ParticipantRoleView

        view = ParticipantRoleView(None)
        self.assertEqual(view.children[0].type.name, "role_select")


if __name__ == "__main__":
    unittest.main()
