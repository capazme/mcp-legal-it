#!/usr/bin/env python3
"""Inspect a REAL Google Tag Manager container (or a gtag.js Google tag) server side.

Usage:
    python3 inspect_container.py GTM-XXXXXXX [GTM-YYYYYYY ...]
    python3 inspect_container.py G-XXXXXXXXXX | AW-123456789 | DC-12345678
    python3 inspect_container.py https://sgtm.example.com/gtm.js?id=GTM-XXXXXXX
    python3 inspect_container.py --file saved_container.js
    python3 inspect_container.py --json GTM-XXXXXXX          # machine-readable output

Why server side: a browser with uBlock/AdGuard receives a STUB of gtm.js and never
shows the real tags; curl/urllib bypasses the ad-blocker.

What it adds over a plain grep: the container is parsed as data, so every tag is
listed with its type, the pixel/vendor it belongs to, the IDs it uses, the user data
it sends (advanced matching, enhanced conversions) and the conditions that make it
fire — including whether any of them refers to consent. Standard library only:
runs with any python3 >= 3.8, no pip install.

Output messages are in Italian (they end up in an Italian audit report).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from collections import OrderedDict

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140 Safari/537.36")
TIMEOUT = 20

# ---------------------------------------------------------------------------
# Vendor fingerprints. Keep the keys aligned with the browser probe (§5 of
# references/browser-probes.md): tests/unit/test_cookie_audit_pixels.py checks it.
# ---------------------------------------------------------------------------
# Each vendor: label, category, host fragments (matched on "host/path"), globals the
# vendor's library defines, regexes that capture an ID from inline code, template
# parameter names that hold an ID, regexes that reveal user data sent with the hit.
VENDORS = OrderedDict([
    ("meta", dict(
        label="Meta Pixel (Facebook/Instagram)", category="Marketing",
        hosts=("connect.facebook.net", "facebook.com/tr", "facebook.net/signals"),
        globals=("fbq", "_fbq"),
        code_ids=(r"fbq\(\s*['\"]init['\"]\s*,\s*['\"]?(\d{6,20})",),
        id_params=("pixelId", "pixel_id", "pixelIds"),
        user_data=(r"fbq\(\s*['\"]init['\"]\s*,\s*['\"]?\d{6,20}['\"]?\s*,\s*[{\w]",),
        calls=(r"\bfbq\(",),
        events=(r"fbq\(\s*['\"](?:track|trackCustom|trackSingle|trackSingleCustom)['\"]\s*,\s*(?:['\"]\d+['\"]\s*,\s*)?['\"]([^'\"]{2,40})['\"]",),
    )),
    ("tiktok", dict(
        label="TikTok Pixel", category="Marketing",
        hosts=("analytics.tiktok.com",),
        globals=("ttq", "TiktokAnalyticsObject"),
        code_ids=(r"ttq\.load\(\s*['\"]([A-Z0-9]{15,25})['\"]", r"sdkid=([A-Z0-9]{15,25})"),
        id_params=("pixel_code", "pixelCode", "pixelId", "pixel_id"),
        user_data=(r"ttq\.identify\(",),
        calls=(r"\bttq\.(?:load|page|track|identify)\(",),
        events=(r"ttq\.track\(\s*['\"]([^'\"]{2,40})['\"]",),
    )),
    ("linkedin", dict(
        label="LinkedIn Insight Tag", category="Marketing",
        hosts=("snap.licdn.com", "px.ads.linkedin.com", "dc.ads.linkedin.com"),
        globals=("_linkedin_partner_id", "_linkedin_data_partner_ids", "lintrk"),
        code_ids=(r"_linkedin_partner_id\s*=\s*['\"]?(\d{3,12})",
                  r"px\.ads\.linkedin\.com/collect/?\?pid=(\d{3,12})"),
        id_params=("partnerId", "partner_id", "insightTagId"),
        user_data=(),
        calls=(r"\blintrk\(|_linkedin_partner_id",),
        events=(r"lintrk\(\s*['\"]track['\"]\s*,\s*\{\s*conversion_id\s*:\s*['\"]?(\d+)",),
    )),
    ("pinterest", dict(
        label="Pinterest Tag", category="Marketing",
        hosts=("s.pinimg.com/ct", "ct.pinterest.com"),
        globals=("pintrk",),
        code_ids=(r"pintrk\(\s*['\"]load['\"]\s*,\s*['\"](\d{6,16})",
                  r"ct\.pinterest\.com/v3/\?[^\"'\s]*tid=(\d{6,16})"),
        id_params=("tagId", "tag_id"),
        user_data=(r"pintrk\(\s*['\"]load['\"]\s*,\s*['\"]\d{6,16}['\"]\s*,\s*\{",),
        calls=(r"\bpintrk\(",),
        events=(r"pintrk\(\s*['\"]track['\"]\s*,\s*['\"]([^'\"]{2,40})['\"]",),
    )),
    ("x", dict(
        label="X (Twitter) Pixel", category="Marketing",
        hosts=("static.ads-twitter.com", "analytics.twitter.com", "t.co/i/adsct", "ads-twitter.com"),
        globals=("twq",),
        code_ids=(r"twq\(\s*['\"](?:config|init)['\"]\s*,\s*['\"]([a-z0-9]{4,12})['\"]",),
        id_params=("twitter_pixel_id", "pixelId", "pixel_id"),
        user_data=(),
        calls=(r"\btwq\(",),
        events=(r"twq\(\s*['\"]event['\"]\s*,\s*['\"]([^'\"]{2,40})['\"]",),
    )),
    ("microsoft", dict(
        label="Microsoft Advertising UET (Bing)", category="Marketing",
        hosts=("bat.bing.com", "bat.bing.net", "c.bing.com"),
        globals=("uetq", "UET"),
        code_ids=(r"\bti\s*:\s*['\"]?(\d{5,12})", r"bat\.bing\.com/action/0\?ti=(\d{5,12})"),
        id_params=("tagId", "uetTagId"),
        user_data=(r"['\"]pid['\"]\s*:\s*\{\s*['\"](?:em|ph)['\"]",),
        calls=(r"\buetq\b",),
        events=(r"uetq\.push\(\s*['\"]event['\"]\s*,\s*['\"]([^'\"]{1,40})['\"]",),
    )),
    ("snap", dict(
        label="Snap Pixel", category="Marketing",
        hosts=("sc-static.net/scevent", "tr.snapchat.com"),
        globals=("snaptr",),
        code_ids=(r"snaptr\(\s*['\"]init['\"]\s*,\s*['\"]([0-9a-f-]{36})['\"]",),
        id_params=("pixelId", "pixel_id"),
        user_data=(r"snaptr\(\s*['\"]init['\"]\s*,\s*['\"][0-9a-f-]{36}['\"]\s*,\s*\{",),
        calls=(r"\bsnaptr\(",),
        events=(r"snaptr\(\s*['\"]track['\"]\s*,\s*['\"]([^'\"]{2,40})['\"]",),
    )),
    ("reddit", dict(
        label="Reddit Pixel", category="Marketing",
        hosts=("redditstatic.com/ads", "alb.reddit.com", "pixel-config.reddit.com"),
        globals=("rdt",),
        code_ids=(r"rdt\(\s*['\"]init['\"]\s*,\s*['\"]([a-z0-9_]{4,30})['\"]",),
        id_params=("pixelId", "advertiserId", "pixel_id"),
        user_data=(r"rdt\(\s*['\"]init['\"]\s*,\s*['\"][a-z0-9_]{4,30}['\"]\s*,\s*\{",),
        calls=(r"\brdt\(",),
        events=(r"rdt\(\s*['\"]track['\"]\s*,\s*['\"]([^'\"]{2,40})['\"]",),
    )),
    ("criteo", dict(
        label="Criteo OneTag", category="Marketing",
        hosts=("static.criteo.net", "dynamic.criteo.com", "sslwidget.criteo.com", "gum.criteo.com"),
        globals=("criteo_q",),
        code_ids=(r"setAccount['\"]\s*,\s*account\s*:\s*['\"]?(\d{3,8})", r"ld\.js\?a=(\d{3,8})"),
        id_params=("accountId", "partnerId", "partner_id"),
        user_data=(r"setEmail|setHashedEmail|['\"]emails?['\"]",),
        calls=(r"\bcriteo_q\b",),
        events=(r"event\s*:\s*['\"](view\w+|track\w+|addToCart)['\"]",),
    )),
    ("taboola", dict(
        label="Taboola Pixel", category="Marketing",
        hosts=("cdn.taboola.com", "trc.taboola.com"),
        globals=("_tfa",),
        code_ids=(r"_tfa\.push\(\{[^}]*\bid\s*:\s*['\"]?(\d{4,9})", r"unip/(\d{4,9})/tfa\.js"),
        id_params=("pixelId", "accountId"),
        user_data=(),
        calls=(r"\b_tfa\.push\(",),
        events=(r"_tfa\.push\(\{[^}]*\bname\s*:\s*['\"]([^'\"]{2,40})['\"]",),
    )),
    ("outbrain", dict(
        label="Outbrain Pixel", category="Marketing",
        hosts=("amplify.outbrain.com", "tr.outbrain.com"),
        globals=("obApi",),
        code_ids=(r"OB_ADV_ID\s*=\s*['\"]([0-9a-f]{20,40})['\"]",),
        id_params=("marketerId", "marketer_id"),
        user_data=(),
        calls=(r"\bobApi\(",),
        events=(r"obApi\(\s*['\"]track['\"]\s*,\s*['\"]([^'\"]{2,40})['\"]",),
    )),
    ("google_ads", dict(
        label="Google Ads (conversioni/remarketing)", category="Marketing",
        hosts=("googleadservices.com/pagead", "googleads.g.doubleclick.net", "google.com/pagead",
               "google.com/ccm"),
        globals=(),
        code_ids=(r"\b(AW-\d{8,12})\b",),
        id_params=("conversionId",),
        user_data=(),
        calls=(r"gtag\(\s*['\"](?:config|event)['\"]\s*,\s*['\"](?:AW-|conversion)",),
        events=(r"['\"]send_to['\"]\s*:\s*['\"](AW-[^'\"]{4,40})['\"]",),
    )),
    ("floodlight", dict(
        label="Google Floodlight (CM360/DV360)", category="Marketing",
        hosts=("fls.doubleclick.net", "ad.doubleclick.net/activity"),
        globals=(),
        code_ids=(r"\b(DC-\d{6,12})\b",),
        id_params=("advertiserId",),
        user_data=(),
        calls=(r"\bDC-\d{6,12}\b",),
        events=(r"['\"]send_to['\"]\s*:\s*['\"](DC-[^'\"]{4,40})['\"]",),
    )),
    ("yandex", dict(
        label="Yandex Metrica", category="Statistica / Marketing",
        hosts=("mc.yandex.ru", "mc.yandex.com"),
        globals=("ym",),
        code_ids=(r"\bym\(\s*(\d{5,10})\s*,\s*['\"]init", r"mc\.yandex\.ru/watch/(\d{5,10})"),
        id_params=("counterId",),
        user_data=(),
        calls=(r"\bym\(\s*\d",),
        events=(r"ym\(\s*\d+\s*,\s*['\"]reachGoal['\"]\s*,\s*['\"]([^'\"]{1,40})['\"]",),
    )),
    ("quora", dict(
        label="Quora Pixel", category="Marketing",
        hosts=("a.quora.com", "q.quora.com"),
        globals=("qp",),
        code_ids=(r"qp\(\s*['\"]init['\"]\s*,\s*['\"]([0-9a-f]{20,40})['\"]",),
        id_params=("pixel_id", "pixelId"),
        user_data=(),
        calls=(r"\bqp\(",),
        events=(r"qp\(\s*['\"]track['\"]\s*,\s*['\"]([^'\"]{2,40})['\"]",),
    )),
    ("adroll", dict(
        label="AdRoll", category="Marketing",
        hosts=("s.adroll.com", "d.adroll.com"),
        globals=("adroll_adv_id", "__adroll"),
        code_ids=(r"adroll_adv_id\s*=\s*['\"]([A-Z0-9]{10,30})['\"]",),
        id_params=("advertiserId",),
        user_data=(),
        calls=(r"adroll_adv_id",),
        events=(),
    )),
    ("amazon", dict(
        label="Amazon Ads", category="Marketing",
        hosts=("amazon-adsystem.com",),
        globals=("amzn",),
        code_ids=(),
        id_params=("tagId",),
        user_data=(),
        calls=(r"amazon-adsystem\.com",),
        events=(),
    )),
    ("adform", dict(
        label="Adform", category="Marketing",
        hosts=("track.adform.net", "adform.net/serving"),
        globals=("_adftrack",),
        code_ids=(r"\bpm\s*:\s*(\d{5,9})",),
        id_params=("trackingPointId",),
        user_data=(),
        calls=(r"_adftrack",),
        events=(),
    )),
    ("awin", dict(
        label="Awin (affiliazione)", category="Marketing (affiliazione)",
        hosts=("dwin1.com", "awin1.com"),
        globals=("AWIN",),
        code_ids=(r"dwin1\.com/(\d{3,8})\.js",),
        id_params=("merchantId", "advertiserId"),
        user_data=(),
        calls=(r"\bAWIN\b",),
        events=(),
    )),
    ("thetradedesk", dict(
        label="The Trade Desk", category="Marketing",
        hosts=("adsrvr.org",),
        globals=("ttd_dom_ready", "TTDUniversalPixelApi"),
        code_ids=(r"adv=([a-z0-9]{5,10})",),
        id_params=("advertiserId",),
        user_data=(),
        calls=(r"TTDUniversalPixelApi|adsrvr\.org",),
        events=(),
    )),
    ("teads", dict(
        label="Teads", category="Marketing",
        hosts=("teads.tv",),
        globals=("teads_e", "teads_buyer_pixel_id"),
        code_ids=(r"teads_buyer_pixel_id\s*=\s*['\"]?(\d{3,10})",),
        id_params=("pixelId",),
        user_data=(),
        calls=(r"teads_buyer_pixel_id|teads_e\b",),
        events=(),
    )),
    ("rtbhouse", dict(
        label="RTB House", category="Marketing",
        hosts=("creativecdn.com",),
        globals=(),
        code_ids=(r"creativecdn\.com/tags(?:/v2)?\?[^'\"]*?id=([A-Za-z0-9_]{6,40})",),
        id_params=(),
        user_data=(),
        calls=(r"creativecdn\.com",),
        events=(),
    )),
    ("tradedoubler", dict(
        label="Tradedoubler (affiliazione)", category="Marketing (affiliazione)",
        hosts=("tradedoubler.com",),
        globals=(),
        code_ids=(r"organization=(\d{3,10})",),
        id_params=("organizationId",),
        user_data=(),
        calls=(r"tradedoubler\.com",),
        events=(),
    )),
    ("hotjar", dict(
        label="Hotjar", category="Statistica (registrazione sessioni)",
        hosts=("static.hotjar.com", "script.hotjar.com"),
        globals=("hj",),
        code_ids=(r"hjid\s*:\s*(\d{4,10})",),
        id_params=("hotjar_site_id",),
        user_data=(),
        calls=(r"\bhj\(|_hjSettings",),
        events=(),
    )),
    ("clarity", dict(
        label="Microsoft Clarity", category="Statistica (registrazione sessioni)",
        hosts=("clarity.ms",),
        globals=("clarity",),
        code_ids=(r"clarity\.ms/tag/([a-z0-9]{6,12})",),
        id_params=("projectId",),
        user_data=(),
        calls=(r"\bclarity\(",),
        events=(),
    )),
    ("klaviyo", dict(
        label="Klaviyo (tracciamento sul sito)", category="Marketing (piattaforma email)",
        hosts=("static.klaviyo.com", "static-tracking.klaviyo.com", "a.klaviyo.com", "fast.a.klaviyo.com"),
        globals=("klaviyo", "_learnq"),
        code_ids=(r"klaviyo\.js\?company_id=([A-Za-z0-9]{6})",),
        id_params=("company_id", "publicApiKey", "public_api_key"),
        user_data=(r"_learnq\.push\(\s*\[\s*['\"]identify['\"]|klaviyo\.identify\(",),
        calls=(r"klaviyo\.(?:push|identify|track)\(|_learnq\.push\(",),
        events=(r"(?:_learnq\.push\(\s*\[\s*['\"]track['\"]|klaviyo\.track\()\s*,?\s*['\"]([^'\"]{2,40})['\"]",),
    )),
    ("hubspot", dict(
        label="HubSpot (tracciamento sul sito)", category="Marketing (piattaforma email)",
        hosts=("js.hs-scripts.com", "js.hs-analytics.net", "track.hubspot.com"),
        globals=("_hsq",),
        code_ids=(r"js\.hs-scripts\.com/(\d+)\.js",),
        id_params=("portalId", "hubId", "hub_id"),
        user_data=(r"_hsq\.push\(\s*\[\s*['\"]identify['\"]",),
        calls=(r"_hsq\.push\(",),
        events=(),
    )),
    ("mailchimp", dict(
        label="Mailchimp (sito collegato)", category="Marketing (piattaforma email)",
        hosts=("chimpstatic.com/mcjs-connected",),
        globals=(),
        code_ids=(r"mcjs-connected/js/users/([0-9a-f]+)/",),
        id_params=(),
        user_data=(),
        calls=(r"chimpstatic\.com/mcjs-connected",),
        events=(),
    )),
    ("activecampaign", dict(
        label="ActiveCampaign (tracciamento sul sito)", category="Marketing (piattaforma email)",
        hosts=("trackcmp.net", "diffuser-cdn.app-us1.com", "prism.app-us1.com"),
        globals=("vgo",),
        code_ids=(r"vgo\(\s*['\"]setAccount['\"]\s*,\s*['\"](\d+)['\"]",),
        id_params=("actid", "accountId"),
        user_data=(r"vgo\(\s*['\"]setEmail['\"]",),
        calls=(r"\bvgo\(",),
        events=(),
    )),
    ("brevo", dict(
        label="Brevo (tracciamento sul sito)", category="Marketing (piattaforma email)",
        hosts=("sibautomation.com", "cdn.brevo.com"),
        globals=("sendinblue", "Brevo"),
        code_ids=(r"sibautomation\.com/sa\.js\?key=([A-Za-z0-9]{8,40})",),
        id_params=("client_key", "clientKey"),
        user_data=(r"sendinblue\.identify\(|Brevo\.push\(\s*\[\s*['\"]identify['\"]",),
        calls=(r"sendinblue\.(?:track|identify|page)\(|Brevo\.push\(",),
        events=(r"sendinblue\.track\(\s*['\"]([^'\"]{2,40})['\"]",),
    )),
    ("omnisend", dict(
        label="Omnisend (tracciamento sul sito)", category="Marketing (piattaforma email)",
        hosts=("omnisnippet1.com", "omnisrv.com"),
        globals=("omnisend",),
        code_ids=(r"omnisend_?brand_?id['\"]?\s*[:=]\s*['\"]([0-9a-f]{20,30})['\"]",),
        id_params=("brandId", "brand_id"),
        user_data=(),
        calls=(r"omnisend\.push\(",),
        events=(),
    )),
    ("stape", dict(
        label="Tagging lato server (Stape / server GTM)", category="Tagging lato server",
        hosts=("stapecdn.com", "stape.io"),
        globals=(),
        code_ids=(),
        id_params=(),
        user_data=(),
        calls=(r"stapecdn\.com",),
        events=(),
    )),
])

# Built-in GTM tag types: function -> (label, vendor key or None, is a pixel/ad tag)
BUILTIN_TAGS = {
    "__googtag": ("Google tag (GA4/Ads)", None, False),
    "__gaawc": ("GA4 – configurazione", None, False),
    "__gaawe": ("GA4 – evento", None, False),
    "__ua": ("Universal Analytics (dismesso)", None, False),
    "__awct": ("Google Ads – monitoraggio conversioni", "google_ads", True),
    "__sp": ("Google Ads – remarketing", "google_ads", True),
    "__awud": ("Google Ads – evento con dati forniti dall'utente", "google_ads", True),
    "__awcc": ("Google Ads – conversioni da chiamata", "google_ads", True),
    "__gclidw": ("Google – Conversion Linker (cookie _gcl_*)", "google_ads", True),
    "__flc": ("Floodlight – contatore", "floodlight", True),
    "__fls": ("Floodlight – vendite", "floodlight", True),
    "__baut": ("Microsoft Advertising UET", "microsoft", True),
    "__bzi": ("LinkedIn Insight", "linkedin", True),
    "__twitter_website_tag": ("X (Twitter) – tag sito", "x", True),
    "__pntr": ("Pinterest Tag", "pinterest", True),
    "__crto": ("Criteo OneTag", "criteo", True),
    "__qpx": ("Quora Pixel", "quora", True),
    "__asp": ("AdRoll Smart Pixel", "adroll", True),
    "__awc": ("Awin – conversione", "awin", True),
    "__awj": ("Awin – journey tag", "awin", True),
    "__qcm": ("Quantcast Measure", None, True),
    "__hjtc": ("Hotjar", "hotjar", False),
    "__cegg": ("Crazy Egg", None, False),
    "__opt": ("Google Optimize (dismesso)", None, False),
    "__img": ("Immagine personalizzata (pixel)", None, True),
    "__html": ("HTML personalizzato", None, False),
    "__scjs": ("Script esterno", None, False),
}
# Listener/structural "tags" that never send data by themselves.
STRUCTURAL = {"__cl", "__lcl", "__evl", "__fsl", "__hl", "__tl", "__sdl", "__ytl", "__tg",
              "__jel", "__ehl", "__fil"}

EVENT_LABELS = {
    "gtm.js": "visualizzazione di pagina (All Pages)",
    "gtm.dom": "DOM pronto",
    "gtm.load": "finestra caricata",
    "gtm.init": "inizializzazione",
    "gtm.init_consent": "inizializzazione del consenso",
    "gtm.click": "clic",
    "gtm.linkClick": "clic su link",
    "gtm.formSubmit": "invio modulo",
    "gtm.historyChange": "cambio cronologia (SPA)",
    "gtm.historyChange-v2": "cambio cronologia (SPA)",
    "gtm.timer": "timer",
    "gtm.scrollDepth": "profondità di scorrimento",
    "gtm.elementVisibility": "visibilità elemento",
    "gtm.video": "video",
    "gtm.triggerGroup": "gruppo di attivatori",
}
PAGE_EVENTS = {"gtm.js", "gtm.dom", "gtm.load", "gtm.init", "gtm.init_consent", "gtm.historyChange",
               "gtm.historyChange-v2"}

# A variable (cookie, dataLayer key, JS variable) that holds a consent decision.
CONSENT_VAR = re.compile(
    r"consent|cookie.?law|cmplz|complianz|cookiebot|onetrust|optanon|ActiveGroups|iubenda|_iub|cookieyes|"
    r"\bcky|usercentrics|didomi|axeptio|\btcf|euconsent|gdpr|ad_storage|analytics_storage|ad_user_data|"
    r"ad_personalization|_tracking_consent", re.I)
# A custom event whose NAME says a choice was made in favour of tracking (cookie_consent_marketing,
# CookiebotOnAccept, iubenda_consent_given…). CMP events that fire on every load whatever the
# choice (OneTrustGroupsUpdated, OneTrustLoaded, consent_update) do not qualify on their own.
CONSENT_EVENT = re.compile(
    r"^(?=.*(?:consent|cookie|cmplz|complianz|iubenda|onetrust|cookiebot|\bcky|cookieyes|usercentrics|didomi|axeptio))"
    r"(?=.*(?:accept|grant|given|allow|marketing|statistic|analytic|advertis|targeting|preferen|profil|C000[2-5]))",
    re.I)
USER_DATA_HINT = re.compile(
    r"e.?mail|phone|telefon|first.?name|last.?name|\bnome\b|cognome|address|indirizzo|"
    r"\bzip\b|postal|\bcap\b|birth|nascita|gender|\bem\b|\bph\b|\bfn\b|\bln\b|external_id|user_?data|"
    r"advanced.?matching|hashed|sha256|md5", re.I)
SERVER_SIDE_KEYS = re.compile(
    r"server_container_url|transport_url|serverContainerUrl|transportUrl|gtm_server_domain|"
    r"server_domain|sgtm|stapecdn|data_tag", re.I)
ID_PARAM = re.compile(r"(pixel|tag|partner|account|advertiser|conversion|counter|marketer|merchant|"
                      r"project|site|measurement)_?(id|ids|code)$|^(hotjar_site_id|pcode|id)$", re.I)


# ---------------------------------------------------------------------------
# Fetch & parse
# ---------------------------------------------------------------------------
def container_url(ident: str) -> str:
    if ident.startswith(("http://", "https://")):
        return ident
    if ident.startswith("GTM-"):
        return f"https://www.googletagmanager.com/gtm.js?id={ident}"
    if re.match(r"^(G|AW|DC|GT)-", ident):
        return f"https://www.googletagmanager.com/gtag/js?id={ident}"
    raise ValueError(f"ID non riconosciuto: {ident} (atteso GTM-/G-/AW-/DC-/GT- o un URL)")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Referer": "https://www.googletagmanager.com/", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310 - fixed https hosts or user URL
        return resp.read().decode("utf-8", errors="replace")


def parse_container(text: str):
    """Return the container's `data` object, or None if it cannot be parsed."""
    i = text.find("var data = ")
    if i < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(text, i + len("var data = "))
    except ValueError:
        return None
    return obj if isinstance(obj, dict) and "resource" in obj else None


