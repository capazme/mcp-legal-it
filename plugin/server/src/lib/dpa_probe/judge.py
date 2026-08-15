"""Decide whether a fetched document is an art. 28 processor designation.

Pure: no I/O. A page that merely discusses GDPR must not confirm — that is the
defect this module exists to prevent (a whitelist entry once pointed at a
vendor's own website privacy notice, which would have suppressed a required
appointment).

Confirmation is gated four times, not once:
1. at least one strong marker (the designation itself, not the topic of
   privacy) and at least one supporting marker (an art. 28(3) duty) must be
   present somewhere in the document;
2. they must actually be about each other — either the strong marker sits in
   the title/heading while a duty appears anywhere in the body, or a strong
   marker and a duty share the same two-sentence window of the body. Two
   keywords scattered on opposite ends of an unrelated page are not evidence;
   a designation states its obligations next to itself.
3. the document must not BE somebody's **own** art. 13/14 notice. Vocabulary
   alone cannot tell direction apart: a privacy notice says "I appoint my
   suppliers", a DPA says "the client appoints me" — same words, opposite
   direction, and the direction is the only thing that matters legally. This is
   decided from the body's content obligations (`_FIRMA_INFORMATIVA`), not from
   the title, because a title is whatever a vendor's CMS decided to call the
   page — and because a title can be *chosen*: an own notice headed `Atto di
   nomina a responsabile del trattamento` would otherwise exempt itself. The
   body signature is therefore absolute. Only the weaker heading backstop
   yields to a strong marker in the title, so that navigation chrome cannot
   veto a document that declares what it is.
4. `dpa_dedicato` must be **anchored**: the strong marker has to sit in the
   title/h1/h2, or the final URL has to be a conventional DPA URL. Body-only
   co-occurrence under a generic heading is not enough — that is the path by
   which a privacy notice reached `dpa_dedicato`, and a false confirmation is
   the fatal error here: it makes an analyst skip a required appointment and
   the cache then freezes that mistake for 90 days.
"""

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

VERDETTO_DEDICATO = "dpa_dedicato"
VERDETTO_CLAUSOLA = "clausola_in_condizioni"
VERDETTO_NON_TROVATO = "non_trovato"


@dataclass
class Giudizio:
    verdetto: str
    marcatori: list[str] = field(default_factory=list)
    evidenza: str = "contenuto"


# "art. 28" alone is not evidence — plenty of internal regulations, building
# codes, and unrelated contracts have an article 28. It counts as a strong
# marker only when a GDPR-specific context sits within 60 characters of it,
# in either order. A bare "regolamento" does not qualify: it must be
# qualified as EU/general ("(UE)", "europeo", "generale") or be GDPR/2016/679
# itself.
_GDPR_CONTEXT = r"(?:GDPR|2016/679|regolamento\s+(?:\(UE\)|europeo|generale))"
_ARTICLE_28 = r"art(?:icolo|icle)?\.?\s*28"

# A strong marker names the designation itself, not the topic of privacy.
_FORTI: dict[str, re.Pattern] = {
    "art_28": re.compile(
        rf"{_GDPR_CONTEXT}.{{0,60}}?{_ARTICLE_28}|{_ARTICLE_28}.{{0,60}}?{_GDPR_CONTEXT}",
        re.I,
    ),
    "titolo_dpa": re.compile(
        r"data\s+process(?:ing|or)\s+(?:agreement|addendum)|"
        r"data\s+protection\s+addendum|"
        r"(?:designazione|nomina)\s+(?:a|del|di)\s+responsabile",
        re.I,
    ),
}

# Supporting markers are the art. 28(3) duties.
_SUPPORTO: dict[str, re.Pattern] = {
    "istruzione_documentata": re.compile(r"istruzione\s+documentata|documented\s+instructions", re.I),
    "sub_responsabile": re.compile(r"sub-?responsabile|sub-?processor", re.I),
    "diritti_interessato": re.compile(r"diritti\s+dell'interessato|data\s+subject\s+rights", re.I),
    "audit": re.compile(r"\baudit\b|attività\s+di\s+revisione|ispezion", re.I),
    "cancellazione_restituzione": re.compile(
        r"cancelli\s+o\s+(?:gli\s+)?restituisca|(?:delete|return)\s+(?:all\s+)?(?:the\s+)?personal\s+data", re.I
    ),
}

_TITOLO_CONDIZIONI = re.compile(
    r"condizioni\s+(?:generali|di\s+fornitura|contrattuali)|termini\s+e\s+condizioni|"
    r"terms\s+(?:and|&)\s+conditions|general\s+conditions",
    re.I,
)

