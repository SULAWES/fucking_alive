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


if __name__ == "__main__":
    unittest.main()
