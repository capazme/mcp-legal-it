#!/usr/bin/env python3
"""Map the tracking inside a newsletter or any e-mail (.eml, or the HTML of its body).

Usage:
    python3 inspect_newsletter.py newsletter.eml
    python3 inspect_newsletter.py --recipient prova1@studio-esempio.example newsletter.eml
    python3 inspect_newsletter.py --compare copia_a.eml copia_b.eml \
        --recipient prova1@studio-esempio.example --recipient prova2@studio-esempio.example
    python3 inspect_newsletter.py --json newsletter.eml

What it reports, for the Garante's Guidelines on tracking pixels in e-mail
(provv. 17 April 2026 n. 284, doc. web 10241943):
- the sending platform, read from the headers (Return-Path, DKIM, Received, List-*);
- remote images that work as open trackers: 1x1 or hidden pixels, images whose URL
  carries an identifier, known open-tracking paths;
- tracked links (redirects) and the per-recipient IDs some platforms append to the
  destination URL, which follow the person onto the website;
- trackers of third parties (analytics, ad networks, dynamic content);
- the recipient's own address inside any URL, in clear or encoded (base64, hex,
  MD5/SHA-1/SHA-256) when --recipient is given: the Guidelines (§6) ask that the
  pixel request carry an unintelligible ID, never the address;
- whether the footer offers unsubscribe, a way to refuse ONLY the tracking (§6) and
  a notice about it (§4).
With --compare, two copies of the same message sent to two test addresses show
whether each recipient gets a different pixel: only an identical pixel can support
the "global open rate" exemption of §5.

Standard library only. Output in Italian (it ends up in an Italian audit report).
"""
from __future__ import annotations

import argparse
import base64
import binascii
import email
import email.policy
import hashlib
import json
import quopri
import re
import sys
from collections import OrderedDict
from html.parser import HTMLParser
from urllib.parse import parse_qsl, unquote, urlsplit

# ---------------------------------------------------------------------------
# Sending platforms (ESP). Matched on domains found in headers and URLs; custom
# tracking domains are common, so the label is a hint, never a requirement.
# ---------------------------------------------------------------------------
ESPS = OrderedDict([
    ("Mailchimp", r"mcsv\.net|mcdlv\.net|rsgsv\.net|list-manage\.com|mailchimp\.com|mcusercontent\.com"),
    ("Mailchimp Transactional (Mandrill)", r"mandrillapp\.com"),
    ("Brevo (ex Sendinblue)", r"sendinblue\.com|brevo\.com|sendib[a-z]*\d*\.com|sibforms\.com"),
    ("MailUp", r"musvc\d*\.(?:com|net)|mailup(?:client)?\.(?:com|it|net)"),
    ("MailerLite", r"mlsend\d*\.com|mailerlite\.com"),
    ("Mailjet", r"mailjet\.com|mjt\.lu"),
    ("SendGrid (Twilio)", r"sendgrid\.(?:net|com|info)"),
    ("Amazon SES", r"amazonses\.com|awstrack\.me"),
    ("Mailgun", r"mailgun\.(?:org|net|info|com)"),
    ("Postmark", r"mtasv\.net|postmarkapp\.com|pstmrk\.it"),
    ("SparkPost", r"sparkpostmail\.com|spgo\.io|sparkpost\.com"),
    ("HubSpot", r"hubspotemail\.net|hubspotlinks\.com|hs-sites\.com|hubspot\.com|hubspotstarter\.net"),
    ("Klaviyo", r"klaviyomail\.com|klaviyo\.com|klclick\d*\.com|kmail-lists\.com"),
    ("Salesforce Marketing Cloud", r"exacttarget\.com|exct\.net|marketingcloudapps\.com"),
    ("Salesforce Account Engagement (Pardot)", r"pardot\.com"),
    ("Adobe Marketo", r"mktomail\.com|mktoweb\.com|marketo\.com"),
    ("Oracle Eloqua", r"eloqua\.com|en25\.com"),
    ("Oracle Responsys", r"rsys\d\.net|responsys\.net"),
    ("Adobe Campaign", r"neolane\.net|campaign\.adobe\.com"),
    ("Emarsys (SAP)", r"emarsys\.(?:net|com)"),
    ("Selligent / Marigold", r"slgnt\.(?:eu|us)|selligent\.com"),
    ("Constant Contact", r"ccsend\.com|rs6\.net|constantcontact\.com"),
    ("Campaign Monitor", r"createsend\d*\.com|cmail\d+\.com"),
    ("ActiveCampaign", r"activehosted\.com|acems\d*\.com|acemln[a-z]\.com"),
    ("GetResponse", r"getresponse\.com|gr-cdn\.com"),
    ("Zoho Campaigns", r"zcsend\.net|maillist-manage\.(?:com|eu|in)"),
    ("Customer.io", r"customeriomail\.com|customer\.io"),
    ("Omnisend", r"omnisend\.com|omnisrv\.com"),
    ("Kit (ConvertKit)", r"convertkit[a-z-]*\.com|ck\.page"),
    ("Dotdigital", r"dotdigital\.com|trackedlink\.net|dmtrk\.com|dotmailer\.com"),
    ("CleverReach", r"cleverreach\.com|crsend\.com"),
    ("Substack", r"substack\.com|substackcdn\.com"),
    ("beehiiv", r"beehiiv\.com"),
    ("Shopify Email", r"shopifyemail\.com"),
    ("Squarespace", r"squarespace-mail\.com"),
    ("MailPoet (WordPress)", r"mailpoet\.com"),
    ("Acumbamail", r"acumbamail\.com"),
    ("4Dem", r"4dem\.it"),
    ("Voxmail", r"voxmail\.it"),
    ("Emailchef", r"emailchef\.com"),
    ("Moosend", r"moosend\.com|mailendo\.com"),
    ("Benchmark Email", r"benchmarkemail\.com|bmetrack\.com"),
])
ESP_HEADERS = {
    "X-MC-User": "Mailchimp", "X-Mandrill-User": "Mailchimp Transactional (Mandrill)",
    "X-Mailin-Campaign": "Brevo (ex Sendinblue)", "X-Mailin-Client": "Brevo (ex Sendinblue)",
    "X-SG-EID": "SendGrid (Twilio)", "X-SG-ID": "SendGrid (Twilio)", "X-SES-Outgoing": "Amazon SES",
    "X-Mailgun-Sid": "Mailgun", "X-Mailgun-Variables": "Mailgun", "X-PM-Message-Id": "Postmark",
    "X-MJ-Mid": "Mailjet", "X-Mailjet-Campaign": "Mailjet", "X-Roving-Id": "Constant Contact",
    "X-SFMC-Stack": "Salesforce Marketing Cloud", "X-MSFBL": "SparkPost",
}

