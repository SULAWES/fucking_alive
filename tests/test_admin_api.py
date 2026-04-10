import unittest

from tests.helpers import build_test_client, reset_database


class AdminApiTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_database()

    def test_healthz_and_admin_auth(self) -> None:
        with build_test_client() as client:
            health = client.get("/healthz")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["status"], "ok")

            unauthorized = client.get("/admin/settings")
            self.assertEqual(unauthorized.status_code, 401)

            authorized = client.get("/admin/settings", headers={"Authorization": "Bearer change_me"})
            self.assertEqual(authorized.status_code, 200)
            self.assertIn("default_llm_provider", authorized.json())
            self.assertIn("chat_prompt_version", authorized.json())

    def test_patch_settings_accepts_prompt_runtime_fields(self) -> None:
        with build_test_client() as client:
            response = client.patch(
                "/admin/settings",
                headers={"Authorization": "Bearer change_me"},
                json={
                    "chat_prompt_version": "chat_v1",
                    "command_repair_prompt_version": "command_repair_v1",
                    "command_repair_enabled": False,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["chat_prompt_version"], "chat_v1")
        self.assertEqual(response.json()["command_repair_prompt_version"], "command_repair_v1")
        self.assertFalse(response.json()["command_repair_enabled"])

    def test_patch_settings_rejects_unknown_prompt_version(self) -> None:
        with build_test_client() as client:
            response = client.patch(
                "/admin/settings",
                headers={"Authorization": "Bearer change_me"},
                json={"chat_prompt_version": "chat_v999"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertIn("chat_prompt_version", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
