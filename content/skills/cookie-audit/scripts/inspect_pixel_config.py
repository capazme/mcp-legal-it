#!/usr/bin/env python3
"""Read the configuration Meta publishes for a Meta Pixel ID (server side).

Usage:
    python3 inspect_pixel_config.py 1234567890123456 [2345678901234567 ...]
    python3 inspect_pixel_config.py --file meta_config.js 1234567890123456
    python3 inspect_pixel_config.py --json 1234567890123456

Every browser that loads the pixel downloads connect.facebook.net/signals/config/<ID>,
so reading it is the same request a visitor makes. It shows what the pixel is SET UP
to do, whatever the ad-blocker of the auditor's browser lets through: Automatic
Advanced Matching and the form fields it reads (email, name, phone, birth date…),
automatic events, page metadata collection, and the parameters Meta itself filters
as unwanted. An ID with no configuration returns no opt-ins (pixel missing or off).

TikTok is deliberately NOT read here: its loader returns the same plugin flags for
every pixel code, an invented one included, so they describe the library, not the
pixel. For TikTok the evidence is the body of the requests (browser-probes.md §6).

Standard library only. Output in Italian (it ends up in an Italian audit report).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140 Safari/537.36")
TIMEOUT = 20

META_URL = "https://connect.facebook.net/signals/config/{id}?v=2.9.239&r=stable"

MATCH_KEYS = {
    "em": "email", "ph": "telefono", "fn": "nome", "ln": "cognome", "ge": "genere",
    "db": "data di nascita", "zp": "CAP", "ct": "città", "st": "provincia/stato",
    "country": "paese", "external_id": "ID cliente del sito",
}
META_PLUGINS = {
    "AutomaticMatching": "Advanced Matching automatico: legge i campi dei moduli e li invia (hash)",
    "AutomaticMatchingForPartnerIntegrations": "Advanced Matching automatico anche via integrazioni partner",
    "InferredEvents": "eventi automatici: clic sui pulsanti e azioni dedotte senza codice",
    "AutomaticParameters": "parametri automatici ricavati dalla pagina",
    "Microdata": "raccolta dei metadati della pagina (JSON-LD, Open Graph, microdata)",
    "FirstPartyCookies": "cookie di prima parte _fbp/_fbc",
    "IWLBootstrapper": "Event Setup Tool (configurazione eventi cliccando sul sito)",
    "OpenBridge": "Conversions API Gateway (invio anche lato server)",
    "ClientHint": "raccolta dei client hints del browser (modello del dispositivo, versione del sistema)",
    "BrowserProperties": "proprietà del browser",
    "LastExternalReferrer": "ultimo referrer esterno",
    "UnwantedData": "filtro Meta dei dati indesiderati",
    "UnwantedParams": "filtro Meta dei parametri indesiderati",
    "ProhibitedSources": "filtro Meta delle fonti vietate",
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310 - fixed vendor hosts
        return resp.read().decode("utf-8", errors="replace")


def vendor_of(pixel_id: str) -> str | None:
    if re.fullmatch(r"\d{15,16}", pixel_id):
        return "meta"
    if re.fullmatch(r"[A-Z0-9]{20}", pixel_id):
        return "tiktok"
    return None


TIKTOK_NOTE = ("pixel TikTok: la configurazione pubblicata non è leggibile in modo affidabile (il loader "
               "restituisce gli stessi flag per ogni codice, anche inventato). Verifica nel browser il corpo "
               "delle richieste a analytics.tiktok.com/api/v2/pixel (browser-probes.md §6)")


def _json_after(text: str, start: int):
    try:
        obj, _ = json.JSONDecoder().raw_decode(text, start)
        return obj
    except ValueError:
        return None


def parse_meta(text: str, pixel_id: str) -> dict:
    pid = re.escape(pixel_id)
    out = {"vendor": "meta", "id": pixel_id, "found": False, "plugins": [], "automatic_matching": [],
           "inferred_events": None, "unwanted_keys": {}, "notes": []}
    plugins = re.findall(r'optIn\("' + pid + r'",\s*"([A-Za-z0-9_]+)",\s*true', text)
    out["plugins"] = list(dict.fromkeys(plugins))
    out["found"] = bool(out["plugins"]) or ('config.set("' + pixel_id + '"') in text
    m = re.search(r'config\.set\("' + pid + r'",\s*"automaticMatching",\s*', text)
    if m:
        obj = _json_after(text, m.end()) or {}
        out["automatic_matching"] = list(obj.get("selectedMatchKeys") or [])
    m = re.search(r'config\.set\("' + pid + r'",\s*"inferredEvents",\s*', text)
    if m:
        out["inferred_events"] = _json_after(text, m.end())
    m = re.search(r'config\.set\("' + pid + r'",\s*"unwantedData",\s*', text)
    if m:
        obj = _json_after(text, m.end()) or {}
        for event, groups in (obj.get("blacklisted_keys") or {}).items():
            keys = []
            for where, names in (groups or {}).items():
                keys += [f"{where}:{n}" for n in names or []]
            if keys:
                out["unwanted_keys"][event] = keys
    if not out["found"]:
        out["notes"].append("nessuna configurazione per questo ID: pixel inesistente, disattivato o ID errato")
    return out


def print_meta(r: dict) -> None:
    print(f"== Meta Pixel {r['id']} ==")
    if not r["found"]:
        for n in r["notes"]:
            print(f"⚠️  {n}")
        return
    labels = [MATCH_KEYS.get(k, k) for k in r["automatic_matching"]]
    if "AutomaticMatching" in r["plugins"] and labels:
        print("⚠ Advanced Matching AUTOMATICO attivo: il pixel legge dai moduli del sito e invia a Meta (hash SHA-256):")
        print("   " + ", ".join(labels))
    elif "AutomaticMatching" in r["plugins"]:
        print("⚠ Advanced Matching automatico attivo (campi non elencati nella configurazione)")
    elif labels:
        print("Advanced Matching automatico: campi configurati (" + ", ".join(labels) + ") ma funzione non attivata "
              "(manca l'opt-in AutomaticMatching)")
    else:
        print("Advanced Matching automatico: non attivo")
    if "InferredEvents" in r["plugins"]:
        print("Eventi automatici attivi: clic sui pulsanti e azioni dedotte vengono inviati senza codice dedicato")
    if r["unwanted_keys"]:
        print("Parametri che Meta FILTRA come indesiderati (indizio di dati personali o sensibili inviati in "
              "passato — da verificare):")
        for event, keys in r["unwanted_keys"].items():
            print(f"   {event}: {', '.join(keys)}")
    print("Plugin attivi:")
    for p in r["plugins"]:
        print(f"   {p}" + (f" — {META_PLUGINS[p]}" if p in META_PLUGINS else ""))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Configurazione pubblicata di un Meta Pixel.")
    ap.add_argument("ids", nargs="+", help="ID del Meta Pixel (15-16 cifre)")
    ap.add_argument("--file", help="configurazione già salvata (un solo ID)")
    ap.add_argument("--json", action="store_true", help="output JSON")
    args = ap.parse_args(argv)
    results = []
    for pixel_id in args.ids:
        vendor = vendor_of(pixel_id)
        if vendor == "tiktok":
            results.append({"id": pixel_id, "vendor": "tiktok", "error": TIKTOK_NOTE})
            continue
        if vendor is None:
            results.append({"id": pixel_id, "error": "formato non riconosciuto (Meta Pixel: 15-16 cifre)"})
            continue
        try:
            if args.file:
                with open(args.file, encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            else:
                text = fetch(META_URL.format(id=pixel_id))
        except (urllib.error.URLError, OSError) as exc:
            results.append({"id": pixel_id, "vendor": vendor, "error": str(exc)})
            continue
        results.append(parse_meta(text, pixel_id))
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0
    for i, r in enumerate(results):
        if i:
            print()
        if r.get("error"):
            print(f"== {r['id']} ==\n⚠️  {r['error']}")
        else:
            print_meta(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
