"""Live gate: every code URN serves the code's article, not the approving decree's.

One serial request per row (36 of NORMATTIVA_URN_CODICI + the code-like acts of
ATTI_DENOMINATI), art. 3, 1 s apart. A decree that approves an annexed code has
1-3 articles (approval, repeals, entry into force): served instead of the code,
its text opens with those words. Run before a release:

    .venv/bin/pytest tests/unit/test_codici_urn_live.py -m live -q
"""

import re
import time

import httpx
import pytest

from src.lib.visualex import map as m
from src.lib.visualex.models import Norma
from src.lib.visualex.scraper import _HEADERS, _normattiva_article_page

pytestmark = pytest.mark.live

_BASE = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:"
# Calibrated on the 58 answers of 21/10/2026: flags exactly the 7 rows that served the decree.
_DECRETO = re.compile(
    r"\b(?:è|e') approvat|\babrogazioni\b|^articolo unico|entrata in vigore"
    r"|predett[ie] codic|testo allegato|allegat[oi] al presente decreto",
    re.IGNORECASE,
)


def _righe():
    rows = [(nome, urn) for nome, urn in m.NORMATTIVA_URN_CODICI.items()]
    nel_codice = {(u.split(":")[0], u.split(";")[1].split(":")[0]) for u in m.NORMATTIVA_URN_CODICI.values() if ";" in u}
    atti = {}
    for nome, a in m.ATTI_DENOMINATI.items():
        atti.setdefault((a["tipo_atto"], a.get("data", ""), a.get("numero_atto", "")), nome)
    for (tipo, data, numero), nome in atti.items():
        if re.search(r"codic|testo unico", nome) and (tipo.replace(" ", "."), numero) not in nel_codice:
            url = Norma(tipo_atto=tipo, data=data, numero_atto=numero).url(article="3")
            rows.append((nome, url.split("urn:nir:stato:", 1)[1].rsplit("~", 1)[0]))
    return rows


def test_every_code_urn_serves_the_code():
    wrong = []
    with httpx.Client(headers=_HEADERS, timeout=40, follow_redirects=True) as client:
        for nome, urn in _righe():
            resp = client.get(f"{_BASE}{urn}~art3")
            testo, servito = _normattiva_article_page(resp.text)
            apertura = re.sub(r"\s+", " ", testo or "")[:220]
            corpo = re.sub(r"^art(?:icolo)?\.? ?3\.? ?", "", apertura, flags=re.I)
            # another article served instead of art. 3 (the decree has fewer), or decree wording
            if resp.status_code != 200 or servito not in ("3", None) or _DECRETO.search(corpo):
                wrong.append(f"{nome} ({urn}): {apertura[:120]}")
            time.sleep(1)
    assert not wrong, "\n".join(wrong)
