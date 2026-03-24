from __future__ import annotations

from functools import partial
import json
from pathlib import Path
from typing import Any

import anyio
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

from .report_html import build_report_html_path, write_report_html
from .run_manager import run_gate, run_nightly
from .runtime import RuntimeSettings


SETTINGS = RuntimeSettings.from_env()
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASETS = {
    "gate": REPO_ROOT / "datasets" / "gate" / "workflow_routing.json",
    "nightly": REPO_ROOT / "datasets" / "nightly" / "tool_use.json",
}

WEB_APP_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>evals-101</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f8fafc;
      --card: #ffffff;
      --border: #cbd5e1;
      --text: #0f172a;
      --muted: #475569;
      --accent: #2563eb;
      --accent-strong: #1d4ed8;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, Arial, Helvetica, sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    main {
      max-width: 1280px;
      margin: 0 auto;
      padding: 24px;
    }
    .shell {
      display: grid;
      grid-template-columns: 380px 1fr;
      gap: 20px;
      align-items: start;
    }
    .panel {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 16px;
    }
    h1, h2, h3, p { margin-top: 0; }
    p { color: var(--muted); }
    label {
      display: block;
      font-size: 14px;
      font-weight: 600;
      margin-bottom: 6px;
    }
    input {
      width: 100%;
      padding: 10px 12px;
      border: 1px solid var(--border);
      border-radius: 10px;
      margin-bottom: 12px;
    }
    button {
      border: 0;
      border-radius: 10px;
      padding: 10px 12px;
      background: var(--accent);
      color: white;
      font-weight: 700;
      cursor: pointer;
    }
    button.secondary {
      background: #e2e8f0;
      color: var(--text);
    }
    button:hover { background: var(--accent-strong); }
    button.secondary:hover { background: #cbd5e1; }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 16px;
    }
    .status {
      min-height: 22px;
      margin-bottom: 12px;
      color: var(--muted);
    }
    .run-list {
      display: grid;
      gap: 10px;
    }
    .run {
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px;
    }
    .run strong {
      display: block;
      margin-bottom: 6px;
    }
    .run-meta {
      font-size: 13px;
      color: var(--muted);
      margin-bottom: 10px;
    }
    iframe {
      width: 100%;
      min-height: 75vh;
      border: 1px solid var(--border);
      border-radius: 16px;
      background: white;
    }
    @media (max-width: 960px) {
      .shell {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <main>
    <h1>evals-101</h1>
    <p>Run gate or nightly evals and view the generated HTML report.</p>
    <div class="shell">
      <section class="panel">
        <h2>Control Panel</h2>
        <label for="token">evals-101 API Bearer token</label>
        <input id="token" type="password" placeholder="Used to authenticate this evals-101 web app">
        <p>Enter <code>EVALS_101_API_AUTH_TOKEN</code> here when API auth is enabled.</p>
        <div class="actions">
          <button id="save-token" class="secondary" type="button">Save token</button>
          <button id="refresh" class="secondary" type="button">Refresh runs</button>
          <button id="run-gate" type="button">Run gate</button>
          <button id="run-nightly" type="button">Run nightly</button>
        </div>
        <div id="status" class="status">Ready.</div>
        <div id="runs" class="run-list"></div>
      </section>
      <section class="panel">
        <h2>Report Viewer</h2>
        <p id="viewer-label">Select a run to load its HTML report.</p>
        <iframe id="viewer" title="eval report viewer"></iframe>
      </section>
    </div>
  </main>
  <script>
    const tokenInput = document.getElementById("token");
    const statusNode = document.getElementById("status");
    const runsNode = document.getElementById("runs");
    const viewer = document.getElementById("viewer");
    const viewerLabel = document.getElementById("viewer-label");

    tokenInput.value = sessionStorage.getItem("evals101ApiToken") || "";

    function setStatus(message) {
      statusNode.textContent = message;
    }

    function getToken() {
      return tokenInput.value.trim();
    }

    function saveToken() {
      sessionStorage.setItem("evals101ApiToken", getToken());
      setStatus("Token saved for this browser session.");
    }

    async function api(path, options = {}) {
      const headers = new Headers(options.headers || {});
      const token = getToken();
      if (token) {
        headers.set("Authorization", `Bearer ${token}`);
      }
      if (options.body && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
      }
      const response = await fetch(path, { ...options, headers });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error || `Request failed with status ${response.status}.`);
      }
      return response;
    }

    function renderRuns(runs) {
      if (!runs.length) {
        runsNode.innerHTML = "<div class='run'>No reports yet.</div>";
        return;
      }

      runsNode.innerHTML = runs.map((run) => `
        <div class="run">
          <strong>${run.run_type} · ${run.run_id}</strong>
          <div class="run-meta">${run.created_at || "Unknown time"}</div>
          <div class="run-meta">${run.summary ? `${run.summary.passed_cases}/${run.summary.total_cases} passed` : "Summary unavailable"}</div>
          <div class="actions">
            <button type="button" data-run-id="${run.run_id}">View HTML</button>
          </div>
        </div>
      `).join("");

      for (const button of runsNode.querySelectorAll("button[data-run-id]")) {
        button.addEventListener("click", () => {
          viewRun(button.getAttribute("data-run-id"));
        });
      }
    }

    async function loadRuns() {
      setStatus("Loading recent runs...");
      const response = await api("/runs");
      const payload = await response.json();
      renderRuns(payload.runs || []);
      setStatus(`Loaded ${payload.runs?.length || 0} runs.`);
    }

    async function createRun(runType) {
      setStatus(`Starting ${runType} run...`);
      const response = await api("/runs", {
        method: "POST",
        body: JSON.stringify({ run_type: runType }),
      });
      const payload = await response.json();
      setStatus(`Finished ${payload.run_type} run ${payload.run_id}.`);
      await loadRuns();
      await viewRun(payload.run_id);
    }

    async function viewRun(runId) {
      setStatus(`Loading HTML report for ${runId}...`);
      const response = await api(`/runs/${runId}/html`);
      const html = await response.text();
      viewer.srcdoc = html;
      viewerLabel.textContent = `Viewing HTML report for ${runId}.`;
      setStatus(`Loaded HTML report for ${runId}.`);
    }

    document.getElementById("save-token").addEventListener("click", saveToken);
    document.getElementById("refresh").addEventListener("click", () => loadRuns().catch((error) => setStatus(error.message)));
    document.getElementById("run-gate").addEventListener("click", () => createRun("gate").catch((error) => setStatus(error.message)));
    document.getElementById("run-nightly").addEventListener("click", () => createRun("nightly").catch((error) => setStatus(error.message)));

    if (getToken()) {
      loadRuns().catch((error) => setStatus(error.message));
    }
  </script>
