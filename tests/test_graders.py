from __future__ import annotations

import unittest

from evals_101.graders import grade_case, grade_security_expectations


class GradeCaseTests(unittest.TestCase):
    def test_grade_case_passes_matching_result(self) -> None:
        case = {
            "expected_workflow": "crop_images",
            "expected_tool_sequence": ["crop_images"],
            "expected_output_count": 1,
        }
        result = {
            "selected_workflow": "crop_images",
            "tool_sequence": ["crop_images"],
            "output_count": 1,
        }

        grade = grade_case(case, result)
        self.assertTrue(grade.passed)

    def test_grade_case_reports_mismatches(self) -> None:
        case = {
            "expected_workflow": "colorize_images",
            "expected_tool_sequence": ["colorize_images"],
            "expected_output_count": 1,
        }
        result = {
            "selected_workflow": "crop_images",
            "tool_sequence": ["crop_images"],
            "output_count": 2,
        }

        grade = grade_case(case, result)
        self.assertFalse(grade.passed)
        self.assertEqual(len(grade.messages), 3)


class SecurityGradeTests(unittest.TestCase):
    def test_security_grade_fails_on_secret_logs(self) -> None:
        grade = grade_security_expectations(
            {
                "image_count": 1,
                "log_lines": ["gemini_api_key should never appear here"],
            }
        )
        self.assertFalse(grade.passed)

    def test_security_grade_fails_on_image_limit(self) -> None:
        grade = grade_security_expectations({"image_count": 6, "log_lines": []})
        self.assertFalse(grade.passed)


if __name__ == "__main__":
    unittest.main()
