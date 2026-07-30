"""VIES (VAT Information Exchange System) REST client.

Free EU service for VAT number validation. For Italian numbers, a local
checksum pre-check avoids useless network calls. Member-state data
(name/address) is returned when the MS provides it; "---" means withheld.
"""

import httpx

from src.lib._http import retry_request

VIES_ENDPOINT = "https://ec.europa.eu/taxation_customs/vies/rest-api/check-vat-number"

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


def checksum_partita_iva(piva: str) -> bool:
    """Luhn-like checksum for Italian 11-digit VAT numbers (DPR 633/1972 art. 35)."""
    piva = piva.strip().replace(" ", "")
    if not piva.isdigit() or len(piva) != 11:
        return False
    somma = 0
    for i, c in enumerate(piva[:10]):
        digit = int(c)
        if i % 2 == 0:
            somma += digit
        else:
            doubled = digit * 2
            somma += doubled if doubled < 10 else doubled - 9
    return (10 - (somma % 10)) % 10 == int(piva[10])


def _clean(value: object) -> str | None:
    """VIES returns '---' or '' when the member state withholds the datum."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if value and value != "---" else None


async def check_vat(vat_number: str, country_code: str = "IT") -> dict:
    """Query VIES for a VAT number. Never raises: errors land in the dict.

    Returns: {disponibile, valido, denominazione, indirizzo, errore}.
    """
    try:
        payload = {"countryCode": country_code.upper(), "vatNumber": vat_number.strip().replace(" ", "")}
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await retry_request(client, "post", VIES_ENDPOINT, json=payload)
            data = resp.json()
    except (httpx.TransportError, httpx.HTTPStatusError, ValueError, AttributeError) as exc:
        return {
            "disponibile": False,
            "valido": None,
            "denominazione": None,
            "indirizzo": None,
            "errore": f"VIES non raggiungibile: {exc.__class__.__name__}",
        }

    if not isinstance(data, dict):
        return {
            "disponibile": False,
            "valido": None,
            "denominazione": None,
            "indirizzo": None,
            "errore": "VIES: risposta in formato inatteso",
        }

    valid = data.get("valid", data.get("isValid"))
    user_error = data.get("userError", "")
    if valid is None:
        return {
            "disponibile": False,
            "valido": None,
            "denominazione": None,
            "indirizzo": None,
            "errore": f"VIES: {user_error or 'risposta senza esito'}",
        }
    return {
        "disponibile": True,
        "valido": bool(valid),
        "denominazione": _clean(data.get("name")),
        "indirizzo": _clean(data.get("address")),
        "errore": None,
    }
