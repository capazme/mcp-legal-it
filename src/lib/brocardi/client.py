"""Standalone Brocardi scraper — async, structured extraction from brocardi.it.

Extracts from each article page:
- Position (breadcrumb): Libro > Titolo > Capo > Art.
- Dispositivo text (article text itself)
- Ratio Legis
- Spiegazione dottrinale
- Brocardi (adagi/proverbi giuridici)
- Massime giurisprudenziali (structured: autorità, numero, anno, testo)
- Relazioni storiche (Guardasigilli, Ruini)
- Note a piè di pagina
- Riferimenti incrociati (link ad altri articoli)
- Articoli correlati (precedente/successivo)
"""

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from ..visualex.map import find_brocardi_url

BASE_URL = "https://www.brocardi.it"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "it-IT,it;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

# In-memory cache for article URLs
_url_cache: dict[str, str] = {}

# ── Italian judicial authorities (for structured massime parsing) ───────────

_AUTORITA = {
    "corte_cost": r"(?:Corte\s+cost\.?|C\.\s*cost\.?|Corte\s+Costituzionale)",
    "cassazione": r"(?:Cass\.?\s*(?:civ|pen|lav|sez\.?\s*un)?\.?)",
    "cons_stato": r"(?:Cons\.?\s*(?:St\.?|Stato)|Consiglio\s+di\s+Stato)",
    "tar": r"(?:TAR\s*(?:Lazio|Lombardia|Campania|Sicilia|Veneto|Piemonte|Emilia[\s-]?Romagna|Toscana|Puglia|Calabria|Liguria|Marche|Abruzzo|Sardegna|Friuli|Umbria|Basilicata|Molise|Valle\s*d'?Aosta|Trentino)?)",
    "corte_conti": r"(?:Corte\s+(?:dei\s+)?[Cc]onti|C\.\s*conti)",
    "appello": r"(?:App\.?|C\.\s*App\.?|Corte\s+(?:d'?)?[Aa]ppello)",
    "tribunale": r"(?:Trib\.?|Tribunale)",
    "cgue": r"(?:CGUE|Corte\s+[Gg]iust\.?\s*(?:UE|CE)?|C\.\s*Giust\.?\s*UE)",
    "cedu": r"(?:CEDU|Corte\s+EDU|Corte\s+[Ee]uropea\s+[Dd]iritti)",
}
_AUTORITA_PATTERN = "|".join(f"({p})" for p in _AUTORITA.values())


# ── Data classes ───────────────────────────────────────────────────────────


@dataclass
class Massima:
    """A single massima giurisprudenziale, structurally parsed."""

    autorita: str | None = None
    numero: str | None = None
    anno: str | None = None
    testo: str = ""

    @property
    def estremi(self) -> str | None:
        """Return formatted citation, e.g. 'Cass. civ. n. 12345/2024'."""
        if self.autorita and self.numero and self.anno:
            return f"{self.autorita} n. {self.numero}/{self.anno}"
        return None

    @property
    def is_cassazione(self) -> bool:
        return bool(self.autorita and re.match(r"Cass", self.autorita))


@dataclass
class Relazione:
    tipo: str
    titolo: str
    testo: str
    articoli_citati: list[dict[str, str]] = field(default_factory=list)


