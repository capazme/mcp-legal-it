"""Numbers written the Italian way, for every amount a tool puts in prose.

Python's ``f"{x:,.2f}"`` writes «25,000.00», which an Italian reader takes for
twenty-five euro: in a deed, a quotation or a fee note the amount must read
«25.000,00» (dot for thousands, comma for decimals). Every tool formats its
amounts through ``numero_it``, so the rule lives in one place.

JSON numbers in a structured answer stay numbers: only text is formatted.
"""

from __future__ import annotations

from decimal import Decimal

_SWAP = str.maketrans({",": ".", ".": ","})


def numero_it(valore: float | int | Decimal, decimali: int = 2) -> str:
    """``valore`` with Italian separators: 25000 -> '25.000,00', 1234.4 with 0 decimals -> '1.234'."""
    return f"{valore:,.{decimali}f}".translate(_SWAP)
