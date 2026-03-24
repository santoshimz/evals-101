from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from evals_101.run_manager import _ensure_model_credentials, _resolve_judge_model_config


class RunManagerJudgeConfigTests(unittest.TestCase):
    def test_google_api_key_satisfies_nightly_credentials(self) -> None:
        with patch.dict(
            os.environ,
            {"GOOGLE_API_KEY": "google-test-key"},
            clear=True,
        ):
            _ensure_model_credentials()

    def test_google_api_key_selects_gemini_judge_by_default(self) -> None:
        with patch.dict(
            os.environ,
            {"GOOGLE_API_KEY": "google-test-key"},
            clear=True,
        ):
            provider, config = _resolve_judge_model_config()

        self.assertEqual(provider, "google")
        self.assertEqual(config["api_key"], "google-test-key")
        self.assertEqual(config["model_name"], "gemini-2.5-pro")

    def test_google_judge_model_can_be_overridden(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GOOGLE_API_KEY": "google-test-key",
                "EVALS_101_DEEPEVAL_MODEL": "gemini-3-pro-preview",
            },
            clear=True,
        ):
            provider, config = _resolve_judge_model_config()

        self.assertEqual(provider, "google")
        self.assertEqual(config["model_name"], "gemini-3-pro-preview")


if __name__ == "__main__":
    unittest.main()
