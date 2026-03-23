from __future__ import annotations

from dataclasses import dataclass, field


WORKFLOW_NAMES = ("crop_images", "colorize_images", "crop_then_colorize", "clarify")
TOOL_NAMES = ("crop_images", "colorize_images", "run_prompt_workflow")


@dataclass(frozen=True)
class RequestField:
    name: str
    required: bool
    secret: bool = False
    notes: str = ""


@dataclass(frozen=True)
class ToolContract:
    name: str
    description: str
    request_fields: tuple[RequestField, ...]
    selected_workflow_field: str | None = None


@dataclass(frozen=True)
class SecurityContract:
    max_images: int
    max_file_size_bytes: int
    auth_header: str
    server_key_env: str
    byok_field: str
    forbidden_log_fields: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class BaselineContract:
    repo: str
    workflows: tuple[str, ...]
    tools: tuple[ToolContract, ...]
    security: SecurityContract


MCP201_BASELINE = BaselineContract(
    repo="mcp-201",
    workflows=WORKFLOW_NAMES,
    tools=(
        ToolContract(
            name="crop_images",
            description="Crop uploaded screenshots or images to the visible frame.",
            request_fields=(
                RequestField("images", required=True, notes="1-5 images; base64 encoded image payloads"),
            ),
        ),
        ToolContract(
            name="colorize_images",
            description="Colorize uploaded images with either server credentials or BYOK.",
            request_fields=(
                RequestField("images", required=True),
                RequestField("credential_mode", required=True, notes="server or byok"),
                RequestField("gemini_api_key", required=False, secret=True),
                RequestField("prompt", required=False),
                RequestField("model", required=False),
            ),
        ),
        ToolContract(
            name="run_prompt_workflow",
            description="Interpret a natural-language prompt with AI planning and route to the correct workflow.",
            request_fields=(
                RequestField("prompt", required=True),
                RequestField("images", required=True),
                RequestField("credential_mode", required=False, notes="server or byok"),
                RequestField("gemini_api_key", required=False, secret=True),
                RequestField("model", required=False),
            ),
            selected_workflow_field="selected_workflow",
        ),
    ),
    security=SecurityContract(
        max_images=5,
        max_file_size_bytes=6 * 1024 * 1024,
        auth_header="Authorization: Bearer <token>",
        server_key_env="MCP_201_SERVER_GEMINI_API_KEY",
        byok_field="geminiApiKey",
        forbidden_log_fields=("gemini_api_key", "geminiApiKey", "authorization", "MCP_201_AUTH_TOKEN"),
    ),
)

# Backward-compatible alias for older imports.
MCP101_BASELINE = MCP201_BASELINE