def unescape_raw(text: str) -> str:
    """Best-effort unescaping so the regexes also work on an unparseable container."""
    text = text.replace('\\"', '"').replace("\\'", "'").replace("\\/", "/")
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)


# ---------------------------------------------------------------------------
# Rendering of GTM values (["macro", 3], ["template", ...], ["escape", ...], ...)
# ---------------------------------------------------------------------------
class Container:
    def __init__(self, data: dict):
        res = data.get("resource", {})
        self.macros = res.get("macros", [])
        self.tags = res.get("tags", [])
        self.predicates = res.get("predicates", [])
        self.rules = res.get("rules", [])
        self.permissions = data.get("permissions", {}) or {}
        self.data = data

    # -- values ------------------------------------------------------------
    def macro_label(self, idx: int) -> str:
        if not isinstance(idx, int) or idx >= len(self.macros):
            return "{{variabile}}"
        m = self.macros[idx]
        fn = m.get("function", "")
        name = m.get("vtp_name")
        if fn == "__e":
            return "evento"
        if fn == "__v":
            return f"dataLayer.{name}"
        if fn == "__k":
            return f"cookie {name}"
        if fn == "__j":
            return f"variabile JS {name}"
        if fn == "__c":
            return f'"{m.get("vtp_value", "")}"'
        if fn == "__u":
            comp = m.get("vtp_component", "URL")
            return f"URL ({comp.lower()})" if isinstance(comp, str) else "URL"
        if fn == "__f":
            return "referrer"
        if fn == "__awec":
            return "dati forniti dall'utente (enhanced conversions)"
        if fn == "__jsm":
            code = self.render(m.get("vtp_javascript", ""))
            hint = " — legge il consenso" if CONSENT_VAR.search(code) else ""
            return f"JS personalizzato{hint}"
        if fn in ("__smm", "__remm"):
            return f"tabella di ricerca su {self.render(m.get('vtp_input', ''))}"
        if fn.startswith("__cvt_"):
            return f"variabile da modello {fn}"
        return fn.lstrip("_") or "variabile"

    def literal(self, value):
        """The literal behind a value when it can be known statically, else None."""
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            return str(value)
        if isinstance(value, list) and len(value) == 2 and value[0] == "macro":
            idx = value[1]
            if isinstance(idx, int) and idx < len(self.macros):
                m = self.macros[idx]
                if m.get("function") == "__c":
                    return self.literal(m.get("vtp_value"))
                if m.get("function") in ("__smm", "__remm"):
                    outs = self._lookup_outputs(m)
                    if len(outs) > 6:
                        outs = outs[:6] + [f"… (+{len(outs) - 6} valori)"]
                    return " | ".join(outs) if outs else None
        return None

    def _lookup_outputs(self, m):
        outs = []
        for row in (m.get("vtp_map") or [])[1:]:
            if isinstance(row, list) and "value" in row:
                lit = self.literal(row[row.index("value") + 1])
                if lit and lit not in outs:
                    outs.append(lit)
        default = m.get("vtp_defaultValue")
        if default is not None and m.get("vtp_setDefaultValue"):
            lit = self.literal(default)
            if lit and lit not in outs:
                outs.append(lit)
        return outs

    def render(self, value, depth: int = 0) -> str:
        if depth > 12:
            return "…"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (str, int, float)):
            return str(value)
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False)
        if not isinstance(value, list) or not value:
            return ""
        head = value[0]
        if head == "macro":
            return "{{" + self.macro_label(value[1]) + "}}"
        if head == "template":
            return "".join(self.render(v, depth + 1) for v in value[1:])
        if head == "escape":
            return self.render(value[1], depth + 1)
        if head == "list":
            return "[" + ", ".join(self.render(v, depth + 1) for v in value[1:]) + "]"
        if head == "map":
            items = value[1:]
            pairs = [f"{self.render(items[k], depth + 1)}={self.render(items[k + 1], depth + 1)}"
                     for k in range(0, len(items) - 1, 2)]
            return "{" + ", ".join(pairs) + "}"
        if head == "tag":
            return f"tag#{value[1]}"
        return " ".join(self.render(v, depth + 1) for v in value)

    # -- conditions --------------------------------------------------------
    def predicate_text(self, idx: int) -> str:
        if not isinstance(idx, int) or idx >= len(self.predicates):
            return "?"
        p = self.predicates[idx]
        op = {"_eq": "=", "_re": "corrisponde a", "_cn": "contiene", "_sw": "inizia con",
              "_ew": "finisce con", "_css": "selettore CSS", "_lt": "<", "_le": "<=", "_gt": ">",
              "_ge": ">="}.get(p.get("function"), p.get("function", "?"))
        left = self.render(p.get("arg0"))
        right = self.render(p.get("arg1"))
        if left == "{{evento}}" and p.get("function") == "_eq":
            label = EVENT_LABELS.get(right)
            return f'evento "{right}"' + (f" ({label})" if label else "")
        if len(right) > 70:
            right = right[:67] + "…"
        if p.get("function") == "_re":
            right = f"/{right}/"
        return f"{left} {op} {right}".replace("{{", "").replace("}}", "")

    def predicate_is_consent(self, idx: int) -> bool:
        """A condition that reads a consent decision: a consent variable on its left side, or a
        custom event whose name means a positive choice. Never URLs or texts (a page path that
        contains "marketing" is not consent) and never gtm.init_consent, which fires first."""
        if not isinstance(idx, int) or idx >= len(self.predicates):
            return False
        p = self.predicates[idx]
        left = p.get("arg0")
        if not (isinstance(left, list) and len(left) == 2 and left[0] == "macro"
                and isinstance(left[1], int) and left[1] < len(self.macros)):
            return False
        fn = self.macros[left[1]].get("function", "")
        if fn == "__e":
            name = self.render(p.get("arg1"))
            return not name.startswith("gtm.") and bool(CONSENT_EVENT.search(name))
        if fn in ("__k", "__v", "__j", "__jsm", "__smm", "__remm"):
            return bool(CONSENT_VAR.search(self.macro_label(left[1])))
        return False

    def predicate_event(self, idx: int):
        if not isinstance(idx, int) or idx >= len(self.predicates):
            return None
        p = self.predicates[idx]
        if p.get("function") == "_eq" and self.render(p.get("arg0")) == "{{evento}}":
            return self.render(p.get("arg1"))
        return None

    def tag_rules(self, tag_idx: int):
        firing, blocking = [], []
        for rule in self.rules:
            ifs, unless, adds, blocks = [], [], [], []
            for clause in rule:
                if not clause:
                    continue
                kind, args = clause[0], clause[1:]
                {"if": ifs, "unless": unless, "add": adds, "block": blocks}.get(kind, []).extend(args)
            if tag_idx in adds:
                firing.append((ifs, unless))
            if tag_idx in blocks:
                blocking.append((ifs, unless))
        return firing, blocking

    def sequenced_by(self, tag_idx: int):
        """Tags that fire this one as setup/teardown (it then has no rule of its own)."""
        parents = []
        for i, t in enumerate(self.tags):
            for key in ("setup_tags", "teardown_tags"):
                for ref in (t.get(key) or [])[1:]:
                    if isinstance(ref, list) and len(ref) >= 2 and ref[0] == "tag" and ref[1] == tag_idx:
                        parents.append(i)
        return parents

    # -- templates ---------------------------------------------------------
    def template_hosts_globals(self, fn: str):
        perm = self.permissions.get(fn) or {}
        hosts, globs = [], []

        def collect_urls(obj):
            if isinstance(obj, str) and obj.startswith(("http", "//")):
                hosts.append(obj)
            elif isinstance(obj, list):
                for x in obj:
                    collect_urls(x)
            elif isinstance(obj, dict):
                for x in obj.values():
                    collect_urls(x)

        for key in ("inject_script", "send_pixel", "inject_hidden_iframe", "send_beacon"):
            collect_urls(perm.get(key))
        for g in (perm.get("access_globals") or {}).get("keys", []) or []:
            if isinstance(g, dict) and g.get("key"):
                globs.append(g["key"])
        return hosts, globs


