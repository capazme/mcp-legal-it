# AKN fixture structure notes (for the parser)

Captured 2026-06-11 from live Normattiva `caricaAKN`. Namespace:
`http://docs.oasis-open.org/legaldocml/ns/akn/3.0` (default ns — use
`lxml` with namespace-aware queries or strip ns).

Two structures exist. The parser MUST handle both.

## Fixtures on disk (`tests/fixtures/akn/`)

| File | Structure | Articles | Size | Notes |
|------|-----------|---------:|-----:|-------|
| `legge_241_1990.xml` | flat | 51 | 0.3 MB | has `art_2-bis` etc. |
| `costituzione.xml` | flat | 139 | 0.2 MB | |
| `dlgs_231_2001.xml` | flat | 109 | 0.4 MB | |
| `dlgs_196_2003.xml` | flat | 221 | 1.5 MB | privacy code |
| `dlgs_152_2006.xml` | flat | 443 | 6.3 MB | large flat act |
| `codice_civile.xml` | component | ~2969 + preleggi | 10.6 MB | `<doc>` per article |
| `codice_penale.xml` | component | ~734 | 4.1 MB | `<doc>` per article |

## Structure 1 — FLAT (laws, decrees, Costituzione)

Articles are `<article>` elements directly under the body:

```xml
<article eId="art_3">
  <num>Art. 3.</num>
  <heading><ins eId="ins_7">(( (Motivazione del provvedimento) ))</ins></heading>
  <paragraph eId="art_3__para_1">
    <num>1.</num>
    <content><p>Ogni provvedimento amministrativo ... deve essere motivato ...</p></content>
  </paragraph>
  <paragraph eId="art_3__para_2"> ... </paragraph>
</article>
```

- Article id: `eId="art_N"`, with bis/ter as `eId="art_2-bis"`.
- Commi: `<paragraph eId="art_N__para_M">` → `<num>` + `<content><p>`.
- Lettere: `eId="art_N__para_M.__point_a"` (`<point>` / nested list items).
- Modifications: `<ins>` (added) and `<del>` (deleted) inline. Render the
  **vigente** text = keep `<ins>` content, drop `<del>` content. Normattiva also
  wraps modified text in literal `(( ))` markers inside the text — strip those.

## Structure 2 — COMPONENT (codici: c.c., c.p.)

Each article is a `<doc>` inside `<attachments>/<attachment>`. The article is
identified by the `name` attribute, **NOT** by eId:

```xml
<attachments>
  <attachment>
    <doc name="CODICE CIVILE-art. 2043">
      <meta> ... </meta>
      <mainBody>
        <paragraph>
          <content>
            <p> Art. 2043.

 (Risarcimento per fatto illecito).

 Qualunque fatto doloso o colposo, che cagiona ad altri un danno ingiusto,
 obbliga colui che ha commesso il fatto a risarcire il danno.
</p>
          </content>
        </paragraph>
      </mainBody>
    </doc>
  </attachment>
  ...
</attachments>
```

- `<doc name>` format: `"<PART NAME>-art. <N>"`, e.g. `"CODICE CIVILE-art. 2043"`.
- The PART prefix disambiguates: the c.c. fixture contains BOTH
  `"Disposizioni sulla legge in generale-art. N"` (the *preleggi*, ~31 articles)
  and `"CODICE CIVILE-art. N"` (the code itself). When resolving "art. 2 c.c."
  pick the `CODICE CIVILE` part; "art. 2 preleggi" picks the other.
- Body: `<mainBody><paragraph><content><p>` with the whole article text inline
  (number + rubrica in parens + body), separated by blank lines. There is no
  per-comma `<num>` here — the text is a single `<p>` block (split on blank lines
  if comma granularity is wanted, best-effort).
- The first 2 articles may ALSO appear as flat `<article eId="art_1">` at the top;
  prefer the component `<doc>` for the full set.

## Article-number → lookup key

- Flat: `numero_articolo` "2043" → `eId="art_2043"`; "2-bis" / "2 bis" →
  `eId="art_2-bis"`.
- Component: match `<doc name>` ending in `-art. 2043` (case-insensitive,
  tolerate the space after "art."). For bis: name ends in `-art. 2-bis` (verify
  against the c.p. fixture which has bis articles).

## Failure / fallback signals (network layer, not parser)

- `caricaAKN` cold (no act-landing-page session) returns a **32254-byte** HTML
  error page, not XML. Treat any response not starting with `<?xml` as failure.
- Session: GET the act landing page (`norma.url()` with no article) on the same
  httpx client BEFORE `caricaAKN`; cookies (`JSESSIONID`, `NCC`) carry the
  session. Headers: `User-Agent` (browser), `Referer: https://www.normattiva.it/`.
- `caricaAKN` URL:
  `https://www.normattiva.it/do/atto/caricaAKN?dataGU=<YYYYMMDD>&codiceRedaz=<CODE>&dataVigenza=<YYYYMMDD>`
- The landing page exposes the params in the `caricaAKN` href and in
  `<meta property="eli:id_local" content="<CODE>">` + a
  `dataPubblicazioneGazzetta=YYYY-MM-DD` occurrence.
