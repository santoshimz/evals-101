from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from evals_101.runtime import RuntimeSettings


class RuntimeSettingsTests(unittest.TestCase):
    def test_local_defaults_remain_developer_friendly(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = RuntimeSettings.from_env()

        self.assertEqual(settings.mcp_201_base_url, "http://localhost:8010/mcp")
        self.assertEqual(settings.reports_dir, Path("reports"))
        self.assertEqual(settings.api_port, 8020)
        self.assertFalse(settings.require_api_auth)

    def test_railway_defaults_use_mounted_volume_and_auth(self) -> None:
        with patch.dict(
            os.environ,
            {
                "RAILWAY_ENVIRONMENT_ID": "env-123",
                "RAILWAY_VOLUME_MOUNT_PATH": "/var/lib/railway/volume",
                "PORT": "9000",
            },
            clear=True,
        ):
            settings = RuntimeSettings.from_env()

        self.assertEqual(settings.reports_dir, Path("/var/lib/railway/volume/reports"))
        self.assertEqual(settings.api_port, 9000)
        self.assertTrue(settings.require_api_auth)

    def test_explicit_env_overrides_railway_defaults(self) -> None:
        with patch.dict(
            os.environ,
            {
                "RAILWAY_ENVIRONMENT_ID": "env-123",
                "RAILWAY_VOLUME_MOUNT_PATH": "/var/lib/railway/volume",
                "EVALS_101_REPORTS_DIR": "~/custom-reports",
                "EVALS_101_REQUIRE_API_AUTH": "false",
                "EVALS_101_API_PORT": "7777",
            },
            clear=True,
        ):
            settings = RuntimeSettings.from_env()

        self.assertEqual(settings.reports_dir, Path("~/custom-reports").expanduser())
        self.assertEqual(settings.api_port, 7777)
        self.assertFalse(settings.require_api_auth)


if __name__ == "__main__":
    unittest.main()