def match_vendor(text: str, globs=(), code: bool = False):
    """Vendor keys whose hosts (or, for code, call patterns) appear in `text`, or whose
    globals are among `globs` (keys a GTM template is allowed to touch)."""
    low = text.lower()
    found = []
    for key, v in VENDORS.items():
        hit = any(h in low for h in v["hosts"])
        hit = hit or any(g == vg or g.startswith(vg + ".") for g in globs for vg in v["globals"])
        hit = hit or (code and any(re.search(rx, text) for rx in v["calls"]))
        if hit:
            found.append(key)
    return found


def ids_in_code(text: str, vendor_keys=None):
    out = OrderedDict()
    for key, v in VENDORS.items():
        if vendor_keys is not None and key not in vendor_keys:
            continue
        for rx in v["code_ids"]:
            for m in re.finditer(rx, text):
                out.setdefault(key, [])
                if m.group(1) not in out[key]:
                    out[key].append(m.group(1))
    return out


def events_in_code(text: str, vendor_keys):
    out = []
    for key in vendor_keys:
        for rx in VENDORS[key]["events"]:
            for m in re.finditer(rx, text):
                if m.group(1) not in out:
                    out.append(m.group(1))
    return out


def host_of(url: str) -> str:
    m = re.match(r"^(?:https?:)?//([^/?#:]+)", url.strip())
    return m.group(1).lower() if m else url[:60]