# Third parties that track inside e-mails (beyond the sending platform).
THIRD_PARTIES = OrderedDict([
    ("Google Analytics (pixel di misurazione)", r"google-analytics\.com|analytics\.google\.com"),
    ("Meta Pixel", r"facebook\.com/tr|facebook\.net"),
    ("Google DoubleClick / Ads", r"doubleclick\.net|googleadservices\.com"),
    ("LiveIntent (pubblicità nelle newsletter)", r"liadm\.com|licasd\.com|liveintent\.com"),
    ("Litmus Email Analytics", r"emltrk\.com|litmus\.com"),
    ("Movable Ink (contenuti dinamici)", r"movableink\.com|movable-ink"),
    ("Nifty Images (contenuti dinamici)", r"niftyimages\.com"),
    ("Zembula (contenuti dinamici)", r"zembula\.com"),
    ("PowerInbox / Jeeng (pubblicità)", r"powerinbox\.com|jeeng\.com"),
    ("Criteo", r"criteo\.(?:com|net)"),
    ("Adobe Analytics", r"omtrdc\.net|2o7\.net|demdex\.net"),
    ("Salesforce Personalization (Evergage)", r"evergage\.com"),
    ("Microsoft Advertising", r"bat\.bing\.com"),
    ("Taboola / Outbrain", r"taboola\.com|outbrain\.com"),
])

# Parameters that carry a per-recipient ID onto the destination website.
CAMPAIGN_PARAMS = {"mc_cid": "Mailchimp: ID della campagna", "elqaid": "Eloqua: ID dell'invio",
                   "_hsmi": "HubSpot: ID del messaggio"}
LINK_ID_PARAMS = OrderedDict([
    ("mc_eid", "Mailchimp: ID del destinatario"),
    ("_hsenc", "HubSpot: ID del contatto"),
    ("_kx", "Klaviyo: ID del contatto"), ("mkt_tok", "Marketo: token del contatto"),
    ("elqTrackId", "Eloqua: ID di tracciamento"),
    ("vgo_ee", "ActiveCampaign: email codificata del contatto"),
    ("ck_subscriber_id", "Kit: ID dell'iscritto"), ("ml_subscriber", "MailerLite: ID dell'iscritto"),
    ("ml_subscriber_hash", "MailerLite: hash dell'iscritto"), ("sib_id", "Brevo: ID del contatto"),
    ("omnisendContactID", "Omnisend: ID del contatto"), ("__s", "Drip: ID dell'iscritto"),
    ("sfmc_id", "Salesforce: ID dell'iscritto"), ("sfmc_sub", "Salesforce: ID dell'iscritto"),
    ("subscriber_id", "ID dell'iscritto"), ("contact_id", "ID del contatto"), ("uid", "ID utente"),
    ("email", "indirizzo email"), ("e", "possibile ID del destinatario"),
])

# Open-tracking and click-tracking paths, matched on the URL PATH only (never the query) and
# on whole segments, so /click-and-collect or Firebase Storage's /v0/b/x/o/… are not taken.
OPEN_PATH = re.compile(
    r"(?:^|/)open(?:\.php|\.aspx|\.html|\.gif|\.png)?$|/open/|^/wf/open$|/track/open|/tr/op/|/oo/|^/o/[^/]{8,}$|"
    r"^/I0/|/e/FooterImages/|/on\.jsp$|(?:^|/)(?:pixel|beacon|imp|impression|pxl|px|1x1)(?:\.gif|\.png)?$|/e/o/",
    re.I)
CLICK_PATH = re.compile(
    r"^/ls/click$|/track/click$|/lnk/|/tr/cl/|^/L0/|^/c/[^/]{8,}|^/e/t$|/Ctc/|(?:^|/)redirect(?:/|$)|^/r/?$|"
    r"(?:^|/)click(?:/|$)|/tn\.jsp$|/link/c/|^/e/er$|^/l/[^/]{8,}|/ss/c/", re.I)
IMAGE_EXT = re.compile(r"\.(?:png|jpe?g|gif|webp|svg|bmp|ico)$", re.I)
# A notice about tracking the e-mail (not "tracking della spedizione", not a phone called Pixel).
NOTICE_TEXT = re.compile(
    r"pixel\W+(?:\w+\W+){0,6}?(?:traccia|tracking|apertur|misur|monitor)|"
    r"(?:traccia|tracking|apertur|misur|monitor)\w*\W+(?:\w+\W+){0,6}?pixel|"
    r"(?:tracci\w*|tracking|monitoragg\w*|misur\w*|statistich\w*|rilev\w*)\W+(?:\w+\W+){0,3}?(?:apertur|letture)|"
    r"apertura (?:dei messaggi|delle (?:e-?mail|email|comunicazioni|newsletter))", re.I)
TRACK_WORD = re.compile(r"tracciament|tracciar|tracking|pixel", re.I)
REFUSE_WORD = re.compile(r"disattiv|rifiut|revoc|\bstop\b|non tracciar|opt-?out|disabilit|interromp|smett|blocc|"
                         r"esclud|senza (?:pixel|tracciament)|preferenz|gestisci|impostazion", re.I)
