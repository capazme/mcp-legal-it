"""Unit tests for the DPA probe lib.

Fixtures are trimmed copies of real pages captured on 2026-07-31.
"""

import os
import stat
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from bs4 import BeautifulSoup

from src.lib.dpa_probe import cache as dpa_cache
from src.lib.dpa_probe import client as dpa_client
from src.lib.dpa_probe.client import (
    DestinazioneNonPubblica,
    motivo_rifiuto_dominio,
    PERCORSI,
    VERDETTO_BLOCCATO,
    VERDETTO_IRRAGGIUNGIBILE,
    EsitoSonda,
    normalizza_dominio,
    sonda_dominio,
)
from src.lib.dpa_probe.judge import (
    _FORTI,
    _SUPPORTO,
    VERDETTO_CLAUSOLA,
    VERDETTO_DEDICATO,
    VERDETTO_NON_TROVATO,
    _notice_signature,
    _strong_markers,
    giudica_html,
    giudica_pdf,
)
from src.tools.analisi_fornitori import verifica_dpa_fornitore

FIXTURES = Path(__file__).parent.parent / "fixtures" / "dpa"


def _fx(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestJudgeNegatives:
    def test_website_privacy_notice_is_not_a_dpa(self):
        """Zucchetti's own privacy notice must never confirm — the regression
        that motivated replacing the whitelist."""
        html = _fx("zucchetti_privacy_notice.html")
        # Guard against a broken/empty fixture silently passing for the wrong
        # reason (giudica_html("") also returns non_trovato).
        assert len(html) > 5000
        assert "Zucchetti" in html
        assert giudica_html(html).verdetto == VERDETTO_NON_TROVATO

    def test_product_page_is_not_a_dpa(self):
        """TeamSystem /legal returned HTTP 200 while landing on a product page."""
        html = _fx("teamsystem_product_page.html")
        assert len(html) > 5000
        assert "TeamSystem" in html
        assert giudica_html(html).verdetto == VERDETTO_NON_TROVATO

    def test_gdpr_mention_alone_does_not_confirm(self):
        html = "<html><head><title>GDPR</title></head><body>Il GDPR e il trattamento dei dati personali sono importanti.</body></html>"
        assert giudica_html(html).verdetto == VERDETTO_NON_TROVATO

    def test_strong_marker_without_support_does_not_confirm(self):
        html = "<html><head><title>Data Processing Addendum</title></head><body>Coming soon.</body></html>"
        assert giudica_html(html).verdetto == VERDETTO_NON_TROVATO

    def test_bare_article_reference_without_gdpr_context_does_not_confirm(self):
        """'art. 28' next to a supporting duty is not enough on its own — the
        article number must sit near a GDPR-specific context (GDPR, 2016/679,
        or a qualified 'regolamento'). An internal company regulation that
        happens to have an article 28 must not be read as a processor
        designation."""
        html = (
            "<html><head><title>Politica interna</title></head><body>"
            "Non ricorre mai a un sub-processor per i dati sensibili."
            " Vedi anche l'art. 28 del nostro regolamento interno aziendale.</body></html>"
        )
        assert giudica_html(html).verdetto == VERDETTO_NON_TROVATO

    def test_scattered_regulation_and_role_mentions_do_not_confirm(self):
        """Mentioning 'regolamento 2016/679' and 'responsabile' and
        'sub-processor' in the same paragraph, without ever stating a
        designation, must not confirm — these are keywords about the topic
        of privacy, not evidence of an appointment."""
        html = (
            "<html><head><title>Note legali</title></head><body>"
            "Trattiamo i dati nel rispetto del regolamento 2016/679...; alcuni terzi"
            " fungono da responsabile del trattamento. Non condividiamo dati con alcun"
            " sub-processor non autorizzato.</body></html>"
        )
        assert giudica_html(html).verdetto == VERDETTO_NON_TROVATO

    def test_real_italian_privacy_notice_appointing_its_own_suppliers(self):
        """A real art. 13 informativa (innovazione.gov.it, captured 2026-07-31)
        that appoints ITS OWN suppliers as processors under art. 28.

        This is the direction problem in the wild: the page carries a genuine
        strong marker, in a sentence that designates somebody — just not the
        publisher. It must never confirm, at any URL."""
        html = _fx("informativa_art13_nomina_fornitori.html")
        assert len(html) > 5000
        # The strong marker really is present: this fixture cannot pass
        # vacuously the way a marker-free page would.
        assert _FORTI["art_28"].search(BeautifulSoup(html, "lxml").get_text(" ", strip=True))
        assert giudica_html(html).verdetto == VERDETTO_NON_TROVATO
        assert giudica_html(html, "https://x.test/legal/dpa").verdetto == VERDETTO_NON_TROVATO

    def test_privacy_notice_with_both_markers_does_not_confirm(self):
        """CONSTRUCTED (idiomatic Italian, from the whole-branch review) — no
        real page could be captured that carries a strong marker *and* a
        supporting duty; see the report.

        The wording is the standard art. 13 paragraph in which a controller
        states that it has appointed its own suppliers. Vocabulary identical to
        a DPA, direction inverted."""
        html = (
            "<html><head><title>Informativa sulla privacy</title></head><body>"
            "<h1>Informativa sul trattamento dei dati personali</h1>"
            "I fornitori di cui ci avvaliamo sono nominati responsabili del"
            " trattamento ai sensi dell'art. 28 GDPR e trattano i dati"
            " esclusivamente su istruzione documentata della scrivente."
            "</body></html>"
        )
        soup_text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
        assert _FORTI["art_28"].search(soup_text)
        assert _SUPPORTO["istruzione_documentata"].search(soup_text)
        assert giudica_html(html).verdetto == VERDETTO_NON_TROVATO

    def test_cookie_policy_with_both_markers_does_not_confirm(self):
        """CONSTRUCTED. Same inversion, in a cookie policy."""
        html = (
            "<html><head><title>Cookie Policy</title></head><body><h1>Cookie Policy</h1>"
            "I fornitori tecnologici sono nominati responsabili del trattamento ex"
            " art. 28 GDPR e operano su istruzione documentata del titolare."
            "</body></html>"
        )
        assert giudica_html(html).verdetto == VERDETTO_NON_TROVATO

    def test_own_notice_heading_beats_a_conventional_dpa_url(self):
        """CONSTRUCTED. The end-to-end trap: a CMS answers an unknown
        `/privacy/dpa` with the publisher's own privacy notice. The host check
        passes, the path looks legal, the soft-404 fingerprint does not fire —
        only the heading reveals what the document actually is. The direction
        gate must therefore outrank the URL anchor, or the cache would freeze
        the false positive for 90 days."""
        html = (
            "<html><head><title>Privacy Policy</title></head><body>"
            "<h1>Privacy Policy</h1>"
            "I nostri fornitori sono nominati responsabili del trattamento ai sensi"
            " dell'art. 28 GDPR e agiscono su istruzione documentata."
            "</body></html>"
        )
        assert giudica_html(html, "https://vendor.test/privacy/dpa").verdetto == VERDETTO_NON_TROVATO

    def test_blog_post_about_gdpr_does_not_confirm(self):
        """CONSTRUCTED. An explanatory article uses every marker a real DPA
        uses, while designating nobody at all."""
        html = (
            "<html><head><title>Blog aziendale - Le novita del GDPR</title></head>"
            "<body><h1>Cosa cambia con il GDPR</h1>"
            "Ricordiamo che ogni titolare deve procedere alla nomina a responsabile"
            " dei propri fornitori, imponendo loro di agire su istruzione documentata"
            " e di consentire audit periodici.</body></html>"
        )
        assert giudica_html(html).verdetto == VERDETTO_NON_TROVATO

    def test_marker_pair_separated_by_unrelated_sentences_does_not_confirm(self):
        """A valid strong marker (article 28 with GDPR context) and a valid
        supporting duty (audit) both appear in the page, but several
        unrelated sentences apart and outside any heading — they must not be
        read as co-occurring."""
        html = (
            "<html><head><title>Termini di servizio del prodotto</title></head><body>"
            "Il presente documento descrive l'uso del servizio ai sensi dell'articolo 28"
            " del GDPR. Il servizio include funzionalita di reportistica avanzata."
            " Gli utenti possono esportare i dati in piu formati."
            " Il pagamento avviene mensilmente tramite carta di credito."
            " Per assistenza contattare il supporto clienti."
            " Il responsabile IT esegue regolarmente un audit dei sistemi interni.</body></html>"
        )
        assert giudica_html(html).verdetto == VERDETTO_NON_TROVATO


# An art. 13/14 notice's actual content obligations, plus the C1 designation
# sentence. This is what all 17 headings below really head in the wild.
CORPO_INFORMATIVA = (
    "La presente informativa e resa ai sensi dell'art. 13 del Regolamento (UE) 2016/679."
    " La base giuridica del trattamento e il legittimo interesse del titolare."
    " I fornitori di cui ci avvaliamo sono nominati responsabili del trattamento ai sensi"
    " dell'art. 28 GDPR e trattano i dati esclusivamente su istruzione documentata della"
    " scrivente. L'interessato ha diritto di proporre reclamo al Garante per la protezione"
    " dei dati personali."
)

# 17 realistic own-notice headings. The first five were on the original
# denylist; the other twelve were not, and every one of them confirmed as
# `dpa_dedicato` when served from a conventional DPA path.
INTESTAZIONI_INFORMATIVA = [
    "Informativa sulla privacy",
    "Privacy Policy",
    "Cookie Policy",
    "Note legali",
    "Privacy",
    "Trattamento dei dati personali",
    "Tutela della privacy",
    "Protezione dei dati personali",
    "Data Protection Policy",
    "Personal Data",
    "Your Privacy",
    "GDPR",
    "Dati personali",
    "Informazioni sul trattamento",
    "Privacy e cookie",
    "Data Protection Notice",
    None,  # no <title> and no <h1> at all
]


def _pagina_informativa(intestazione: str | None) -> str:
    if intestazione is None:
        return f"<html><head></head><body><div>{CORPO_INFORMATIVA}</div></body></html>"
    return (
        f"<html><head><title>{intestazione}</title></head><body>"
        f"<h1>{intestazione}</h1>{CORPO_INFORMATIVA}</body></html>"
    )


class TestDirectionGateIsContentBased:
    """The gate must recognise an art. 13/14 notice by what it *is*, not by
    what it calls itself.

    The first version enumerated headings. 12 of the 17 below were not on that
    list, and each confirmed as `dpa_dedicato` when served from a conventional
    DPA path — then got cached for 90 days. A longer list of headings is the
    whitelist mistake at a larger size."""

    @pytest.mark.parametrize("intestazione", INTESTAZIONI_INFORMATIVA)
    def test_own_notice_never_confirms_whatever_its_heading(self, intestazione):
        html = _pagina_informativa(intestazione)
        assert giudica_html(html).verdetto == VERDETTO_NON_TROVATO
        assert giudica_html(html, "https://x.test/legal/dpa").verdetto == VERDETTO_NON_TROVATO

    def test_signature_fires_on_the_real_notice_and_on_no_real_dpa(self):
        """The three signals must separate the corpus, not merely the cases
        they were written against."""
        def firma(nome):
            testo = BeautifulSoup(_fx(nome), "lxml").get_text(" ", strip=True)
            return _notice_signature(testo)

        assert len(firma("informativa_art13_nomina_fornitori.html")) >= 2
        for nome in (
            "hubspot_dpa.html",
            "atlassian_dpa.html",
            "aruba_terms.html",
            "teamsystem_product_page.html",
            "zucchetti_privacy_notice.html",
        ):
            assert firma(nome) == [], nome

    def test_one_signal_alone_does_not_veto(self):
        """`base giuridica` on its own is not proof: a DPA annex may legitimately
        describe the lawful basis of the processing it governs. Two independent
        art. 13 obligations are required.

        The title is deliberately marker-free (`Allegato tecnico`) so the gate is
        actually reached: with a `Data Processing Agreement` title the heading
        exemption short-circuits the heading branch and this test would stay
        green even if the threshold were forced to 1, pinning nothing."""
        html = (
            "<html><head><title>Allegato tecnico</title></head><body>"
            "<h1>Allegato tecnico</h1>"
            "La base giuridica del trattamento e il contratto. Il responsabile tratta i"
            " dati ai sensi dell'art. 28 GDPR solo su istruzione documentata e non"
            " ricorre a un sub-responsabile senza autorizzazione.</body></html>"
        )
        assert _notice_signature(BeautifulSoup(html, "lxml").body.get_text(" ", strip=True)) == [
            "base_giuridica"
        ]
        assert giudica_html(html, "https://x.test/legal/dpa").verdetto == VERDETTO_DEDICATO


class TestDirectionGateDoesNotVetoOnNavigationChrome:
    def test_dpa_title_survives_privacy_headings_in_the_nav(self):
        """`_has_notice_heading` inspects the first eight h1/h2, which on a real
        vendor page are mega-menu and footer items. A document whose own title
        declares it a DPA must not be refused because `Privacy Policy` appears
        in the navigation — both true-positive fixtures survived this only by
        markup luck (HubSpot has 38 h1/h2; the eight inspected happened to be
        product nav)."""
        html = (
            "<html><head><title>Data Processing Agreement</title></head><body>"
            "<h1>Data Processing Agreement</h1>"
            "<h2>Privacy Policy</h2><h2>Cookie Policy</h2><h2>Note legali</h2>"
            "Il fornitore tratta i dati solo su istruzione documentata del titolare"
            " e non ricorre a un sub-responsabile senza autorizzazione.</body></html>"
        )
        assert giudica_html(html).verdetto == VERDETTO_DEDICATO

    @pytest.mark.parametrize(
        "titolo",
        [
            "Informativa privacy e nomina a responsabile dei fornitori",
            "Informativa sul trattamento dei dati ex art. 28 GDPR",
            "Privacy Policy - Data Processing Agreement con i nostri fornitori",
            "Nomina del responsabile del trattamento - informativa clienti",
            "Informativa privacy | GDPR art. 28",
            "Atto di nomina a responsabile del trattamento",
        ],
    )
    def test_a_notice_cannot_exempt_itself_with_its_own_title(self, titolo):
        """The exemption must NOT reach the body signature.

        An own notice can put a strong marker in its own title — most
        realistically `Atto di nomina a responsabile del trattamento`, the
        designation letter a controller publishes toward its OWN suppliers,
        routine on Italian public-sector and healthcare sites. When the
        exemption covered the whole gate, each of these confirmed as
        `dpa_dedicato` with no URL at all, reachable from every path in
        `PERCORSI`.

        This test is deliberately NOT an enumeration of safe titles: it asserts
        the property (strong title + notice body ⇒ refused) on titles chosen to
        defeat the exemption. Asserting instead that some list of titles carries
        no strong marker would be a tautology over that list — the denylist
        mistake moved up one level."""
        html = (
            f"<html><head><title>{titolo}</title></head><body>"
            f"<h1>{titolo}</h1>{CORPO_INFORMATIVA}</body></html>"
        )
        assert _strong_markers(titolo), "title must carry a strong marker for this to test anything"
        assert giudica_html(html).verdetto == VERDETTO_NON_TROVATO
        assert giudica_html(html, "https://x.test/legal/dpa").verdetto == VERDETTO_NON_TROVATO


class TestJudgePositives:
    def test_hubspot_dpa_is_dedicated(self):
        g = giudica_html(_fx("hubspot_dpa.html"))
        assert g.verdetto == VERDETTO_DEDICATO
        assert g.evidenza == "contenuto"
        assert g.marcatori

    def test_atlassian_dpa_is_dedicated(self):
        assert giudica_html(_fx("atlassian_dpa.html")).verdetto == VERDETTO_DEDICATO

    def test_heading_marker_with_body_duty_confirms(self):
        """Minimal confirmation path (a): a strong marker in the title/heading
        plus a single supporting duty anywhere in the body is sufficient —
        only one duty is required, not two, despite this example happening to
        include two."""
        html = (
            "<html><head><title>Designazione a responsabile</title></head><body>"
            "Ai sensi dell'art. 28 del Regolamento, il responsabile tratta i dati"
            " solo su istruzione documentata del titolare e non ricorre a un"
            " sub-responsabile senza autorizzazione scritta.</body></html>"
        )
        g = giudica_html(html)
        assert g.verdetto == VERDETTO_DEDICATO
        assert len(g.marcatori) >= 2

    def test_same_window_marker_pair_confirms_when_url_anchors_it(self):
        """Minimal confirmation path (b): no strong marker in the heading — a
        strong marker and a supporting duty in the same two-sentence window of
        the body confirm only once the FINAL URL anchors the document as a DPA.

        This test used to assert that the body pair alone was sufficient. It
        was the vulnerable path: the same shape is what an art. 13 informativa
        has, so `dpa_dedicato` was reachable from a document about somebody
        else's suppliers. Rather than delete it, it keeps its subject and gains
        the anchor the design spec always required."""
        html = (
            "<html><head><title>Contratto di servizio</title></head><body>"
            "Il fornitore agisce quale responsabile del trattamento ai sensi"
            " dell'articolo 28 del GDPR. Il fornitore tratta i dati solo su"
            " istruzione documentata del titolare.</body></html>"
        )
        g = giudica_html(html, "https://vendor.test/legal/dpa")
        assert g.verdetto == VERDETTO_DEDICATO

    def test_same_window_marker_pair_alone_does_not_confirm(self):
        """The negative half of the pair above: identical document, no URL
        evidence. Body-only co-occurrence under a generic heading is not a
        dedicated DPA."""
        html = (
            "<html><head><title>Contratto di servizio</title></head><body>"
            "Il fornitore agisce quale responsabile del trattamento ai sensi"
            " dell'articolo 28 del GDPR. Il fornitore tratta i dati solo su"
            " istruzione documentata del titolare.</body></html>"
        )
        assert giudica_html(html).verdetto == VERDETTO_NON_TROVATO


class TestJudgeClauseInsideTerms:
    def test_general_conditions_with_art28_is_a_clause(self):
        """Aruba publishes no standalone DPA: the appointment is a clause inside
        each service's general conditions."""
        html = (
            "<html><head><title>Condizioni Generali di Fornitura</title></head><body>"
            "<h1>Condizioni generali</h1>"
            "21. Nomina a responsabile del trattamento. Il Cliente designa Aruba"
            " quale responsabile del trattamento ai sensi dell'art. 28 GDPR; il"
            " responsabile agisce su istruzione documentata e il sub-responsabile"
            " assume gli stessi obblighi.</body></html>"
        )
        assert giudica_html(html).verdetto == VERDETTO_CLAUSOLA

    def test_real_terms_page_is_not_dedicated(self):
        html = _fx("aruba_terms.html")
        assert len(html) > 5000
        assert "Aruba" in html
        assert giudica_html(html).verdetto != VERDETTO_DEDICATO


class TestJudgePdf:
    def test_pdf_named_dpa_confirms_on_url_evidence(self):
        g = giudica_pdf("https://example.com/legal/data-processing-addendum.pdf")
        assert g.verdetto == VERDETTO_DEDICATO
        assert g.evidenza == "url"

    def test_unrelated_pdf_does_not_confirm(self):
        assert giudica_pdf("https://example.com/brochure.pdf").verdetto == VERDETTO_NON_TROVATO

    @pytest.mark.parametrize("percorso", ["/legal/dpa", "/dpa", "/privacy/dpa", "/gdpr"])
    def test_bare_conventional_path_does_not_confirm_a_pdf(self, percorso):
        """The PDF branch judges on the URL and nothing else — it never sees the
        document, so it has neither a direction gate nor a content check. It
        must keep the narrow rule the spec justifies (the file is *named* after
        a DPA); a bare `/privacy/dpa` names nothing and is the C1 trap path.

        The HTML anchor may use the wider pattern precisely because there the
        URL only breaks a tie between markers that already passed four gates."""
        assert giudica_pdf(f"https://example.com{percorso}").verdetto == VERDETTO_NON_TROVATO

    @pytest.mark.parametrize(
        "url",
        [
            "https://example.com/legal/data-processing-addendum.pdf",
            "https://example.com/legal/data_processing_agreement.pdf",
            "https://example.com/legal/dpa.pdf",
            "https://example.com/legal/dpa-en.pdf",
            "https://example.com/legal/data-protection-addendum.pdf",
        ],
    )
    def test_named_pdf_still_confirms(self, url):
        assert giudica_pdf(url).verdetto == VERDETTO_DEDICATO


def _resp(status=200, text="", content_type="text/html", url="https://x.test/legal/dpa"):
    r = MagicMock(spec=httpx.Response)
    r.status_code = status
    r.text = text
    r.headers = {"content-type": content_type}
    r.url = httpx.URL(url)
    r.raise_for_status = MagicMock()
    if status >= 400:
        r.raise_for_status.side_effect = httpx.HTTPStatusError("err", request=MagicMock(), response=r)
    return r



@pytest.fixture(autouse=True)
def _dns_pubblico(monkeypatch):
    """Unit tests never touch the resolver: every name is a public address."""
    async def risolvi(host):
        return ["93.184.216.34"]
    monkeypatch.setattr(dpa_client, "_risolvi", risolvi)

def _client_with(handler):
    """Patch httpx.AsyncClient so every request is served by `handler(url)`."""
    client = MagicMock()
    async def _get(url, **kwargs):
        return handler(url)
    client.get = AsyncMock(side_effect=_get)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


DPA_HTML = (
    "<html><head><title>Data Processing Agreement</title></head><body>"
    "Ai sensi dell'art. 28 il responsabile tratta i dati su istruzione documentata"
    " e non ricorre a un sub-responsabile senza autorizzazione.</body></html>"
)
DPA_HTML_GENERIC_TITLE = (
    "<html><head><title>Legal</title></head><body>"
    "Il fornitore agisce quale responsabile del trattamento ai sensi dell'articolo 28"
    " del GDPR. Il fornitore tratta i dati solo su istruzione documentata del"
    " titolare.</body></html>"
)
ERROR_PAGE = "<html><head><title>404</title></head><body>Pagina non trovata</body></html>"


class TestNormalizzaDominio:
    def test_strips_scheme_www_and_path(self):
        assert normalizza_dominio("https://www.Example.com/legal/") == "example.com"

    def test_bare_host(self):
        assert normalizza_dominio("Example.COM") == "example.com"


class TestSondaDominio:
    @pytest.mark.asyncio
    async def test_finds_dedicated_dpa(self):
        def handler(url):
            if "__dpa_probe_404__" in url:
                return _resp(404, ERROR_PAGE)
            if url.endswith("/legal/dpa"):
                return _resp(200, DPA_HTML, url=url)
            return _resp(404, ERROR_PAGE)

        with patch("httpx.AsyncClient", return_value=_client_with(handler)):
            esito = await sonda_dominio("example.com")
        assert esito.verdetto == VERDETTO_DEDICATO
        assert esito.url_evidenza.endswith("/legal/dpa")

    @pytest.mark.asyncio
    async def test_final_url_anchors_a_dpa_served_under_a_generic_title(self):
        """The prober must hand the FINAL url to the judge: a real DPA whose
        page title is generic confirms on the strength of the conventional
        path it was served from."""
        def handler(url):
            if "__dpa_probe_404__" in url:
                return _resp(404, ERROR_PAGE)
            if url.endswith("/legal/dpa"):
                return _resp(200, DPA_HTML_GENERIC_TITLE, url=url)
            return _resp(404, ERROR_PAGE)

        with patch("httpx.AsyncClient", return_value=_client_with(handler)):
            esito = await sonda_dominio("example.com")
        assert esito.verdetto == VERDETTO_DEDICATO
        # Same document off a non-conventional path is not confirmed.
        assert giudica_html(DPA_HTML_GENERIC_TITLE).verdetto == VERDETTO_NON_TROVATO

    @pytest.mark.asyncio
    async def test_own_notice_under_an_unlisted_heading_is_refused_end_to_end(self):
        """The full R1 path: a CMS answers `/legal/dpa` with the publisher's own
        art. 13 notice under a heading no denylist would contain. Host check,
        `_PATH_LEGALE` and the soft-404 fingerprint all pass — only the body
        signature stands between this and a `dpa_dedicato` cached for 90 days."""
        pagina = _pagina_informativa("Trattamento dei dati personali")

        def handler(url):
            if "__dpa_probe_404__" in url:
                return _resp(404, ERROR_PAGE)
            if url.endswith("/legal/dpa"):
                return _resp(200, pagina, url=url)
            return _resp(404, ERROR_PAGE)

        with patch("httpx.AsyncClient", return_value=_client_with(handler)):
            esito = await sonda_dominio("example.com")
        assert esito.verdetto == VERDETTO_NON_TROVATO

    @pytest.mark.asyncio
    async def test_soft_404_does_not_confirm(self):
        """A 200 that is really the domain's error page must not be trusted."""
        def handler(url):
            return _resp(200, ERROR_PAGE, url=url)

        with patch("httpx.AsyncClient", return_value=_client_with(handler)):
            esito = await sonda_dominio("example.com")
        assert esito.verdetto == VERDETTO_NON_TROVATO

    @pytest.mark.asyncio
    async def test_anti_bot_block_is_not_a_negative(self):
        """Meta answers 400 to non-browser clients although the page is valid.
        A false negative would generate an unnecessary appointment."""
        def handler(url):
            return _resp(400, "Error", url=url)

        with patch("httpx.AsyncClient", return_value=_client_with(handler)):
            esito = await sonda_dominio("example.com")
        assert esito.verdetto == VERDETTO_BLOCCATO

    @pytest.mark.asyncio
    async def test_unreachable_domain(self):
        def handler(url):
            raise httpx.ConnectError("dns")

        with patch("httpx.AsyncClient", return_value=_client_with(handler)):
            esito = await sonda_dominio("nowhere.test")
        assert esito.verdetto == VERDETTO_IRRAGGIUNGIBILE
        assert esito.errore

    @pytest.mark.asyncio
    async def test_redirect_to_other_host_is_rejected(self):
        def handler(url):
            if "__dpa_probe_404__" in url:
                return _resp(404, ERROR_PAGE)
            return _resp(200, DPA_HTML, url="https://elsewhere.test/marketing")

        with patch("httpx.AsyncClient", return_value=_client_with(handler)):
            esito = await sonda_dominio("example.com")
        assert esito.verdetto == VERDETTO_NON_TROVATO

    @pytest.mark.asyncio
    async def test_pdf_is_judged_from_url(self):
        def handler(url):
            if "__dpa_probe_404__" in url:
                return _resp(404, ERROR_PAGE)
            if url.endswith("/dpa"):
                return _resp(
                    200, "%PDF-1.4", content_type="application/pdf",
                    url="https://example.com/legal/data-processing-addendum.pdf",
                )
            return _resp(404, ERROR_PAGE)

        with patch("httpx.AsyncClient", return_value=_client_with(handler)):
            esito = await sonda_dominio("example.com")
        assert esito.verdetto == VERDETTO_DEDICATO
        assert esito.evidenza == "url"

    @pytest.mark.asyncio
    async def test_malformed_domain_does_not_raise(self):
        """`httpx.InvalidURL` inherits directly from `Exception`, not from
        `httpx.TransportError` or `httpx.HTTPError`, so it slips past every
        specific handler in `sonda_dominio`. Deliberately does NOT patch
        `httpx.AsyncClient` — the point is to exercise real httpx URL
        construction, which is exactly what the mocked tests above cannot
        catch."""
        esito = await sonda_dominio("example.com:abc")
        assert esito.verdetto == VERDETTO_IRRAGGIUNGIBILE
        assert esito.errore

    @pytest.mark.asyncio
    async def test_block_on_first_path_is_remembered_across_subsequent_404s(self):
        """A block encountered on one path must not be forgotten just
        because every later path comes back as a plain 404 rather than
        another block."""
        def handler(url):
            if "__dpa_probe_404__" in url:
                return _resp(404, ERROR_PAGE)
            if url.endswith(PERCORSI[0]):
                return _resp(400, "Error", url=url)
            return _resp(404, ERROR_PAGE)

        with patch("httpx.AsyncClient", return_value=_client_with(handler)):
            esito = await sonda_dominio("example.com")
        assert esito.verdetto == VERDETTO_BLOCCATO

    @pytest.mark.asyncio
    async def test_confirmation_after_a_block_wins_over_the_remembered_block(self):
        """A block remembered from an earlier path must not override a
        genuine confirmation found on a later path."""
        def handler(url):
            if "__dpa_probe_404__" in url:
                return _resp(404, ERROR_PAGE)
            if url.endswith(PERCORSI[0]):
                return _resp(400, "Error", url=url)
            if url.endswith(PERCORSI[1]):
                return _resp(200, DPA_HTML, url=url)
            return _resp(404, ERROR_PAGE)

        with patch("httpx.AsyncClient", return_value=_client_with(handler)):
            esito = await sonda_dominio("example.com")
        assert esito.verdetto == VERDETTO_DEDICATO


@pytest.mark.live
class TestDestinazionePubblica:
    """The probe reaches public registrable names only: never an address, a port,
    a local name, or a public name that resolves to a private address."""

    @pytest.mark.parametrize("host", [
        "localhost", "127.0.0.1", "10.0.0.5:8080", "192.168.1.1", "169.254.169.254",
        "[::1]", "intranet", "nas.local", "vault.internal", "evil.test", "-bad.com",
        "bad-.com", "user@example.com", "1.2.3.4.5", "",
    ])
    def test_rejected_before_any_request(self, host):
        assert motivo_rifiuto_dominio(host)

    @pytest.mark.parametrize("host", ["example.com", "sub.example.co.uk", "x-y.example.org"])
    def test_public_names_pass_the_syntactic_check(self, host):
        assert motivo_rifiuto_dominio(host) is None

    @pytest.mark.asyncio
    async def test_no_request_for_a_refused_host(self):
        handler = MagicMock(side_effect=AssertionError("must not be called"))
        with patch("httpx.AsyncClient", return_value=_client_with(handler)):
            esito = await sonda_dominio("http://169.254.169.254/latest/meta-data/")
        assert esito.verdetto == VERDETTO_IRRAGGIUNGIBILE
        assert esito.errore == "indirizzo IP invece di un dominio"
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_public_name_resolving_to_private_address_is_refused(self, monkeypatch):
        async def risolvi(host):
            return ["93.184.216.34", "10.0.0.7"]
        monkeypatch.setattr(dpa_client, "_risolvi", risolvi)
        handler = MagicMock(side_effect=AssertionError("must not be called"))
        with patch("httpx.AsyncClient", return_value=_client_with(handler)):
            esito = await sonda_dominio("example.com")
        assert esito.verdetto == VERDETTO_IRRAGGIUNGIBILE
        assert esito.errore == "il dominio risolve a un indirizzo non pubblico"
        handler.assert_not_called()

    @pytest.mark.asyncio
    async def test_unresolvable_name_is_unreachable(self, monkeypatch):
        import socket

        async def risolvi(host):
            raise socket.gaierror(8, "nodename nor servname provided")
        monkeypatch.setattr(dpa_client, "_risolvi", risolvi)
        esito = await sonda_dominio("example.com")
        assert esito.verdetto == VERDETTO_IRRAGGIUNGIBILE
        assert esito.errore == "dominio non risolvibile"

    @pytest.mark.asyncio
    async def test_request_hook_blocks_redirects_off_the_public_internet(self, monkeypatch):
        seen = []

        async def risolvi(host):
            seen.append(host)
            return ["10.1.1.1"] if host == "cdn.example.net" else ["93.184.216.34"]
        monkeypatch.setattr(dpa_client, "_risolvi", risolvi)
        hook = dpa_client._guardia_destinazioni({})
        await hook(httpx.Request("GET", "https://example.com/legal/dpa"))          # public: passes
        with pytest.raises(DestinazioneNonPubblica):
            await hook(httpx.Request("GET", "http://10.0.0.1/admin"))               # literal address
        with pytest.raises(DestinazioneNonPubblica):
            await hook(httpx.Request("GET", "https://cdn.example.net/dpa.pdf"))     # resolves privately
        with pytest.raises(DestinazioneNonPubblica):
            await hook(httpx.Request("GET", "ftp://example.com/dpa"))               # scheme
        # the refusal is what the probe reports, not a crash
        assert issubclass(DestinazioneNonPubblica, httpx.TransportError)

    @pytest.mark.asyncio
    async def test_resolution_is_memoised_per_probe(self, monkeypatch):
        calls = []

        async def risolvi(host):
            calls.append(host)
            return ["93.184.216.34"]
        monkeypatch.setattr(dpa_client, "_risolvi", risolvi)
        memo = {}
        hook = dpa_client._guardia_destinazioni(memo)
        for _ in range(3):
            await hook(httpx.Request("GET", "https://example.com/a"))
        assert calls == ["example.com"]
        assert memo == {"example.com": None}


class TestSondaLive:
    """Canary on URL conventions. Excluded from the default suite.

    Run explicitly: .venv/bin/pytest tests/unit/test_dpa_probe.py -m live -v
    """

    @pytest.mark.asyncio
    async def test_hubspot_publishes_a_dpa(self):
        esito = await sonda_dominio("legal.hubspot.com")
        assert esito.verdetto in (VERDETTO_DEDICATO, VERDETTO_CLAUSOLA)

    @pytest.mark.asyncio
    async def test_atlassian_publishes_a_dpa(self):
        esito = await sonda_dominio("atlassian.com")
        assert esito.verdetto in (VERDETTO_DEDICATO, VERDETTO_CLAUSOLA)

    @pytest.mark.asyncio
    async def test_unregistered_domain_is_unreachable(self):
        esito = await sonda_dominio("dominio-che-non-esiste-mcp-legal-it.invalid")
        assert esito.verdetto == VERDETTO_IRRAGGIUNGIBILE


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_CACHE_DIR", str(tmp_path))
    return tmp_path


ADESSO = datetime(2026, 7, 31, 12, 0, 0)


class TestCache:
    def test_roundtrip(self, cache_dir):
        esito = EsitoSonda(VERDETTO_DEDICATO, "https://example.com/legal/dpa", ["art_28"], "contenuto")
        dpa_cache.scrivi("example.com", esito, ADESSO)
        letto = dpa_cache.leggi("example.com", ADESSO)
        assert letto["verdetto"] == VERDETTO_DEDICATO
        assert letto["url_evidenza"] == "https://example.com/legal/dpa"
        assert letto["verificato_il"] == "2026-07-31"

    def test_domain_is_normalised_on_write_and_read(self, cache_dir):
        dpa_cache.scrivi("https://WWW.Example.com/legal", EsitoSonda(VERDETTO_NON_TROVATO), ADESSO)
        assert dpa_cache.leggi("example.com", ADESSO) is not None

    def test_miss_returns_none(self, cache_dir):
        assert dpa_cache.leggi("unknown.test", ADESSO) is None

    def test_entry_expires_after_ttl(self, cache_dir):
        dpa_cache.scrivi("example.com", EsitoSonda(VERDETTO_DEDICATO, "u"), ADESSO)
        dopo = ADESSO + timedelta(days=dpa_cache.TTL_GIORNI + 1)
        assert dpa_cache.leggi("example.com", dopo) is None

    def test_entry_alive_within_ttl(self, cache_dir):
        dpa_cache.scrivi("example.com", EsitoSonda(VERDETTO_DEDICATO, "u"), ADESSO)
        dopo = ADESSO + timedelta(days=dpa_cache.TTL_GIORNI - 1)
        assert dpa_cache.leggi("example.com", dopo) is not None


class TestCacheNeverPersistsFailures:
    """Caching a transient failure would freeze it for 90 days — recreating the
    whitelist's defect through the back door."""

    def test_blocked_is_not_written(self, cache_dir):
        dpa_cache.scrivi("example.com", EsitoSonda(VERDETTO_BLOCCATO, errore="403"), ADESSO)
        assert dpa_cache.leggi("example.com", ADESSO) is None

    def test_unreachable_is_not_written(self, cache_dir):
        dpa_cache.scrivi("example.com", EsitoSonda(VERDETTO_IRRAGGIUNGIBILE, errore="dns"), ADESSO)
        assert dpa_cache.leggi("example.com", ADESSO) is None

    def test_failure_does_not_create_the_file(self, cache_dir):
        dpa_cache.scrivi("example.com", EsitoSonda(VERDETTO_IRRAGGIUNGIBILE), ADESSO)
        assert not dpa_cache.percorso_cache().exists()

    def test_failure_leaves_existing_entries_untouched(self, cache_dir):
        dpa_cache.scrivi("good.test", EsitoSonda(VERDETTO_DEDICATO, "u"), ADESSO)
        prima = dpa_cache.percorso_cache().read_text()
        dpa_cache.scrivi("bad.test", EsitoSonda(VERDETTO_BLOCCATO), ADESSO)
        assert dpa_cache.percorso_cache().read_text() == prima

    def test_corrupt_cache_file_is_ignored(self, cache_dir):
        dpa_cache.percorso_cache().write_text("{not json", encoding="utf-8")
        assert dpa_cache.leggi("example.com", ADESSO) is None


_tool_fn = getattr(verifica_dpa_fornitore, "fn", verifica_dpa_fornitore)


class TestToolVerificaDpaFornitore:
    @pytest.mark.asyncio
    async def test_probe_result_is_returned_and_cached(self, cache_dir):
        esito = EsitoSonda(VERDETTO_DEDICATO, "https://example.com/legal/dpa", ["art_28"], "contenuto")
        with patch("src.tools.analisi_fornitori.sonda_dominio", AsyncMock(return_value=esito)):
            out = await _tool_fn(dominio="https://www.example.com/")
        assert out["verdetto"] == VERDETTO_DEDICATO
        assert out["dominio"] == "example.com"
        assert out["da_cache"] is False
        assert dpa_cache.leggi("example.com", datetime.fromisoformat(out["verificato_il"])) is not None

    @pytest.mark.asyncio
    async def test_second_call_is_served_from_cache_without_probing(self, cache_dir):
        esito = EsitoSonda(VERDETTO_DEDICATO, "https://example.com/legal/dpa", ["art_28"], "contenuto")
        with patch("src.tools.analisi_fornitori.sonda_dominio", AsyncMock(return_value=esito)):
            await _tool_fn(dominio="example.com")
        sonda = AsyncMock(return_value=EsitoSonda(VERDETTO_NON_TROVATO))
        with patch("src.tools.analisi_fornitori.sonda_dominio", sonda):
            out = await _tool_fn(dominio="example.com")
        assert out["da_cache"] is True
        assert out["verdetto"] == VERDETTO_DEDICATO
        sonda.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_blocked_is_reported_and_not_cached(self, cache_dir):
        esito = EsitoSonda(VERDETTO_BLOCCATO, errore="403")
        with patch("src.tools.analisi_fornitori.sonda_dominio", AsyncMock(return_value=esito)):
            out = await _tool_fn(dominio="example.com")
        assert out["verdetto"] == VERDETTO_BLOCCATO
        assert out["errore"]
        assert not dpa_cache.percorso_cache().exists()

    @pytest.mark.asyncio
    async def test_cache_entry_without_a_verdict_is_treated_as_a_miss(self, cache_dir):
        """A malformed entry must degrade to a re-probe, not raise a KeyError
        out of a tool documented as never raising."""
        dpa_cache.percorso_cache().parent.mkdir(parents=True, exist_ok=True)
        dpa_cache.percorso_cache().write_text(
            '{"example.com": {"verificato_il": "2026-07-31", "url_evidenza": "u"}}',
            encoding="utf-8",
        )
        sonda = AsyncMock(return_value=EsitoSonda(VERDETTO_DEDICATO, "https://example.com/legal/dpa"))
        with patch("src.tools.analisi_fornitori.sonda_dominio", sonda):
            out = await _tool_fn(dominio="example.com")
        assert out["verdetto"] == VERDETTO_DEDICATO
        assert out["da_cache"] is False
        sonda.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_domain_is_rejected_without_network(self, cache_dir):
        sonda = AsyncMock()
        with patch("src.tools.analisi_fornitori.sonda_dominio", sonda):
            out = await _tool_fn(dominio="   ")
        assert out["verdetto"] == VERDETTO_IRRAGGIUNGIBILE
        sonda.assert_not_awaited()


@pytest.fixture
def unwritable_cache_dir(cache_dir):
    """`cache_dir` with its write bit stripped, restored on teardown even if the
    test body raises — a failing assertion here must not leave a read-only
    directory behind to poison later tests."""
    original_mode = cache_dir.stat().st_mode
    cache_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        yield cache_dir
    finally:
        cache_dir.chmod(original_mode)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits do not apply on Windows")
@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root bypasses directory permission checks, so the write would not fail",
)
class TestCacheWriteSurvivesOSError:
    """A cache that cannot be written must degrade to 'no cache', never to a
    failed analysis (mirrors the OSError handling already in `_carica()` on
    the read side, previously asymmetric on the write side)."""

    def test_scrivi_does_not_raise_and_leaves_no_entry(self, unwritable_cache_dir):
        esito = EsitoSonda(VERDETTO_DEDICATO, "https://example.com/legal/dpa", ["art_28"], "contenuto")
        dpa_cache.scrivi("example.com", esito, ADESSO)  # must not raise
        # The directory is unwritable, so the write is a silent no-op — the
        # entry cannot have landed (readable regardless of write permission).
        assert dpa_cache.leggi("example.com", ADESSO) is None

    @pytest.mark.asyncio
    async def test_tool_still_returns_well_formed_result(self, unwritable_cache_dir):
        esito = EsitoSonda(VERDETTO_DEDICATO, "https://example.com/legal/dpa", ["art_28"], "contenuto")
        with patch("src.tools.analisi_fornitori.sonda_dominio", AsyncMock(return_value=esito)):
            out = await _tool_fn(dominio="example.com")  # must not raise
        assert out["verdetto"] == VERDETTO_DEDICATO
        assert out["dominio"] == "example.com"
        assert out["da_cache"] is False
        assert out["errore"] is None
