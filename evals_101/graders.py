from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import MCP201_BASELINE


@dataclass(frozen=True)
class GradeResult:
    passed: bool
    checks: dict[str, bool]
    messages: list[str]


def _as_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value}
    raise TypeError(f"Unsupported tool sequence type: {type(value)!r}")


def grade_case(case: dict[str, Any], result: dict[str, Any]) -> GradeResult:
    checks: dict[str, bool] = {}
    messages: list[str] = []

    expected_workflow = case.get("expected_workflow")
    actual_workflow = result.get("selected_workflow") or result.get("workflow")
    checks["workflow_match"] = actual_workflow == expected_workflow
    if not checks["workflow_match"]:
        messages.append(f"Expected workflow {expected_workflow!r}, got {actual_workflow!r}.")

    expected_tool_sequence = _as_set(case.get("expected_tool_sequence"))
    actual_tool_sequence = _as_set(result.get("tool_sequence"))
    checks["tool_sequence_match"] = not expected_tool_sequence or actual_tool_sequence == expected_tool_sequence
    if not checks["tool_sequence_match"]:
        messages.append(
            f"Expected tool sequence {sorted(expected_tool_sequence)!r}, got {sorted(actual_tool_sequence)!r}."
        )

    output_count = result.get("output_count")
    if "expected_output_count" in case:
        checks["output_count_match"] = output_count == case["expected_output_count"]
        if not checks["output_count_match"]:
            messages.append(
                f"Expected output_count {case['expected_output_count']!r}, got {output_count!r}."
            )

    return GradeResult(
        passed=all(checks.values()) if checks else True,
        checks=checks,
        messages=messages,
    )


def grade_security_expectations(report: dict[str, Any]) -> GradeResult:
    checks = {
        "no_secret_logs": True,
        "image_limit_respected": report.get("image_count", 0) <= MCP201_BASELINE.security.max_images,
    }
    messages: list[str] = []

    logs = " ".join(str(part) for part in report.get("log_lines", []))
    for forbidden_field in MCP201_BASELINE.security.forbidden_log_fields:
        if forbidden_field in logs:
            checks["no_secret_logs"] = False
            messages.append(f"Forbidden field {forbidden_field!r} appeared in logs.")

    if not checks["image_limit_respected"]:
        messages.append(
            f"Image count exceeded {MCP201_BASELINE.security.max_images}."
        )

    return GradeResult(passed=all(checks.values()), checks=checks, messages=messages)
