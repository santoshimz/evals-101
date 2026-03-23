from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlsplit

import anyio
import httpx
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client


_SAMPLE_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO2p4Z0AAAAASUVORK5CYII="
)


def _image_payload(image_count: int) -> list[dict[str, str]]:
    return [
        {
            "filename": f"eval-image-{index + 1}.png",
            "content_base64": _SAMPLE_PNG_BASE64,
        }
        for index in range(max(1, image_count))
    ]


def _redact(text: str, secrets: list[str]) -> str:
    redacted = text
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def _extract_text_content(content_blocks: list[Any]) -> str:
    parts: list[str] = []
    for block in content_blocks:
        text = getattr(block, "text", None)
        if text:
            parts.append(str(text))
    return "\n".join(parts).strip()


def _derive_tool_sequence(selected_workflow: str | None, tool_name: str) -> list[str]:
    if selected_workflow == "crop_then_colorize":
        return ["crop_images", "colorize_images"]
    if selected_workflow in {"crop_images", "colorize_images"}:
        return [selected_workflow]
    if tool_name in {"crop_images", "colorize_images"}:
        return [tool_name]
    return []


def _workflow_to_tool_name(workflow: str | None) -> str:
    if workflow in {"crop_images", "colorize_images"}:
        return workflow
    return "run_prompt_workflow"


def _payload_for_case(case: dict[str, Any], tool_name: str) -> tuple[dict[str, Any], list[str]]:
    image_count = int(case.get("image_count", 1))
    payload: dict[str, Any] = {"images": _image_payload(image_count)}
    secrets: list[str] = []

    if tool_name == "run_prompt_workflow":
        payload["prompt"] = str(case.get("prompt", ""))
        payload["credential_mode"] = str(case.get("credential_mode", "server"))
    elif tool_name == "colorize_images":
        payload["credential_mode"] = str(case.get("credential_mode", "server"))
        payload["prompt"] = str(case.get("colorize_prompt") or case.get("prompt") or "")

    if case.get("model"):
        payload["model"] = str(case["model"])

    gemini_api_key = str(case.get("gemini_api_key") or "").strip()
    if gemini_api_key:
        payload["gemini_api_key"] = gemini_api_key
        secrets.append(gemini_api_key)

    return payload, secrets


class Mcp201RemoteSystem:
    def __init__(
        self,
        *,
        base_url: str,
        auth_token: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        asgi_app: Any | None = None,
    ) -> None:
        self.base_url = base_url
        self.auth_token = auth_token
        self.http_client = http_client
        self.asgi_app = asgi_app

    def run_case(self, case: dict[str, Any]) -> dict[str, Any]:
        return anyio.run(self.run_case_async, case)

    async def run_case_async(self, case: dict[str, Any]) -> dict[str, Any]:
        expected_workflow = case.get("expected_workflow")
        tool_name = str(case.get("tool_name") or _workflow_to_tool_name(expected_workflow if not case.get("prompt") else None))
        if case.get("prompt"):
            tool_name = str(case.get("tool_name") or "run_prompt_workflow")

        payload, secrets = _payload_for_case(case, tool_name)
        if self.auth_token:
            secrets.append(self.auth_token)

        async with self._get_http_client() as http_client:
            async with streamable_http_client(self.base_url, http_client=http_client) as (read_stream, write_stream, _):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    call_result = await session.call_tool(tool_name, payload)
        return self._normalize_result(case, tool_name, call_result, secrets)

    @asynccontextmanager
    async def _get_http_client(self) -> AsyncIterator[httpx.AsyncClient]:
        if self.http_client is not None:
            yield self.http_client
            return

        headers: dict[str, str] = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        if self.asgi_app is not None:
            parsed = urlsplit(self.base_url)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            transport = httpx.ASGITransport(app=self.asgi_app)
            async with self.asgi_app.router.lifespan_context(self.asgi_app):
                async with httpx.AsyncClient(
                    transport=transport,
                    base_url=base_url,
                    headers=headers,
                    timeout=60.0,
                ) as client:
                    yield client
            return

        async with httpx.AsyncClient(headers=headers, timeout=60.0) as client:
            yield client

    def _normalize_result(self, case: dict[str, Any], tool_name: str, call_result: Any, secrets: list[str]) -> dict[str, Any]:
        if getattr(call_result, "isError", False):
            error_text = _redact(_extract_text_content(list(getattr(call_result, "content", []))), secrets)
            selected_workflow = "clarify" if "did not clearly match a supported workflow" in error_text.lower() else None
            return {
                "workflow": selected_workflow,
                "selected_workflow": selected_workflow,
                "tool_sequence": [],
                "output_count": 0,
                "image_count": int(case.get("image_count", 0)),
                "log_lines": [error_text] if error_text else [],
            }

        structured_content = dict(getattr(call_result, "structuredContent", None) or {})
        if not structured_content:
            raw_text = _extract_text_content(list(getattr(call_result, "content", [])))
            if raw_text:
                structured_content = json.loads(raw_text)

        selected_workflow = structured_content.get("selected_workflow") or structured_content.get("tool_name") or (
            tool_name if tool_name != "run_prompt_workflow" else None
        )
        outputs = structured_content.get("outputs", [])
        warnings = [str(item) for item in structured_content.get("warnings", [])]

        return {
            "workflow": selected_workflow,
            "selected_workflow": selected_workflow,
            "tool_sequence": _derive_tool_sequence(selected_workflow, tool_name),
            "output_count": len(outputs),
            "image_count": int(structured_content.get("image_count", case.get("image_count", 0))),
            "log_lines": [_redact(warning, secrets) for warning in warnings],
            "warnings": [_redact(warning, secrets) for warning in warnings],
            "raw_result": {
                "tool_name": structured_content.get("tool_name"),
                "selected_workflow": structured_content.get("selected_workflow"),
                "credential_mode": structured_content.get("credential_mode"),
            },
        }