@dataclass
class BrocardiResult:
    """Full Brocardi extraction result for an article."""

    url: str = ""
    position: str = ""
    brocardi: list[str] = field(default_factory=list)
    ratio: str = ""
    spiegazione: str = ""
    massime: list[Massima] = field(default_factory=list)
    relazioni: list[Relazione] = field(default_factory=list)
    footnotes: list[dict[str, str | int]] = field(default_factory=list)
    cross_references: list[dict[str, str]] = field(default_factory=list)
    related_articles: dict[str, dict[str, str]] = field(default_factory=dict)
    error: str = ""

    @property
    def cassazione_references(self) -> list[Massima]:
        """Return only massime from Corte di Cassazione (linkable to Italgiure)."""
        return [m for m in self.massime if m.is_cassazione]

    def to_markdown(self) -> str:
        """Format the full result as markdown."""
        if self.error:
            return f"**Errore Brocardi**: {self.error}"

        parts: list[str] = []
        parts.append(f"**Fonte**: Brocardi — {self.url}\n")

        if self.position:
            parts.append(f"**Posizione**: {self.position}\n")

        if self.ratio:
            parts.append(f"## Ratio Legis\n{self.ratio}\n")

        if self.spiegazione:
            parts.append(f"## Spiegazione\n{self.spiegazione}\n")

        if self.brocardi:
            parts.append("## Brocardi (adagi)")
            for b in self.brocardi:
                parts.append(f"- _{b}_")
            parts.append("")

        if self.massime:
            parts.append("## Massime giurisprudenziali")
            for m in self.massime:
                header = m.estremi or "—"
                parts.append(f"- **{header}**: {m.testo}")
            parts.append("")

        if self.relazioni:
            parts.append("## Relazioni storiche")
            for r in self.relazioni:
                parts.append(f"### {r.titolo}\n{r.testo}\n")

        if self.footnotes:
            parts.append("## Note")
            for fn in self.footnotes:
                parts.append(f"({fn['numero']}) {fn['testo']}")
            parts.append("")

        return "\n".join(parts)


# ── Public API ─────────────────────────────────────────────────────────────