# WHAT AN ART. 13/14 NOTICE *IS*, independent of what it calls itself.
#
# The first version of this gate was a list of headings, and it failed the way
# every such list fails: 12 of 17 realistic own-notice titles were simply not on
# it (`Trattamento dei dati personali`, `Tutela della privacy`,
# `Data Protection Policy`, `Dati personali`, a page with no <title> at all …),
# and each of them confirmed as `dpa_dedicato` when served from a conventional
# DPA path. Enumerating more headings is the whitelist mistake at a larger size.
#
# These three signals describe the *content obligations* of an art. 13/14
# notice, which a DPA has no reason to carry. Measured on the fixtures: 3/3 on
# the real informativa, 0/3 on each of hubspot, atlassian, aruba, teamsystem and
# zucchetti.
_FIRMA_INFORMATIVA: dict[str, re.Pattern] = {
    "art_13_14": re.compile(r"art(?:icoli|icolo|t)?\.?\s*1[34]\b", re.I),
    "reclamo_garante": re.compile(
        r"reclamo\s+al\s+garante|reclamo\s+all['’]autorit|"
        r"diritto\s+di\s+(?:proporre|presentare)\s+reclamo",
        re.I,
    ),
    "base_giuridica": re.compile(r"base\s+giuridica|legittimo\s+interesse", re.I),
}

# Two of the three. One alone is not enough: a DPA annex may legitimately
# discuss the `base giuridica` of the processing it governs. Two independent
# art. 13-specific obligations in the same document are not a coincidence.
_SOGLIA_FIRMA_INFORMATIVA = 2

# Retained as a second, independent route into the same gate. It still earns
# its place: it catches a short notice whose body carries only one of the three
# signals, where the body signature alone would not fire. The two are a union —
# the body signature carries the rule, the headings are a backstop.
_INTESTAZIONE_INFORMATIVA = re.compile(
    r"informativa|"
    r"privacy\s+(?:policy|notice|statement)|"
    r"cookie\s+policy|"
    r"note\s+legali|"
    r"^\s*(?:privacy|cookie)\s*$",
    re.I,
)

# A conventional DPA URL, used ONLY to anchor an HTML document whose content has
# already passed every gate above. `/dpa` is recognised as a whole path segment
# (so `/legal/dpa`, `/legal/dpa/`, `/legal/dpa.html` and `/legal/dpa-en` all
# count) — the narrow form below missed the two bare conventions the prober
# actually asks for first.
_URL_DPA = re.compile(
    r"data[-_]process(?:ing|or)[-_](?:agreement|addendum)|"
    r"data[-_]protection[-_]addendum|"
    r"[-_/]dpa(?:[-_./?#]|$)",
    re.I,
)

# The PDF branch judges on the URL and NOTHING else — no direction gate, no
# content check, because the file is deliberately not parsed. It therefore keeps
# the narrow form, which requires the document to be *named* after a DPA
# (`data-processing-addendum.pdf`, `/dpa.pdf`, `/dpa-en`). A bare `/privacy/dpa`
# names nothing, and is the exact path of the C1 trap: widening this pattern
# would confirm a PDF on the strength of a requested path alone.
_URL_DPA_NAMED = re.compile(
    r"data[-_]process(?:ing|or)[-_](?:agreement|addendum)|"
    r"data[-_]protection[-_]addendum|"
    r"[-_/]dpa[-_.]",
    re.I,
)

# Sentence boundary for the co-occurrence window: split after ".", "!", "?"
# followed by whitespace.
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def _heading_parts(soup: BeautifulSoup) -> list[str]:
    """Title and top headings, kept apart so each can be matched on its own.

    The negative gate needs the individual parts: `^privacy$` must recognise a
    page whose whole title is "Privacy" (the observed Zucchetti case) without
    firing on a DPA that merely mentions the word.
    """
    parts = []
    if soup.title and soup.title.string:
        parts.append(soup.title.string)
    for tag in soup.find_all(["h1", "h2"], limit=8):
        parts.append(tag.get_text(" ", strip=True))
    return parts


def _title_text(soup: BeautifulSoup) -> str:
    return soup.title.string if soup.title and soup.title.string else ""


def _notice_signature(body_text: str) -> list[str]:
    return [name for name, rx in _FIRMA_INFORMATIVA.items() if rx.search(body_text)]


def _has_notice_signature(body_text: str) -> bool:
    """Does the BODY carry the content obligations of an art. 13/14 notice?

    This is the rule, and it is not exemptable by anything in the markup: what
    the document *does* cannot be overridden by what it calls itself.
    """
    return len(_notice_signature(body_text)) >= _SOGLIA_FIRMA_INFORMATIVA


def _has_notice_heading(heading_parts: list[str]) -> bool:
    """Does the title or a top heading name the document as an own notice?

    Backstop for a short notice whose body carries only one signal. Weaker
    evidence than the body — it can be defeated by navigation chrome — so this
    branch, and only this branch, yields to a strong marker in the title.
    """
    return any(_INTESTAZIONE_INFORMATIVA.search(part) for part in heading_parts)


def _strong_markers(text: str) -> list[str]:
    return [name for name, rx in _FORTI.items() if rx.search(text)]