UNSUB_TEXT = re.compile(
    r"disiscri|cancell\w* (?:la tua |l')?iscrizione|annull\w* (?:la )?iscrizione|unsubscribe|opt-?out|"
    r"non (?:ricevere|desideri ricevere) più|rimuovi\w* (?:dalla|il tuo indirizzo)|cancellati",
    re.I)
PREF_TEXT = re.compile(r"preferenz|gestisci|aggiorna (?:il tuo |i tuoi )?(?:profilo|dati)|manage|update profile|"
                       r"modifica (?:il tuo )?profilo", re.I)
PRIVACY_TEXT = re.compile(r"privacy|informativa|trattamento dei dati|protezione dei dati", re.I)
TRANSACTIONAL_SUBJECT = re.compile(
    r"conferm|verific|attiva|password|benvenut|welcome|ordine|order|fattura|ricevuta|spedizion|"
    r"reimposta|codice", re.I)


def registrable(host: str) -> str:
    host = (host or "").lower().strip(".")
    parts = host.split(".")
    two = re.search(r"\.(?:co|com|org|net|gov|ac|edu)\.[a-z]{2}$", host)
    return ".".join(parts[-3:] if two else parts[-2:])


def split(url: str):
    """urlsplit that never raises: a malformed URL (an unreplaced placeholder) is skipped."""
    try:
        parts = urlsplit(url if not url.startswith("//") else "https:" + url)
        parts.hostname  # raises on a broken IPv6 literal
        return parts
    except ValueError:
        return None


def host_of(url: str) -> str:
    parts = split(url)
    return ((parts.hostname if parts else "") or "").lower()


def domain_match(host: str, rx: str) -> bool:
    """`rx` matches the host itself or one of its parent domains, never a substring elsewhere."""
    return bool(host) and re.search(r"(?:^|\.)(?:" + rx + r")$", host.lower()) is not None


def is_open_path(url: str) -> bool:
    parts = split(url)
    if parts is None:
        return False
    q = dict(parse_qsl(parts.query))
    return bool(OPEN_PATH.search(parts.path)) or (parts.path.endswith("/trk") and q.get("t") == "1") \
        or (parts.path.endswith("lt.php") and q.get("l") == "open")


def is_click_path(url: str) -> bool:
    parts = split(url)
    if parts is None:
        return False
    q = dict(parse_qsl(parts.query))
    return bool(CLICK_PATH.search(parts.path)) or "qs" in q or (parts.path.endswith("/trk") and q.get("t") == "2")


def looks_token(s: str) -> bool:
    """An opaque per-message/per-recipient token rather than a word or a number."""
    s = unquote(s)
    if len(s) < 16:
        return False
    if re.fullmatch(r"[A-Za-z0-9_\-+/=.~%]{16,}", s) is None:
        return False
    classes = sum(bool(re.search(rx, s)) for rx in (r"[a-z]", r"[A-Z]", r"\d"))
    return classes >= 2 or bool(re.fullmatch(r"[0-9a-f]{24,}", s, re.I))


def tokens_in(url: str):
    parts = split(url)
    if parts is None:
        return []
    toks = [seg for seg in parts.path.split("/") if looks_token(seg) and not IMAGE_EXT.search(seg)]
    toks += [f"{k}={v[:12]}…" for k, v in parse_qsl(parts.query, keep_blank_values=True) if looks_token(v)]
    return toks


def shape(url: str) -> str:
    """URL with every token replaced, to align the same resource across two copies."""
    parts = split(url)
    if parts is None:
        return url
    path = "/".join("*" if looks_token(seg) else seg for seg in parts.path.split("/"))
    keys = sorted(k for k, _ in parse_qsl(parts.query, keep_blank_values=True))
    return f"{(parts.hostname or '').lower()}{path}?{'&'.join(keys)}"


def email_variants(addr: str) -> dict:
    a = addr.strip()
    low = a.lower()
    out = OrderedDict()
    out["in chiaro"] = [a, low]
    out["URL-encoded"] = [low.replace("@", "%40"), low.replace("@", "%40").replace(".", "%2E")]
    raw = low.encode()
    b64 = base64.b64encode(raw).decode()
    b64u = base64.urlsafe_b64encode(raw).decode()
    out["base64"] = list(dict.fromkeys([b64, b64.rstrip("="), b64u, b64u.rstrip("=")]))
    out["esadecimale"] = [raw.hex()]
    out["hash MD5"] = [hashlib.md5(raw).hexdigest()]  # noqa: S324 - matching, not security
    out["hash SHA-1"] = [hashlib.sha1(raw).hexdigest()]  # noqa: S324 - matching, not security
    out["hash SHA-256"] = [hashlib.sha256(raw).hexdigest()]
    return out


def find_address(url: str, variants: dict):
    hay = url + " " + unquote(url)
    low = hay.lower()
    for label, vals in variants.items():
        for v in vals:
            if not v:
                continue
            if label in ("in chiaro", "URL-encoded", "esadecimale") or label.startswith("hash"):
                if v.lower() in low:
                    return label
            elif v in hay:
                return label
    return None


# ---------------------------------------------------------------------------
# HTML extraction
# ---------------------------------------------------------------------------
class MailHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.images, self.links, self.css_urls, self.text = [], [], [], []
        self._a = None
        self._style = False

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        style = a.get("style", "")
        for m in re.finditer(r"url\(\s*['\"]?([^'\")]+)", style):
            self.css_urls.append(m.group(1))
        if a.get("background"):
            self.css_urls.append(a["background"])
        if tag == "img" or tag in ("v:image", "v:fill"):
            self.images.append({"src": a.get("src", ""), "width": a.get("width", ""), "height": a.get("height", ""),
                                "style": style, "alt": a.get("alt", "")})
        elif tag == "a":
            self._a = {"href": a.get("href", ""), "text": ""}
        elif tag == "link" and "stylesheet" in a.get("rel", "").lower():
            self.css_urls.append(a.get("href", ""))
        elif tag == "style":
            self._style = True

    def handle_endtag(self, tag):
        if tag == "a" and self._a is not None:
            self._a["text"] = re.sub(r"\s+", " ", self._a["text"]).strip()
            self.links.append(self._a)
            self._a = None
        elif tag == "style":
            self._style = False

    def handle_data(self, data):
        if self._style:
            for m in re.finditer(r"(?:url\(|@import\s+)\s*['\"]?((?:https?:)?//[^'\")\s;]+)", data):
                self.css_urls.append(m.group(1))
            return
        if self._a is not None:
            self._a["text"] += data
        if data.strip():
            self.text.append(data.strip())


