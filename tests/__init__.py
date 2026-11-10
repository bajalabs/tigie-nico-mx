"""Tests on fixtures cut from the real Cámara files (`scripts/make_fixtures.py`).

Run them with `python3 -m unittest` from the repository root.
"""

from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
TARIFF = FIXTURES / "tariff"
