from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from .runners import EvaluationReport


_SECRET_FIELDS = {"gemini_api_key", "geminiApiKey", "authorization", "Authorization"}


@dataclass(frozen=True)
class ReportMetadata:
    run_type: str
    system_name: str
    target_url: str
    dataset_path: str
    report_path: Path
    created_at: str
    run_id: str


def build_report_path(
    reports_dir: Path,
    *,
    run_type: str,
    system_name: str,
    dataset_path: str | Path,
    run_id: str,
) -> Path:
    dataset_stem = Path(dataset_path).stem
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return reports_dir / run_type / f"{timestamp}-{system_name}-{dataset_stem}-{run_id}.json"


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if key in _SECRET_FIELDS else _sanitize_value(inner)) for key, inner in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def build_report_document(report: EvaluationReport, metadata: ReportMetadata) -> dict[str, Any]:
    return {
        "run_id": metadata.run_id,
        "created_at": metadata.created_at,
        "run_type": metadata.run_type,
        "system_name": metadata.system_name,
        "target_url": metadata.target_url,
        "dataset_path": metadata.dataset_path,
        "report_path": str(metadata.report_path),
        "summary": {
            "total_cases": report.total_cases,
            "passed_cases": report.passed_cases,
            "failed_cases": report.total_cases - report.passed_cases,
            "security_passed": report.security_result.passed,
            "security_messages": report.security_result.messages,
            "pass_rate": (report.passed_cases / report.total_cases) if report.total_cases else 0.0,
        },
        "security": asdict(report.security_result),
        "cases": [
            {
                "id": case.case_id,
                "expected": _sanitize_value(case.case),
                "actual": _sanitize_value(case.result),
                "grade": asdict(case.grade),
            }
            for case in report.case_results
        ],
    }


def write_report_document(document: dict[str, Any], report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