def is_remote(url: str) -> bool:
    return url.startswith(("http://", "https://", "//"))


def px(v: str):
    m = re.match(r"\s*(\d+(?:\.\d+)?)", v or "")
    return float(m.group(1)) if m else None


def image_kind(img: dict) -> tuple:
    """(is_pixel, reasons)."""
    reasons = []
    w, h = px(img["width"]), px(img["height"])
    st = (img["style"] or "").lower().replace(" ", "")
    sw = re.search(r"(?:^|;)width:(\d+(?:\.\d+)?)px", st)
    sh = re.search(r"(?:^|;)height:(\d+(?:\.\d+)?)px", st)
    def tiny(a, b):
        return (a is not None and a <= 1 and (b is None or b <= 1)) or (b is not None and b <= 1 and a is None)
    if tiny(w, h):
        reasons.append("dimensioni ≤ 1 px")
    elif tiny(float(sw.group(1)) if sw else None, float(sh.group(1)) if sh else None):
        reasons.append("stile ≤ 1 px")
    if re.search(r"display:none|visibility:hidden|opacity:0(?:[;!]|$)|max-height:0|mso-hide:all", st):
        reasons.append("immagine nascosta")
    if is_open_path(img["src"]):
        reasons.append("percorso tipico dei pixel di apertura")
    return bool(reasons), reasons


# ---------------------------------------------------------------------------
# Message analysis
# ---------------------------------------------------------------------------
class NotAnEml(ValueError):
    pass


def attached_message(part):
    """The original message of a forward-as-attachment. Some clients encode message/rfc822 in
    base64 or quoted-printable (RFC 2046 says they should not): the parser then sees the encoded
    text as a message without headers, so it is decoded and parsed again."""
    payload = part.get_payload()
    inner = payload[0] if isinstance(payload, list) and payload else None
    cte = str(part.get("Content-Transfer-Encoding", "")).strip().lower()
    if inner is not None and cte in ("base64", "quoted-printable"):
        body = inner.get_payload()
        if isinstance(body, str):
            try:
                data = base64.b64decode(body) if cte == "base64" else quopri.decodestring(body.encode())
                return email.message_from_bytes(data, policy=email.policy.default)
            except (ValueError, binascii.Error):
                return inner
    return inner


def load_message(path: str):
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        raise NotAnEml("file .msg di Outlook: salva il messaggio come .eml, oppure inoltralo come allegato a una casella "
                       "Gmail e scarica il messaggio ricevuto (lo strumento legge l'originale allegato)")
    head = data[:4000].lower()
    is_html = path.lower().endswith((".html", ".htm")) or (b"<html" in head and b"\nreceived:" not in head
                                                         and b"\nfrom:" not in head and b"\nsubject:" not in head)
    if is_html:
        return None, data.decode("utf-8", errors="replace"), "", False
    msg = email.message_from_bytes(data, policy=email.policy.default)
    forwarded = False
    for part in msg.walk():
        if part.get_content_type() == "message/rfc822":
            inner = attached_message(part)
            if inner is not None:
                msg, forwarded = inner, True
            break
    html, text = "", ""
    for part in msg.walk():
        ctype = part.get_content_type()
        if part.get_content_disposition() == "attachment":
            continue
        try:
            if ctype == "text/html" and not html:
                html = part.get_content()
            elif ctype == "text/plain" and not text:
                text = part.get_content()
        except (LookupError, ValueError):
            payload = part.get_payload(decode=True) or b""
            if ctype == "text/html" and not html:
                html = payload.decode("utf-8", errors="replace")
    return msg, html, text, forwarded


def header_domains(msg) -> list:
    if msg is None:
        return []
    found = []
    blob = []
    for name in ("Return-Path", "Sender", "From", "Reply-To", "List-Unsubscribe", "List-Id", "Message-ID",
                 "Feedback-ID", "X-Mailer"):
        for v in msg.get_all(name) or []:
            blob.append(str(v))
    for v in msg.get_all("DKIM-Signature") or []:
        m = re.search(r"\bd=([^;\s]+)", str(v))
        if m:
            blob.append(m.group(1))
    for name in ("Authentication-Results", "ARC-Authentication-Results"):
        for v in msg.get_all(name) or []:
            blob += re.findall(r"(?:smtp\.mailfrom|header\.d|header\.i|header\.from)=([^;\s]+)", str(v))
    for v in msg.get_all("Received") or []:
        blob += re.findall(r"from\s+([a-z0-9.-]+\.[a-z]{2,})", str(v), re.I)
    for item in blob:
        for d in re.findall(r"[a-z0-9.-]+\.[a-z]{2,}", item.lower()):
            if d not in found:
                found.append(d)
    return found