def _supporting_markers(text: str) -> list[str]:
    return [name for name, rx in _SUPPORTO.items() if rx.search(text)]


def _split_sentences(text: str) -> list[str]:
    sentences = [s.strip() for s in _SENTENCE_BOUNDARY.split(text) if s.strip()]
    if sentences:
        return sentences
    return [text.strip()] if text.strip() else []


def _co_occur_in_same_window(body_text: str) -> bool:
    """Two-sentence windows: sentence i joined with sentence i+1, so a pair
    that straddles a single sentence boundary still counts."""
    sentences = _split_sentences(body_text)
    for i, sentence in enumerate(sentences):
        window = sentence
        if i + 1 < len(sentences):
            window += " " + sentences[i + 1]
        if _strong_markers(window) and _supporting_markers(window):
            return True
    return False


def _markers_co_occur(heading: str, body_text: str) -> bool:
    if _strong_markers(heading) and _supporting_markers(body_text):
        return True
    return _co_occur_in_same_window(body_text)


def giudica_html(html: str, url: str = "") -> Giudizio:
    """Judge a fetched HTML document. Confirmation must be earned.

    `url` is the document's FINAL url (after redirects) and is optional only so
    that existing callers keep working; without it the sole way to reach
    `dpa_dedicato` is a strong marker in the title or a heading.
    """
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)
    heading_parts = _heading_parts(soup)
    heading = " ".join(heading_parts)
    title = _title_text(soup)
    body_text = soup.body.get_text(" ", strip=True) if soup.body else text

    strong = _strong_markers(text)
    supporting = _supporting_markers(text)

    if not strong or not supporting:
        return Giudizio(VERDETTO_NON_TROVATO, [])

    if not _markers_co_occur(heading, body_text):
        return Giudizio(VERDETTO_NON_TROVATO, [])

    # Direction gate. An art. 13/14 notice is, by definition, the publisher
    # designating ITS OWN suppliers. It uses the very same vocabulary as a DPA
    # and must never be mistaken for one.
    #
    # The BODY signature is absolute — no title can buy an exemption from it.
    # An earlier version let any strong marker in the title skip the whole gate,
    # which let an own notice exempt itself: `Atto di nomina a responsabile del
    # trattamento` (the designation letter a controller publishes toward its own
    # suppliers, routine on Italian public-sector and healthcare sites) carries
    # `titolo_dpa` in its title, and so confirmed as `dpa_dedicato` — the
    # inverted direction, from any path, with no URL needed.
    if _has_notice_signature(body_text):
        return Giudizio(VERDETTO_NON_TROVATO, [])

    # The HEADING branch is weaker evidence and does yield to a strong marker in
    # the title. That is the whole and only justification for the exemption:
    # navigation chrome is a heading problem. `_heading_parts` reads the first
    # eight h1/h2, which on a real vendor page are mega-menu and footer items,
    # so without this a document titled `Data Processing Agreement` was refused
    # because `Privacy Policy` sat in its navigation.
    if not _strong_markers(title) and _has_notice_heading(heading_parts):
        return Giudizio(VERDETTO_NON_TROVATO, [])

    marcatori = strong + supporting

    # General conditions: the designation is a clause inside the vendor's own
    # contract with its customer (the Aruba case). The TITLE decides the
    # dominant subject — a `Nomina a responsabile` section heading buried in a
    # terms page does not promote the whole document to a standalone DPA, and
    # collapsing the two loses the caveat that coverage depends on the service
    # actually purchased.
    if _TITOLO_CONDIZIONI.search(heading) and not _strong_markers(title):
        return Giudizio(VERDETTO_CLAUSOLA, marcatori)

    # Anchoring: the document must be ABOUT the designation, not merely contain
    # one. Either it says so in its title/headings, or it is served from a
    # conventional DPA URL.
    if _strong_markers(heading) or (url and _URL_DPA.search(url)):
        return Giudizio(VERDETTO_DEDICATO, marcatori)

    return Giudizio(VERDETTO_NON_TROVATO, [])


def giudica_pdf(url: str) -> Giudizio:
    """Judge a PDF from its URL alone.

    Deliberately shallow: parsing PDFs would require a new dependency (see the
    design spec). A PDF served on a conventional path and **named after** a DPA
    is already strong evidence, flagged as `evidenza: "url"` so the caller knows
    what the verdict rests on.

    This branch has no direction gate and no content check — it never sees the
    document. It therefore uses `_URL_DPA_NAMED`, not the wider `_URL_DPA` the
    HTML anchor uses: there, the URL only breaks a tie between markers that have
    already passed four content gates; here it would be the whole verdict.
    """
    if _URL_DPA_NAMED.search(url):
        return Giudizio(VERDETTO_DEDICATO, ["url_dpa"], evidenza="url")
    return Giudizio(VERDETTO_NON_TROVATO, [], evidenza="url")
