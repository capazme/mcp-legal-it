# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Imported from VisuaLex (MPL-2.0), services/visualex/tests/validity_pages.py at eca698dc.
# Adapted: the fixtures folder is tests/fixtures/visualex/normattiva.
"""Pages for the validity tests: the repository's captures, and the portal's markup.

Not a test module (no `test_` prefix): the helpers are shared by
`test_normattiva_validity.py` and `test_validity_wire.py`.
"""
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "visualex" / "normattiva"


def page(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def window(dal=None, al=None) -> str:
    """The "Testo in vigore" block, in the portal's markup.

    The start date is as served (attachment.html, abrogato.html). The end date's
    elements were read from a historical page when the three trimmed captures
    were taken; the extraction reads the block's text, so it does not depend on
    them.
    """
    if dal and al:
        inner = (f'<span>Testo in vigore dal:</span> <span id="artInizio" class="rosso">&nbsp;{dal}</span> '
                 f'<span>al:</span> <span id="artFine" class="rosso">&nbsp;{al}</span>')
    elif dal:
        inner = f'<span>Testo in vigore dal:</span> <span id="artInizio" class="rosso">&nbsp;{dal}</span>'
    elif al:
        inner = f'<span>Testo in vigore al:</span> <span id="artFine" class="rosso">&nbsp;{al}</span>'
    else:
        inner = "<span>Testo in vigore</span>"
    return f'<div class="vigore my-5">\n{inner}\n</div>'


def synthetic(*, dal=None, al=None, label="Art. 7", content=None, version=None, updated=None) -> str:
    """A page: the window, the update link, the act line, then the body."""
    content = content if content is not None else '<span class="art-just-text-akn">Il testo dell\'articolo.</span>'
    link = (
        '<a href="#" data-href="/do/atto/vediAggiornamentiAllArticolo?art.idArticolo=7'
        f'&amp;art.versione={version}" id="aggiornamenti_articolo_button">aggiornamenti</a>'
        if version else ""
    )
    act_line = f"<em>(Ultimo aggiornamento all&#39;atto pubblicato il {updated})</em>" if updated else ""
    return (
        f'<html><body>{window(dal, al)}{link}{act_line}'
        f'<div class="bodyTesto"><h2 class="article-num-akn">{label}</h2>{content}</div>'
        "</body></html>"
    )