MAILER_TOKENS = OrderedDict([
    ("mailchimp", "Mailchimp"), ("mandrill", "Mailchimp Transactional (Mandrill)"), ("sendinblue", "Brevo (ex Sendinblue)"),
    ("brevo", "Brevo (ex Sendinblue)"), ("mailup", "MailUp"), ("mailerlite", "MailerLite"), ("mailjet", "Mailjet"),
    ("sendgrid", "SendGrid (Twilio)"), ("hubspot", "HubSpot"), ("klaviyo", "Klaviyo"),
    ("createsend", "Campaign Monitor"), ("campaign monitor", "Campaign Monitor"), ("roving", "Constant Contact"),
    ("constant contact", "Constant Contact"), ("activecampaign", "ActiveCampaign"), ("getresponse", "GetResponse"),
    ("zoho campaigns", "Zoho Campaigns"), ("mailpoet", "MailPoet (WordPress)"), ("acumbamail", "Acumbamail"),
    ("4dem", "4Dem"), ("voxmail", "Voxmail"), ("emailchef", "Emailchef"), ("moosend", "Moosend"),
    ("benchmark email", "Benchmark Email"), ("exacttarget", "Salesforce Marketing Cloud"),
    ("eloqua", "Oracle Eloqua"), ("marketo", "Adobe Marketo"), ("selligent", "Selligent / Marigold"),
    ("emarsys", "Emarsys (SAP)"), ("customer.io", "Customer.io"), ("omnisend", "Omnisend"),
    ("substack", "Substack"), ("beehiiv", "beehiiv"), ("dotmailer", "Dotdigital"), ("dotdigital", "Dotdigital"),
    ("cleverreach", "CleverReach"), ("convertkit", "Kit (ConvertKit)"),
])


def identify_esp(msg, urls: list) -> list:
    evidence = OrderedDict()
    domains = header_domains(msg)
    hosts = sorted({host_of(u) for u in urls} - {""})
    for name, rx in ESPS.items():
        hits = [d for d in domains if domain_match(d, rx)]
        url_hits = [h for h in hosts if domain_match(h, rx)]
        if hits or url_hits:
            evidence[name] = (["intestazioni: " + ", ".join(hits[:4])] if hits else []) + \
                             (["URL: " + ", ".join(url_hits[:4])] if url_hits else [])
    if any("mailpoet_router" in u for u in urls):
        evidence.setdefault("MailPoet (WordPress)", []).append("parametro mailpoet_router nei link")
    if msg is not None:
        for header, name in ESP_HEADERS.items():
            if msg.get(header) is not None:
                evidence.setdefault(name, []).append(f"intestazione {header}")
        mailer = str(msg.get("X-Mailer") or "")
        for token, name in MAILER_TOKENS.items():
            if re.search(r"(?:^|[^a-z0-9])" + re.escape(token) + r"(?:$|[^a-z0-9])", mailer.lower()):
                evidence.setdefault(name, []).append(f"X-Mailer: {mailer[:60]}")
    return [{"name": k, "evidence": v} for k, v in evidence.items()]


def third_party(url: str):
    parts = split(url)
    if parts is None:
        return None
    where = ((parts.hostname or "") + parts.path).lower()
    for name, rx in THIRD_PARTIES.items():
        if re.search(rx, where, re.I):
            return name
    return None


