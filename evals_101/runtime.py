from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimeSettings:
    system_name: str = "mcp-201"
    mcp_201_base_url: str = "http://localhost:8010/mcp"
    mcp_201_auth_token: str | None = None
    reports_dir: Path = Path("reports")
    api_host: str = "0.0.0.0"
    api_port: int = 8020
    require_api_auth: bool = False
    api_auth_token: str | None = None

    @classmethod
    def from_env(cls) -> "RuntimeSettings":
        reports_dir = Path(os.environ.get("EVALS_101_REPORTS_DIR", "reports")).expanduser()
        require_api_auth = os.environ.get("EVALS_101_REQUIRE_API_AUTH", "false").strip().lower() == "true"
        api_auth_token = os.environ.get("EVALS_101_API_AUTH_TOKEN", "").strip() or None
        return cls(
            mcp_201_base_url=os.environ.get("MCP_201_BASE_URL", "http://localhost:8010/mcp").strip()
            or "http://localhost:8010/mcp",
            mcp_201_auth_token=os.environ.get("MCP_201_AUTH_TOKEN", "").strip() or None,
            reports_dir=reports_dir,
            api_host=os.environ.get("EVALS_101_API_HOST", "0.0.0.0").strip() or "0.0.0.0",
            api_port=int(os.environ.get("EVALS_101_API_PORT", "8020")),
            require_api_auth=require_api_auth,
            api_auth_token=api_auth_token,
        )
