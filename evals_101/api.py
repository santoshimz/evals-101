from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .run_manager import run_gate, run_nightly
from .runtime import RuntimeSettings


SETTINGS = RuntimeSettings.from_env()
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASETS = {
    "gate": REPO_ROOT / "datasets" / "gate" / "workflow_routing.json",
    "nightly": REPO_ROOT / "datasets" / "nightly" / "tool_use.json",
}


def _require_api_auth(request: Request, settings: RuntimeSettings) -> None:
    if not settings.require_api_auth:
        return

    expected = settings.api_auth_token or ""
    authorization = request.headers.get("authorization", "").strip()
    if not expected or authorization != f"Bearer {expected}":
        raise PermissionError("Unauthorized request.")


def _resolve_dataset(run_type: str, requested_dataset: str | None) -> Path:
    if not requested_dataset:
        return DEFAULT_DATASETS[run_type]

    candidate = (REPO_ROOT / requested_dataset).resolve()
    if REPO_ROOT not in candidate.parents or candidate.suffix != ".json":
        raise ValueError("Dataset path must stay within the evals-101 repo and end with .json.")
    return candidate


def _load_report(report_path: Path) -> dict[str, Any]:
    return json.loads(report_path.read_text(encoding="utf-8"))


def _find_report(run_id: str, settings: RuntimeSettings) -> Path | None:
    reports_dir = settings.reports_dir.expanduser()
    if not reports_dir.exists():
        return None
    matches = sorted(reports_dir.rglob(f"*{run_id}.json"))
    return matches[-1] if matches else None


async def healthz(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


async def list_runs(request: Request) -> JSONResponse:
    try:
        _require_api_auth(request, SETTINGS)
    except PermissionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    reports_dir = SETTINGS.reports_dir.expanduser()
    if not reports_dir.exists():
        return JSONResponse({"runs": []})

    reports = sorted(reports_dir.rglob("*.json"), reverse=True)[:20]
    summaries = [_load_report(report_path) for report_path in reports]
    return JSONResponse(
        {
            "runs": [
                {
                    "run_id": summary.get("run_id"),
                    "run_type": summary.get("run_type"),
                    "created_at": summary.get("created_at"),
                    "report_path": str(report_path),
                }
                for report_path, summary in zip(reports, summaries, strict=False)
            ]
        }
    )


async def create_run(request: Request) -> JSONResponse:
    try:
        _require_api_auth(request, SETTINGS)
    except PermissionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    payload = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    run_type = str(payload.get("run_type", "gate"))
    if run_type not in {"gate", "nightly"}:
        return JSONResponse({"error": "run_type must be either 'gate' or 'nightly'."}, status_code=400)

    try:
        dataset_path = _resolve_dataset(run_type, payload.get("dataset"))
        if run_type == "nightly":
            document = run_nightly(dataset_path, settings=SETTINGS)
        else:
            document = run_gate(dataset_path, settings=SETTINGS)
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except SystemExit as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": str(exc)}, status_code=500)

    return JSONResponse(
        {
            "run_id": document["run_id"],
            "run_type": document["run_type"],
            "report_path": document["report_path"],
            "summary": document["summary"],
        },
        status_code=201,
    )


async def get_run(request: Request) -> JSONResponse:
    try:
        _require_api_auth(request, SETTINGS)
    except PermissionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    run_id = request.path_params["run_id"]
    report_path = _find_report(run_id, SETTINGS)
    if report_path is None:
        return JSONResponse({"error": f"Run {run_id!r} was not found."}, status_code=404)
    return JSONResponse(_load_report(report_path))


app = Starlette(
    debug=False,
    routes=[
        Route("/healthz", healthz),
        Route("/runs", list_runs, methods=["GET"]),
        Route("/runs", create_run, methods=["POST"]),
        Route("/runs/{run_id}", get_run, methods=["GET"]),
    ],
)


def main() -> None:
    uvicorn.run("evals_101.api:app", host=SETTINGS.api_host, port=SETTINGS.api_port, reload=False)


if __name__ == "__main__":
    main()
