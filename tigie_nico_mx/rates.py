"""A tariff cell ("15", "Ex.", "AE (0.36 Dls EUA por Kg)", "Prohibida") as a rate.

The Tarifa's "CUOTA (ARANCEL)" columns hold ad valorem percents as bare numbers (LIGIE art. 2,
regla complementaria), "Ex." for exempt, specific (AE) and mixed (AMX) duties, or a prohibition.

- `text` is the rate as a reader expects it ("15%", "Ex.", "AE (0.36 Dls EUA por Kg)");
- `cell` is the Tarifa's own convention ("15", "Ex.", "AE (0.36 Dls EUA por Kg)"), the form the
  CSV files use;
- `numeric` is the ad valorem percent, 0 for exempt, and None for anything that is not a single
  percent (specific, mixed, prohibited).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

_PERCENT = re.compile(r"^(\d+(?:\.\d+)?)\s*%?$")
_EXEMPT = re.compile(r"^ex\.?$", re.IGNORECASE)


@dataclass(frozen=True)
class Rate:
    text: str
    numeric: Decimal | None

    @property
    def exempt(self) -> bool:
        return self.text == "Ex."

    @property
    def percent(self) -> bool:
        return self.numeric is not None and not self.exempt

    @property
    def cell(self) -> str:
        """The rate in the Tarifa's own convention: a bare number for a percent."""
        if self.percent:
            return self.text.removesuffix("%")
        return self.text

    def json_numeric(self) -> int | float | None:
        if self.numeric is None:
            return None
        if self.numeric == self.numeric.to_integral_value():
            return int(self.numeric)
        return float(self.numeric)


def parse_rate(cell: str) -> Rate | None:
    """None for an empty cell; otherwise the normalized rate."""
    text = " ".join(cell.split())
    if not text:
        return None
    if _EXEMPT.match(text):
        return Rate("Ex.", Decimal(0))
    match = _PERCENT.match(text)
    if match:
        value = Decimal(match.group(1))
        shown = format(value.normalize(), "f")
        return Rate(f"{shown}%", value)
    return Rate(text, None)
