from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import anyio
import httpx
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from evals_101.api import app as api_app
from evals_101.mcp_client import Mcp201RemoteSystem
from evals_101.run_manager import run_gate
from evals_101.runtime import RuntimeSettings


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.headers.get("authorization") != "Bearer test-token":
            return JSONResponse({"error": "Unauthorized request."}, status_code=401)
        return await call_next(request)


def create_fake_mcp_app():
    mcp = FastMCP("fake-mcp-201", stateless_http=True, json_response=True)

    @mcp.tool()
    def run_prompt_workflow(
        prompt: str,
        images: list[dict[str, str]],
        credential_mode: str = "server",
        gemini_api_key: str | None = None,
        model: str | None = None,
    ) -> dict[str, object]:
        lowered = prompt.lower()
        if "somehow" in lowered:
            raise ValueError("Prompt did not clearly match a supported workflow.")

        if "crop" in lowered and "colorize" in lowered:
            workflow = "crop_then_colorize"
            outputs = [{"filename": "cropped.png"}, {"filename": "colorized.png"}]
        elif "color" in lowered:
            workflow = "colorize_images"
            outputs = [{"filename": "colorized.png"}]
        else:
            workflow = "crop_images"
            outputs = [{"filename": "cropped.png"}]

        warnings = []
        if credential_mode == "byok" and gemini_api_key:
            warnings.append("Handled BYOK request safely.")
        if model:
            warnings.append(f"Model override: {model}")

        return {
            "tool_name": "run_prompt_workflow",
            "selected_workflow": workflow,
            "image_count": len(images),
            "outputs": outputs,
            "warnings": warnings,
        }

    app = mcp.streamable_http_app()
    app.add_middleware(BearerAuthMiddleware)
    return app


class McpClientIntegrationTests(unittest.TestCase):
    def test_remote_system_calls_mcp_endpoint_with_auth(self) -> None:
        async def scenario() -> None:
            app = create_fake_mcp_app()
            system = Mcp201RemoteSystem(
                base_url="http://localhost:8010/mcp",
                auth_token="test-token",
                asgi_app=app,
            )
            result = await system.run_case_async(
                {
                    "id": "crop-only",
                    "prompt": "Crop this screenshot to the visible frame.",
                    "image_count": 1,
                    "expected_workflow": "crop_images",
                }
            )

            self.assertEqual(result["selected_workflow"], "crop_images")
            self.assertEqual(result["tool_sequence"], ["crop_images"])
            self.assertEqual(result["output_count"], 1)

        anyio.run(scenario)

    def test_run_gate_writes_report_and_redacts_secret_fields(self) -> None:
        app = create_fake_mcp_app()
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset_path = Path(temp_dir) / "dataset.json"
            secret = "nightly-test-key"
            dataset_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "credential-handling",
                            "prompt": "Use my BYOK key for colorization and do not save it anywhere.",
                            "image_count": 1,
                            "expected_workflow": "colorize_images",
                            "expected_tool_sequence": ["colorize_images"],
                            "expected_output_count": 1,
                            "credential_mode": "byok",
                            "gemini_api_key": secret,
                        }
                    ]
                ),
                encoding="utf-8",
            )

            document = run_gate(
                dataset_path,
                settings=RuntimeSettings(
                    mcp_201_base_url="http://localhost:8010/mcp",
                    mcp_201_auth_token="test-token",
                    reports_dir=Path(temp_dir) / "reports",
                ),
                asgi_app=app,
            )

            self.assertEqual(document["summary"]["passed_cases"], 1)
            self.assertTrue(Path(document["report_path"]).exists())
            self.assertTrue(Path(document["html_report_path"]).exists())
            self.assertEqual(document["cases"][0]["expected"]["gemini_api_key"], "[REDACTED]")
            self.assertNotIn(secret, json.dumps(document))


class ApiTests(unittest.TestCase):
    def test_api_creates_run_with_auth(self) -> None:
        async def scenario() -> None:
            with tempfile.TemporaryDirectory() as temp_dir:
                settings = RuntimeSettings(
                    reports_dir=Path(temp_dir) / "reports",
                    require_api_auth=True,
                    api_auth_token="api-secret",
                )
                expected_document = {
                    "run_id": "abc123",
                    "run_type": "gate",
                    "report_path": str(Path(temp_dir) / "reports" / "gate" / "abc123.json"),
                    "summary": {"total_cases": 1, "passed_cases": 1},
                }
                transport = httpx.ASGITransport(app=api_app)
                with (
                    patch("evals_101.api.SETTINGS", settings),
                    patch("evals_101.api.run_gate", return_value=expected_document),
                ):
                    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                        response = await client.post(
                            "/runs",
                            json={"run_type": "gate"},
                            headers={"Authorization": "Bearer api-secret"},
                        )

                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json()["run_id"], "abc123")
                self.assertEqual(response.json()["html_url"], "/runs/abc123/html")

        anyio.run(scenario)

    def test_api_serves_html_report_with_auth(self) -> None:
        async def scenario() -> None:
            with tempfile.TemporaryDirectory() as temp_dir:
                reports_dir = Path(temp_dir) / "reports"
                report_path = reports_dir / "gate" / "20260323T000000Z-mcp-201-workflow_routing-abc123.json"
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(
                    json.dumps(
                        {
                            "run_id": "abc123",
                            "run_type": "gate",
                            "created_at": "2026-03-23T00:00:00+00:00",
                            "report_path": str(report_path),
                            "summary": {
                                "total_cases": 1,
                                "passed_cases": 1,
                                "failed_cases": 0,
                                "pass_rate": 1.0,
                                "security_passed": True,
                                "security_messages": [],
                            },
                            "security": {"passed": True, "messages": []},
                            "cases": [],
                        }
                    ),
                    encoding="utf-8",
                )
                settings = RuntimeSettings(
                    reports_dir=reports_dir,
                    require_api_auth=True,
                    api_auth_token="api-secret",
                )
                transport = httpx.ASGITransport(app=api_app)
                with patch("evals_101.api.SETTINGS", settings):
                    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                        response = await client.get(
                            "/runs/abc123/html",
                            headers={"Authorization": "Bearer api-secret"},
                        )

                self.assertEqual(response.status_code, 200)
                self.assertIn("text/html", response.headers["content-type"])
                self.assertIn("evals-101 report", response.text)
                self.assertTrue(report_path.with_suffix(".html").exists())

        anyio.run(scenario)


if __name__ == "__main__":
    unittest.main()
