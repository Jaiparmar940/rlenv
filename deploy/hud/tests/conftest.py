"""Path wiring for the marketplace parity tests.

These tests import each deployment directory's ``adapter_core`` and the
authoritative source packages side by side, so they can prove the managed path
and the published path produce the same bytes. They deliberately do **not**
import ``hud`` or ``fastmcp``: keeping them dependency-free means they run in
the project's own venv, on the same interpreter as the published Inspect suite.

    <repo>/.venv/bin/python -m pytest deploy/hud/tests -q
"""

from __future__ import annotations

import sys
from pathlib import Path

HUD_DIR = Path(__file__).resolve().parents[1]
REPO = HUD_DIR.parent.parent

# Authoritative sources.
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "decision-layer"))