CMP_RX = re.compile(r"cookiebot|onetrust|cookielaw|iubenda|usercentrics|didomi|cookieyes|complianz|"
                    r"axeptio|consentmanager|trustarc|sourcepoint|cookie-script|termly|osano|klaro|"
                    r"cookiefirst|cookiehub|quantcast\.mgr|privacy-center", re.I)
CONSENT_TYPES = ("vtp_ad_storage", "vtp_analytics_storage", "vtp_functionality_storage",
                 "vtp_personalization_storage", "vtp_security_storage", "vtp_ad_user_data",
                 "vtp_ad_personalization")


def is_cmp_tag(c: Container, idx: int) -> bool:
    t = c.tags[idx]
    fn = t.get("function", "")
    if not fn.startswith("__cvt_"):
        return False
    hosts, globs = c.template_hosts_globals(fn)
    if CMP_RX.search(" ".join(hosts) + " " + " ".join(globs)):
        return True
    return c.render(t.get("vtp_command", "")) in ("default", "update") and any(k in t for k in CONSENT_TYPES)


def describe_list_param(c: Container, value) -> str:
    """Names inside a GTM list-of-maps parameter (advanced matching keys, user data…)."""
    names = []
    for item in value[1:]:
        if isinstance(item, list) and item and item[0] == "map":
            kv = item[1:]
            pairs = {str(kv[i]): kv[i + 1] for i in range(0, len(kv) - 1, 2)}
            name = pairs.get("name") or pairs.get("key") or pairs.get("parameter")
            if isinstance(name, str):
                names.append(name)
            elif "email" in pairs:
                hm = pairs.get("hash_method")
                names.append("email" + (f" ({hm})" if isinstance(hm, str) else ""))
    return ", ".join(dict.fromkeys(names)) or c.render(value)[:80]


