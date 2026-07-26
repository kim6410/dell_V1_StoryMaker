import os
import unittest

os.environ["SUPERTONIC_API_KEY"] = "test-key"

import httpx

from app import app


class ApiAuthTest(unittest.IsolatedAsyncioTestCase):
    async def test_health_and_bearer_auth(self):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            self.assertEqual((await client.get("/health")).status_code, 200)
            self.assertEqual((await client.get("/api/audio/list")).status_code, 401)
            response = await client.get(
                "/api/audio/list",
                headers={"Authorization": "Bearer test-key"},
            )
            self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
