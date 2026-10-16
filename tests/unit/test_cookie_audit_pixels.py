"""cookie-audit skill: pixels on the site, GTM containers and tracking inside newsletters.

The skill's scripts are what turns an audit into evidence, so their readings are pinned
here on synthetic fixtures (tests/fixtures/cookie_audit, every ID and domain invented):

- inspect_container.py reads a GTM container as data. The verdicts that end up in an
  audit report — "fires on every page with no consent condition", "the Meta template's
  consent=true is not a filter", "default consent granted" — must not drift.
- inspect_pixel_config.py reads Meta's published pixel configuration (Automatic
  Advanced Matching and the form fields it reads).
- inspect_newsletter.py maps the tracking inside an e-mail against the Garante's
  Guidelines on tracking pixels in e-mail (provv. 17 April 2026 n. 284): only the
  comparison of two copies may call a pixel individual or identical for everyone.
- The browser probe of references/browser-probes.md §5 is pasted by the model into the
  page: it is executed here in Node against a mocked page, and its vendor keys must
  cover the container analyser's ones.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "plugin" / "skills" / "cookie-audit"
SCRIPTS = SKILL / "scripts"
FIX = ROOT / "tests" / "fixtures" / "cookie_audit"
NODE = shutil.which("node")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"cookie_audit_{name}", SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


container = _load("inspect_container")
pixel_config = _load("inspect_pixel_config")
newsletter = _load("inspect_newsletter")


# ---------------------------------------------------------------------------
# inspect_container.py
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def gtm_report():
    raw = (FIX / "gtm_container.js").read_text(encoding="utf-8")
    return container.analyse(raw, "GTM-TEST", "file:gtm_container.js")


def _tag(report, tag_id):
    return next(p for p in report["pixels"] if p["tag_id"] == tag_id)


def test_container_is_parsed_as_data(gtm_report):
    assert gtm_report["parsed"] is True
    assert gtm_report["tags_total"] == 10
    assert gtm_report["google_ids"]["GA4"] == ["G-ABCDEF1234"]


def test_meta_template_consent_true_is_not_a_filter(gtm_report):
    tag = _tag(gtm_report, 10)
    assert tag["vendors"] == ["meta"]
    assert tag["ids"]["meta"] == ["1234567890123456"]  # resolved through the constant variable
    assert any("NON è un filtro" in o for o in tag["consent_options"])
    assert "advancedMatching attivo" in tag["user_data"]
    # gated only because a blocking trigger reads the OneTrust cookie
    assert tag["blocked_by"] and tag["consent_linked"] is True


def test_custom_html_pixel_on_every_page_without_consent_is_flagged(gtm_report):
    tag = _tag(gtm_report, 11)
    assert tag["vendors"] == ["meta"]
    assert tag["ids"]["meta"] == ["6543210987654321"]
    assert tag["events"] == ["PageView"]
    assert container.verdict(tag)[0] == "ungated_page"


def test_gtm_additional_consent_checks_gate_the_tag(gtm_report):
    tag = _tag(gtm_report, 12)
    assert tag["consent_gtm"] == ["ad_storage", "ad_user_data"]
    assert container.verdict(tag)[0] == "gated"


def test_sequenced_tag_points_to_its_parent(gtm_report):
    tag = _tag(gtm_report, 13)
    assert tag["fires_on"] == [] and tag["sequenced_by"] == [4]
    assert container.verdict(tag)[0] == "sequenced"
    parent = _tag(gtm_report, 14)
    assert parent["vendors"] == ["microsoft"] and parent["events"] == ["purchase"]
    assert container.verdict(parent)[0] == "ungated_event"


def test_unknown_image_pixel_and_paused_tag(gtm_report):
    img = _tag(gtm_report, 15)
    assert img["pixel_hosts"] == ["pixel.esempio-adnet.example"]
    assert container.verdict(img)[0] == "ungated_page"
    paused = _tag(gtm_report, 17)
    assert paused["paused"] and paused["vendors"] == ["pinterest"]
    assert container.verdict(paused)[0] == "paused"


def test_consent_mode_default_and_hashed_email_in_ga4(gtm_report):
    cmp = gtm_report["cmp_templates"]
    assert len(cmp) == 1 and cmp[0]["command"] == "default"
    assert cmp[0]["states"]["analytics_storage"] == "granted"
    assert any("md5email" in line for line in gtm_report["other_user_data"])
    assert all(p["tag_id"] != 18 for p in gtm_report["pixels"])  # click listener is not a tag


def _container(tags, predicates, rules, macros=None):
    data = {"resource": {"version": "1", "macros": macros or [
                {"function": "__e"},
                {"function": "__u", "vtp_component": "PATH"},
                {"function": "__k", "vtp_name": "cookie_consent_marketing"}],
            "tags": tags, "predicates": predicates, "rules": rules}, "permissions": {}}
    return container.analyse("var data = " + json.dumps(data) + ";", "GTM-EDGE", "file:edge")


FB_HTML = {"function": "__html", "vtp_html": "<script>fbq('init','1111111111111111');fbq('track','PageView');</script>"}


def _first_pixel_verdict(rep):
    assert rep["pixels"], rep
    return container.verdict(rep["pixels"][0])[0]


def test_consent_initialization_trigger_is_not_a_consent_condition():
    rep = _container([dict(FB_HTML, tag_id=1)],
                     [{"function": "_eq", "arg0": ["macro", 0], "arg1": "gtm.init_consent"}],
                     [[["if", 0], ["add", 0]]])
    assert _first_pixel_verdict(rep) == "ungated_page"


def test_any_ungated_firing_rule_makes_the_tag_ungated():
    rep = _container([dict(FB_HTML, tag_id=1)],
                     [{"function": "_eq", "arg0": ["macro", 0], "arg1": "gtm.js"},
                      {"function": "_eq", "arg0": ["macro", 0], "arg1": "cookie_consent_marketing"}],
                     [[["if", 0], ["add", 0]], [["if", 1], ["add", 0]]])
    pixel = rep["pixels"][0]
    assert container.verdict(pixel)[0] == "ungated_page"
    assert pixel["ungated_rules"] and "gtm.js" in pixel["ungated_rules"][0]


def test_positive_consent_event_alone_gates_the_tag():
    rep = _container([dict(FB_HTML, tag_id=1)],
                     [{"function": "_eq", "arg0": ["macro", 0], "arg1": "cookie_consent_marketing"}],
                     [[["if", 0], ["add", 0]]])
    assert _first_pixel_verdict(rep) == "gated"


def test_cmp_event_fired_on_every_load_does_not_gate():
    rep = _container([dict(FB_HTML, tag_id=1)],
                     [{"function": "_eq", "arg0": ["macro", 0], "arg1": "OneTrustGroupsUpdated"}],
                     [[["if", 0], ["add", 0]]])
    assert _first_pixel_verdict(rep) == "ungated_event"


def test_marketing_in_a_page_path_is_not_consent():
    rep = _container([dict(FB_HTML, tag_id=1)],
                     [{"function": "_eq", "arg0": ["macro", 0], "arg1": "gtm.js"},
                      {"function": "_cn", "arg0": ["macro", 1], "arg1": "/servizi-marketing"}],
                     [[["if", 0, 1], ["add", 0]]])
    assert _first_pixel_verdict(rep) == "ungated_page"


def test_consent_cookie_condition_gates_the_tag():
    rep = _container([dict(FB_HTML, tag_id=1)],
                     [{"function": "_eq", "arg0": ["macro", 0], "arg1": "gtm.js"},
                      {"function": "_eq", "arg0": ["macro", 2], "arg1": "granted"}],
                     [[["if", 0, 1], ["add", 0]]])
    assert _first_pixel_verdict(rep) == "gated"


def test_script_loader_and_loose_ids_are_not_pixels():
    cmp_loader = {"function": "__html", "tag_id": 1, "vtp_html":
                  "<script>var s=document.createElement('script');s.src='https://cs.iubenda.example/cs.js';"
                  "document.head.appendChild(s);</script>"}
    widget = {"function": "__html", "tag_id": 2, "vtp_html":
              "<script>var w='https://widget.esempio.example/w?organization=12345&adv=abcdef1';</script>"}
    rep = _container([cmp_loader, widget],
                     [{"function": "_eq", "arg0": ["macro", 0], "arg1": "gtm.js"}],
                     [[["if", 0], ["add", 0, 1]]])
    assert rep["pixels"] == []
    assert rep["vendors_by_code"] == {}


def test_ad_blocker_stub_is_refused():
    report = container.analyse("/* uBlock Origin noopfn */", "GTM-STUB", "file:stub")
    assert report["parsed"] is False and any("STUB" in w for w in report["warnings"])


def test_shell_wrapper_runs_the_python_analyser():
    out = subprocess.run(["bash", str(SCRIPTS / "inspect_container.sh"), "--json", "--file",
                          str(FIX / "gtm_container.js")], capture_output=True, text=True, check=True)
    data = json.loads(out.stdout)
    assert data[0]["tags_total"] == 10


# ---------------------------------------------------------------------------
# inspect_pixel_config.py
# ---------------------------------------------------------------------------
def test_meta_published_configuration():
    text = (FIX / "meta_signals_config.js").read_text(encoding="utf-8")
    r = pixel_config.parse_meta(text, "1111111111111111")
    assert r["found"] is True
    assert r["automatic_matching"] == ["em", "ph", "fn", "ln", "db"]
    assert "InferredEvents" in r["plugins"]
    assert r["unwanted_keys"] == {"PageView": ["url:email_address"]}


def test_meta_unknown_pixel_and_tiktok_are_not_read():
    assert pixel_config.parse_meta("/* nothing for this id */", "2222222222222222")["found"] is False
    assert pixel_config.vendor_of("CABCDEFGHIJ123456789") == "tiktok"  # reported, never parsed


# ---------------------------------------------------------------------------
# inspect_newsletter.py
# ---------------------------------------------------------------------------
def test_two_copies_show_an_individual_pixel():
    a = newsletter.analyse_message(str(FIX / "mailchimp_like_a.eml"), "prova1@studio-esempio.example")
    b = newsletter.analyse_message(str(FIX / "mailchimp_like_b.eml"), "prova2@studio-esempio.example")
    assert [e["name"] for e in a["esp"]] == ["Mailchimp"]
    assert len(a["pixels"]) == 1 and "dimensioni ≤ 1 px" in a["pixels"][0]["reasons"]
    cmp = newsletter.compare(a, b)
    assert cmp["pixel_individuali"] and not cmp["pixel_identici"]
    assert "mc_eid" in a["link_id_params"] and "mc_cid" not in a["link_id_params"]
    assert a["unsubscribe"] and not a["tracking_optout"]
    found = " ".join(newsletter.findings(a, cmp))
    assert "DIVERSE nelle due copie" in found and "revoca anche granulare" in found


def test_single_copy_does_not_claim_an_individual_pixel():
    a = newsletter.analyse_message(str(FIX / "mailchimp_like_a.eml"))
    found = " ".join(newsletter.findings(a))
    assert "possono identificare il destinatario o solo la campagna" in found
    assert "DIVERSE" not in found


def test_compliant_copy_has_identical_pixel_and_tracking_optout():
    a = newsletter.analyse_message(str(FIX / "conforme_a.eml"))
    b = newsletter.analyse_message(str(FIX / "conforme_b.eml"))
    cmp = newsletter.compare(a, b)
    assert cmp["pixel_identici"] and not cmp["pixel_individuali"]
    assert a["tracking_optout"] and a["tracking_notice"]
    assert not any("Disattiva il tracciamento" in u for u in a["unsubscribe"])
    assert "revoca anche granulare" not in " ".join(newsletter.findings(a, cmp))


def test_address_in_urls_and_third_parties():
    r = newsletter.analyse_message(str(FIX / "indirizzo_negli_url.eml"), "prova1@studio-esempio.example")
    encodings = {a["encoding"] for a in r["address_in_urls"]}
    assert {"in chiaro", "base64", "hash MD5"} <= encodings
    assert "Google Analytics (pixel di misurazione)" in r["third_parties"]
    assert "LiveIntent (pubblicità nelle newsletter)" in r["third_parties"]
    assert "_kx" in r["link_id_params"]
    assert [e["name"] for e in r["esp"]] == ["Klaviyo"]


def _html_mail(tmp_path, name, body, headers=""):
    path = tmp_path / name
    path.write_text("From: Studio Esempio <news@studio-esempio.example>\nTo: prova1@studio-esempio.example\n"
                    "Subject: Novita\nMIME-Version: 1.0\n" + headers +
                    "Content-Type: text/html; charset=utf-8\n\n<html><body>" + body + "</body></html>\n",
                    encoding="utf-8")
    return str(path)


def test_identical_pixel_with_a_per_recipient_image_is_individual(tmp_path):
    pixel = '<img src="https://news.studio-esempio.example/stats/open.gif?campaign=10" width="1" height="1">'
    a = _html_mail(tmp_path, "a.eml", pixel + '<img src="https://img.esp.example/r/48213/logo.png" width="200">')
    b = _html_mail(tmp_path, "b.eml", pixel + '<img src="https://img.esp.example/r/48214/logo.png" width="200">')
    ra, rb = newsletter.analyse_message(a), newsletter.analyse_message(b)
    cmp = newsletter.compare(ra, rb)
    assert cmp["apertura_individuale"] is True and not cmp["pixel_identici"]
    found = " ".join(newsletter.findings(ra, cmp))
    assert "DIVERSE nelle due copie" in found and "IDENTICHE" not in found


def test_message_forwarded_as_attachment_is_read_from_the_original(tmp_path):
    from email.message import EmailMessage
    original = (FIX / "mailchimp_like_a.eml").read_bytes()
    wrapper = EmailMessage()
    wrapper["From"] = "collega@studio-esempio.example"
    wrapper["To"] = "prova1@studio-esempio.example"
    wrapper["Subject"] = "Fwd: Newsletter di ottobre"
    wrapper.set_content("Inoltro la newsletter come allegato.")
    wrapper.add_attachment(original, maintype="message", subtype="rfc822", filename="newsletter.eml")
    path = tmp_path / "inoltro.eml"
    path.write_bytes(bytes(wrapper))
    r = newsletter.analyse_message(str(path))
    assert any("inoltrato come allegato" in w for w in r["warnings"])
    assert [e["name"] for e in r["esp"]] == ["Mailchimp"] and len(r["pixels"]) == 1


def test_wide_spacers_cloud_storage_and_click_and_collect_are_not_tracking(tmp_path):
    body = ('<img src="https://cdn.studio-esempio.example/spacer.gif" width="600" height="1">'
            '<img src="https://firebasestorage.googleapis.com/v0/b/progetto/o/immagini%2Fbanner.png?alt=media" width="300">'
            '<a href="https://www.negozio-esempio.example/click-and-collect">Ritiro in negozio</a>')
    r = newsletter.analyse_message(_html_mail(tmp_path, "spacer.eml", body))
    assert r["pixels"] == [] and r["tracked_links"] == []


def test_shipment_tracking_link_is_neither_opt_out_nor_notice(tmp_path):
    body = ('<img src="https://news.studio-esempio.example/o/pixel" width="1" height="1">'
            '<a href="https://corriere.esempio.example/tracking?n=123">Tracking della spedizione</a>')
    r = newsletter.analyse_message(_html_mail(tmp_path, "spedizione.eml", body))
    assert r["tracking_optout"] == [] and r["tracking_notice"] == []


def test_mailer_names_do_not_invent_a_platform(tmp_path):
    r = newsletter.analyse_message(_html_mail(tmp_path, "mailkit.eml", "<p>Ciao</p>", "X-Mailer: MailKit 4.3\n"))
    assert r["esp"] == []
    r = newsletter.analyse_message(_html_mail(
        tmp_path, "utm.eml", '<a href="https://www.studio-esempio.example/?utm_source=mailchimp.com">Sito</a>'))
    assert r["esp"] == []


def test_malformed_url_is_skipped_not_fatal(tmp_path):
    body = '<img src="https://[TRACK/o.gif" width="1" height="1"><a href="https://[LINK">x</a>'
    r = newsletter.analyse_message(_html_mail(tmp_path, "rotto.eml", body))
    assert any("malformato" in w for w in r["warnings"])


def test_json_findings_include_the_address_found_in_copy_b():
    out = subprocess.run([sys.executable, str(SCRIPTS / "inspect_newsletter.py"), "--json", "--compare",
                          str(FIX / "conforme_a.eml"), str(FIX / "indirizzo_negli_url.eml"),
                          "--recipient", "prova2@studio-esempio.example", "--recipient", "prova1@studio-esempio.example"],
                         capture_output=True, text=True, check=True)
    data = json.loads(out.stdout)
    assert any("L'indirizzo del destinatario compare negli URL" in f for f in data[0]["findings"])


def test_plain_text_message_cannot_carry_pixels():
    r = newsletter.analyse_message(str(FIX / "solo_testo.eml"))
    assert r["html"] is False
    assert newsletter.findings(r) == ["Messaggio solo testo: nessun pixel possibile."]


def test_outlook_msg_is_rejected_with_instructions(tmp_path):
    msg = tmp_path / "copia.msg"
    msg.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64)
    out = subprocess.run([sys.executable, str(SCRIPTS / "inspect_newsletter.py"), str(msg)],
                         capture_output=True, text=True)
    assert out.returncode == 1 and ".eml" in out.stdout


# ---------------------------------------------------------------------------
# Browser probe §5 (references/browser-probes.md)
# ---------------------------------------------------------------------------
PROBES = (SKILL / "references" / "browser-probes.md").read_text(encoding="utf-8")


def _probe_block(section: str) -> str:
    start = PROBES.index(f"## {section}")
    m = re.search(r"```js\n(.*?)```", PROBES[start:], re.S)
    return m.group(1)


def test_probe_vendor_keys_cover_the_container_analyser():
    probe_keys = set(re.findall(r"\{k:'([a-z0-9_]+)'", _probe_block("§5")))
    assert set(container.VENDORS) <= probe_keys
    assert probe_keys - set(container.VENDORS) == {"ga4"}


@pytest.mark.skipif(NODE is None, reason="node non disponibile")
def test_every_probe_is_valid_javascript():
    for i, block in enumerate(re.findall(r"```js\n(.*?)```", PROBES, re.S)):
        out = subprocess.run([NODE, "-e", "new Function('return (' + require('fs').readFileSync(0, 'utf8') + ')')"],
                             input=block, capture_output=True, text=True)
        assert out.returncode == 0, f"blocco {i}: {out.stderr[:300]}"


HARNESS = r"""
const fs = require('fs');
const code = fs.readFileSync(0, 'utf8');
const entries = [
  { name: 'https://connect.facebook.net/en_US/fbevents.js', initiatorType: 'script', startTime: 100 },
  { name: 'https://www.facebook.com/tr/?id=1234567890123456&ev=PageView&dl=https%3A%2F%2Fshop.example.com%2F%3Femail%3Dmario%40example.com&ud%5Bem%5D=abc123&a=tmgoogletagmanager&eid=e1', initiatorType: 'img', startTime: 200 },
  { name: 'https://www.google-analytics.com/g/collect?v=2&tid=G-ABC123&gcs=G100&en=page_view', initiatorType: 'beacon', startTime: 300 },
  { name: 'https://sgtm.example.com/g/collect?v=2&tid=G-ABC123&en=page_view', initiatorType: 'fetch', startTime: 400 },
  { name: 'https://analytics.tiktok.com/api/v2/pixel', initiatorType: 'beacon', startTime: 1500 },
  { name: 'https://unknown-adnet.example/collect?uid=123456789012345678901234567890', initiatorType: 'img', startTime: 1600 },
  { name: 'https://static.klaviyo.com/onsite/js/klaviyo.js?company_id=AbC123', initiatorType: 'script', startTime: 50 },
  { name: 'https://googleads.g.doubleclick.net/pagead/viewthroughconversion/123456789/?random=1&cv=11', initiatorType: 'script', startTime: 600 },
];
globalThis.window = globalThis;
window.frames = [];
globalThis.location = { href: 'https://shop.example.com/', hostname: 'shop.example.com' };
globalThis.performance = { timeOrigin: 1000, getEntriesByType: () => entries, setResourceTimingBufferSize() {} };
globalThis.sessionStorage = { getItem: () => JSON.stringify({ origin: 1000, t: 1000, at: 'test' }) };
globalThis.getComputedStyle = () => ({ display: 'block' });
const scripts = [{ textContent: "fbq('init','1234567890123456');fbq('track','PageView');" }];
const noscripts = [{ textContent: '<img height="1" width="1" src="https://www.facebook.com/tr?id=1234567890123456&ev=PageView&noscript=1"/>' }];
const iframes = [{ src: 'https://td.doubleclick.net/td/rul/123' }];
globalThis.document = {
  images: [{ src: 'https://px.ads-esempio.example/p.gif?u=abcdefghijklmnop', complete: true, naturalWidth: 1, naturalHeight: 1, getAttribute: () => null }],
  querySelectorAll: sel => sel.startsWith('script') ? scripts : sel === 'noscript' ? noscripts : sel.startsWith('iframe') ? iframes : [],
};
window.fbq = { getState: () => ({ pixels: [{ id: '1234567890123456', agent: 'tmgoogletagmanager', userData: { em: 'x' }, userDataFormFields: {} }] }) };
const fn = eval('(' + code + ')');
process.stdout.write(JSON.stringify(fn()));
"""


@pytest.mark.skipif(NODE is None, reason="node non disponibile")
def test_pixel_probe_on_a_mocked_page():
    out = subprocess.run([NODE, "-e", HARNESS], input=_probe_block("§5"), capture_output=True, text=True)
    assert out.returncode == 0, out.stderr[:500]
    r = json.loads(out.stdout)
    meta = r["pixels"]["meta"]
    assert meta["ids"] == ["1234567890123456"]
    assert meta["scripts"] == 1 and meta["hits"] == 1 and meta["pre"] == 2 and meta["post"] == 0
    assert meta["userData"] == ["ud[em]"] and meta["emailInUrl"] == ["dl"]
    assert "tmgoogletagmanager" in meta["integration"]
    assert all("mario%40example.com" not in s and "abc123" not in s for s in meta["samples"])
    assert any(c.startswith("gcs=G100 (ad_storage negato, analytics_storage negato)") for c in r["pixels"]["ga4"]["consent"])
    assert any("sgtm.example.com" in s for s in r["serverSide"])
    assert r["pixels"]["tiktok"]["post"] == 1 and r["pixels"]["tiktok"]["pre"] == 0
    assert r["pixels"]["klaviyo"]["ids"] == ["AbC123"]
    assert r["inlineIds"]["meta"] == ["1234567890123456"]
    assert r["noscript"] and r["onePxImages"] == ["non classificato: px.ads-esempio.example"]
    assert r["iframes"] == ["td.doubleclick.net"]
    assert "unknown-adnet.example/collect" in r["unknownBeacons"]
    assert r["globals"]["meta"][0]["userData"] == ["em"]
    ads = r["pixels"]["google_ads"]  # JSONP conversion call loaded as <script>: an event, not a library
    assert ads["hits"] == 1 and ads["scripts"] == 0 and ads["ids"] == ["123456789"]


MARKER_HARNESS = r"""
const fs = require('fs');
const code = fs.readFileSync(0, 'utf8');
let store = { __cookieAudit_consent: '{"origin":1,"t":1}' };
globalThis.sessionStorage = { getItem: k => store[k] || null, removeItem: k => { delete store[k]; },
  length: 0, key: () => null };