def consent_option_text(c: Container, name: str, value, vendors) -> tuple:
    """(text, gates?) for a consent-related template option, read per vendor."""
    rendered = c.render(value)
    is_var = isinstance(value, list) and value and value[0] == "macro"
    if is_var:
        return f"{name} = {rendered} (letto da variabile: probabile collegamento alla CMP)", True
    if "meta" in vendors and name == "consent":
        if value is True:
            return "consent = true → il modello invia sempre fbq('consent','grant'): NON è un filtro", False
        if value is False:
            return "consent = false → fbq('consent','revoke'): libreria caricata ma eventi trattenuti", True
    if name in ("c_consentInheritGtm", "c_consentUpdates") and value is True:
        return (f"{name} = true → UET segue lo stato di Consent Mode di GTM "
                "(senza consenso niente cookie, ma le chiamate possono partire)"), False
    if name in ("add_consent_state",) and value is True:
        return "add_consent_state = true → inoltra lo stato del consenso al server (informativo, non un filtro)", False
    return f"{name} = {rendered}", False


def analyse_tag(c: Container, idx: int) -> dict | None:
    t = c.tags[idx]
    fn = t.get("function", "")
    if fn in STRUCTURAL:
        return None
    info = {"index": idx, "tag_id": t.get("tag_id"), "function": fn, "vendors": [], "ids": {},
            "events": [], "user_data": [], "consent_gtm": [], "consent_options": [],
            "fires_on": [], "blocked_by": [], "sequenced_by": [], "paused": False,
            "consent_linked": False, "page_level": False, "server_side": [], "label": "",
            "script_hosts": [], "pixel_hosts": [], "is_marketing": False, "ungated_rules": []}

    if fn == "__paused":
        info["paused"] = True
        fn_orig = "__" + str(t.get("vtp_originalTagType", "?"))
        info["label"] = f"tag in pausa (tipo {fn_orig})"
        builtin = BUILTIN_TAGS.get(fn_orig)
        if builtin and builtin[1]:
            info["vendors"].append(builtin[1])
        if fn_orig.startswith("__cvt_"):
            hosts, globs = c.template_hosts_globals(fn_orig)
            info["vendors"] += match_vendor(" ".join(hosts), globs)
        info["is_marketing"] = bool(info["vendors"]) or bool(builtin and builtin[2])
        return info

    params = {k: v for k, v in t.items() if k.startswith("vtp_")}
    rendered = {k: c.render(v) for k, v in params.items()}
    builtin = BUILTIN_TAGS.get(fn)
    if builtin:
        info["label"] = builtin[0]
        if builtin[1]:
            info["vendors"].append(builtin[1])

    if fn == "__html":
        html = c.render(t.get("vtp_html", ""))
        vk = match_vendor(html, code=True)
        info["vendors"] += [k for k in vk if k not in info["vendors"]]
        for key, ids in ids_in_code(html, vendor_keys=info["vendors"]).items():
            for i in ids:
                if i not in info["ids"].setdefault(key, []):
                    info["ids"][key].append(i)
        info["events"] += events_in_code(html, info["vendors"])
        for key in info["vendors"]:
            for rx in VENDORS[key]["user_data"]:
                if re.search(rx, html):
                    info["user_data"].append(f"{VENDORS[key]['label']}: dati utente passati nel codice")
        scripts = re.findall(r"<script[^>]+src=['\"]([^'\"]+)['\"]", html, re.I)
        scripts += re.findall(r"createElement\(\s*['\"]script['\"]\s*\)[\s\S]{0,200}?\.src\s*=\s*['\"]((?:https?:)?//[^'\"]+)['\"]", html)
        pix = re.findall(r"<img[^>]+src=['\"]([^'\"]+)['\"]", html, re.I)
        pix += re.findall(r"new Image\([^)]*\)[\s\S]{0,120}?\.src\s*=\s*['\"]((?:https?:)?//[^'\"]+)['\"]", html)
        pix += re.findall(r"sendBeacon\(\s*['\"]((?:https?:)?//[^'\"]+)['\"]", html)
        scripts += [u for u in pix if re.search(r"\.js(?:[?#]|$)", u)]
        pix = [u for u in pix if not re.search(r"\.js(?:[?#]|$)", u)]
        for src in scripts:
            info["script_hosts"].append(host_of(src))
        for src in pix:
            vkp = match_vendor(src)
            info["vendors"] += [k for k in vkp if k not in info["vendors"]]
            if not vkp:
                info["pixel_hosts"].append(host_of(src))
        info["script_hosts"] = list(dict.fromkeys(info["script_hosts"]))
        info["pixel_hosts"] = list(dict.fromkeys(info["pixel_hosts"]))
        if not info["vendors"] and info["script_hosts"]:
            info["label"] = "HTML personalizzato (script: " + ", ".join(info["script_hosts"][:4]) + ")"
    elif fn == "__img":
        url = c.render(t.get("vtp_url", ""))
        info["label"] = f"Immagine personalizzata (pixel) → {url[:90]}"
        vk = match_vendor(url)
        info["vendors"] += [k for k in vk if k not in info["vendors"]]
        if not vk:
            info["pixel_hosts"].append(host_of(url))
    elif fn.startswith("__cvt_"):
        hosts, globs = c.template_hosts_globals(fn)
        vk = match_vendor(" ".join(hosts), globs) or match_vendor(" ".join(rendered.values()))
        info["vendors"] += [k for k in vk if k not in info["vendors"]]
        shown = sorted(set(host_of(h) for h in hosts))
        info["label"] = "modello della galleria " + fn + (f" (script: {', '.join(shown)[:120]})" if shown else "")
    elif fn == "__scjs":
        url = rendered.get("vtp_url", "")
        info["vendors"] += match_vendor(url)
        info["label"] = f"Script esterno → {url[:90]}"
    elif not builtin:
        info["label"] = f"tipo {fn}"

    # IDs from parameters (pixelId, tagId, conversionId, …)
    for k, v in params.items():
        if ID_PARAM.search(k[4:]):
            lit = c.literal(v)
            val = lit if lit is not None else c.render(v)
            if not val or val in ("false", "true"):
                continue
            vkey = info["vendors"][0] if info["vendors"] else "altro"
            if val not in info["ids"].setdefault(vkey, []):
                info["ids"][vkey].append(val)

    # Event names configured on the tag
    for k in ("vtp_eventName", "vtp_standardEventName", "vtp_event_name_standard", "vtp_customEventName",
              "vtp_eventType", "vtp_type", "vtp_customEventAction", "vtp_activityTag", "vtp_labels"):
        val = rendered.get(k)
        if val and val not in ("standard", "custom", "false", "CUSTOM") and val not in info["events"]:
            info["events"].append(val)
    if fn == "__awct" and rendered.get("vtp_conversionLabel"):
        info["events"].append(f"conversione {rendered['vtp_conversionLabel']}")

    # User data sent with the hit (advanced matching, enhanced conversions, e-mail…)
    for k, v in params.items():
        name = k[4:]
        if not USER_DATA_HINT.search(name):
            continue
        val = rendered[k]
        if val in ("", "false", "[]", "{}", "none", "NONE"):
            continue
        if v is True:
            info["user_data"].append(f"{name} attivo")
        elif isinstance(v, list) and v and v[0] == "list":
            info["user_data"].append(f"{name}: {describe_list_param(c, v)}")
        elif not isinstance(v, bool):
            info["user_data"].append(f"{name} = {val[:80]}")
    if any("dati forniti dall'utente" in val for val in rendered.values()):
        info["user_data"].append("variabile «dati forniti dall'utente» (enhanced conversions)")
    for k in ("vtp_userProperties", "vtp_user_properties"):
        if k in params:
            names = re.findall(r"name=([A-Za-z0-9_]+)", rendered[k])
            sens = [n for n in names if re.search(r"mail|phone|md5|sha|hash", n, re.I)]
            if sens:
                info["user_data"].append(f"proprietà utente: {', '.join(sens)}")
    info["user_data"] = list(dict.fromkeys(info["user_data"]))

    # Consent: GTM "additional consent checks" + template/vendor consent options
    gates = False
    consent = t.get("consent")
    if isinstance(consent, list) and consent and consent[0] == "list":
        info["consent_gtm"] = [str(x) for x in consent[1:]]
        gates = bool(info["consent_gtm"])
    for k, v in params.items():
        if "consent" in k.lower():
            text, g = consent_option_text(c, k[4:], v, info["vendors"])
            info["consent_options"].append(text)
            gates = gates or g

    # Server-side tagging hints
    for k, val in rendered.items():
        if (SERVER_SIDE_KEYS.search(k) or SERVER_SIDE_KEYS.search(val or "")) and val not in ("false", ""):
            lit = c.literal(params[k])
            info["server_side"].append(f"{k[4:]} = {(lit or val)[:80]}")

    # Firing / blocking conditions. Firing rules are alternatives (any one fires the tag), so the
    # tag is tied to consent only if EVERY firing rule reads a consent decision, or a blocking
    # rule / GTM consent check / template option does.
    firing, blocking = c.tag_rules(idx)
    ungated = []
    for ifs, unless in firing:
        parts = [c.predicate_text(p) for p in ifs] + ["NON " + c.predicate_text(p) for p in unless]
        text = " E ".join(parts) or "(sempre)"
        info["fires_on"].append(text)
        if not any(c.predicate_is_consent(p) for p in ifs + unless):
            ungated.append(text)
            if any(c.predicate_event(p) in PAGE_EVENTS for p in ifs):
                info["page_level"] = True
    for ifs, unless in blocking:
        parts = [c.predicate_text(p) for p in ifs] + ["NON " + c.predicate_text(p) for p in unless]
        info["blocked_by"].append(" E ".join(parts) or "(sempre)")
        gates = gates or any(c.predicate_is_consent(p) for p in ifs + unless)
    gates = gates or (bool(firing) and not ungated)
    info["ungated_rules"] = ungated if not gates else []
    info["sequenced_by"] = c.sequenced_by(idx)
    info["consent_linked"] = gates
    info["vendors"] = list(dict.fromkeys(info["vendors"]))
    if not info["label"]:
        info["label"] = fn
    info["is_marketing"] = bool(
        (builtin and builtin[2]) or info["pixel_hosts"]
        or any(VENDORS[v]["category"].startswith("Marketing") for v in info["vendors"]))
    return info


