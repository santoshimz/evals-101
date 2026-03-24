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


def render_report_html(document: dict[str, Any]) -> str:
    summary = document.get("summary", {})
    cases = document.get("cases", [])
    security = document.get("security", {})
    security_messages = summary.get("security_messages", [])

    case_sections = []
    for case in cases:
        grade = case.get("grade", {})
        checks = grade.get("checks", {})
        warnings = case.get("actual", {}).get("warnings") or case.get("actual", {}).get("log_lines") or []
        case_sections.append(
            f"""
            <section class="case">
              <div class="case-header">
                <h2>{_escape(case.get("id", "unknown-case"))}</h2>
                {_bool_badge(bool(grade.get("passed")))}
              </div>
              <div class="case-grid">
                <div class="panel">
                  <h3>Expected</h3>
                  <pre>{_pretty_json(case.get("expected", {}))}</pre>
                </div>
                <div class="panel">
                  <h3>Actual</h3>
                  <pre>{_pretty_json(case.get("actual", {}))}</pre>
                </div>
              </div>
              <div class="checks">
                <span>{_bool_badge(bool(checks.get("workflow_match")))} workflow</span>
                <span>{_bool_badge(bool(checks.get("tool_sequence_match")))} tool sequence</span>
                <span>{_bool_badge(bool(checks.get("output_count_match")))} output count</span>
              </div>
              <div class="panel">
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
      --bg: #f8fafc;
      --card: #ffffff;
      --border: #cbd5e1;
      --text: #0f172a;
      --muted: #475569;
      --pass-bg: #dcfce7;
      --pass-text: #166534;
      --fail-bg: #fee2e2;
      --fail-text: #991b1b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, Arial, Helvetica, sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    main {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}
    h1, h2, h3 {{ margin: 0 0 12px; }}
    p, li {{ color: var(--muted); }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin: 24px 0;
    }}
    .panel, .metric, .case {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 16px;
    }}
    .metric strong {{
      display: block;
      font-size: 28px;
      margin-top: 8px;
    }}
    .meta {{
      display: grid;
      grid-template-columns: 180px 1fr;
      gap: 8px 16px;
      margin-bottom: 24px;
    }}
    .meta div:nth-child(odd) {{
      color: var(--muted);
      font-weight: 600;
    }}
    .badge {{
      display: inline-block;
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 12px;
      font-weight: 700;
      letter-spacing: 0.04em;
    }}
    .badge.pass {{ background: var(--pass-bg); color: var(--pass-text); }}
    .badge.fail {{ background: var(--fail-bg); color: var(--fail-text); }}
    .case {{
      margin-top: 18px;
    }}
    .case-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 16px;
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
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      background: #f8fafc;
      border-radius: 12px;
      padding: 12px;
      overflow-x: auto;
    }}
    ul {{
      margin: 0;
      padding-left: 18px;
    }}
  </style>
</head>
<body>
  <main>
    <h1>evals-101 report</h1>
    <p>HTML view for run <code>{_escape(document.get("run_id", ""))}</code></p>

    <section class="meta">
      <div>Run type</div><div>{_escape(document.get("run_type", ""))}</div>
      <div>System</div><div>{_escape(document.get("system_name", ""))}</div>
      <div>Created</div><div>{_escape(document.get("created_at", ""))}</div>
      <div>Dataset</div><div>{_escape(document.get("dataset_path", ""))}</div>
      <div>Target URL</div><div>{_escape(document.get("target_url", ""))}</div>
      <div>JSON report</div><div>{_escape(document.get("report_path", ""))}</div>
    </section>

    <section class="summary">
      <div class="metric"><div>Total cases</div><strong>{_escape(summary.get("total_cases", 0))}</strong></div>
      <div class="metric"><div>Passed cases</div><strong>{_escape(summary.get("passed_cases", 0))}</strong></div>
      <div class="metric"><div>Failed cases</div><strong>{_escape(summary.get("failed_cases", 0))}</strong></div>
      <div class="metric"><div>Pass rate</div><strong>{summary.get("pass_rate", 0.0):.0%}</strong></div>
      <div class="metric"><div>Security</div><strong>{'PASS' if summary.get("security_passed") else 'FAIL'}</strong></div>
    </section>

    <section class="panel">
      <h2>Security Messages</h2>
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