globalThis.localStorage = { length: 0, key: () => null, getItem: () => null };
globalThis.location = { href: 'https://shop.example.com/' };
globalThis.window = globalThis;
globalThis.document = { title: 't', cookie: process.argv[1] || '' };
const out = eval('(' + code + ')')();
process.stdout.write(JSON.stringify({ reset: !!out.markerReset, left: Object.keys(store) }));
"""


@pytest.mark.skipif(NODE is None, reason="node non disponibile")
@pytest.mark.parametrize("cookie, reset", [("", True), ("OptanonConsent=groups%3DC0001%3A1", False)])
def test_probe_1_resets_a_stale_consent_marker(cookie, reset):
    out = subprocess.run([NODE, "-e", MARKER_HARNESS, cookie], input=_probe_block("§1"), capture_output=True, text=True)
    assert out.returncode == 0, out.stderr[:500]
    r = json.loads(out.stdout)
    assert r["reset"] is reset and (r["left"] == []) is reset


# ---------------------------------------------------------------------------
# generate_report.js
# ---------------------------------------------------------------------------
def _docx_module_available() -> bool:
    if NODE is None:
        return False
    npm = shutil.which("npm")
    if npm is None:
        return False
    root = subprocess.run([npm, "root", "-g"], capture_output=True, text=True).stdout.strip()
    probe = subprocess.run([NODE, "-e", "require('docx')"], capture_output=True, env={"NODE_PATH": root, "PATH": ""})
    return probe.returncode == 0


@pytest.mark.skipif(not _docx_module_available(), reason="node o pacchetto npm globale docx non disponibili")
def test_report_includes_pixel_map_and_newsletter(tmp_path):
    docx = pytest.importorskip("docx")
    audit = {
        "site": "studio-esempio.example", "url": "https://www.studio-esempio.example/", "date": "15 ottobre 2026",
        "cookies": [{"name": "_fbp", "provider": "Meta", "purpose": "Pubblicità", "duration": "90 giorni",
                     "category": "Marketing", "state": "Osservato"}],
        "pixels": [{"tool": "Meta Pixel", "where": "Sito (pagina)", "id": "1234567890123456",
                    "data": "PageView · ud[em]", "when": "Pre-consenso", "state": "Osservato"}],
        "newsletter": [{"message": "Newsletter di ottobre", "platform": "Mailchimp",
                        "findings": ["Pixel individuale", "Manca la revoca del solo tracciamento"]}],
    }
    src = tmp_path / "audit.json"
    src.write_text(json.dumps(audit), encoding="utf-8")
    dest = tmp_path / "report.docx"
    npm_root = subprocess.run([shutil.which("npm"), "root", "-g"], capture_output=True, text=True).stdout.strip()
    subprocess.run([NODE, str(SCRIPTS / "generate_report.js"), str(src), str(dest)], check=True,
                   capture_output=True, env={"NODE_PATH": npm_root, "PATH": str(Path(NODE).parent)})
    doc = docx.Document(str(dest))
    headers = [[c.text for c in t.rows[0].cells] for t in doc.tables]
    assert ["Strumento", "Dove", "ID", "Eventi e dati inviati", "Momento", "Stato"] in headers
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Newsletter e comunicazioni email" in text and "Manca la revoca del solo tracciamento" in text