def google_ids(raw: str) -> dict:
    found = OrderedDict()
    for label, rx in (("GA4", r"\bG-[A-Z0-9]{6,12}\b"), ("Google Ads", r"\bAW-\d{8,12}\b"),
                      ("Floodlight", r"\bDC-\d{6,12}\b"), ("Universal Analytics (dismesso)", r"\bUA-\d{4,10}-\d+\b"),
                      ("Google tag", r"\bGT-[A-Z0-9]{6,12}\b"), ("Optimize (dismesso)", r"\bOPT-[A-Z0-9]{6,10}\b")):
        ids = sorted(set(re.findall(rx, raw)))
        if ids:
            found[label] = ids
    return found


CONSENT_SIGNALS = ("ad_storage", "analytics_storage", "ad_user_data", "ad_personalization",
                   "ads_data_redaction", "url_passthrough", "wait_for_update", "google_signals",
                   "allow_google_signals", "conversion_linker")


def analyse(raw: str, ident: str, url: str) -> dict:
    report = {"id": ident, "url": url, "bytes": len(raw.encode("utf-8")), "warnings": [], "parsed": False,
              "tags_total": 0, "pixels": [], "other_tags": {}, "other_user_data": [], "google_ids": {},
              "vendors_by_code": {}, "consent_signals": {}, "server_side": [], "cmp_templates": []}
    data = parse_container(raw)
    if data is None and re.search(r"uBlock|noopfn|ublockorigin", raw, re.I):
        report["warnings"].append("risposta = STUB di un ad-blocker, non il container reale: rilancia in rete senza filtri")
        return report
    clean = unescape_raw(raw)
    report["google_ids"] = google_ids(clean)
    present = match_vendor(clean, code=True)
    report["vendors_by_code"] = {VENDORS[k]["label"]: v for k, v in ids_in_code(clean, vendor_keys=present).items()}
    for sig in CONSENT_SIGNALS:
        n = len(re.findall(sig, clean))
        if n:
            report["consent_signals"][sig] = n
    for m in re.findall(r"(?:server_container_url|transport_url)[^h]{0,40}(https?://[^'\"\s,\]]{4,120})", clean):
        if m not in report["server_side"]:
            report["server_side"].append(m)
    if data is None:
        if len(raw) < 10000:
            report["warnings"].append("risposta molto piccola (<10KB): possibile stub o ID inesistente")
        report["warnings"].append("struttura del container non leggibile come dati: analisi solo per testo (ID e domini)")
        return report
    report["parsed"] = True
    c = Container(data)
    report["tags_total"] = len(c.tags)
    if not c.tags:
        report["warnings"].append(
            "container SENZA tag: vuoto, usato solo come loader, o i tag stanno in un altro container/lato server")
    for idx in range(len(c.tags)):
        info = analyse_tag(c, idx)
        if info is None:
            continue
        for s in info["server_side"]:
            if s not in report["server_side"]:
                report["server_side"].append(s)
        if is_cmp_tag(c, idx):
            t = c.tags[idx]
            states = OrderedDict()
            for k in CONSENT_TYPES:
                if k in t:
                    states[k[4:]] = c.literal(t[k]) or c.render(t[k])
            for k in ("vtp_wait_for_update", "vtp_regions", "vtp_ads_data_redaction", "vtp_url_passthrough"):
                if k in t:
                    states[k[4:]] = c.render(t[k])
            report["cmp_templates"].append({"tag_id": info["tag_id"], "label": info["label"],
                                            "command": c.render(t.get("vtp_command", "")),
                                            "states": states})
            continue
        if info["vendors"] or info["is_marketing"]:
            report["pixels"].append(info)
        else:
            report["other_tags"][info["label"]] = report["other_tags"].get(info["label"], 0) + 1
            if info["user_data"]:
                report["other_user_data"].append(f"[tag {info['tag_id']}] {info['label']}: "
                                                 + "; ".join(info["user_data"]))
    return report