</body>
</html>
"""


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


def _report_html_path(report_path: Path, document: dict[str, Any]) -> Path:
    html_path = document.get("html_report_path")
    return Path(html_path) if html_path else build_report_html_path(report_path)


def _run_summary(report_path: Path, document: dict[str, Any]) -> dict[str, Any]:
    run_id = str(document.get("run_id", report_path.stem))
    html_path = _report_html_path(report_path, document)
    return {
        "run_id": run_id,
        "run_type": document.get("run_type"),
        "created_at": document.get("created_at"),
        "report_path": str(report_path),
        "html_report_path": str(html_path),
        "html_url": f"/runs/{run_id}/html",
        "summary": document.get("summary"),
    }


def _error_message(exc: BaseException) -> str:
    nested = getattr(exc, "exceptions", None)
    if nested:
        for inner in nested:
            message = _error_message(inner)
            if message:
                return message
    return str(exc) or exc.__class__.__name__


async def index(_request: Request) -> HTMLResponse:
    return HTMLResponse(WEB_APP_HTML)


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
            "runs": [_run_summary(report_path, summary) for report_path, summary in zip(reports, summaries, strict=False)]
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
            document = await anyio.to_thread.run_sync(partial(run_nightly, dataset_path, settings=SETTINGS))
        else:
            document = await anyio.to_thread.run_sync(partial(run_gate, dataset_path, settings=SETTINGS))
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except SystemExit as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": _error_message(exc)}, status_code=500)

    return JSONResponse(
        _run_summary(Path(document["report_path"]), document),
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


async def get_run_html(request: Request) -> HTMLResponse | JSONResponse:
    try:
        _require_api_auth(request, SETTINGS)
    except PermissionError as exc:
        return JSONResponse({"error": str(exc)}, status_code=401)

    run_id = request.path_params["run_id"]
    report_path = _find_report(run_id, SETTINGS)
    if report_path is None:
        return JSONResponse({"error": f"Run {run_id!r} was not found."}, status_code=404)

    document = _load_report(report_path)
    html_path = _report_html_path(report_path, document)
    if not html_path.exists():
        write_report_html(document, html_path)
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


app = Starlette(
    debug=False,
    routes=[
        Route("/", index),
        Route("/healthz", healthz),
        Route("/runs", list_runs, methods=["GET"]),
        Route("/runs", create_run, methods=["POST"]),
        Route("/runs/{run_id}/html", get_run_html, methods=["GET"]),
        Route("/runs/{run_id}", get_run, methods=["GET"]),
    ],
)


def main() -> None:
    uvicorn.run("evals_101.api:app", host=SETTINGS.api_host, port=SETTINGS.api_port, reload=False)


if __name__ == "__main__":
    main()