def analyse_message(path: str, recipient: str | None = None) -> dict:
    msg, html, text, forwarded = load_message(path)
    r = {"file": path, "subject": "", "from": "", "date": "", "kind": [], "esp": [], "html": bool(html),
         "pixels": [], "tracked_images": [], "remote_images": 0, "css_remote": [], "tracked_links": [],
         "link_id_params": OrderedDict(), "campaign_params": OrderedDict(), "third_parties": OrderedDict(),
         "address_in_urls": [],
         "unsubscribe": [], "tracking_optout": [], "preferences": [], "privacy_links": [],
         "tracking_notice": [], "hosts": OrderedDict(), "all_urls": [], "warnings": []}
    if forwarded:
        r["warnings"].append("messaggio inoltrato come allegato: analizzati intestazioni e corpo del messaggio originale allegato")
    if msg is not None:
        r["subject"] = str(msg.get("Subject", ""))
        r["from"] = str(msg.get("From", ""))
        r["date"] = str(msg.get("Date", ""))
        lu = str(msg.get("List-Unsubscribe", "") or "")
        if lu:
            r["unsubscribe"].append(f"intestazione List-Unsubscribe ({'one-click' if msg.get('List-Unsubscribe-Post') else 'semplice'})")
        bulk = [h for h in ("List-Unsubscribe", "List-Id") if msg.get(h)] + \
               [f"Precedence: {msg.get('Precedence')}" for _ in [0] if str(msg.get("Precedence", "")).lower() in ("bulk", "list")]
        if bulk:
            r["kind"].append("invio massivo (newsletter/DEM): " + ", ".join(bulk))
        if TRANSACTIONAL_SUBJECT.search(r["subject"]):
            r["kind"].append("oggetto tipico di un messaggio automatico/transazionale (conferma, benvenuto, password…)")
    if not html:
        r["warnings"].append("nessuna parte HTML: un messaggio solo testo non può contenere pixel")
        r["esp"] = identify_esp(msg, [])
        return r

    parser = MailHTML()
    try:
        parser.feed(html)
    except Exception as exc:  # malformed HTML: keep what was read
        r["warnings"].append(f"HTML non del tutto leggibile ({exc.__class__.__name__}): analisi parziale")
    variants = email_variants(recipient) if recipient else None
    from_dom = registrable(re.sub(r".*@", "", re.sub(r"[<>\s]", "", r["from"].split("<")[-1])) if r["from"] else "")

    def note_host(url, role):
        h = host_of(url)
        if not h:
            return
        entry = r["hosts"].setdefault(h, {"roles": [], "party": ""})
        if role not in entry["roles"]:
            entry["roles"].append(role)

    for img in parser.images:
        src = img["src"].strip()
        if not is_remote(src):
            continue
        if split(src) is None:
            r["warnings"].append(f"URL di immagine malformato, ignorato: {src[:80]}")
            continue
        r["remote_images"] += 1
        r["all_urls"].append(("immagine", src))
        is_pix, reasons = image_kind({**img, "src": src})
        toks = tokens_in(src)
        dynamic = bool(toks) and not IMAGE_EXT.search(split(src).path)
        if is_pix:
            r["pixels"].append({"url": src, "host": host_of(src), "reasons": reasons, "tokens": toks})
            note_host(src, "pixel")
        elif toks and (dynamic or any("=" in t for t in toks)):
            r["tracked_images"].append({"url": src, "host": host_of(src), "tokens": toks})
            note_host(src, "immagine con identificativo")
        else:
            note_host(src, "immagine")
        tp = third_party(src)
        if tp:
            r["third_parties"].setdefault(tp, []).append(src[:160])
    for css in parser.css_urls:
        if is_remote(css) and split(css) is not None:
            r["css_remote"].append(css)
            r["all_urls"].append(("stile/sfondo", css))
            note_host(css, "stile o sfondo remoto")
            tp = third_party(css)
            if tp:
                r["third_parties"].setdefault(tp, []).append(css[:160])
    for link in parser.links:
        href = link["href"].strip()
        txt = link["text"]
        label = f"{txt[:60]} → {host_of(href) or href[:60]}"
        is_optout = (bool(TRACK_WORD.search(txt)) and bool(REFUSE_WORD.search(txt))) or (
            bool(re.search(r"track|tracciament|pixel", href, re.I))
            and bool(re.search(r"opt-?out|disattiv|revoc|rifiut|disable|stop", href + " " + txt, re.I)))
        is_unsub = not is_optout and bool(UNSUB_TEXT.search(txt) or UNSUB_TEXT.search(href))
        is_pref = bool(PREF_TEXT.search(txt))
        if is_optout:
            r["tracking_optout"].append(label)
        if is_unsub:
            r["unsubscribe"].append(label)
        if is_pref:
            r["preferences"].append(label)
        if PRIVACY_TEXT.search(txt):
            r["privacy_links"].append(label)
        if not is_remote(href):
            continue
        if split(href) is None:
            r["warnings"].append(f"link malformato, ignorato: {href[:80]}")
            continue
        toks = tokens_in(href)
        functional = is_unsub or is_pref or is_optout
        tracked = not functional and (is_click_path(href)
                                      or (bool(toks) and registrable(host_of(href)) != from_dom))
        r["all_urls"].append(("link di servizio" if functional else "link", href))
        if tracked:
            r["tracked_links"].append({"url": href, "host": host_of(href), "text": txt[:60], "tokens": toks})
            note_host(href, "link tracciato")
        else:
            note_host(href, "link")
        for k, _v in parse_qsl(split(href).query, keep_blank_values=True):
            if functional:
                break
            if k in LINK_ID_PARAMS and (k not in ("e", "uid", "email") or looks_token(_v) or "@" in unquote(_v)):
                r["link_id_params"].setdefault(k, LINK_ID_PARAMS[k])
            elif k in CAMPAIGN_PARAMS:
                r["campaign_params"].setdefault(k, CAMPAIGN_PARAMS[k])
        tp = third_party(href)
        if tp:
            r["third_parties"].setdefault(tp, []).append(href[:160])
    joined = " ".join(parser.text)
    for m in NOTICE_TEXT.finditer(joined):
        snippet = joined[max(0, m.start() - 80): m.end() + 80].replace("\n", " ")
        r["tracking_notice"].append("…" + snippet + "…")
        if len(r["tracking_notice"]) >= 3:
            break
    if variants:
        for kind, url in r["all_urls"]:
            enc = find_address(url, variants)
            item = {"where": kind, "host": host_of(url), "encoding": enc}
            if enc and item not in r["address_in_urls"]:
                r["address_in_urls"].append(item)
    esp = identify_esp(msg, [u for _, u in r["all_urls"]])
    r["esp"] = esp
    esp_rx = [ESPS[e["name"]] for e in esp if e["name"] in ESPS]
    for h, entry in r["hosts"].items():
        if any(domain_match(h, rx) for rx in esp_rx):
            entry["party"] = "piattaforma di invio"
        elif third_party(h):
            entry["party"] = "terza parte"
        elif from_dom and registrable(h) == from_dom:
            entry["party"] = "dominio del mittente (anche dominio di tracciamento personalizzato)"
        else:
            entry["party"] = "da qualificare"
    r["unsubscribe"] = list(dict.fromkeys(r["unsubscribe"]))
    r["tracking_optout"] = list(dict.fromkeys(r["tracking_optout"]))
    r["preferences"] = list(dict.fromkeys(r["preferences"]))
    r["privacy_links"] = list(dict.fromkeys(r["privacy_links"]))
    return r


def compare(a: dict, b: dict) -> dict:
    """Same message to two recipients: which resources differ between the two copies.

    Every remote resource loaded when the message is opened counts, not only the 1x1
    pixels: a logo whose URL changes per recipient tracks the opening just as well."""
    def group(rep, kinds):
        g = OrderedDict()
        for kind, url in rep["all_urls"]:
            if kind in kinds:
                g.setdefault(shape(url), set()).add(url)
        return g

    out = {}
    for label, kinds in (("immagini e pixel", ("immagine", "stile/sfondo")), ("link", ("link",))):
        ga, gb = group(a, kinds), group(b, kinds)
        same, diff, only = [], [], []
        for key in OrderedDict.fromkeys(list(ga) + list(gb)):
            if key in ga and key in gb:
                (same if ga[key] == gb[key] else diff).append(key)
            else:
                only.append(key)
        out[label] = {"identici": same, "diversi": diff, "solo_in_una_copia": only}
    opened = out["immagini e pixel"]
    differing = opened["diversi"] + opened["solo_in_una_copia"]
    pix = {shape(p["url"]) for p in a["pixels"] + b["pixels"]}
    out["apertura_individuale"] = bool(differing)
    out["pixel_individuali"] = differing
    out["pixel_identici"] = [k for k in opened["identici"] if k in pix] if not differing else []
    out["clic_individuali"] = bool(out["link"]["diversi"] + out["link"]["solo_in_una_copia"])
    return out