# ---------------------------------------------------------------------------
# Text output
# ---------------------------------------------------------------------------
def verdict(p: dict) -> tuple:
    """(code, text). code: paused | gated | google | sequenced | inactive | ungated_page | ungated_event."""
    if p["paused"]:
        return "paused", "in pausa: non scatta"
    if p["consent_linked"]:
        return "gated", ("ogni attivazione è legata a una scelta di consenso nel container: confermare in browser "
                         "(alla prima visita il cookie della CMP può non esistere ancora)")
    google_builtin = p["function"] in ("__awct", "__sp", "__awud", "__flc", "__fls", "__gclidw", "__awcc")
    if google_builtin:
        return "google", ("nessuna condizione di consenso nel container, ma è un tag Google con controllo di "
                          "consenso integrato (Consent Mode): verificare in browser i parametri gcs/gcd")
    if not p["fires_on"] and p["sequenced_by"]:
        return "sequenced", "scatta in sequenza con altri tag: valutare le condizioni del tag principale"
    if not p["fires_on"]:
        return "inactive", "nessuna regola di attivazione propria: non risulta attivo"
    server = " — invia al server del sito: l'eventuale filtro di consenso sta lato server" if "stape" in p["vendors"] else ""
    rule = f" (regola: {p['ungated_rules'][0][:90]})" if p.get("ungated_rules") else ""
    if p["page_level"]:
        return "ungated_page", ("⚠ almeno una regola lo attiva al caricamento della pagina SENZA condizioni di "
                                f"consenso{rule}: verificare in browser (Fase 1) se parte prima del consenso — a meno "
                                "che la CMP blocchi l'intero GTM" + server)
    return "ungated_event", (f"⚠ almeno una regola di attivazione non legge il consenso{rule}: verificare in browser "
                             "se l'evento si verifica prima del consenso" + server)


