from __future__ import annotations

import argparse
import json

from .run_manager import run_nightly
from .runtime import RuntimeSettings


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run DeepEval-backed nightly scoring.")
    parser.add_argument("--dataset", default="datasets/nightly/tool_use.json")
    parser.add_argument("--system", choices=("mcp-201",), default="mcp-201")
    parser.add_argument("--output", help="Optional report output path.")
    parser.add_argument("--base-url", help="Override the target MCP-201 base URL.")
    parser.add_argument("--auth-token", help="Optional MCP-201 bearer token.")
    args = parser.parse_args(argv)

    settings = RuntimeSettings.from_env()
    if args.base_url:
        settings = RuntimeSettings(
            system_name=settings.system_name,
            mcp_201_base_url=args.base_url,
            mcp_201_auth_token=args.auth_token if args.auth_token is not None else settings.mcp_201_auth_token,
            reports_dir=settings.reports_dir,
            api_host=settings.api_host,
            api_port=settings.api_port,
            require_api_auth=settings.require_api_auth,
            api_auth_token=settings.api_auth_token,
        )
    elif args.auth_token is not None:
        settings = RuntimeSettings(
            system_name=settings.system_name,
            mcp_201_base_url=settings.mcp_201_base_url,
            mcp_201_auth_token=args.auth_token,
            reports_dir=settings.reports_dir,
            api_host=settings.api_host,
            api_port=settings.api_port,
            require_api_auth=settings.require_api_auth,
            api_auth_token=settings.api_auth_token,
        )

    document = run_nightly(args.dataset, settings=settings, output_path=args.output)
    print(json.dumps(document, indent=2))


if __name__ == "__main__":
    main()
