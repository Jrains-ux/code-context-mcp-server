"""Load the ``src``-layout package when running directly from the repository."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


PACKAGE_DIR = Path(__file__).resolve().parents[1] / "src" / "code_context"
PACKAGE_INIT = PACKAGE_DIR / "__init__.py"
SPEC = spec_from_file_location(
    __name__, PACKAGE_INIT, submodule_search_locations=[str(PACKAGE_DIR)]
)

if SPEC is None or SPEC.loader is None:
    raise ImportError(f"Cannot load package from {PACKAGE_INIT}")

MODULE = module_from_spec(SPEC)
sys.modules[__name__] = MODULE
SPEC.loader.exec_module(MODULE)