def group_pixels(pixels):
    groups = OrderedDict()
    for p in pixels:
        key = tuple(p["vendors"]) or ("altro:" + p["label"],)
        groups.setdefault(key, []).append(p)
    return groups


def group_title(key) -> str:
    if key and key[0].startswith("altro:"):
        return "Non classificato — " + key[0][6:]
    return " + ".join(f"{VENDORS[k]['label']} [{VENDORS[k]['category']}]" for k in key)


def group_ids(items):
    ids = OrderedDict()
    for p in items:
        for vals in p["ids"].values():
            for v in vals:
                ids[v] = True
    return list(ids)


def print_summary(r: dict) -> None:
    groups = group_pixels(r["pixels"])
    if not groups:
        return
    print("\n-- Sintesi --")
    for key, items in groups.items():
        codes = [verdict(p)[0] for p in items]
        flags = []
        n_ungated = sum(c.startswith("ungated") for c in codes)
        if n_ungated:
            flags.append(f"⚠ {n_ungated} tag senza vincolo di consenso")
        if any(p["user_data"] for p in items):
            flags.append("dati utente")
        if all(c == "paused" for c in codes):
            flags.append("tutti in pausa")
        ids = group_ids(items)
        print(f"  {group_title(key)}: {len(items)} tag" + (f" · ID {', '.join(ids[:6])}" if ids else "")
              + (f" · {'; '.join(flags)}" if flags else ""))


def print_report(r: dict) -> None:
    print(f"== Container {r['id']} ==")
    print(f"URL:  {r['url']}")
    print(f"Peso: {r['bytes']} byte" + (f" · tag: {r['tags_total']}" if r["parsed"] else ""))
    for w in r["warnings"]:
        print(f"⚠️  {w}")
    print_summary(r)
    if r["google_ids"]:
        print("\n-- ID Google nel container --")
        for label, ids in r["google_ids"].items():
            print(f"{label}: {', '.join(ids)}")
    if r["pixels"]:
        print(f"\n-- Pixel, tracker e tag di terze parti ({len(r['pixels'])}) --")
        for key, items in group_pixels(r["pixels"]).items():
            ids = group_ids(items)
            print(f"\n■ {group_title(key)}" + (f" — ID: {', '.join(ids)}" if ids else ""))
            for p in items:
                head = f"  [tag {p['tag_id']}] {p['label']}"
                if p["events"]:
                    head += f" · evento: {', '.join(p['events'])}"
                tag_ids = [v for vals in p["ids"].values() for v in vals]
                if len(ids) > 1 and tag_ids:
                    head += f" · ID {', '.join(tag_ids)}"
                print(head)
                if p["user_data"]:
                    print(f"      dati utente: {'; '.join(p['user_data'])}")
                if p["consent_gtm"]:
                    print(f"      consenso richiesto in GTM: {', '.join(p['consent_gtm'])}")
                for opt in p["consent_options"]:
                    print(f"      opzione di consenso del tag: {opt}")
                if p["pixel_hosts"]:
                    print(f"      pixel verso host non classificati: {', '.join(p['pixel_hosts'])}")
                for cond in p["fires_on"][:4]:
                    print(f"      scatta se: {cond}")
                if len(p["fires_on"]) > 4:
                    print(f"      … e altre {len(p['fires_on']) - 4} regole")
                for cond in p["blocked_by"][:3]:
                    print(f"      bloccato se: {cond}")
                if p["sequenced_by"]:
                    print(f"      in sequenza con i tag (indice) {', '.join(str(x) for x in p['sequenced_by'])}")
                print(f"      → {verdict(p)[1]}")
    elif r["parsed"]:
        print("\n-- Pixel, tracker e tag di terze parti --\n   (nessuno)")
    if r["vendors_by_code"]:
        print("\n-- ID di pixel trovati nel codice (riepilogo) --")
        for label, ids in r["vendors_by_code"].items():
            print(f"{label}: {', '.join(ids)}")
    if r["cmp_templates"]:
        print("\n-- Tag di gestione del consenso (CMP / Consent Mode) --")
        for t in r["cmp_templates"]:
            print(f"  [tag {t['tag_id']}] {t['label']}" + (f" · comando: {t['command']}" if t["command"] else ""))
            if t.get("states"):
                print("      " + ", ".join(f"{k}={v}" for k, v in t["states"].items()))
            granted = [k for k, v in (t.get("states") or {}).items()
                       if k in ("ad_storage", "analytics_storage", "ad_user_data", "ad_personalization")
                       and str(v).lower() == "granted"]
            if t["command"] == "default" and granted:
                print(f"      ⚠ default «granted» per {', '.join(granted)}: i tag Google partono con cookie "
                      "PRIMA di qualsiasi scelta (verificare se limitato a regioni extra-UE)")
    if r["other_tags"]:
        print("\n-- Altri tag (non pixel) --")
        for label, n in sorted(r["other_tags"].items(), key=lambda kv: -kv[1]):
            print(f"  {n} × {label}")
    if r["other_user_data"]:
        print("\n-- Dati utente inviati da altri tag (es. GA4) --")
        for line in r["other_user_data"]:
            print(f"  {line}")
    print("\n-- Consent Mode v2 / Google Signals --")
    if r["consent_signals"]:
        print("  " + ", ".join(f"{k} ({n})" for k, n in r["consent_signals"].items()))
    else:
        print("  (nessun segnale di Consent Mode: verificare il gating dei tag Google)")
    if r["server_side"]:
        print("\n-- Tagging lato server (i dati passano da un server del sito: flussi NON visibili dal browser) --")
        for s in r["server_side"]:
            print(f"  {s}")
    print("\nNote: le condizioni sono quelle del container; una CMP che blocca l'intero GTM fino al consenso "
          "non si vede qui. Riferimenti a googleadservices/doubleclick in un container con solo G- sono "
          "boilerplate GA4, non tag Ads (vedi cmp-tracker-fingerprints.md).")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ispeziona un container GTM / Google tag lato server.")
    ap.add_argument("ids", nargs="*", help="GTM-XXXX, G-XXXX, AW-XXXX, DC-XXXX o URL completo del loader")
    ap.add_argument("--file", action="append", default=[], help="analizza un container già salvato")
    ap.add_argument("--json", action="store_true", help="output JSON")
    args = ap.parse_args(argv)
    if not args.ids and not args.file:
        ap.print_usage()
        return 1
    reports = []
    for path in args.file:
        with open(path, encoding="utf-8", errors="replace") as fh:
            reports.append(analyse(fh.read(), path, f"file:{path}"))
    for ident in args.ids:
        try:
            url = container_url(ident)
            raw = fetch(url)
        except (ValueError, urllib.error.URLError, OSError) as exc:
            reports.append({"id": ident, "url": "", "error": str(exc)})
            continue
        reports.append(analyse(raw, ident, url))
    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
    else:
        for i, r in enumerate(reports):
            if i:
                print("\n" + "=" * 72 + "\n")
            if r.get("error"):
                print(f"== {r['id']} ==\n⚠️  impossibile ottenere il container: {r['error']}")
                continue
            print_report(r)
    stub = any("STUB" in w for r in reports for w in r.get("warnings", []))
    return 2 if stub else 0


if __name__ == "__main__":
    sys.exit(main())
