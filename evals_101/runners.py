from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .graders import GradeResult, grade_case, grade_security_expectations


class WorkflowSystem(Protocol):
    def run_case(self, case: dict[str, Any]) -> dict[str, Any]:
        """Execute a single evaluation case."""


@dataclass
class CaseEvaluation:
    case_id: str
    case: dict[str, Any]
    result: dict[str, Any]
    grade: GradeResult


@dataclass
class EvaluationReport:
    system_name: str
    dataset_path: Path
    total_cases: int
    passed_cases: int
    case_results: list[CaseEvaluation]
    security_result: GradeResult


def load_cases(dataset_path: str | Path) -> list[dict[str, Any]]:
    path = Path(dataset_path)
    return json.loads(path.read_text(encoding="utf-8"))


class BaseRunner:
    system_name = "base"

    def __init__(self, system: WorkflowSystem):
        self.system = system

    def evaluate(self, dataset_path: str | Path) -> EvaluationReport:
        cases = load_cases(dataset_path)
        case_results: list[CaseEvaluation] = []
        aggregate_report = {"image_count": 0, "log_lines": []}
        for case in cases:
            result = self.system.run_case(case)
            grade = grade_case(case, result)
            case_results.append(
                CaseEvaluation(
                    case_id=str(case.get("id", f"case-{len(case_results) + 1}")),
                    case=case,
                    result=result,
                    grade=grade,
                )
            )
            aggregate_report["image_count"] = max(aggregate_report["image_count"], result.get("image_count", 0))
            aggregate_report["log_lines"].extend(result.get("log_lines", []))

        security_result = grade_security_expectations(aggregate_report)
        return EvaluationReport(
            system_name=self.system_name,
            dataset_path=Path(dataset_path),
            total_cases=len(case_results),
            passed_cases=sum(1 for case in case_results if case.grade.passed),
            case_results=case_results,
            security_result=security_result,
        )


class Mcp201Runner(BaseRunner):
    system_name = "mcp-201"
