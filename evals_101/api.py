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
      --bg: #0f172a;
      --bg-soft: #e2e8f0;
      --surface: rgba(255, 255, 255, 0.9);
      --surface-strong: #ffffff;
      --surface-muted: #eef2ff;
      --border: rgba(148, 163, 184, 0.24);
      --border-strong: rgba(99, 102, 241, 0.18);
      --text: #0f172a;
      --muted: #475569;
      --muted-strong: #334155;
      --accent: #4f46e5;
      --accent-strong: #4338ca;
      --accent-soft: rgba(79, 70, 229, 0.12);
      --success: #15803d;
      --success-soft: rgba(34, 197, 94, 0.14);
      --warning: #b45309;
      --warning-soft: rgba(245, 158, 11, 0.16);
      --danger: #b91c1c;
      --danger-soft: rgba(239, 68, 68, 0.14);
      --shadow-lg: 0 24px 60px rgba(15, 23, 42, 0.18);
      --shadow-md: 0 16px 32px rgba(15, 23, 42, 0.1);
      --radius-xl: 28px;
      --radius-lg: 22px;
      --radius-md: 16px;
      --radius-sm: 12px;
    }
    * { box-sizing: border-box; }
    html { background: #f8fafc; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: Inter, Arial, Helvetica, sans-serif;
      background:
        radial-gradient(circle at top left, rgba(99, 102, 241, 0.16), transparent 28%),
        radial-gradient(circle at top right, rgba(14, 165, 233, 0.14), transparent 24%),
        linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);
      color: var(--text);
    }
    main {
      max-width: 1440px;
      margin: 0 auto;
      padding: 32px 24px 40px;
    }
    h1, h2, h3, p {
      margin-top: 0;
    }
    .hero {
      position: relative;
      overflow: hidden;
      margin-bottom: 24px;
      padding: 28px;
      border: 1px solid rgba(255, 255, 255, 0.42);
      border-radius: var(--radius-xl);
      background:
        linear-gradient(135deg, rgba(15, 23, 42, 0.96), rgba(30, 41, 59, 0.92)),
        linear-gradient(135deg, rgba(79, 70, 229, 0.24), rgba(14, 165, 233, 0.2));
      box-shadow: var(--shadow-lg);
      color: #f8fafc;
    }
    .hero::after {
      content: "";
      position: absolute;
      inset: auto -8% -35% auto;
      width: 340px;
      height: 340px;
      border-radius: 999px;
      background: radial-gradient(circle, rgba(129, 140, 248, 0.34), transparent 68%);
      pointer-events: none;
    }
    .hero-grid {
      position: relative;
      display: grid;
      grid-template-columns: minmax(0, 1.6fr) minmax(280px, 0.9fr);
      gap: 20px;
      align-items: end;
    }
    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 14px;
      padding: 7px 12px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.08);
      color: rgba(248, 250, 252, 0.84);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }
    .headline {
      max-width: 760px;
      margin-bottom: 12px;
      font-size: clamp(2rem, 4vw, 3.4rem);
      line-height: 1.02;
      letter-spacing: -0.04em;
    }
    .hero-copy {
      max-width: 700px;
      margin-bottom: 0;
      color: rgba(226, 232, 240, 0.88);
      font-size: 1rem;
      line-height: 1.7;
    }
    .hero-summary {
      display: grid;
      gap: 12px;
      padding: 18px;
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: var(--radius-lg);
      background: rgba(255, 255, 255, 0.06);
      backdrop-filter: blur(12px);
    }
    .hero-summary-label {
      color: rgba(226, 232, 240, 0.78);
      font-size: 13px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .hero-summary-value {
      font-size: 2rem;
      font-weight: 800;
      letter-spacing: -0.04em;
    }
    .hero-summary-detail {
      color: rgba(226, 232, 240, 0.82);
      line-height: 1.6;
    }
    .layout {
      display: grid;
      grid-template-columns: 380px minmax(0, 1fr);
      gap: 20px;
      align-items: start;
    }
    .sidebar,
    .viewer-panel,
    .panel {
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      background: var(--surface);
      box-shadow: var(--shadow-md);
      backdrop-filter: blur(14px);
    }
    .sidebar {
      display: grid;
      gap: 16px;
      padding: 18px;
    }
    .panel {
      padding: 18px;
    }
    .section-title {
      margin-bottom: 6px;
      font-size: 1.05rem;
      letter-spacing: -0.02em;
    }
    .section-copy {
      margin-bottom: 16px;
      color: var(--muted);
      line-height: 1.6;
    }
    label {
      display: block;
      margin-bottom: 8px;
      font-size: 13px;
      font-weight: 700;
      color: var(--muted-strong);
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    input {
      width: 100%;
      padding: 13px 14px;
      border: 1px solid rgba(148, 163, 184, 0.28);
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.86);
      color: var(--text);
      font: inherit;
      box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.04);
      transition: border-color 120ms ease, box-shadow 120ms ease, background 120ms ease;
    }
    input:focus {
      outline: none;
      border-color: rgba(79, 70, 229, 0.5);
      box-shadow: 0 0 0 4px rgba(79, 70, 229, 0.12);
      background: #ffffff;
    }
    .token-hint {
      margin: 10px 0 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.6;
    }
    .button-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    button {
      border: 0;
      border-radius: 14px;
      padding: 11px 14px;
      background: var(--accent);
      color: #ffffff;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      box-shadow: 0 12px 24px rgba(79, 70, 229, 0.22);
      transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease, opacity 120ms ease;
    }
    button:hover:not(:disabled) {
      transform: translateY(-1px);
      background: var(--accent-strong);
      box-shadow: 0 16px 28px rgba(79, 70, 229, 0.28);
    }
    button.secondary {
      background: rgba(255, 255, 255, 0.78);
      color: var(--text);
      box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.22);
    }
    button.secondary:hover:not(:disabled) {
      background: #ffffff;
      box-shadow: inset 0 0 0 1px rgba(99, 102, 241, 0.16), 0 10px 20px rgba(15, 23, 42, 0.08);
    }
    button:disabled {
      opacity: 0.65;
      cursor: wait;
      transform: none;
      box-shadow: none;
    }
    .quick-stats {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .stat-card {
      padding: 16px;
      border: 1px solid var(--border-strong);
      border-radius: var(--radius-md);
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(238, 242, 255, 0.92));
    }
    .stat-label {
      color: var(--muted);
      font-size: 13px;
      font-weight: 600;
    }
    .stat-value {
      margin-top: 10px;
      font-size: 1.8rem;
      font-weight: 800;
      letter-spacing: -0.04em;
    }
    .stat-note {
      margin-top: 6px;
      color: var(--muted);
      font-size: 13px;
    }
    .status {
      min-height: 24px;
      padding: 12px 14px;
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.76);
      color: var(--muted-strong);
      line-height: 1.5;
    }
    .status[data-tone="loading"] {
      background: var(--accent-soft);
      color: var(--accent-strong);
    }
    .status[data-tone="success"] {
      background: var(--success-soft);
      color: var(--success);
    }
    .status[data-tone="error"] {
      background: var(--danger-soft);
      color: var(--danger);
    }
    .run-list {
      display: grid;
      gap: 12px;
    }
    .empty-state,
    .run-card {
      padding: 16px;
      border: 1px solid rgba(148, 163, 184, 0.2);
      border-radius: var(--radius-md);
      background: rgba(255, 255, 255, 0.78);
    }
    .empty-state {
      color: var(--muted);
      text-align: center;
      line-height: 1.7;
    }
    .run-card.active {
      border-color: rgba(79, 70, 229, 0.3);
      box-shadow: inset 0 0 0 1px rgba(79, 70, 229, 0.12);
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(238, 242, 255, 0.88));
    }
    .run-header {
      display: flex;
      gap: 10px;
      align-items: flex-start;
      justify-content: space-between;
      margin-bottom: 10px;
    }
    .run-title {
      margin: 0;
      font-size: 1rem;
      line-height: 1.45;
      word-break: break-word;
    }
    .chip-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 10px;
    }
    .chip {
      display: inline-flex;
      align-items: center;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.03em;
    }
    .chip.gate {
      background: rgba(79, 70, 229, 0.1);
      color: var(--accent-strong);
    }
    .chip.nightly {
      background: rgba(14, 165, 233, 0.12);
      color: #0369a1;
    }
    .chip.success {
      background: var(--success-soft);
      color: var(--success);
    }
    .chip.warn {
      background: var(--warning-soft);
      color: var(--warning);
    }
    .run-meta {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
    }
    .run-actions {
      margin-top: 14px;
      display: flex;
      gap: 8px;
    }
    .viewer-panel {
      padding: 18px;
    }
    .viewer-header {
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
      align-items: end;
      justify-content: space-between;
      margin-bottom: 16px;
    }
    .viewer-title {
      margin-bottom: 6px;
      font-size: 1.25rem;
      letter-spacing: -0.03em;
    }
    .viewer-copy {
      margin-bottom: 0;
      color: var(--muted);
      line-height: 1.6;
    }
    .viewer-badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 10px 12px;
      border-radius: 999px;
      background: rgba(79, 70, 229, 0.1);
      color: var(--accent-strong);
      font-size: 13px;
      font-weight: 700;
    }
    .viewer-frame {
      overflow: hidden;
      border: 1px solid rgba(148, 163, 184, 0.22);
      border-radius: calc(var(--radius-lg) - 4px);
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.94));
    }
    iframe {
      width: 100%;
      min-height: 78vh;
      border: 0;
      background: #ffffff;
    }
    code {
      padding: 2px 6px;
      border-radius: 8px;
      background: rgba(15, 23, 42, 0.06);
      font-size: 0.92em;
    }
    @media (max-width: 1100px) {
      .hero-grid,
      .layout {
        grid-template-columns: 1fr;
      }
    }
    @media (max-width: 720px) {
      main {
        padding: 20px 16px 28px;
      }
      .hero,
      .sidebar,
      .viewer-panel,
      .panel {
        padding: 16px;
      }
      .quick-stats {
        grid-template-columns: 1fr;
      }
      .button-row,
      .run-actions {
        flex-direction: column;
      }
      button {
        width: 100%;
      }
      iframe {
        min-height: 64vh;
      }
    }
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="hero-grid">
        <div>
          <div class="eyebrow">Live evaluation workspace</div>
          <h1 class="headline">Professional run control and report review for gate and nightly evals.</h1>
          <p class="hero-copy">Launch deterministic or rubric-based runs, keep recent results within reach, and review the generated HTML report in a cleaner workspace built for day-to-day evaluation work.</p>
        </div>
        <div class="hero-summary">
          <div class="hero-summary-label">Workspace status</div>
          <div id="hero-run-count" class="hero-summary-value">0 runs</div>
          <div id="hero-summary" class="hero-summary-detail">Save a token if auth is enabled, then refresh recent reports or start a new run.</div>
        </div>
      </div>
    </section>

    <div class="layout">
      <aside class="sidebar">
        <section class="panel">
          <h2 class="section-title">Access</h2>
          <p class="section-copy">Use the session token field when the eval API is protected.</p>
          <label for="token">evals-101 API Bearer token</label>
          <input id="token" type="password" placeholder="Used only in this browser session">
          <p class="token-hint">Enter <code>EVALS_101_API_AUTH_TOKEN</code> here when API auth is enabled.</p>
          <div class="button-row" style="margin-top: 14px;">
            <button id="save-token" class="secondary" type="button">Save token</button>
            <button id="refresh" class="secondary" type="button" data-busy-label="Refreshing...">Refresh runs</button>
          </div>
        </section>

        <section class="panel">
          <h2 class="section-title">Run Actions</h2>
          <p class="section-copy">Start a fresh report and automatically load it into the viewer when it completes.</p>
          <div class="button-row">
            <button id="run-gate" type="button" data-busy-label="Running gate...">Run gate</button>
            <button id="run-nightly" type="button" data-busy-label="Running nightly...">Run nightly</button>
          </div>
        </section>

        <section class="quick-stats" aria-label="Run summary">
          <div class="stat-card">
            <div class="stat-label">Recent runs</div>
            <div id="stat-total-runs" class="stat-value">0</div>
            <div class="stat-note">Last 20 reports surfaced here.</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Average pass rate</div>
            <div id="stat-average-pass-rate" class="stat-value">0%</div>
            <div class="stat-note">Across reports with summary data.</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Gate runs</div>
            <div id="stat-gate-runs" class="stat-value">0</div>
            <div class="stat-note">Deterministic routing and security checks.</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Nightly runs</div>
            <div id="stat-nightly-runs" class="stat-value">0</div>
            <div class="stat-note">Broader judge-model grading.</div>
          </div>
        </section>

        <section>
          <h2 class="section-title">Recent Reports</h2>
          <p class="section-copy">Open a recent run to inspect its HTML report in the viewer.</p>
          <div id="status" class="status" data-tone="neutral">Ready.</div>
          <div id="runs" class="run-list" style="margin-top: 12px;"></div>
        </section>
      </aside>

      <section class="viewer-panel">
        <div class="viewer-header">
          <div>
            <h2 class="viewer-title">Report Viewer</h2>
            <p id="viewer-label" class="viewer-copy">Select a run to load its generated HTML report.</p>
          </div>
          <div id="viewer-run-pill" class="viewer-badge">No report selected</div>
        </div>
        <div class="viewer-frame">
          <iframe id="viewer" title="eval report viewer"></iframe>
        </div>
      </section>
    </div>
  </main>
  <script>
    const tokenInput = document.getElementById("token");
    const statusNode = document.getElementById("status");
    const runsNode = document.getElementById("runs");
    const viewer = document.getElementById("viewer");
    const viewerLabel = document.getElementById("viewer-label");
    const viewerRunPill = document.getElementById("viewer-run-pill");
    const heroRunCount = document.getElementById("hero-run-count");
    const heroSummary = document.getElementById("hero-summary");
    const statTotalRuns = document.getElementById("stat-total-runs");
    const statAveragePassRate = document.getElementById("stat-average-pass-rate");
    const statGateRuns = document.getElementById("stat-gate-runs");
    const statNightlyRuns = document.getElementById("stat-nightly-runs");
    const actionButtons = Array.from(document.querySelectorAll("button[data-busy-label]"));
    let currentRunId = "";
    let latestRuns = [];

    tokenInput.value = sessionStorage.getItem("evals101ApiToken") || "";

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function setStatus(message, tone = "neutral") {
      statusNode.textContent = message;
      statusNode.dataset.tone = tone;
    }

    function getToken() {
      return tokenInput.value.trim();
    }

    function saveToken() {
      sessionStorage.setItem("evals101ApiToken", getToken());
      setStatus("Token saved for this browser session.", "success");
    }

    function setBusy(isBusy) {
      for (const button of actionButtons) {
        if (isBusy) {
          button.dataset.originalLabel = button.textContent;
          button.textContent = button.dataset.busyLabel || button.textContent;
        } else if (button.dataset.originalLabel) {
          button.textContent = button.dataset.originalLabel;
        }
        button.disabled = isBusy;
      }
    }

    function setButtonBusy(buttonId, isBusy) {
      const button = document.getElementById(buttonId);
      if (!button) {
        return;
      }
      if (isBusy) {
        button.dataset.originalLabel = button.textContent;
        button.textContent = button.dataset.busyLabel || button.textContent;
      } else if (button.dataset.originalLabel) {
        button.textContent = button.dataset.originalLabel;
      }
      button.disabled = isBusy;
    }

    function renderViewerPlaceholder(message) {
      viewer.srcdoc = `
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="utf-8">
          <style>
            body {
              margin: 0;
              min-height: 100vh;
              display: grid;
              place-items: center;
              padding: 32px;
              background: linear-gradient(180deg, #f8fafc, #eef2ff);
              color: #334155;
              font-family: Inter, Arial, Helvetica, sans-serif;
            }
            .placeholder {
              max-width: 520px;
              padding: 28px;
              border: 1px solid rgba(148, 163, 184, 0.24);
              border-radius: 24px;
              background: rgba(255, 255, 255, 0.92);
              text-align: center;
              line-height: 1.7;
              box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
            }
            h1 {
              margin: 0 0 12px;
              color: #0f172a;
              font-size: 28px;
            }
            p {
              margin: 0;
            }
          </style>
        </head>
        <body>
          <section class="placeholder">
            <h1>Report viewer</h1>
            <p>${escapeHtml(message)}</p>
          </section>
        </body>
        </html>
      `;
    }

    function updateSummaryCards(runs) {
      const totalRuns = runs.length;
      const gateRuns = runs.filter((run) => run.run_type === "gate").length;
      const nightlyRuns = runs.filter((run) => run.run_type === "nightly").length;
      const passRates = runs
        .map((run) => Number(run.summary && typeof run.summary.pass_rate === "number" ? run.summary.pass_rate : NaN))
        .filter((value) => !Number.isNaN(value));
      const averagePassRate = passRates.length
        ? Math.round((passRates.reduce((total, value) => total + value, 0) / passRates.length) * 100)
        : 0;

      statTotalRuns.textContent = String(totalRuns);
      statGateRuns.textContent = String(gateRuns);
      statNightlyRuns.textContent = String(nightlyRuns);
      statAveragePassRate.textContent = `${averagePassRate}%`;
      heroRunCount.textContent = `${totalRuns} ${totalRuns === 1 ? "run" : "runs"}`;
      heroSummary.textContent = totalRuns
        ? `${gateRuns} gate and ${nightlyRuns} nightly reports are ready to review.`
        : "Save a token if auth is enabled, then refresh recent reports or start a new run.";
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
      updateSummaryCards(runs);

      if (!runs.length) {
        runsNode.innerHTML = "<div class='empty-state'>No reports yet. Run a gate or nightly eval to generate your first HTML report.</div>";
        return;
      }

      runsNode.innerHTML = runs.map((run) => {
        const summary = run.summary || {};
        const passRate = typeof summary.pass_rate === "number"
          ? `${Math.round(summary.pass_rate * 100)}% pass rate`
          : "Summary unavailable";
        const passLabel = summary.total_cases
          ? `${summary.passed_cases}/${summary.total_cases} cases passed`
          : "Summary unavailable";
        const securityPassed = summary.security_passed !== undefined ? Boolean(summary.security_passed) : null;
        return `
          <article class="run-card ${run.run_id === currentRunId ? "active" : ""}">
            <div class="run-header">
              <div>
                <h3 class="run-title">${escapeHtml(run.run_id || "unknown-run")}</h3>
                <div class="run-meta">${escapeHtml(run.created_at || "Unknown time")}</div>
              </div>
            </div>
            <div class="chip-row">
              <span class="chip ${escapeHtml(run.run_type || "gate")}">${escapeHtml(run.run_type || "run")}</span>
              <span class="chip ${securityPassed === false ? "warn" : "success"}">${escapeHtml(passRate)}</span>
              ${securityPassed === null ? "" : `<span class="chip ${securityPassed ? "success" : "warn"}">Security ${securityPassed ? "pass" : "review"}</span>`}
            </div>
            <div class="run-meta">${escapeHtml(passLabel)}</div>
            <div class="run-actions">
              <button type="button" data-run-id="${escapeHtml(run.run_id)}">View HTML</button>
            </div>
          </article>
        `;
      }).join("");

      for (const button of runsNode.querySelectorAll("button[data-run-id]")) {
        button.addEventListener("click", () => {
          viewRun(button.getAttribute("data-run-id"));
        });
      }
    }

    async function loadRuns(options = {}) {
      const shouldAutoSelect = options.autoSelect !== false;
      setBusy(true);
      setStatus("Loading recent runs...", "loading");
      try {
        const response = await api("/runs");
        const payload = await response.json();
        const runs = payload.runs || [];
        latestRuns = runs;
        renderRuns(runs);
        setStatus(`Loaded ${runs.length} recent run${runs.length === 1 ? "" : "s"}.`, "success");
        if (shouldAutoSelect && runs.length && !currentRunId) {
          await viewRun(runs[0].run_id, { preserveStatus: true });
        }
      } finally {
        setBusy(false);
      }
    }

    async function createRun(runType) {
      const buttonId = runType === "nightly" ? "run-nightly" : "run-gate";
      setButtonBusy(buttonId, true);
      setStatus(`Starting ${runType} run...`, "loading");
      try {
        const response = await api("/runs", {
          method: "POST",
          body: JSON.stringify({ run_type: runType }),
        });
        const payload = await response.json();
        currentRunId = payload.run_id || "";
        setStatus(`Finished ${payload.run_type} run ${payload.run_id}.`, "success");
        await loadRuns({ autoSelect: false });
        await viewRun(payload.run_id, { preserveStatus: true });
      } finally {
        setButtonBusy(buttonId, false);
      }
    }

    async function viewRun(runId, options = {}) {
      const preserveStatus = Boolean(options.preserveStatus);
      currentRunId = runId || "";
      renderRuns(latestRuns);
      if (!preserveStatus) {
        setStatus(`Loading HTML report for ${runId}...`, "loading");
      }
      const response = await api(`/runs/${runId}/html`);
      const html = await response.text();
      viewer.srcdoc = html;
      viewerLabel.textContent = `Viewing the generated HTML report for ${runId}.`;
      viewerRunPill.textContent = runId;
      if (!preserveStatus) {
        setStatus(`Loaded HTML report for ${runId}.`, "success");
      }
    }

    renderViewerPlaceholder("Select a run to preview its generated HTML report.");

    document.getElementById("save-token").addEventListener("click", saveToken);
    document.getElementById("refresh").addEventListener("click", async () => {
      try {
        await loadRuns();
      } catch (error) {
        setStatus(error.message, "error");
      }
    });
    document.getElementById("run-gate").addEventListener("click", async () => {
      try {
        await createRun("gate");
      } catch (error) {
        setStatus(error.message, "error");
      }
    });
    document.getElementById("run-nightly").addEventListener("click", async () => {
      try {
        await createRun("nightly");
      } catch (error) {
        setStatus(error.message, "error");
      }
    });

    if (getToken()) {
      loadRuns().catch((error) => setStatus(error.message, "error"));
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
