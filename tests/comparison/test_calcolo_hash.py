"""Comparison tests: calcolo_hash vs avvocatoandreani.it (impronta hash SHA-256).

Site page: https://www.avvocatoandreani.it/servizi/calcolo-verifica-impronta-hash.php
The site hashes FILES in the browser (asmcrypto), the tool hashes a STRING encoded
as UTF-8. To compare them the test uploads, via Playwright, an in-memory file whose
bytes are exactly ``testo.encode("utf-8")`` (no BOM, no trailing newline unless the
case has one) and reads "Dimensioni: N byte" and "Impronta Hash SHA256" from
``#ResultDiv``. Nothing is written to disk.

Reference: FIPS 180-4 (SHA-256) and the NIST test vectors. The tool's Vigenza line
cites DM 44/2011 and the PCT technical specifications (SHA-256).

Tolerance: none. A hash either matches bit for bit or it does not.

Convention noted, not asserted as tool == site: ``lunghezza_input`` counts Unicode
code points (``len(testo)``), while the site shows the file size in bytes. They
coincide for ASCII only (e.g. "è": 1 character vs 2 bytes).
"""

import re

import pytest

from tests.comparison.conftest import accept_cookies

URL = "https://www.avvocatoandreani.it/servizi/calcolo-verifica-impronta-hash.php"

_HASH_RE = re.compile(r"Impronta Hash SHA256:\s*([0-9a-fA-F]{64})")
_SIZE_RE = re.compile(r"Dimensioni:\s*(\d+)\s*byte")


def _tool(testo: str) -> dict:
    import src.server  # noqa: F401  registers all tool modules
    from src.tools.atti_giudiziari import calcolo_hash

    fn = getattr(calcolo_hash, "fn", calcolo_hash)
    return fn(testo=testo)


