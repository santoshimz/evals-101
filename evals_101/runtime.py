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
        reports_dir = _reports_dir_from_env()
        require_api_auth = _bool_from_env("EVALS_101_REQUIRE_API_AUTH", default=_is_railway_environment())
        api_auth_token = os.environ.get("EVALS_101_API_AUTH_TOKEN", "").strip() or None
        api_port = os.environ.get("EVALS_101_API_PORT", "").strip() or os.environ.get("PORT", "8020")
        return cls(
            mcp_201_base_url=os.environ.get("MCP_201_BASE_URL", "http://localhost:8010/mcp").strip()
            or "http://localhost:8010/mcp",
            mcp_201_auth_token=os.environ.get("MCP_201_AUTH_TOKEN", "").strip() or None,
            reports_dir=reports_dir,
            api_host=os.environ.get("EVALS_101_API_HOST", "0.0.0.0").strip() or "0.0.0.0",
            api_port=int(api_port),
            require_api_auth=require_api_auth,
            api_auth_token=api_auth_token,
        )


def _is_railway_environment() -> bool:
    return bool(os.environ.get("RAILWAY_ENVIRONMENT_ID", "").strip())


def _bool_from_env(name: str, *, default: bool) -> bool:
    raw_value = os.environ.get(name, "").strip().lower()
    if not raw_value:
        return default
    return raw_value in {"1", "true", "yes", "on"}


def _reports_dir_from_env() -> Path:
    configured_dir = os.environ.get("EVALS_101_REPORTS_DIR", "").strip()
    if configured_dir:
        return Path(configured_dir).expanduser()

    railway_volume_mount = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    if railway_volume_mount:
        return Path(railway_volume_mount).expanduser() / "reports"

    return Path("reports").expanduser()
