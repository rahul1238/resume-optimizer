from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deploy_render import DeployConfig, RenderDeploymentError, wait_for_deploy


class FakeRenderClient:
    def __init__(
        self,
        statuses: list[str],
        *,
        trigger_id: str | None = "dep-123",
    ) -> None:
        self.statuses = iter(statuses)
        self.trigger_id = trigger_id
        self.find_calls = 0

    def trigger(self, commit: str) -> str | None:
        return self.trigger_id

    def find_deploy(self, commit: str) -> str | None:
        self.find_calls += 1
        return "dep-queued"

    def get_deploy(self, deploy_id: str) -> dict[str, str]:
        return {"id": deploy_id, "status": next(self.statuses)}


class WaitForDeployTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = DeployConfig(
            api_key="secret",
            service_id="srv-123",
            commit="abc123",
            timeout_seconds=30,
            poll_seconds=1,
        )

    @patch("deploy_render.time.sleep")
    def test_waits_until_deployment_is_live(self, sleep: object) -> None:
        client = FakeRenderClient(["queued", "build_in_progress", "live"])

        deploy_id = wait_for_deploy(client, self.config)  # type: ignore[arg-type]

        self.assertEqual(deploy_id, "dep-123")

    @patch("deploy_render.time.sleep")
    def test_resolves_id_for_queued_trigger(self, sleep: object) -> None:
        client = FakeRenderClient(["created", "live"], trigger_id=None)

        deploy_id = wait_for_deploy(client, self.config)  # type: ignore[arg-type]

        self.assertEqual(deploy_id, "dep-queued")
        self.assertEqual(client.find_calls, 1)

    @patch("deploy_render.time.sleep")
    def test_fails_on_terminal_failure(self, sleep: object) -> None:
        client = FakeRenderClient(["build_in_progress", "build_failed"])

        with self.assertRaisesRegex(RenderDeploymentError, "build_failed"):
            wait_for_deploy(client, self.config)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
