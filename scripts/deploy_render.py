#!/usr/bin/env python3
"""Trigger and verify a Render deployment for one Git commit."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


IN_PROGRESS_STATUSES = {
    "created",
    "queued",
    "build_in_progress",
    "pre_deploy_in_progress",
    "update_in_progress",
}
FAILED_STATUSES = {
    "build_failed",
    "pre_deploy_failed",
    "update_failed",
    "canceled",
    "deactivated",
}


class RenderDeploymentError(RuntimeError):
    """Raised when Render rejects or fails a deployment."""


@dataclass(frozen=True)
class DeployConfig:
    api_key: str
    service_id: str
    commit: str
    timeout_seconds: int = 1800
    poll_seconds: int = 10


class RenderClient:
    def __init__(self, api_key: str, service_id: str) -> None:
        self.api_key = api_key
        self.service_id = quote(service_id, safe="")
        self.base_url = f"https://api.render.com/v1/services/{self.service_id}"

    def request(
        self, method: str, path: str, payload: dict[str, str] | None = None
    ) -> tuple[int, Any | None]:
        body = json.dumps(payload).encode() if payload is not None else None
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "resume-optimizer-jenkins/1.0",
            },
        )

        attempts = 5 if method == "GET" else 1
        for attempt in range(attempts):
            try:
                with urlopen(request, timeout=30) as response:
                    response_body = response.read()
                    data = json.loads(response_body) if response_body else None
                    return response.status, data
            except HTTPError as error:
                retryable = error.code == 429 or error.code >= 500
                if method == "GET" and retryable and attempt < attempts - 1:
                    delay = min(2**attempt, 16)
                    print(
                        f"Render API returned HTTP {error.code}; retrying in {delay}s...",
                        flush=True,
                    )
                    time.sleep(delay)
                    continue
                detail = error.read().decode(errors="replace")[:500]
                raise RenderDeploymentError(
                    f"Render API returned HTTP {error.code}: {detail or error.reason}"
                ) from error
            except (URLError, TimeoutError) as error:
                if method == "GET" and attempt < attempts - 1:
                    delay = min(2**attempt, 16)
                    print(f"Render API unavailable; retrying in {delay}s...", flush=True)
                    time.sleep(delay)
                    continue
                raise RenderDeploymentError(
                    f"Render API request failed: {error}"
                ) from error

        raise RenderDeploymentError("Render API retry limit reached")

    def trigger(self, commit: str) -> str | None:
        status_code, deploy = self.request(
            "POST",
            "/deploys",
            {"clearCache": "do_not_clear", "commitId": commit},
        )
        if status_code not in {201, 202}:
            raise RenderDeploymentError(
                f"Render returned unexpected trigger status {status_code}"
            )
        if isinstance(deploy, dict) and deploy.get("id"):
            return str(deploy["id"])
        return None

    def get_deploy(self, deploy_id: str) -> dict[str, Any]:
        _, deploy = self.request("GET", f"/deploys/{quote(deploy_id, safe='')}")
        if not isinstance(deploy, dict):
            raise RenderDeploymentError("Render returned an invalid deployment response")
        return deploy

    def find_deploy(self, commit: str) -> str | None:
        _, items = self.request("GET", "/deploys?limit=20")
        if not isinstance(items, list):
            raise RenderDeploymentError("Render returned an invalid deployment list")

        for item in items:
            deploy = item.get("deploy", item) if isinstance(item, dict) else None
            if not isinstance(deploy, dict):
                continue
            deployed_commit = deploy.get("commit")
            if (
                isinstance(deployed_commit, dict)
                and deployed_commit.get("id") == commit
                and deploy.get("id")
            ):
                return str(deploy["id"])
        return None


def wait_for_deploy(client: RenderClient, config: DeployConfig) -> str:
    deadline = time.monotonic() + config.timeout_seconds
    deploy_id = client.trigger(config.commit)

    while deploy_id is None and time.monotonic() < deadline:
        print("Render queued the request; waiting for a deployment ID...", flush=True)
        time.sleep(config.poll_seconds)
        deploy_id = client.find_deploy(config.commit)

    if deploy_id is None:
        raise RenderDeploymentError("Timed out waiting for Render to queue the deployment")

    previous_status = ""
    while time.monotonic() < deadline:
        deploy = client.get_deploy(deploy_id)
        status = str(deploy.get("status", ""))
        if status != previous_status:
            print(f"Render deployment {deploy_id}: {status or 'unknown'}", flush=True)
            previous_status = status

        if status == "live":
            return deploy_id
        if status in FAILED_STATUSES:
            raise RenderDeploymentError(
                f"Render deployment {deploy_id} ended with status {status}"
            )
        if status not in IN_PROGRESS_STATUSES:
            raise RenderDeploymentError(
                f"Render deployment {deploy_id} returned unknown status {status!r}"
            )
        time.sleep(config.poll_seconds)

    raise RenderDeploymentError(f"Render deployment {deploy_id} timed out")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True, help="Git commit SHA to deploy")
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--poll-seconds", type=int, default=10)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_key = os.environ.get("RENDER_API_KEY", "").strip()
    service_id = os.environ.get("RENDER_SERVICE_ID", "").strip()
    if not api_key or not service_id:
        print("RENDER_API_KEY and RENDER_SERVICE_ID are required", file=sys.stderr)
        return 2
    if args.timeout_seconds <= 0 or args.poll_seconds <= 0:
        print("Timeout and poll interval must be positive", file=sys.stderr)
        return 2

    config = DeployConfig(
        api_key=api_key,
        service_id=service_id,
        commit=args.commit,
        timeout_seconds=args.timeout_seconds,
        poll_seconds=args.poll_seconds,
    )
    try:
        deploy_id = wait_for_deploy(
            RenderClient(config.api_key, config.service_id), config
        )
    except RenderDeploymentError as error:
        print(f"Render deployment failed: {error}", file=sys.stderr)
        return 1

    print(f"Render deployment {deploy_id} is live.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
