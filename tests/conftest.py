import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest


@pytest.fixture(autouse=True)
def clean_wtffmpeg_env(monkeypatch):
    """Isolate tests from the developer's own WTFFMPEG_* environment."""
    for k in list(os.environ):
        if k.startswith("WTFFMPEG_"):
            monkeypatch.delenv(k)
