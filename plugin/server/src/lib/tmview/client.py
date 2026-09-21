"""Client for TMview — the EUIPO/TMDN trademark database aggregator.

Data source: https://www.tmdn.org/tmview/ — the JSON API behind the official
SPA. No authentication; aggregates ~75 IP offices (UIBM, EUIPO, WIPO, national
offices) for a total of 140M+ trademarks.

Endpoints:
- POST /tmview/api/search/results          — search (JSON body, JSON response)
- GET  /tmview/api/trademark/detail/{ST13} — full record for one trademark

WAF: the site sits behind an F5/APM gate. Rapid request bursts from non-browser
clients get connection resets or an HTML challenge page instead of JSON. The
client mitigates with browser-like headers, a cookie warm-up GET on the home
page, and a minimum interval between requests. A challenge response raises
TMviewBlockedError — callers should tell the user to retry in a minute.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from src.lib._http import retry_request

_BASE_URL = "https://www.tmdn.org/tmview"
_HOME_URL = f"{_BASE_URL}/"
_SEARCH_URL = f"{_BASE_URL}/api/search/results"
_DETAIL_URL = f"{_BASE_URL}/api/trademark/detail/{{st13}}"

_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_MAX_PAGE_SIZE = 50
_GOODS_TEXT_MAX = 600

#: Minimum seconds between consecutive requests to TMview (WAF trips on bursts).
_MIN_INTERVAL = 1.0
_last_request_at = 0.0
_throttle_lock: asyncio.Lock | None = None

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "it-IT,it;q=0.9",
    "Origin": "https://www.tmdn.org",
    "Referer": "https://www.tmdn.org/tmview/",
}

#: Italian-friendly status names → TMview status codes ("Registered" verified
#: live; the others follow the same TM-XML vocabulary).
STATI: dict[str, str] = {
    "registrato": "Registered",
    "depositato": "Filed",
    "scaduto": "Expired",
    "terminato": "Ended",
}

#: TMview status codes → Italian display labels.
STATO_LABELS_IT: dict[str, str] = {
    "Registered": "Registrato",
    "Filed": "Depositato",
    "Expired": "Scaduto",
    "Ended": "Terminato",
}


class TMviewBlockedError(Exception):
    """TMview's WAF answered with a challenge page instead of JSON."""


@dataclass
class TrademarkResult:
    st13: str
    name: str
    office: str
    application_number: str
    registration_number: str
    status: str
    nice_classes: list[int]
    applicants: list[str]
    application_date: str
    registration_date: str
    expiry_date: str
    mark_type: str
    image_url: str


@dataclass
class TrademarkDetail:
    st13: str
    name: str
    office_name: str
    office_last_update: str
    application_number: str
    application_date: str
    registration_number: str
    registration_date: str
    status: str
    status_date: str
    expiry_date: str
    mark_feature: str
    kind_mark: str
    image_description: str
    applicants: list[str] = field(default_factory=list)
    representatives: list[str] = field(default_factory=list)
    goods_services: list[tuple[str, str]] = field(default_factory=list)
    publications: list[str] = field(default_factory=list)
    image_url: str = ""


def _parse_date(value: str | None) -> str:
    """ISO-8601 timestamp → GG/MM/AAAA; empty stays empty, garbage verbatim."""
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except ValueError:
        return value


def _normalize_name(name: str) -> str:
    """Case/punctuation-insensitive form for identity comparison."""
    return "".join(ch for ch in name.casefold() if ch.isalnum())


