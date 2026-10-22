# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at
# https://mozilla.org/MPL/2.0/.
#
# Imported from VisuaLex (MPL-2.0), services/visualex/visualex_api/tools/article_suffixes.py at 0f1477c2.
# Kept byte for byte below this header: tests/unit/test_article_suffixes.py checks it
# against VisuaLex's file, whose TypeScript mirrors are pinned to it on VisuaLex's side.

"""Ordinal suffixes of Italian article numbering — the one copy.

Numbering does not stop at "decies". The catalogue of reati presupposto of
d.lgs. 231/2001 runs 25-bis ... 25-sexiesdecies and beyond, and
``tests/test_article_existence.py`` records the spellings captured live from
Normattiva's article tree: "281 undecies" (c.p.c.), "669 terdecies" (c.p.c.),
"452 quaterdecies" (c.p.), "518 duodevicies" (c.p.), "2409 octiesdecies" and
"2409 noviesdecies" (c.c.), "25 undecies", "25 quinquiesdecies",
"25 septiesdecies", "25 undevicies" (d.lgs. 231/2001).

Nine regexes across the Python API and the frontend each carried their own copy
of the alternation, and all nine stopped at "decies": "art. 25-terdecies" was
read as art. 25-ter — an article that exists, so the truncation produced a
plausible link to the wrong text rather than an error. Mirrored by
``apps/web/src/utils/articleSuffixes.ts`` and
``apps/server/src/utils/articleSuffixes.ts``; change all three together (the
server's ``tests/unit/articleSuffixes.test.ts`` fails when a mirror drifts).

Two spellings circulate for 9, 15, 16, 18 and 19 ("novies" / "nonies",
"quinquiesdecies" / "quindecies", "sexiesdecies" / "sexdecies", "octiesdecies"
/ "duodevicies", "noviesdecies" / "undevicies"); both are listed because
Normattiva returns both — "nonies" in art. 21-nonies l. 241/1990 and art.
25-nonies d.lgs. 231/2001 (tests/fixtures/akn), which a table that knew only
"novies" read as art. 21 and art. 25. The table covers 2 to 20 — a suffix past that needs a new entry here and
nowhere else.

This module imports nothing on purpose: every layer (services, tools, the
controller) reads it, so it must stay a leaf.
"""

ARTICLE_ORDINAL_SUFFIXES = (
    # 2-10
    "bis", "ter", "quater", "quinquies", "sexies", "septies", "octies",
    "novies", "decies",
    # 11-20
    "undecies", "duodecies", "terdecies", "quaterdecies", "quinquiesdecies",
    "sexiesdecies", "septiesdecies", "octiesdecies", "noviesdecies", "vicies",
    # variant spellings of 9, 15, 16, 18, 19, 20 (nonies: art. 21-nonies l. 241/1990,
    # art. 25-nonies d.lgs. 231/2001, as Normattiva prints them)
    "nonies", "quindecies", "sexdecies", "duodevicies", "undevicies", "vices",
    # second word of the compound forms ("vicies semel", 21)
    "semel",
)

# The alternation, LONGEST FIRST. In a regex alternation the first branch that
# matches wins, so "ter" listed before "terdecies" claims the head of the longer
# word and leaves "decies" stranded. Sorting here means an entry added above can
# be written in any position without reintroducing that bug.
#
# Every pattern that embeds this must close the group with ``\b``, or a suffix
# still matches the head of an ordinary word ("art. 5 bisogna" -> art. 5-bis).
ARTICLE_SUFFIX_ALTERNATION = "|".join(
    sorted(ARTICLE_ORDINAL_SUFFIXES, key=len, reverse=True)
)

# The two spellings of one ordinal. An act uses one of them, and a request may use the
# other: «391-nonies» c.p.p., asked through the MCP, was «non presente» because Normattiva writes «391
# novies» there, while it writes «21 nonies» in l. 241/1990. Only for comparing what was
# asked with what the act holds (`other_ordinal_spelling`): `normalize_article_key` keeps
# the spelling it was given, because its keys are what /fetch_rubriche and the
# fingerprints answer, under the act's own spelling.
ORDINAL_SPELLINGS = (
    ("novies", "nonies"),
    ("quinquiesdecies", "quindecies"),
    ("sexiesdecies", "sexdecies"),
    ("octiesdecies", "duodevicies"),
    ("noviesdecies", "undevicies"),
    ("vicies", "vices"),
)
_OTHER_SPELLING = {a: b for a, b in ORDINAL_SPELLINGS} | {b: a for a, b in ORDINAL_SPELLINGS}


def other_ordinal_spelling(key: str):
    """The same article with the other spelling of its ordinal, or None.

    `key` is a canonical key (`normalize_article_key`): «391-nonies» -> «391-novies»,
    «25-quindecies.1» -> «25-quinquiesdecies.1»; «2-bis» and «2043» have no other spelling.
    """
    number, dash, rest = key.partition("-")
    if not dash:
        return None
    suffix, dot, tail = rest.partition(".")
    other = _OTHER_SPELLING.get(suffix)
    if other is None:
        return None
    return f"{number}-{other}{dot}{tail}"