def _open(page):
    page.goto(URL, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    accept_cookies(page)


def _wait_results(page, n_files: int, timeout: int = 30000):
    page.wait_for_function(
        "n => { const d = document.querySelector('#ResultDiv');"
        " return d && (d.innerText.match(/[0-9a-fA-F]{64}/g) || []).length >= n; }",
        arg=n_files,
        timeout=timeout,
    )
    page.wait_for_timeout(500)


def _site_hashes(page, files: list[tuple[str, bytes]], verifica: str | None = None) -> dict:
    """Upload in-memory files to the site and return per-file size/hash plus messages."""
    _open(page)
    if verifica is not None:
        page.check("#Operazione-Verifica", force=True)
        page.wait_for_timeout(500)
        page.fill("#Verifica", verifica)
    page.set_input_files(
        "#fileselect",
        files=[{"name": name, "mimeType": "text/plain", "buffer": data} for name, data in files],
    )
    _wait_results(page, len(files))
    out = {}
    for idx, (name, _data) in enumerate(files):
        txt = page.inner_text(f"#file-{idx}")
        h = _HASH_RE.search(txt)
        s = _SIZE_RE.search(txt)
        assert h and s, f"risultato del sito non leggibile per {name}: {txt!r}"
        out[name] = {"hash": h.group(1).lower(), "byte": int(s.group(1)), "testo": txt}
    out["_message"] = page.inner_text("#Message")
    out["_error"] = page.inner_text("#Error")
    return out


def _compare(page, testo: str, name: str = "documento.txt") -> tuple[dict, dict]:
    tool = _tool(testo)
    site = _site_hashes(page, [(name, testo.encode("utf-8"))])[name]
    assert tool["algoritmo"] == "SHA-256"
    assert tool["hash"] == site["hash"], (
        f"hash diverso: tool={tool['hash']} sito={site['hash']}"
    )
    # The uploaded file is exactly the UTF-8 encoding of testo.
    assert site["byte"] == len(testo.encode("utf-8"))
    return tool, site


class TestCalcoloHashVsSito:

    def test_vettore_abc(self, page):
        """Piano: 'abc' -> ba7816bf...f20015ad (FIPS 180-4), lunghezza_input 3.
        Norma: FIPS 180-4, vettore di prova SHA-256 a un blocco."""
        tool, site = _compare(page, "abc", "abc.txt")
        assert tool["hash"] == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        assert tool["lunghezza_input"] == site["byte"] == 3

    def test_stringa_vuota(self, page):
        """Piano (limite: input vuoto): '' -> e3b0c442...7852b855, lunghezza_input 0.
        Norma: FIPS 180-4 (messaggio di lunghezza zero)."""
        tool, site = _compare(page, "", "vuoto.txt")
        assert tool["hash"] == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert tool["lunghezza_input"] == site["byte"] == 0

    def test_vettore_due_blocchi_448_bit(self, page):
        """Piano (limite di padding: 56 byte = 448 bit, il padding sfora nel secondo
        blocco): 'abcdbcde...nopq' -> 248d6a61...19db06c1 (FIPS 180-4)."""
        testo = "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"
        tool, site = _compare(page, testo, "448bit.txt")
        assert tool["hash"] == "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"
        assert tool["lunghezza_input"] == site["byte"] == 56

    def test_carattere_accentato_utf8(self, page):
        """Piano (limite di codifica): 'è' -> 97c916cd...39b8a0c7 (byte c3 a8);
        lunghezza_input 1 carattere contro 2 byte del file.
        Norma: FIPS 180-4 sui byte UTF-8 del testo (RFC 3629)."""
        tool, site = _compare(page, "è", "accento.txt")
        assert tool["hash"] == "97c916cd94785d7b9b52ae7013c267854f275691ddaae212bc1c07f639b8a0c7"
        # Convention difference, documented: the tool counts characters, the site bytes.
        assert tool["lunghezza_input"] == 1
        assert site["byte"] == 2

    def test_a_capo_finale(self, page):
        """Piano: 'abc\\n' -> edeaaff3...0efd18cb; il file caricato ha lo stesso a capo.
        Norma: FIPS 180-4 (l'a capo e' un byte del messaggio)."""
        tool, site = _compare(page, "abc\n", "newline.txt")
        assert tool["hash"] == "edeaaff3f1774ad2888673770c6d64097e391bc362d7d6fb34982ddf0efd18cb"
        assert tool["lunghezza_input"] == site["byte"] == 4

    def test_a_capo_windows_crlf(self, page):
        """Aggiunto (limite: file salvato su Windows): 'abc\\r\\n' ha un hash diverso
        da 'abc\\n'; tool e sito devono coincidere byte per byte (5 byte).
        Atteso: nessun valore nel piano; 552bab68...85fdb025 da FIPS 180-4."""
        tool, site = _compare(page, "abc\r\n", "crlf.txt")
        assert tool["hash"] != "edeaaff3f1774ad2888673770c6d64097e391bc362d7d6fb34982ddf0efd18cb"
        assert tool["lunghezza_input"] == site["byte"] == 5

    def test_emoji_quattro_byte(self, page):
        """Aggiunto (limite di codifica: carattere fuori dal BMP, 4 byte UTF-8).
        lunghezza_input 1 carattere contro 4 byte.
        Norma: FIPS 180-4 sui byte UTF-8 (RFC 3629); atteso f0443a34...3a37e2d9."""
        tool, site = _compare(page, "\U0001F600", "emoji.txt")
        assert tool["lunghezza_input"] == 1
        assert site["byte"] == 4

    def test_forma_decomposta_nfd(self, page):
        """Aggiunto (limite: normalizzazione Unicode). 'e' + U+0300 (NFD) produce byte
        diversi da 'è' (NFC): il tool non normalizza, come il sito che legge i byte.
        Norma: FIPS 180-4 sui byte UTF-8; atteso 24b24862...a72487b4."""
        tool, site = _compare(page, "e\u0300", "nfd.txt")  # escaped: keep NFD in the source
        assert tool["hash"] != "97c916cd94785d7b9b52ae7013c267854f275691ddaae212bc1c07f639b8a0c7"
        assert tool["lunghezza_input"] == 2
        assert site["byte"] == 3

    def test_confine_blocco_55_e_64_byte(self, page):
        """Aggiunto (limite di padding): 55 byte stanno in un blocco con il padding,
        64 byte richiedono due blocchi. Due file nello stesso caricamento (il sito
        accetta piu' file). Norma: FIPS 180-4, par. 5.1.1 (padding)."""
        t55, t64 = "a" * 55, "a" * 64
        site = _site_hashes(page, [("a55.txt", t55.encode()), ("a64.txt", t64.encode())])
        r55, r64 = _tool(t55), _tool(t64)
        assert r55["hash"] == site["a55.txt"]["hash"]
        assert r64["hash"] == site["a64.txt"]["hash"]
        assert r55["lunghezza_input"] == site["a55.txt"]["byte"] == 55
        assert r64["lunghezza_input"] == site["a64.txt"]["byte"] == 64

    def test_un_milione_di_a(self, page):
        """Aggiunto (limite dimensionale): 1.000.000 x 'a' -> cdc76e5c...c7112cd0
        (vettore lungo NIST, FIPS 180-4). Verifica anche la lettura a blocchi del file
        sul sito."""
        tool, site = _compare(page, "a" * 1_000_000, "milione.txt")
        assert tool["hash"] == "cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0"
        assert tool["lunghezza_input"] == site["byte"] == 1_000_000

    def test_verifica_sito_riconosce_hash_del_tool(self, page):
        """Aggiunto (opzione enumerata 'VERIFICA' del sito): l'impronta prodotta dal
        tool per un'attestazione di conformita' (testo multiriga con accenti),
        incollata nel campo di verifica, e' riconosciuta dal sito per lo stesso file.
        Contesto: impronta nelle attestazioni di conformita' del PCT (specifiche
        tecniche DGSIA richiamate dal DM 44/2011, citato nella riga Vigenza del tool)."""
        testo = (
            "Attestazione di conformità\n"
            "Il sottoscritto avv. Mario Rossi attesta che la presente copia informatica "
            "è conforme all'originale analogico, ai sensi dell'art. 16-undecies "
            "d.l. 179/2012.\n"
        )
        tool = _tool(testo)
        site = _site_hashes(
            page,
            [("attestazione.txt", testo.encode("utf-8"))],
            verifica=f"Impronta SHA-256 del file attestazione.txt: {tool['hash']}",
        )
        assert site["attestazione.txt"]["hash"] == tool["hash"]
        # "il file corrisponde", not just "corrisponde": the negative wording
        # "nessuna corrispondenza" contains "corrisponde" as a substring.
        assert "il file corrisponde" in site["_message"].lower()
        assert "nessuna corrispondenza" not in site["_error"].lower()

    def test_file_binario_non_utf8(self):
        """Aggiunto (limite d'uso): un PDF o qualsiasi file con byte non UTF-8 non si
        puo' passare al tool, che accetta solo una stringa e la ricodifica in UTF-8.
        Il sito calcola l'impronta di qualunque file: caso non confrontabile."""
        pytest.skip(
            "non confrontabile: il tool accetta solo testo (str -> UTF-8), "
            "non i byte di un file binario come il PDF da depositare"
        )
