# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Imported from VisuaLex (MPL-2.0), services/visualex/tests/test_tree_annex_positions.py at 0f1477c2.
# Adapted: the imports name this package; _parse_normattiva_tree is a plain function here.
"""An annex's number in a Normattiva URN is its position in the act's tree.

Normattiva addresses an annex by where it sits among the tree's annex headings, not by
the name the act gives it (services/visualex/CLAUDE.md, gotcha 24): in d.lgs. 36/2023 «Allegato I.7»
is `;36:8` and «Allegato I.11» is `;36:12`, and a part after a dash («Allegato
I.4-Tabella A») belongs to the annex it follows. The portal writes its own number in
every link of the tree (`flagTipoArticolo`), so the fixture checks the reader against it.
"""
import re
from pathlib import Path

from bs4 import BeautifulSoup

from mcp_legal_it.lib.visualex.albero_normattiva import _parse_normattiva_tree

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "visualex" / "normattiva" / "dlgs36_2023_tree_trimmed.html"
URN = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2023-03-31;36"


def _soup():
    return BeautifulSoup(FIXTURE.read_text(encoding="utf-8"), "html.parser")


def _parse():
    return _parse_normattiva_tree(_soup(), URN, True, False, True)


def test_annex_labels_take_their_position_in_the_tree():
    _, _, metadata = _parse()
    numbers = {a["label"]: a["number"] for a in metadata["annexes"]}
    assert numbers["Allegato I.7"] == "8"
    assert numbers["Allegato I.11"] == "12"
    assert numbers["Allegati"] == "1"  # the index of the annexes is the first entry


def test_a_part_after_a_dash_is_not_an_annex_of_its_own():
    _, _, metadata = _parse()
    labels = [a["label"] for a in metadata["annexes"]]
    assert not [label for label in labels if "Tabella" in label or "bis" in label]


def test_each_annex_number_is_the_portal_own():
    # The first link under each annex heading carries the portal's number for that annex.
    portal = {}
    heading = None
    for li in _soup().select("div#albero li"):
        if "box_allegati_small" in li.get("class", []):
            heading = li.get_text(strip=True)
            continue
        a = li.find("a", class_="numero_articolo")
        if heading and heading not in portal and a is not None and a.find_parent("li") is li:
            m = re.search(r"flagTipoArticolo=(\d+)", a.get("onclick") or "")
            if m:
                portal[heading] = m.group(1)
    _, _, metadata = _parse()
    reader = {a["label"]: a["number"] for a in metadata["annexes"] if a["number"] is not None}
    assert len(reader) > 20
    assert reader == {label: portal[label] for label in reader}


def test_every_article_url_names_its_annex():
    result, _, _ = _parse()
    articles = [r for r in result if isinstance(r, dict)]
    assert articles
    for item in articles:
        annex = item.get("allegato")
        expected = f";36:{annex}~art" if annex else ";36~art"
        assert expected in item["url"], item


def test_articles_written_without_the_dot_are_read():
    # Allegato I.4 (`:5`) writes «art 1»; the tree used to drop them, so the annex was
    # missing from the metadata and its articles failed the existence check.
    result, _, metadata = _parse()
    numbers = {a["number"]: a["article_numbers"] for a in metadata["annexes"]}
    assert numbers.get("5", [])[:3] == ["1", "2", "3"]
    urls = [r["url"] for r in result if isinstance(r, dict) and r.get("allegato") == "5"]
    assert urls[0].endswith(";36:5~art1")