# ---------------------------------------------------------------------------
# Findings against the Guidelines (provv. 17.4.2026 n. 284)
# ---------------------------------------------------------------------------
def findings(r: dict, cmp: dict | None = None) -> list:
    out = []
    if not r["html"]:
        return ["Messaggio solo testo: nessun pixel possibile."]
    trackers = bool(r["pixels"] or r["tracked_images"])
    individual = cmp is not None and cmp["apertura_individuale"]
    identical = cmp is not None and not individual and bool(cmp["pixel_identici"])
    automatic = any("transazionale" in k for k in r["kind"])
    service_note = (" Per i messaggi di sicurezza dell'autenticazione o di servizio dovuti per legge può valere una "
                    "deroga del §5." if automatic else "")
    if trackers or individual:
        n = len(r["pixels"]) + len(r["tracked_images"])
        out.append(f"⚠ Strumenti di tracciamento dell'apertura presenti ({n or 'vedi confronto'}): si applica "
                   "l'art. 122 del Codice (Linee guida §1). Servono informativa (§4) e, salvo deroga (§5), "
                   "consenso (§6)." + service_note)
        if individual:
            out.append("⚠ Il confronto mostra risorse caricate all'apertura DIVERSE nelle due copie (pixel o immagini "
                       "con un identificativo per destinatario, oppure contenuti personalizzati): misurazione "
                       "individuale delle aperture. La deroga del conteggio statistico globale (§5) richiede pixel "
                       "uguali per tutti i destinatari e dati anonimizzati: qui non è dimostrata.")
        elif identical:
            out.append("Il confronto mostra che tutte le risorse caricate all'apertura sono IDENTICHE nelle due copie: "
                       "compatibile con il conteggio statistico globale (§5), se IP e dati del client sono anonimizzati "
                       "e le aperture non sono usate per singolo destinatario (da verificare con il cliente).")
        elif r["address_in_urls"] and any(a["where"] == "immagine" for a in r["address_in_urls"]):
            out.append("⚠ Il pixel contiene l'indirizzo del destinatario (vedi sotto): la misurazione è individuale.")
        elif any(p["tokens"] for p in r["pixels"]) or r["tracked_images"]:
            out.append("L'URL del pixel contiene parametri opachi: possono identificare il destinatario o solo la "
                       "campagna. Per stabilirlo confronta due copie inviate a due caselle di prova (--compare).")
    else:
        out.append("Nessun pixel di apertura riconosciuto nel corpo del messaggio (verificare comunque le immagini "
                   "remote elencate: qualunque immagine con un identificativo individuale traccia l'apertura).")
    if r["address_in_urls"]:
        where = "; ".join(f"{a['where']} su {a['host']} ({a['encoding']})" for a in r["address_in_urls"][:5])
        out.append(f"⚠ L'indirizzo del destinatario compare negli URL: {where}. Le Linee guida (§6, privacy by "
                   "design) chiedono un identificativo inintelligibile e non sequenziale, senza l'indirizzo nella richiesta.")
    if r["tracked_links"]:
        confirmed = cmp is not None and cmp["clic_individuali"]
        out.append(f"Link tracciati con reindirizzamento: {len(r['tracked_links'])}. Il clic "
                   + ("è registrato per destinatario (i link sono diversi nelle due copie)" if confirmed
                      else "può essere registrato per destinatario")
                   + ": da dichiarare in informativa (Linee guida EDPB 2/2023, §3.1: il tracciamento via URL "
                     "rientra nell'art. 5(3) della direttiva e-Privacy).")
    if r["link_id_params"]:
        params = ", ".join(f"{k} ({v})" for k, v in r["link_id_params"].items())
        out.append(f"⚠ I link portano sul sito identificativi del destinatario: {params}. Il sito può riconoscere chi "
                   "arriva dalla newsletter: verificare con l'audit del sito che nessun tracciatore li usi prima del consenso.")
    if r["third_parties"]:
        out.append("⚠ Tracciatori di terze parti nel messaggio: " + ", ".join(r["third_parties"]) +
                   ". Ruoli da qualificare (artt. 26 e 28 GDPR, Linee guida §3), informativa e consenso.")
    if not r["unsubscribe"]:
        out.append("⚠ Nessun link o intestazione di disiscrizione riconosciuti.")
    if (trackers or individual) and not r["tracking_optout"]:
        if identical:
            out.append("Nessun link per rifiutare il solo tracciamento: non serve finché il pixel resta nel perimetro "
                       "della deroga statistica (§5); serve se le aperture vengono usate per singolo destinatario (§6).")
        else:
            out.append("⚠ Se il pixel richiede il consenso (nessuna deroga del §5), manca un modo per rifiutare SOLO il "
                       "tracciamento continuando a ricevere le email: le Linee guida (§6) chiedono la revoca anche "
                       "granulare, ad esempio con un link o un'icona nel footer di ogni messaggio — anche per le liste "
                       "già in uso." + service_note)
    if (trackers or individual) and not r["tracking_notice"]:
        out.append("Nel testo del messaggio non c'è alcun riferimento al tracciamento delle aperture: l'informativa "
                   "(§4) è comunque dovuta (al momento della raccolta dell'indirizzo o, per le liste già in uso, con il "
                   "primo invio utile).")
    return out


