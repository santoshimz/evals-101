from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from .mcp_client import Mcp201RemoteSystem
from .reporting import ReportMetadata, build_report_document, build_report_path, write_report_document
from .runners import Mcp201Runner
from .runtime import RuntimeSettings


def _resolve_output_path(
    settings: RuntimeSettings,
    *,
    run_type: str,
    dataset_path: str | Path,
    output_path: str | Path | None,
    run_id: str,
) -> Path:
    if output_path is not None:
        return Path(output_path)
    return build_report_path(
        settings.reports_dir,
        run_type=run_type,
        system_name=settings.system_name,
        dataset_path=dataset_path,
        run_id=run_id,
    )


def _build_metadata(
    settings: RuntimeSettings,
    *,
    run_type: str,
    dataset_path: str | Path,
    output_path: str | Path | None,
) -> ReportMetadata:
    run_id = uuid4().hex
    report_path = _resolve_output_path(
        settings,
        run_type=run_type,
        dataset_path=dataset_path,
        output_path=output_path,
        run_id=run_id,
    )
    return ReportMetadata(
        run_type=run_type,
        system_name=settings.system_name,
        target_url=settings.mcp_201_base_url,
        dataset_path=str(dataset_path),
        report_path=report_path,
        created_at=datetime.now(UTC).isoformat(),
        run_id=run_id,
    )


def run_gate(
    dataset_path: str | Path,
    *,
    settings: RuntimeSettings,
    output_path: str | Path | None = None,
    http_client: httpx.AsyncClient | None = None,
    asgi_app: Any | None = None,
) -> dict[str, Any]:
    system = Mcp201RemoteSystem(
        base_url=settings.mcp_201_base_url,
        auth_token=settings.mcp_201_auth_token,
        http_client=http_client,
        asgi_app=asgi_app,
    )
    runner = Mcp201Runner(system)
    report = runner.evaluate(dataset_path)
    metadata = _build_metadata(settings, run_type="gate", dataset_path=dataset_path, output_path=output_path)
    document = build_report_document(report, metadata)
    write_report_document(document, metadata.report_path)
    return document


def _ensure_model_credentials() -> None:
    if os.environ.get("OPENAI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"):
        return
    raise SystemExit(
        "DeepEval nightly runs require a judge model key. Set OPENAI_API_KEY or ANTHROPIC_API_KEY first."
    )


def run_nightly(
    dataset_path: str | Path,
    *,
    settings: RuntimeSettings,
    output_path: str | Path | None = None,
    http_client: httpx.AsyncClient | None = None,
    asgi_app: Any | None = None,
) -> dict[str, Any]:
    _ensure_model_credentials()

    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams

    system = Mcp201RemoteSystem(
        base_url=settings.mcp_201_base_url,
        auth_token=settings.mcp_201_auth_token,
        http_client=http_client,
        asgi_app=asgi_app,
    )
    runner = Mcp201Runner(system)
    report = runner.evaluate(dataset_path)
    metadata = _build_metadata(settings, run_type="nightly", dataset_path=dataset_path, output_path=output_path)
    document = build_report_document(report, metadata)

    metric = GEval(
        name="workflow_selection_quality",
        criteria=(
            "Score whether the actual workflow chosen by the system is appropriate for the user prompt, "
            "matches the expected workflow when one is provided, and avoids unsafe overreach."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
    )

    nightly_passed = 0
    for case_document, case_result in zip(document["cases"], report.case_results, strict=False):
        actual_output = (
            f"workflow={case_result.result.get('selected_workflow') or case_result.result.get('workflow')} "
            f"tools={case_result.result.get('tool_sequence')} warnings={case_result.result.get('warnings', [])}"
        )
        expected_output = str(case_result.case.get("expected_workflow", "clarify"))
        test_case = LLMTestCase(
            input=str(case_result.case.get("prompt", "")),
            actual_output=actual_output,
            expected_output=expected_output,
        )
        score = metric.measure(test_case, _show_indicator=False, _log_metric_to_confident=False)
        nightly_case = {
            "passed": bool(metric.success),
            "score": score,
            "reason": metric.reason,
            "evaluation_model": metric.evaluation_model,
        }
        case_document["nightly"] = nightly_case
        nightly_passed += int(metric.success)

    document["nightly"] = {
        "passed_cases": nightly_passed,
        "total_cases": len(report.case_results),
        "failed_cases": len(report.case_results) - nightly_passed,
        "evaluation_model": getattr(metric, "evaluation_model", None),
    }
    write_report_document(document, metadata.report_path)
    return document
