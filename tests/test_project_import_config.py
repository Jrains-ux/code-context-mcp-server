"""Regression coverage for running tests directly from the project root."""

from __future__ import annotations

from pathlib import Path
import unittest

from code_context.bootstrap import first_build


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ProjectImportConfigTest(unittest.TestCase):
    def test_test_runner_imports_code_context_from_src_layout(self) -> None:
        module_path = Path(first_build.__file__).resolve()

        self.assertEqual(
            module_path,
            PROJECT_ROOT / "src" / "code_context" / "bootstrap" / "first_build.py",
        )