def print_message(r: dict, cmp: dict | None = None) -> None:
    print(f"== {r['file']} ==")
    if r["subject"] or r["from"]:
        print(f"Oggetto: {r['subject']}\nMittente: {r['from']}" + (f"\nData: {r['date']}" if r["date"] else ""))
    for w in r["warnings"]:
        print(f"⚠️  {w}")
    if r["kind"]:
        print("Tipo (indicativo): " + "; ".join(r["kind"]))
    if not r["html"]:
        print("\n-- Valutazione --\n  " + "\n  ".join(findings(r, cmp)))
        return
    if r["esp"]:
        print("\n-- Piattaforma di invio --")
        for e in r["esp"]:
            print(f"  {e['name']}: {'; '.join(e['evidence'])}")
    else:
        print("\n-- Piattaforma di invio --\n  non riconosciuta (dominio personalizzato o piattaforma non in elenco)")
    print(f"\n-- Pixel e immagini di tracciamento (immagini remote: {r['remote_images']}) --")
    for p in r["pixels"]:
        print(f"  PIXEL {p['host']} · {', '.join(p['reasons'])}" + (f" · identificativi: {', '.join(p['tokens'][:3])}" if p["tokens"] else ""))
        print(f"      {p['url'][:180]}")
    for p in r["tracked_images"]:
        print(f"  IMMAGINE CON IDENTIFICATIVO {p['host']} · {', '.join(p['tokens'][:3])}")
        print(f"      {p['url'][:180]}")
    if not r["pixels"] and not r["tracked_images"]:
        print("  (nessuno riconosciuto)")
    if r["css_remote"]:
        print(f"  Stili/sfondi/font remoti: {len(r['css_remote'])} ({', '.join(sorted({host_of(u) for u in r['css_remote']}))})")
    if r["tracked_links"]:
        hosts = OrderedDict()
        for l in r["tracked_links"]:
            hosts[l["host"]] = hosts.get(l["host"], 0) + 1
        print("\n-- Link tracciati --")
        for h, n in hosts.items():
            print(f"  {h}: {n} link")
    if r["link_id_params"]:
        print("  Parametri con identificativi del destinatario portati sul sito: " +
              ", ".join(f"{k} ({v})" for k, v in r["link_id_params"].items()))
    if r["campaign_params"]:
        print("  Parametri della campagna nei link: " + ", ".join(f"{k} ({v})" for k, v in r["campaign_params"].items()))
    if r["third_parties"]:
        print("\n-- Terze parti nel messaggio --")
        for name, urls in r["third_parties"].items():
            print(f"  {name}: {urls[0]}")
    if r["address_in_urls"]:
        print("\n-- Indirizzo del destinatario negli URL --")
        for a in r["address_in_urls"]:
            print(f"  {a['where']} su {a['host']}: {a['encoding']}")
    if r["hosts"]:
        print("\n-- Domini contattati all'apertura o al clic --")
    for h, e in r["hosts"].items():
        print(f"  {h} · {', '.join(e['roles'])} · {e['party']}")
    print("\n-- Piè di pagina e trasparenza --")
    print("  Disiscrizione: " + ("; ".join(r["unsubscribe"][:3]) if r["unsubscribe"] else "NON trovata"))
    print("  Revoca del solo tracciamento: " + ("; ".join(r["tracking_optout"][:3]) if r["tracking_optout"] else "NON trovata"))
    print("  Centro preferenze: " + ("; ".join(r["preferences"][:3]) if r["preferences"] else "non trovato"))
    print("  Link privacy/informativa: " + ("; ".join(r["privacy_links"][:3]) if r["privacy_links"] else "non trovato"))
    print("  Riferimenti al tracciamento nel testo: " + (" | ".join(r["tracking_notice"][:2]) if r["tracking_notice"] else "nessuno"))
    if cmp is not None:
        print("\n-- Confronto tra le due copie --")
        for label in ("immagini e pixel", "link"):
            c = cmp[label]
            print(f"  {label}: identici {len(c['identici'])} · diversi tra destinatari {len(c['diversi'])} · "
                  f"presenti in una sola copia {len(c['solo_in_una_copia'])}")
        if cmp["pixel_individuali"]:
            print("  Risorse caricate all'apertura diverse tra le copie: " + ", ".join(k[:80] for k in cmp["pixel_individuali"][:4]))
        if cmp["pixel_identici"]:
            print("  Pixel identici nelle due copie: " + ", ".join(k[:80] for k in cmp["pixel_identici"][:4]))
        if cmp["clic_individuali"]:
            print("  Link (esclusi quelli di servizio) diversi tra le copie: il clic è attribuito al destinatario")
    print("\n-- Valutazione (Linee guida Garante sui tracking pixel nelle e-mail, provv. 17.4.2026 n. 284) --")
    for f in findings(r, cmp):
        print(f"  {f}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Mappa il tracciamento dentro una newsletter (.eml o .html).")
    ap.add_argument("files", nargs="*", help="file .eml (consigliato) o .html del messaggio")
    ap.add_argument("--compare", nargs=2, metavar=("COPIA_A", "COPIA_B"),
                    help="due copie dello stesso messaggio inviate a due caselle di prova")
    ap.add_argument("--recipient", action="append", default=[],
                    help="indirizzo di prova che ha ricevuto il messaggio (ripetibile, nell'ordine dei file)")
    ap.add_argument("--json", action="store_true", help="output JSON")
    args = ap.parse_args(argv)
    if not args.files and not args.compare:
        ap.print_usage()
        return 1
    results = []
    try:
        return _run(args, results)
    except (NotAnEml, OSError) as exc:
        print(f"⚠️  {exc}")
        return 1


def _run(args, results) -> int:
    if args.compare:
        ra = analyse_message(args.compare[0], args.recipient[0] if args.recipient else None)
        rb = analyse_message(args.compare[1], args.recipient[1] if len(args.recipient) > 1 else None)
        cmp = compare(ra, rb)
        if rb["address_in_urls"]:
            ra["address_in_urls"] += [{**x, "where": x["where"] + " (copia B)"} for x in rb["address_in_urls"]]
        ra["warnings"] += [f"copia B: {w}" for w in rb["warnings"]]
        results.append({"message": ra, "compare_with": rb["file"], "comparison": cmp, "findings": findings(ra, cmp)})
    for i, f in enumerate(args.files):
        rec = args.recipient[i] if i < len(args.recipient) and not args.compare else (args.recipient[0] if len(args.recipient) == 1 else None)
        r = analyse_message(f, rec)
        results.append({"message": r, "findings": findings(r)})
    if args.json:
        for res in results:
            res["message"].pop("all_urls", None)
        print(json.dumps(results, ensure_ascii=False, indent=2, default=list))
        return 0
    for i, res in enumerate(results):
        if i:
            print("\n" + "=" * 72 + "\n")
        print_message(res["message"], res.get("comparison"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