def _build_search_payload(
    term: str,
    offices: list[str] | None = None,
    nice_classes: list[str] | None = None,
    statuses: list[str] | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    payload: dict = {
        "page": str(page),
        "pageSize": str(page_size),
        "criteria": "C",
        "basicSearch": term,
    }
    if offices:
        payload["offices"] = offices
    if nice_classes:
        payload["niceClass"] = nice_classes
    if statuses:
        payload["tmStatus"] = statuses
    return payload


def _parse_search_response(data: dict) -> tuple[int, list[TrademarkResult]]:
    results = []
    for tm in data.get("tradeMarks", []):
        results.append(TrademarkResult(
            st13=tm.get("ST13", ""),
            name=tm.get("tmName", ""),
            office=tm.get("tmOffice", ""),
            application_number=tm.get("applicationNumber", ""),
            registration_number=tm.get("registrationNumber", ""),
            status=tm.get("tradeMarkStatus", ""),
            nice_classes=tm.get("niceClass", []),
            applicants=tm.get("applicantName", []),
            application_date=_parse_date(tm.get("applicationDate")),
            registration_date=_parse_date(tm.get("registrationDate")),
            expiry_date=_parse_date(tm.get("expirationDate")),
            mark_type=tm.get("tradeMarkType", ""),
            image_url=tm.get("detailImageURI", ""),
        ))
    return data.get("totalResults", 0), results


def _format_person(entry: dict) -> str:
    name = entry.get("fullName", "")
    country = entry.get("addressDetails", {}).get("countryCode", "")
    return f"{name} ({country})" if country else name


def _parse_detail_response(data: dict) -> TrademarkDetail:
    tm = data.get("tradeMark", {})
    goods = [
        (g.get("niceClass", ""), g.get("goodsAndServices", ""))
        for g in tm.get("goodAndServices", [])
    ]
    publications = [
        f"{p.get('section', '')} {p.get('identifier', '')} ({_parse_date(p.get('date'))})".strip()
        for p in data.get("publication", [])
    ]
    return TrademarkDetail(
        st13=data.get("ST13", ""),
        name=tm.get("tmName", ""),
        office_name=tm.get("tmOffice", ""),
        office_last_update=_parse_date(data.get("officeLastUpdateDate")),
        application_number=tm.get("applicationNumber", ""),
        application_date=_parse_date(tm.get("applicationDate")),
        registration_number=tm.get("registrationNumber", ""),
        registration_date=_parse_date(tm.get("codeRegistrationDate")),
        status=tm.get("markCurrentStatusCode", ""),
        status_date=_parse_date(tm.get("markCurrentStatusDate")),
        expiry_date=_parse_date(tm.get("expiryDate") or tm.get("expirationDate")),
        mark_feature=tm.get("markFeature", ""),
        kind_mark=tm.get("kindMark", ""),
        image_description=tm.get("imageDescription", ""),
        applicants=[_format_person(a) for a in data.get("applicants", [])],
        representatives=[_format_person(r) for r in data.get("representatives", [])],
        goods_services=goods,
        publications=publications,
        image_url=tm.get("markImageURI", ""),
    )


def _status_label(code: str) -> str:
    return STATO_LABELS_IT.get(code, code)


def format_result(tm: TrademarkResult) -> str:
    classes = ", ".join(str(c) for c in tm.nice_classes)
    lines = [f"### {tm.name}"]
    lines.append(f"**ST13**: `{tm.st13}` | **Ufficio**: {tm.office} | **Stato**: {_status_label(tm.status)}")
    lines.append(f"**Titolare**: {'; '.join(tm.applicants) or '—'}")
    parts = [f"**Tipo**: {tm.mark_type}", f"**Classi Nizza**: {classes or '—'}"]
    lines.append(" | ".join(parts))
    dates = [f"**Deposito**: {tm.application_date or '—'}"]
    if tm.registration_date:
        dates.append(f"**Registrazione**: {tm.registration_date} (n. {tm.registration_number})")
    if tm.expiry_date:
        dates.append(f"**Scadenza**: {tm.expiry_date}")
    lines.append(" | ".join(dates))
    return "\n".join(lines)


def format_detail(detail: TrademarkDetail) -> str:
    lines = [f"# {detail.name}"]
    lines.append(f"**ST13**: `{detail.st13}` | **Ufficio**: {detail.office_name}")
    lines.append(f"**Stato**: {_status_label(detail.status)} ({detail.status_date or '—'})")
    lines.append(f"**Tipo marchio**: {detail.mark_feature} | **Natura**: {detail.kind_mark}")
    lines.append(f"**Domanda**: n. {detail.application_number} del {detail.application_date or '—'}")
    if detail.registration_number:
        lines.append(f"**Registrazione**: n. {detail.registration_number} del {detail.registration_date or '—'}")
    if detail.expiry_date:
        lines.append(f"**Scadenza**: {detail.expiry_date}")
    lines.append(f"**Titolare**: {'; '.join(detail.applicants) or '—'}")
    if detail.representatives:
        lines.append(f"**Rappresentante**: {'; '.join(detail.representatives)}")
    if detail.image_description:
        lines.append(f"**Descrizione grafica**: {detail.image_description}")
    if detail.goods_services:
        lines.append("\n## Prodotti e servizi (classificazione di Nizza)")
        for nice_class, text in detail.goods_services:
            body = text if len(text) <= _GOODS_TEXT_MAX else text[:_GOODS_TEXT_MAX] + "…"
            lines.append(f"- **Classe {nice_class}**: {body}")
    if detail.publications:
        lines.append("\n## Pubblicazioni")
        for pub in detail.publications:
            lines.append(f"- {pub}")
    if detail.office_last_update:
        lines.append(f"\n*Dati dell'ufficio aggiornati al {detail.office_last_update} (fonte TMview).*")
    return "\n".join(lines)


async def _throttle() -> None:
    """Space requests out — TMview's WAF blocks rapid bursts."""
    global _last_request_at, _throttle_lock
    if _throttle_lock is None:
        _throttle_lock = asyncio.Lock()
    async with _throttle_lock:
        elapsed = time.monotonic() - _last_request_at
        if elapsed < _MIN_INTERVAL:
            await asyncio.sleep(_MIN_INTERVAL - elapsed)
        _last_request_at = time.monotonic()


def _json_or_blocked(resp: httpx.Response) -> dict:
    try:
        return resp.json()
    except ValueError:
        raise TMviewBlockedError(
            "TMview ha risposto con una pagina di challenge anti-bot invece del JSON."
        )


async def _warm_up(client: httpx.AsyncClient) -> None:
    """Collect the WAF session cookies before hitting the API.

    When the gate has already decided to turn this client away it answers the
    home page with a redirect and hands out no cookie. Detecting that here
    costs one request; carrying on would spend the API call plus its retries
    against a WAF that is counting them.
    """
    await client.get(_HOME_URL)
    if not client.cookies:
        raise TMviewBlockedError(
            "TMview non ha rilasciato una sessione: il gate anti-bot sta "
            "rifiutando le richieste automatiche."
        )


async def search_trademarks(
    term: str,
    offices: list[str] | None = None,
    nice_classes: list[str] | None = None,
    statuses: list[str] | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[TrademarkResult]]:
    """Search TMview. Returns (total_results, results_on_page)."""
    page_size = max(1, min(page_size, _MAX_PAGE_SIZE))
    payload = _build_search_payload(term, offices, nice_classes, statuses, page, page_size)
    await _throttle()
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True) as client:
        await _warm_up(client)
        resp = await retry_request(client, "POST", _SEARCH_URL, dataset="tmview", json=payload)
        return _parse_search_response(_json_or_blocked(resp))


async def fetch_trademark(st13: str) -> TrademarkDetail:
    """Fetch the full TMview record for one trademark by ST13 identifier."""
    await _throttle()
    async with httpx.AsyncClient(timeout=_TIMEOUT, headers=_HEADERS, follow_redirects=True) as client:
        await _warm_up(client)
        resp = await retry_request(
            client, "GET", _DETAIL_URL.format(st13=st13), dataset="tmview", params={"translate": "false"}
        )
        return _parse_detail_response(_json_or_blocked(resp))
