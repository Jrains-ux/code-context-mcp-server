"""Expose the project ``src`` package to test runners' discovery path."""

from __future__ import annotations

from pathlib import Path


__path__ = [str(Path(__file__).resolve().parents[2] / "src" / "code_context")]