async def fetch_brocardi(
    tipo_atto: str,
    articolo: str,
    numero_atto: str = "",
) -> BrocardiResult:
    """Fetch full Brocardi annotations for an article.

    Args:
        tipo_atto: Normalized act type (e.g. "codice civile", "codice penale")
        articolo: Article number (e.g. "2043", "13", "640-bis")
        numero_atto: Act number for disambiguation (e.g. "196", "231")
    """
    base_url = find_brocardi_url(tipo_atto, numero_atto)
    if not base_url:
        return BrocardiResult(error=f"Nessun mapping Brocardi per '{tipo_atto}'")

    article_num = articolo.replace("-", "") if articolo else ""
    if not article_num:
        return BrocardiResult(url=base_url, error="Numero articolo richiesto per Brocardi")

    async with httpx.AsyncClient(
        headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True
    ) as client:
        article_url = await find_article_url(client, base_url, article_num)
        if not article_url:
            return BrocardiResult(
                url=base_url,
                error=f"Articolo {articolo} non trovato su Brocardi",
            )

        resp = await client.get(article_url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

    result = BrocardiResult(url=article_url)
    result.position = _extract_position(soup)
    _extract_all_sections(soup, result)
    return result


async def find_article_url(
    client: httpx.AsyncClient, base_url: str, article_num: str
) -> str | None:
    """Navigate Brocardi to find the article page URL."""
    cache_key = f"{base_url}#{article_num}"
    if cache_key in _url_cache:
        return _url_cache[cache_key]

    resp = await client.get(base_url)
    resp.raise_for_status()

    pattern = re.compile(rf'href=["\']([^"\']*art{re.escape(article_num)}\.html)["\']')

    # Direct match
    matches = pattern.findall(resp.text)
    if matches:
        result = urljoin(BASE_URL, matches[0])
        _url_cache[cache_key] = result
        return result

    # Search in sub-pages (section-title links)
    soup = BeautifulSoup(resp.text, "lxml")
    max_sub = 15
    fetched = 0
    for section in soup.find_all("div", class_="section-title"):
        if fetched >= max_sub:
            break
        for a_tag in section.find_all("a", href=True):
            if fetched >= max_sub:
                break
            sub_url = urljoin(BASE_URL, a_tag.get("href", ""))
            if not sub_url.startswith(BASE_URL):
                continue
            fetched += 1
            try:
                sub_resp = await client.get(sub_url)
                sub_resp.raise_for_status()
                sub_matches = pattern.findall(sub_resp.text)
                if sub_matches:
                    result = urljoin(BASE_URL, sub_matches[0])
                    _url_cache[cache_key] = result
                    return result
            except httpx.HTTPError:
                continue

    return None


def parse_massime_references(massime: list[Massima]) -> list[dict[str, str | int]]:
    """Extract Cassazione decision references from massime for Italgiure lookup.

    Returns list of dicts with {autorita, numero, anno} ready for leggi_sentenza().
    """
    refs = []
    seen = set()
    for m in massime:
        if m.is_cassazione and m.numero and m.anno:
            key = f"{m.numero}/{m.anno}"
            if key not in seen:
                seen.add(key)
                refs.append({
                    "autorita": m.autorita or "",
                    "numero": int(m.numero),
                    "anno": int(m.anno),
                })
    return refs


# ── Internal extraction ────────────────────────────────────────────────────


def _clean_text(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r">(\w)", r"> \1", text)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _extract_position(soup: BeautifulSoup) -> str:
    breadcrumb = soup.find("div", id="breadcrumb")
    if breadcrumb:
        text = breadcrumb.get_text(strip=False).replace("\n", "").replace("  ", "")
        # Strip "Brocardi.it > " prefix
        return re.sub(r"^Brocardi\.it\s*>\s*", "", text).strip()
    return ""


def _extract_all_sections(soup: BeautifulSoup, result: BrocardiResult) -> None:
    corpo = soup.find(
        "div",
        class_="panes-condensed panes-w-ads content-ext-guide content-mark",
    )
    if not corpo:
        corpo = soup.find("body") or soup
        if not corpo:
            return

    _extract_brocardi_adagi(corpo, result)
    _extract_ratio(corpo, result)
    _extract_spiegazione(corpo, result)
    _extract_massime(corpo, result)
    _extract_relazioni(corpo, result)
    _extract_footnotes(corpo, result)
    _extract_cross_references(corpo, result)
    _extract_related_articles(soup, result)


def _extract_brocardi_adagi(corpo: Tag, result: BrocardiResult) -> None:
    for div in corpo.find_all("div", class_="brocardi-content"):
        text = _clean_text(div.get_text())
        if text:
            result.brocardi.append(text)


def _extract_ratio(corpo: Tag, result: BrocardiResult) -> None:
    ratio_section = corpo.find("div", class_="container-ratio")
    if ratio_section:
        ratio_text = ratio_section.find("div", class_="corpoDelTesto")
        if ratio_text:
            result.ratio = _clean_text(ratio_text.get_text())


def _extract_spiegazione(corpo: Tag, result: BrocardiResult) -> None:
    header = corpo.find("h3", string=lambda t: t and "Spiegazione dell'art" in t)
    if header:
        content = header.find_next_sibling("div", class_="text")
        if content:
            result.spiegazione = _clean_text(content.get_text())


def _extract_massime(corpo: Tag, result: BrocardiResult) -> None:
    header = corpo.find("h3", string=lambda t: t and "Massime relative all'art" in t)
    if not header:
        return

    content = header.find_next_sibling("div", class_="text")
    if not content:
        return

    for sentenza_div in content.find_all("div", class_="sentenza"):
        massima = _parse_single_massima(sentenza_div)
        if massima:
            result.massime.append(massima)


def _parse_single_massima(sentenza_div: Tag) -> Massima | None:
    """Parse a single massima extracting authority, number, year, and text."""
    massima = Massima()

    header_tag = sentenza_div.find("strong")
    if header_tag:
        header_text = header_tag.get_text(strip=True)

        # Try structured pattern: Autorità n. NUMERO/ANNO
        match = re.match(
            rf"^({_AUTORITA_PATTERN})\s*n\.\s*(\d+)/(\d{{4}})",
            header_text,
            re.IGNORECASE,
        )
        if match:
            groups = match.groups()
            # Find which authority group matched
            for g in groups[: len(_AUTORITA)]:
                if g:
                    massima.autorita = g.strip()
                    break
            massima.numero = groups[-2]
            massima.anno = groups[-1]
        else:
            # Fallback: extract number/year
            num_match = re.search(r"n\.\s*(\d+)/(\d{4})", header_text)
            if num_match:
                massima.numero = num_match.group(1)
                massima.anno = num_match.group(2)

            # Extract authority from beginning
            auth_match = re.match(rf"^({_AUTORITA_PATTERN})", header_text, re.IGNORECASE)
            if auth_match:
                for g in auth_match.groups():
                    if g:
                        massima.autorita = g.strip().rstrip(".")
                        break
            elif not massima.autorita:
                # Last fallback: text before "n."
                fb_match = re.match(r"^([^n]+?)(?:\s*n\.|\s*$)", header_text)
                if fb_match:
                    massima.autorita = fb_match.group(1).strip().rstrip(".")

    # Get text (excluding header)
    full_text = _clean_text(sentenza_div.get_text())
    if massima.numero and massima.anno:
        # Remove the header portion to keep just the massima body
        pattern = rf"(?:{_AUTORITA_PATTERN})[^n]*n\.\s*{massima.numero}/{massima.anno}\s*"
        body = re.sub(pattern, "", full_text, count=1, flags=re.IGNORECASE).strip()
        massima.testo = body if body else full_text
    else:
        massima.testo = full_text

    return massima if massima.testo else None


def _extract_relazioni(corpo: Tag, result: BrocardiResult) -> None:
    # Relazione al Progetto della Costituzione (Meuccio Ruini, 1947)
    cost_header = corpo.find(
        "h3", string=lambda t: t and "Relazione al Progetto della Costituzione" in t
    )
    if cost_header:
        content = cost_header.find_next_sibling("div", class_="text")
        if content:
            result.relazioni.append(
                Relazione(
                    tipo="costituzione",
                    titolo="Relazione al Progetto della Costituzione (Meuccio Ruini, 1947)",
                    testo=_clean_text(content.get_text()),
                )
            )

    # Relazione al Libro delle Obbligazioni
    libro_header = corpo.find(
        "h3", string=lambda t: t and "Libro delle Obbligazioni" in t
    )
    if libro_header:
        content = libro_header.find_next_sibling("div", class_="text")
        if content:
            result.relazioni.append(
                Relazione(
                    tipo="libro_obbligazioni",
                    titolo="Relazione al Libro delle Obbligazioni (1941)",
                    testo=_clean_text(content.get_text()),
                    articoli_citati=_extract_article_links(content),
                )
            )

    # Relazione al Codice Civile
    cc_header = corpo.find(
        "h3",
        string=lambda t: t and "Codice Civile" in t and "Relazione" in t,
    )
    if cc_header:
        content = cc_header.find_next_sibling("div", class_="text")
        if content:
            result.relazioni.append(
                Relazione(
                    tipo="codice_civile",
                    titolo="Relazione al Codice Civile (1942)",
                    testo=_clean_text(content.get_text()),
                    articoli_citati=_extract_article_links(content),
                )
            )


def _extract_article_links(element: Tag) -> list[dict[str, str]]:
    links = []
    for a_tag in element.find_all("a", href=True):
        href = a_tag.get("href", "")
        if "/art" in href and ".html" in href:
            match = re.search(r"/art(\d+[a-z]*)\.html", href)
            if match:
                links.append({
                    "numero": match.group(1),
                    "titolo": a_tag.get("title", ""),
                    "url": href if href.startswith("http") else f"{BASE_URL}{href}",
                })
    return links


def _extract_footnotes(corpo: Tag, result: BrocardiResult) -> None:
    footnotes: list[dict[str, str | int]] = []

    # Pattern 1: <a class="nota-ref" href="#nota_XXXX">
    nota_refs = corpo.find_all("a", class_="nota-ref")
    for nota_ref in nota_refs:
        href = nota_ref.get("href", "")
        if not href.startswith("#nota_"):
            continue
        anchor_name = href[1:]
        numero_text = nota_ref.get_text(strip=True)
        numero_match = re.search(r"\((\d+)\)|^(\d+)$", numero_text)
        if not numero_match:
            continue
        numero = int(numero_match.group(1) or numero_match.group(2))

        target = corpo.find("a", attrs={"name": anchor_name})
        if target:
            parent_div = target.find_parent("div", class_="nota")
            if parent_div:
                testo = parent_div.get_text(separator=" ", strip=True)
                testo = re.sub(r"^\(\d+\)\s*", "", testo)
                if testo:
                    footnotes.append({"numero": numero, "testo": _clean_text(testo)})

    # Pattern 2: div.corpoDelTesto.nota (alternative)
    if not footnotes:
        nota_divs = corpo.find_all(
            "div",
            class_=lambda c: c and "nota" in c and "corpoDelTesto" in c,
        )
        for nota_div in nota_divs:
            text = nota_div.get_text(separator=" ", strip=True)
            match = re.match(r"^\((\d+)\)\s*(.+)$", text, re.DOTALL)
            if match:
                footnotes.append({
                    "numero": int(match.group(1)),
                    "testo": _clean_text(match.group(2)),
                })

    # Pattern 3: <sup> + div.nota
    if not footnotes:
        for sup in corpo.find_all("sup"):
            num_text = sup.get_text(strip=True)
            if num_text.isdigit():
                nota_div = corpo.find(
                    "div", class_="nota", string=lambda t: t and num_text in t
                )
                if nota_div:
                    footnotes.append({
                        "numero": int(num_text),
                        "testo": _clean_text(nota_div.get_text()),
                    })

    # Deduplicate and sort
    seen: dict[int, dict] = {}
    for fn in footnotes:
        n = fn["numero"]
        if n not in seen:
            seen[n] = fn
    result.footnotes = sorted(seen.values(), key=lambda x: x["numero"])


def _extract_cross_references(corpo: Tag, result: BrocardiResult) -> None:
    seen_urls: set[str] = set()
    sections_map = {
        "brocardi-content": "brocardi",
        "container-ratio": "ratio",
        "text": "spiegazione",
        "sentenza": "massime",
    }

    _tipo_atto_from_path = {
        "/codice-civile/": "Codice Civile",
        "/codice-penale/": "Codice Penale",
        "/costituzione/": "Costituzione",
        "/codice-di-procedura-civile/": "Codice Procedura Civile",
        "/codice-di-procedura-penale/": "Codice Procedura Penale",
        "/codice-del-consumo/": "Codice del Consumo",
        "/codice-della-privacy/": "Codice Privacy",
    }

    for section_class, section_name in sections_map.items():
        for section in corpo.find_all("div", class_=section_class):
            for a_tag in section.find_all("a", href=True):
                href = a_tag.get("href", "")
                if "/art" not in href or ".html" not in href:
                    continue
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                art_match = re.search(r"/art(\d+[a-z]*)\.html", href)
                if not art_match:
                    continue

                tipo = None
                for path_pattern, tipo_name in _tipo_atto_from_path.items():
                    if path_pattern in href:
                        tipo = tipo_name
                        break

                result.cross_references.append({
                    "articolo": art_match.group(1),
                    "tipo_atto": tipo or "",
                    "url": href if href.startswith("http") else f"{BASE_URL}{href}",
                    "sezione": section_name,
                    "testo": a_tag.get_text(strip=True),
                })


def _extract_related_articles(soup: BeautifulSoup, result: BrocardiResult) -> None:
    for a_tag in soup.find_all("a", href=True):
        text = a_tag.get_text(strip=True).lower()
        href = a_tag.get("href", "")
        if "/art" not in href:
            continue

        art_match = re.search(r"/art(\d+[a-z]*)\.html", href)
        if not art_match:
            continue

        entry = {
            "numero": art_match.group(1),
            "url": href if href.startswith("http") else f"{BASE_URL}{href}",
            "titolo": a_tag.get("title", ""),
        }

        if "precedente" in text:
            result.related_articles["previous"] = entry
        elif "successivo" in text:
            result.related_articles["next"] = entry
