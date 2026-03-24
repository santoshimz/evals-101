from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


def _escape(value: Any) -> str:
    return html.escape(str(value))


def _pretty_json(value: Any) -> str:
    return html.escape(json.dumps(value, indent=2, sort_keys=True))


def _bool_badge(value: bool) -> str:
    label = "PASS" if value else "FAIL"
    badge_class = "pass" if value else "fail"
    return f'<span class="badge {badge_class}">{label}</span>'


def build_report_html_path(report_path: str | Path) -> Path:
    return Path(report_path).with_suffix(".html")


def _format_percent(value: Any) -> str:
    try:
        return f"{float(value):.0%}"
    except (TypeError, ValueError):
        return "0%"


def _render_check(label: str, passed: Any) -> str:
    return f'<span class="check-item">{_bool_badge(bool(passed))}<span>{_escape(label)}</span></span>'


def render_report_html(document: dict[str, Any]) -> str:
    summary = document.get("summary", {})
    cases = document.get("cases", [])
    security = document.get("security", {})
    security_messages = summary.get("security_messages", [])
    nightly_summary = document.get("nightly")
    overall_passed = bool(summary.get("failed_cases", 0) == 0 and summary.get("security_passed"))

    case_sections = []
    for case in cases:
        grade = case.get("grade", {})
        checks = grade.get("checks", {})
        actual = case.get("actual", {})
        expected = case.get("expected", {})
        warnings = actual.get("warnings") or actual.get("log_lines") or []
        selected_workflow = actual.get("selected_workflow") or actual.get("workflow") or "Unavailable"
        tool_sequence = actual.get("tool_sequence") or []
        output_count = actual.get("output_count")
        nightly = case.get("nightly")
        prompt = expected.get("prompt")
        check_items = [
            _render_check("Workflow match", checks.get("workflow_match")),
            _render_check("Tool sequence", checks.get("tool_sequence_match")),
            _render_check("Output count", checks.get("output_count_match")),
        ]
        if nightly:
            check_items.append(
                f'<span class="check-item">'
                f'{_bool_badge(bool(nightly.get("passed")))}'
                f"<span>Nightly quality {_escape(_format_percent(nightly.get('score', 0)))}</span>"
                f"</span>"
            )
        case_sections.append(
            f"""
            <section class="case">
              <div class="case-topline">
                <span class="case-kicker">Case review</span>
                <span class="case-id">{_escape(case.get("id", "unknown-case"))}</span>
              </div>
              <div class="case-header">
                <div>
                  <h2>{_escape(case.get("id", "unknown-case"))}</h2>
                  <p class="case-copy">Expected inputs, actual results, and grading signals for this evaluation case.</p>
                </div>
                {_bool_badge(bool(grade.get("passed")))}
              </div>
              {"<div class='prompt-block'><div class='prompt-label'>Prompt</div><p>" + _escape(prompt) + "</p></div>" if prompt else ""}
              <div class="case-summary">
                <div class="mini-stat">
                  <div class="mini-stat-label">Selected workflow</div>
                  <strong>{_escape(selected_workflow)}</strong>
                </div>
                <div class="mini-stat">
                  <div class="mini-stat-label">Tool path</div>
                  <strong>{_escape(" -> ".join(str(item) for item in tool_sequence) if tool_sequence else "Unavailable")}</strong>
                </div>
                <div class="mini-stat">
                  <div class="mini-stat-label">Output count</div>
                  <strong>{_escape(output_count if output_count is not None else "Unavailable")}</strong>
                </div>
              </div>
              <div class="case-grid">
                <div class="panel detail-panel">
                  <h3>Expected</h3>
                  <pre>{_pretty_json(expected)}</pre>
                </div>
                <div class="panel detail-panel">
                  <h3>Actual</h3>
                  <pre>{_pretty_json(actual)}</pre>
                </div>
              </div>
              <div class="checks">
                {''.join(check_items)}
              </div>
              {f'''
              <div class="panel nightly-panel">
                <h3>Nightly Grading</h3>
                <div class="nightly-grid">
                  <div><span class="muted-label">Score</span><strong>{_escape(_format_percent(nightly.get("score", 0)))}</strong></div>
                  <div><span class="muted-label">Evaluation model</span><strong>{_escape(nightly.get("evaluation_model", "Unavailable"))}</strong></div>
                </div>
                <p class="nightly-reason">{_escape(nightly.get("reason", "No nightly rationale provided."))}</p>
              </div>
              ''' if nightly else ""}
              <div class="panel detail-panel">
                <h3>Warnings</h3>
                <pre>{_pretty_json(warnings)}</pre>
              </div>
            </section>
            """
        )

    security_items = "".join(f"<li>{_escape(message)}</li>" for message in security_messages) or "<li>None</li>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>evals-101 report { _escape(document.get("run_id", "")) }</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #0f172a;
      --surface: rgba(255, 255, 255, 0.92);
      --surface-strong: #ffffff;
      --surface-soft: #eef2ff;
      --border: rgba(148, 163, 184, 0.24);
      --border-strong: rgba(99, 102, 241, 0.16);
      --text: #0f172a;
      --muted: #475569;
      --muted-strong: #334155;
      --accent: #4f46e5;
      --accent-soft: rgba(79, 70, 229, 0.12);
      --pass-bg: rgba(34, 197, 94, 0.14);
      --pass-text: #166534;
      --fail-bg: rgba(239, 68, 68, 0.14);
      --fail-text: #991b1b;
      --warn-bg: rgba(245, 158, 11, 0.16);
      --warn-text: #b45309;
      --shadow-lg: 0 24px 60px rgba(15, 23, 42, 0.16);
      --shadow-md: 0 16px 30px rgba(15, 23, 42, 0.1);
      --radius-xl: 28px;
      --radius-lg: 22px;
      --radius-md: 16px;
    }}
    * {{ box-sizing: border-box; }}
    html {{ background: #f8fafc; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: Inter, Arial, Helvetica, sans-serif;
      background:
        radial-gradient(circle at top left, rgba(99, 102, 241, 0.16), transparent 28%),
        radial-gradient(circle at top right, rgba(14, 165, 233, 0.12), transparent 24%),
        linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);
      color: var(--text);
    }}
    main {{
      max-width: 1320px;
      margin: 0 auto;
      padding: 32px 24px 48px;
    }}
    h1, h2, h3 {{ margin: 0 0 12px; }}
    p, li {{ color: var(--muted); }}
    .hero {{
      position: relative;
      overflow: hidden;
      margin-bottom: 24px;
      padding: 28px;
      border: 1px solid rgba(255, 255, 255, 0.4);
      border-radius: var(--radius-xl);
      background: linear-gradient(135deg, rgba(15, 23, 42, 0.96), rgba(30, 41, 59, 0.92));
      box-shadow: var(--shadow-lg);
      color: #f8fafc;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      inset: auto -8% -36% auto;
      width: 360px;
      height: 360px;
      border-radius: 999px;
      background: radial-gradient(circle, rgba(129, 140, 248, 0.34), transparent 68%);
      pointer-events: none;
    }}
    .hero-grid {{
      position: relative;
      display: grid;
      grid-template-columns: minmax(0, 1.6fr) minmax(260px, 0.9fr);
      gap: 18px;
      align-items: end;
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 14px;
      padding: 7px 12px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.08);
      color: rgba(226, 232, 240, 0.82);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .hero h1 {{
      font-size: clamp(2rem, 4vw, 3.2rem);
      line-height: 1.04;
      letter-spacing: -0.04em;
    }}
    .hero p {{
      max-width: 720px;
      margin-bottom: 0;
      color: rgba(226, 232, 240, 0.84);
      line-height: 1.7;
    }}
    .hero-status {{
      display: grid;
      gap: 12px;
      padding: 18px;
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: var(--radius-lg);
      background: rgba(255, 255, 255, 0.06);
      backdrop-filter: blur(12px);
    }}
    .hero-status-label {{
      color: rgba(226, 232, 240, 0.78);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .hero-status-value {{
      font-size: 2rem;
      font-weight: 800;
      letter-spacing: -0.04em;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 16px;
      margin: 24px 0;
    }}
    .panel, .metric, .case {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 18px;
      box-shadow: var(--shadow-md);
      backdrop-filter: blur(14px);
    }}
    .metric strong {{
      display: block;
      margin-top: 10px;
      font-size: 2rem;
      letter-spacing: -0.04em;
    }}
    .metric-label {{
      color: var(--muted);
      font-size: 13px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .meta {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
      margin-bottom: 24px;
    }}
    .meta-item {{
      padding: 16px;
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      background: rgba(255, 255, 255, 0.8);
    }}
    .meta-item span {{
      display: block;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .badge {{
      display: inline-block;
      border-radius: 999px;
      padding: 7px 11px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.04em;
    }}
    .badge.pass {{ background: var(--pass-bg); color: var(--pass-text); }}
    .badge.fail {{ background: var(--fail-bg); color: var(--fail-text); }}
    .case {{
      margin-top: 18px;
    }}
    .case-topline {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }}
    .case-kicker,
    .case-id {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .case-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 14px;
    }}
    .case-copy {{
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
    }}
    .prompt-block {{
      margin-bottom: 16px;
      padding: 16px;
      border: 1px solid var(--border-strong);
      border-radius: var(--radius-md);
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(238, 242, 255, 0.88));
    }}
    .prompt-label,
    .muted-label {{
      display: block;
      margin-bottom: 8px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .prompt-block p,
    .nightly-reason {{
      margin: 0;
      color: var(--muted-strong);
      line-height: 1.7;
    }}
    .case-summary,
    .nightly-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }}
    .mini-stat {{
      padding: 14px 16px;
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      background: rgba(255, 255, 255, 0.82);
    }}
    .mini-stat strong,
    .nightly-grid strong {{
      display: block;
      margin-top: 6px;
      font-size: 1rem;
      line-height: 1.5;
      word-break: break-word;
    }}
    .case-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
      margin-bottom: 16px;
    }}
    .checks {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 16px;
    }}
    .check-item {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 9px 12px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.78);
      border: 1px solid var(--border);
      color: var(--muted-strong);
      font-size: 13px;
      font-weight: 600;
    }}
    .detail-panel,
    .nightly-panel {{
      background: rgba(255, 255, 255, 0.86);
    }}
    .security-panel {{
      margin-bottom: 24px;
    }}
    .security-header {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 14px;
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      background: #f8fafc;
      border: 1px solid rgba(148, 163, 184, 0.16);
      border-radius: 14px;
      padding: 14px;
      overflow-x: auto;
    }}
    ul {{
      margin: 0;
      padding-left: 18px;
    }}
    code {{
      padding: 2px 6px;
      border-radius: 8px;
      background: rgba(15, 23, 42, 0.06);
      font-size: 0.92em;
    }}
    @media (max-width: 960px) {{
      .hero-grid {{
        grid-template-columns: 1fr;
      }}
    }}
    @media (max-width: 720px) {{
      main {{
        padding: 20px 16px 28px;
      }}
      .hero,
      .panel,
      .metric,
      .case {{
        padding: 16px;
      }}
      .case-topline,
      .case-header,
      .security-header {{
        flex-direction: column;
        align-items: flex-start;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="hero-grid">
        <div>
          <div class="eyebrow">HTML report</div>
          <h1>evals-101 report</h1>
          <p>Review the run summary, security signals, and case-by-case grading for <code>{_escape(document.get("run_id", ""))}</code>.</p>
        </div>
        <div class="hero-status">
          <div class="hero-status-label">Overall outcome</div>
          <div class="hero-status-value">{'Pass' if overall_passed else 'Needs review'}</div>
          <div>{_bool_badge(overall_passed)}</div>
        </div>
      </div>
    </section>

    <section class="meta">
      <div class="meta-item"><span>Run type</span>{_escape(document.get("run_type", ""))}</div>
      <div class="meta-item"><span>System</span>{_escape(document.get("system_name", ""))}</div>
      <div class="meta-item"><span>Created</span>{_escape(document.get("created_at", ""))}</div>
      <div class="meta-item"><span>Dataset</span>{_escape(document.get("dataset_path", ""))}</div>
      <div class="meta-item"><span>Target URL</span>{_escape(document.get("target_url", ""))}</div>
      <div class="meta-item"><span>JSON report</span>{_escape(document.get("report_path", ""))}</div>
    </section>

    <section class="summary">
      <div class="metric"><div class="metric-label">Total cases</div><strong>{_escape(summary.get("total_cases", 0))}</strong></div>
      <div class="metric"><div class="metric-label">Passed cases</div><strong>{_escape(summary.get("passed_cases", 0))}</strong></div>
      <div class="metric"><div class="metric-label">Failed cases</div><strong>{_escape(summary.get("failed_cases", 0))}</strong></div>
      <div class="metric"><div class="metric-label">Pass rate</div><strong>{_format_percent(summary.get("pass_rate", 0.0))}</strong></div>
      <div class="metric"><div class="metric-label">Security</div><strong>{'PASS' if summary.get("security_passed") else 'FAIL'}</strong></div>
      {f'<div class="metric"><div class="metric-label">Nightly cases passed</div><strong>{_escape(nightly_summary.get("passed_cases", 0))}/{_escape(nightly_summary.get("total_cases", 0))}</strong></div>' if nightly_summary else ''}
    </section>

    <section class="panel security-panel">
      <div class="security-header">
        <div>
          <h2>Security Messages</h2>
          <p>Review the top-level security summary before drilling into case details.</p>
        </div>
        {_bool_badge(bool(summary.get("security_passed")))}
      </div>
      <ul>{security_items}</ul>
      <h3 style="margin-top: 16px;">Security Details</h3>
      <pre>{_pretty_json(security)}</pre>
    </section>

    {''.join(case_sections)}
  </main>
</body>
</html>
"""


def write_report_html(document: dict[str, Any], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report_html(document), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Render a JSON eval report as HTML.")
    parser.add_argument("--input", required=True, help="Path to the JSON report.")
    parser.add_argument("--output", help="Optional output HTML path.")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    document = json.loads(input_path.read_text(encoding="utf-8"))
    output_path = Path(args.output) if args.output else build_report_html_path(input_path)
    write_report_html(document, output_path)
    print(output_path)


if __name__ == "__main__":
    main()
