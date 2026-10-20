# Browser probes — frammenti JavaScript

Da incollare nel tool «evaluate script in page» del browser MCP (chrome-devtools: `evaluate_script({function: ...})`; claude-in-chrome: `javascript_tool`). Ogni frammento è una funzione/espressione che ritorna JSON serializzabile.

---

## §1 — Probe pre-consenso (e riusabile post-consenso)
Legge cookie, storage e globali dei tracker. Eseguila in Fase 1 (prima di toccare il banner) e di nuovo in Fase 3. Se il browser non ha ancora un cookie di consenso, cancella il marcatore di un ciclo di test precedente (`markerReset: true`): per ripetere la prova (es. «Rifiuta» dopo «Accetta») usa comunque un **nuovo contesto isolato**.

```js
() => {
  const parse = s => (s||'').split(';').map(c=>c.trim()).filter(Boolean).map(c=>{
    const i=c.indexOf('='); return {name:i>=0?c.slice(0,i):c, value:i>=0?c.slice(i+1).slice(0,80):''};
  });
  const out = { url: location.href, title: document.title };
  // Fase 1: nessun cookie di consenso nel browser → il marcatore dell'audit (§3) di un ciclo precedente non vale più
  if (!/OptanonAlertBoxClosed|OptanonConsent|CookieConsent|cmplz_|_iub_cs|cookieyes-consent|cky-consent|euconsent-v2|didomi_token|_tracking_consent|CookieScriptConsent|borlabs-cookie|cookielawinfo/.test(document.cookie)) {
    try { if (sessionStorage.getItem('__cookieAudit_consent')) { sessionStorage.removeItem('__cookieAudit_consent'); out.markerReset = true; } } catch (e) {}
  }
  out.cookies = parse(document.cookie);
  out.cookieCount = out.cookies.length;
  out.localStorage = {}; try { for (let i=0;i<localStorage.length;i++){const k=localStorage.key(i);out.localStorage[k]=(localStorage.getItem(k)||'').slice(0,160);} } catch(e){}
  out.sessionStorage = {}; try { for (let i=0;i<sessionStorage.length;i++){const k=sessionStorage.key(i);out.sessionStorage[k]=(sessionStorage.getItem(k)||'').slice(0,160);} } catch(e){}
  out.trackerGlobals = {
    gtag:typeof window.gtag, ga:typeof window.ga, fbq:typeof window.fbq,
    _linkedin:typeof window._linkedin_data_partner_ids, lintrk:typeof window.lintrk,
    ttq:typeof window.ttq, pintrk:typeof window.pintrk, twq:typeof window.twq, uetq:typeof window.uetq,
    snaptr:typeof window.snaptr, rdt:typeof window.rdt, criteo_q:typeof window.criteo_q, _tfa:typeof window._tfa,
    obApi:typeof window.obApi, ym:typeof window.ym,
    hj:typeof window.hj, clarity:typeof window.clarity, _hsq:typeof window._hsq,
    Cookiebot:typeof window.Cookiebot, OneTrust:typeof window.OneTrust,
    _iub:typeof window._iub, cmplz:typeof window.cmplz, Usercentrics:typeof window.UC_UI
  };
  out.dataLayer = (window.dataLayer||[]).map(x=>{try{return JSON.stringify(x).slice(0,200);}catch(e){return String(x).slice(0,120);}});
  return out;
}
```

Poi lista le **richieste di rete** (chrome-devtools `list_network_requests`) e individua i domini di terze parti (tutto ciò che non è il dominio del sito): `googletagmanager.com`, `google-analytics.com`, `*.g.doubleclick.net`, `connect.facebook.net`, `*.linkedin.com`, `static.hotjar.com`, `*.clarity.ms`, `*.hs-scripts.com`, ecc. Per i **pixel** usa subito dopo la sonda §5, che classifica le chiamate per fornitore.

## §2 — Struttura del banner (funziona anche se l'ad-blocker lo nasconde)
Legge i pulsanti e le categorie dal DOM, con gli stili calcolati per valutare la **parità Accetta/Rifiuta**.

```js
() => {
  const sel = '.cmplz-cookiebanner, #CybotCookiebotDialog, #onetrust-banner-sdk, #iubenda-cs-banner, [id*="usercentrics"], [class*="cookie"][class*="banner"], [id*="cookie"][id*="consent"]';
  const banner = document.querySelector(sel);
  const out = { bannerFound: !!banner };
  if (!banner) return out;
  const cs = getComputedStyle(banner);
  out.visibility = { display: cs.display, visibility: cs.visibility, opacity: cs.opacity };
  const btns = banner.querySelectorAll('button, a[role="button"], .cmplz-btn, [class*="accept"], [class*="deny"], [class*="reject"]');
  out.buttons = Array.from(btns).slice(0,20).map(b=>{const s=getComputedStyle(b);return{
    text:(b.innerText||b.textContent||'').trim().slice(0,50), cls:b.className.toString().slice(0,60),
    bg:s.backgroundColor, color:s.color, fontSize:s.fontSize, border:s.borderStyle
  };});
  out.categories = Array.from(document.querySelectorAll('[class*="categor"], input[type="checkbox"][name*="consent"], input[type="checkbox"][class*="cmplz"]'))
    .map(c=>(c.getAttribute('data-category')||c.name||c.value||c.className||'').toString().slice(0,50)).filter(Boolean).slice(0,15);
  out.policyLinks = Array.from(banner.querySelectorAll('a[href]')).map(a=>({t:(a.innerText||'').trim().slice(0,40),href:a.href})).slice(0,10);
  return out;
}
```

## §3 — Concessione del consenso (per CMP)
Prima identifica la CMP (§ fingerprints), poi usa il frammento giusto. In caso di dubbio, prova tutti — quelli non applicabili sono no-op.

```js
() => {
  const t0 = performance.now();  // momento del consenso, per la sonda pixel (§5)
  const done = [];
  // Complianz
  try { if (typeof window.cmplz_set_consent==='function'){cmplz_set_consent('allow');done.push('complianz');} } catch(e){}
  // Cookiebot
  try { if (window.Cookiebot && Cookiebot.submitCustomConsent){Cookiebot.submitCustomConsent(true,true,true);done.push('cookiebot');} } catch(e){}
  try { if (window.Cookiebot && Cookiebot.dialog && document.getElementById('CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll')){document.getElementById('CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll').click();done.push('cookiebot-click');} } catch(e){}
  // OneTrust
  try { if (window.OneTrust && OneTrust.AllowAll){OneTrust.AllowAll();done.push('onetrust');} } catch(e){}
  // iubenda
  try { if (window._iub && _iub.cs && _iub.cs.api && _iub.cs.api.consent){_iub.cs.api.consent();done.push('iubenda');} } catch(e){}
  // fallback generico: click su qualsiasi pulsante "accetta"
  try {
    const b = document.querySelector('.cmplz-accept, #onetrust-accept-btn-handler, #CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll, .iubenda-cs-accept-btn, [class*="accept-all"], [id*="accept"]');
    if (b){ b.click(); done.push('generic-click:'+b.className); }
  } catch(e){}
  if (!done.length) return { granted: done, avviso: 'nessuna CMP gestita: concedi il consenso a mano, eseguendo PRIMA il marcatore qui sotto' };
  try { sessionStorage.setItem('__cookieAudit_consent', JSON.stringify({ origin: performance.timeOrigin, t: t0, at: new Date().toISOString() })); } catch (e) {}
  return { granted: done };
}
```

Dopo aver concesso il consenso: **attendi ~2s** (i tag si iniettano in modo asincrono), poi ri-esegui §1, §5 e ri-lista la rete. Cerca il cookie `*_consent_mode` (Complianz) o equivalenti che riportino i segnali Consent Mode v2.

**Consenso dato cliccando a mano** (CMP non gestita da §3): esegui SUBITO PRIMA del clic il marcatore, altrimenti §5 non sa distinguere le chiamate pre/post consenso:

```js
() => { try { sessionStorage.setItem('__cookieAudit_consent', JSON.stringify({ origin: performance.timeOrigin, t: performance.now(), at: new Date().toISOString() })); return 'marcatore impostato'; } catch (e) { return 'sessionStorage non disponibile: annota l\'ora del clic'; } }
```

La chiave `__cookieAudit_consent` in sessionStorage è dell'audit, non del sito: escludila dall'inventario.

## §4 — Enumerazione script bloccati dalla CMP
Alcune CMP «congelano» gli script di tracciamento come `type="text/plain"` con `data-category`/`data-service` finché manca il consenso. Enumerarli dà l'inventario **senza** doverli far scattare (immune all'ad-blocker), ma **non** rivela i tag iniettati da GTM a runtime (per quelli serve la Fase 3-bis).

```js
() => {
  const blocked = document.querySelectorAll('script[type="text/plain"], script[data-category], script[data-service]');
  return Array.from(blocked).map(s=>({
    category: s.getAttribute('data-category')||'', service: s.getAttribute('data-service')||'',
    src: s.getAttribute('data-src')||s.src||'(inline)',
    hint: (!s.src && !s.getAttribute('data-src')) ? (s.textContent||'').replace(/\s+/g,' ').slice(0,100):''
  }));
}
```

## §5 — Pixel e beacon (chi riceve dati, con quali ID ed eventi, prima o dopo il consenso)
Classifica le chiamate già partite (Resource Timing), gli ID scritti nel codice della pagina, i `<noscript>` e le immagini 1×1, e legge gli ID esposti dalle librerie (`fbq.getState()`, `ttq._i`, `_linkedin_data_partner_ids`, `google_tag_manager`). Eseguila in Fase 1 (prima del banner) e in Fase 3 (dopo §3).

- **Momento**: se §3 (o il marcatore) è stato eseguito, ogni pixel ha i contatori `pre`/`post`; senza marcatore la sonda lo dice e — se gira prima di toccare il banner — tutte le chiamate sono pre-consenso.
- **`hits` vs `scripts`**: `scripts` è il solo caricamento della libreria (file `.js`, configurazione del pixel: comunica comunque IP e browser al fornitore — zona grigia, come `gtm.js`); `hits` sono tutte le altre chiamate, che trasmettono eventi — anche quando il fornitore le carica come `<script>` (es. conversioni Google Ads, eventi Criteo, X).
- **`userData`**: nomi dei parametri con dati dell'utente (`ud[em]` Meta, `em` Google Ads enhanced conversions, `pd.em` Pinterest…); **`emailInUrl`**: parametri che contengono un indirizzo email in chiaro (es. `dl` = URL della pagina con l'email nella query) — verifica che sia l'indirizzo di un visitatore e non, ad esempio, il contatto del sito presente nella pagina. I valori non vengono mai riportati.
- **`consent`**: segnali di consenso trasmessi (`gcs` decodificato, `gcd`, `npa`, `dma`, stringa TCF).
- **`serverSide`**: chiamate di misurazione verso il dominio del sito (es. `/g/collect` su un sottodominio): tagging lato server o proxy, i cui inoltri a terzi non si vedono dal browser.
- **`otherHosts`**: domini di terze parti contattati e non classificati (CDN, recensioni, chat, geolocalizzazione dell'IP…): vanno qualificati a mano.
- **Piattaforme email sul sito** (Klaviyo, HubSpot, Mailchimp, ActiveCampaign, Brevo, Omnisend): sono il ponte tra newsletter e sito — riconoscono chi arriva da un link della newsletter (parametri come `_kx`, `mc_eid`, `_hsenc`, `vgo_ee`) e ne seguono la navigazione. Collegale all'analisi della newsletter (Fase 5).
- **Limiti**: con un ad-blocker attivo una richiesta bloccata può comparire tra quelle *avviate* (Chrome la registra comunque): per la valutazione conta che il sito l'abbia avviata, ma conferma con `list_network_requests` (`ERR_BLOCKED_BY_CLIENT`) e, per l'inventario, con `inlineIds`, §4 e la Fase 3-bis. Le chiamate dentro iframe di altri domini o dentro web worker (es. i pixel delle app Shopify in sandbox «strict») non sono visibili: usa la lista rete. Il buffer del browser conserva 250 voci se nessuno lo amplia: la sonda lo porta a 5000 per le chiamate successive e avvisa se era già pieno; con chrome-devtools puoi ampliarlo prima di ogni script con `navigate_page({…, initScript: "performance.setResourceTimingBufferSize(5000)"})`.

```js
() => {
  // Pixel/beacon vendors. Keys aligned with VENDORS in scripts/inspect_container.py (plus ga4).
  // re: host+path of the request; id: query params with the pixel ID; idRe: ID inside path/query; ev: event params.
  const V = [
    {k:'meta', n:'Meta Pixel', re:/facebook\.com\/tr\b|connect\.facebook\.net\/(signals\/|[A-Za-z_]+\/fbevents)/, id:['id'], idRe:/signals\/config\/(\d+)/, ev:['ev']},
    {k:'tiktok', n:'TikTok Pixel', re:/analytics\.tiktok\.com\/(api\/v2\/pixel|i18n\/pixel)/, id:['sdkid'], ev:[]},
    {k:'linkedin', n:'LinkedIn Insight Tag', re:/px\.ads\.linkedin\.com|dc\.ads\.linkedin\.com|snap\.licdn\.com\/li\.lms-analytics/, id:['pid'], ev:['conversionId']},
    {k:'pinterest', n:'Pinterest Tag', re:/ct\.pinterest\.com\/(v3|user)|s\.pinimg\.com\/ct\//, id:['tid'], ev:['event']},
    {k:'x', n:'X (Twitter) Pixel', re:/(analytics\.twitter\.com|t\.co)\/i\/adsct|ads-twitter\.com/, id:['txn_id'], ev:['events']},
    {k:'microsoft', n:'Microsoft Advertising UET', re:/bat\.bing\.(com|net)\/(action|bat\.js|p\/action)|c\.bing\.com\/c\.gif/, id:['ti'], idRe:/p\/action\/(\d+)/, ev:['evt','ea']},
    {k:'snap', n:'Snap Pixel', re:/tr\.snapchat\.com|tr-shadow\.snapchat\.com|sc-static\.net\/scevent/, id:['pid'], ev:['ev']},
    {k:'reddit', n:'Reddit Pixel', re:/alb\.reddit\.com\/rp\.gif|redditstatic\.com\/ads\/|pixel-config\.reddit\.com/, id:['id'], idRe:/pixels\/([a-z0-9_]+)\/config/, ev:['event']},
    {k:'criteo', n:'Criteo OneTag', re:/(sslwidget|gum|dis|static|dynamic|bidder)\.criteo\.(com|net)/, id:['a'], ev:[]},
    {k:'taboola', n:'Taboola Pixel', re:/(trc|cdn)\.taboola\.com/, id:['id'], idRe:/unip\/(\d+)\//, ev:['en']},
    {k:'outbrain', n:'Outbrain Pixel', re:/tr\.outbrain\.com|amplify\.outbrain\.com/, id:['marketerId'], ev:['name']},
    {k:'google_ads', n:'Google Ads', re:/googleadservices\.com\/pagead\/conversion|googleads\.g\.doubleclick\.net\/pagead\/(viewthroughconversion|conversion)|google\.[a-z.]+\/(pagead\/(1p-user-list|1p-conversion|conversion)|ccm\/collect)/, idRe:/(?:conversion|viewthroughconversion|1p-user-list|1p-conversion)\/(\d+)/, ev:['label','en']},
    {k:'floodlight', n:'Google Floodlight', re:/(ad|fls)\.doubleclick\.net\/(activity|activityi|ddm\/(fls|activity))/, idRe:/src=(\d+)/, ev:[]},
    {k:'yandex', n:'Yandex Metrica', re:/mc\.yandex\.(ru|com)\//, idRe:/watch\/(\d+)/, ev:[]},
    {k:'quora', n:'Quora Pixel', re:/q\.quora\.com\/_\/ad\/|a\.quora\.com\/qevents/, idRe:/_\/ad\/([0-9a-f]+)\//, ev:[]},
    {k:'adroll', n:'AdRoll', re:/(d|s)\.adroll\.com/, id:['adroll_adv_id','advertisable'], ev:[]},
    {k:'amazon', n:'Amazon Ads', re:/amazon-adsystem\.com/, id:['pid'], ev:[]},
    {k:'adform', n:'Adform', re:/adform\.net/, id:['pm'], ev:[]},
    {k:'awin', n:'Awin', re:/dwin1\.com|awin1\.com/, idRe:/dwin1\.com\/(\d+)\.js/, ev:[]},
    {k:'thetradedesk', n:'The Trade Desk', re:/adsrvr\.org/, id:['adv'], ev:[]},
    {k:'teads', n:'Teads', re:/teads\.tv/, id:['buyer_pixel_id'], ev:['action']},
    {k:'rtbhouse', n:'RTB House', re:/creativecdn\.com/, id:['id'], ev:[]},
    {k:'tradedoubler', n:'Tradedoubler', re:/tradedoubler\.com/, id:['organization'], ev:['event']},
    {k:'hotjar', n:'Hotjar', re:/hotjar\.(com|io)/, id:['hjid'], idRe:/hotjar-(\d+)\.js/, ev:[]},
    {k:'clarity', n:'Microsoft Clarity', re:/clarity\.ms/, idRe:/tag\/([a-z0-9]+)/, ev:[]},
    {k:'stape', n:'Stape (server GTM)', re:/stapecdn\.com|stape\.io/, ev:[]},
    {k:'klaviyo', n:'Klaviyo (tracciamento sul sito)', re:/(static|static-tracking|a|fast\.a)\.klaviyo\.com/, id:['company_id'], ev:[]},
    {k:'hubspot', n:'HubSpot (tracciamento sul sito)', re:/js\.hs-scripts\.com|js\.hs-analytics\.net|track\.hubspot\.com/, idRe:/hs-(?:scripts|analytics)\.(?:com|net)\/(?:analytics\/\d+\/)?(\d+)\.js/, ev:[]},
    {k:'mailchimp', n:'Mailchimp (sito collegato)', re:/chimpstatic\.com\/mcjs-connected/, idRe:/users\/([0-9a-f]+)\//, ev:[]},
    {k:'activecampaign', n:'ActiveCampaign (tracciamento sul sito)', re:/trackcmp\.net|diffuser-cdn\.app-us1\.com|prism\.app-us1\.com/, id:['actid'], ev:[]},
    {k:'brevo', n:'Brevo (tracciamento sul sito)', re:/sibautomation\.com|cdn\.brevo\.com/, id:['key'], ev:[]},
    {k:'omnisend', n:'Omnisend (tracciamento sul sito)', re:/omnisnippet1\.com|omnisrv\.com/, ev:[]},
    {k:'ga4', n:'Google Analytics 4', re:/\/g\/collect$/, id:['tid'], ev:['en']},
  ];
  // Pixel IDs written in the page's own inline code (seen even when an ad-blocker stops the network call)
  const C = [
    ['meta', /fbq\(/, /fbq\(\s*['"]init['"]\s*,\s*['"]?(\d{6,20})/g],
    ['tiktok', /ttq\./, /ttq\.load\(\s*['"]([A-Z0-9]{15,25})['"]/g],
    ['linkedin', /_linkedin/, /_linkedin_partner_id\s*=\s*['"]?(\d{3,12})/g],
    ['pinterest', /pintrk\(/, /pintrk\(\s*['"]load['"]\s*,\s*['"](\d{6,16})/g],
    ['x', /twq\(/, /twq\(\s*['"](?:config|init)['"]\s*,\s*['"]([a-z0-9]{4,12})['"]/g],
    ['microsoft', /uetq|bat\.bing/, /\bti\s*:\s*['"]?(\d{5,12})/g],
    ['snap', /snaptr\(/, /snaptr\(\s*['"]init['"]\s*,\s*['"]([0-9a-f-]{36})['"]/g],
    ['reddit', /rdt\(/, /rdt\(\s*['"]init['"]\s*,\s*['"]([a-z0-9_]{4,30})['"]/g],
    ['criteo', /criteo_q/, /setAccount['"]\s*,\s*account\s*:\s*['"]?(\d{3,8})/g],
    ['taboola', /_tfa/, /_tfa\.push\(\{[^}]*\bid\s*:\s*['"]?(\d{4,9})/g],
    ['outbrain', /OB_ADV_ID/, /OB_ADV_ID\s*=\s*['"]([0-9a-f]{20,40})['"]/g],
    ['yandex', /\bym\(/, /\bym\(\s*(\d{5,10})\s*,\s*['"]init/g],
    ['google_ads', /AW-\d/, /\b(AW-\d{8,12})\b/g],
    ['floodlight', /DC-\d/, /\b(DC-\d{6,12})\b/g],
    ['quora', /qp\(/, /qp\(\s*['"]init['"]\s*,\s*['"]([0-9a-f]{20,40})['"]/g],
    ['adroll', /adroll_adv_id/, /adroll_adv_id\s*=\s*['"]([A-Z0-9]{10,30})['"]/g],
    ['hotjar', /hotjar|_hjSettings/, /hjid\s*:\s*(\d{4,10})/g],
    ['clarity', /clarity/, /clarity\.ms\/tag\/([a-z0-9]{6,12})/g],
    ['klaviyo', /klaviyo/, /klaviyo\.js\?company_id=([A-Za-z0-9]{6})/g],
    ['hubspot', /hs-scripts|_hsq/, /js\.hs-scripts\.com\/(\d+)\.js/g],
    ['activecampaign', /vgo\(/, /vgo\(\s*['"]setAccount['"]\s*,\s*['"](\d+)['"]/g],
  ];
  const UD = /^(ud|udff)\[|^(em|ph|email|user_email|hashed_email|sha256_email|sha256_email_address|external_id|phone|phone_number|u_hem|u_hpn)$/i;
  const EMAIL = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i;
  const reg = h => { const p = h.split('.'); return p.slice(/\.(co|com|org|net|gov|ac|edu)\.[a-z]{2}$/.test(h) ? -3 : -2).join('.'); };
  const site = reg(location.hostname);
  let mk = null; try { mk = JSON.parse(sessionStorage.getItem('__cookieAudit_consent') || 'null'); } catch (e) {}
  const sameDoc = !!mk && Math.abs(mk.origin - performance.timeOrigin) < 5;
  const phase = t => !mk ? null : (sameDoc ? (t < mk.t ? 'pre' : 'post') : 'post (pagina ricaricata dopo il consenso)');
  const dec = s => { try { return decodeURIComponent(s); } catch (e) { return s; } };
  const out = { url: location.href, consentMarker: mk ? { at: mk.at, sameDocument: sameDoc } : null,
    pixels: {}, inlineIds: {}, noscript: [], onePxImages: [], iframes: [], globals: {}, serverSide: [], unknownBeacons: [], otherHosts: {}, notes: [] };
  try { performance.setResourceTimingBufferSize(5000); } catch (e) {}
  let entries = performance.getEntriesByType('resource').map(e => [e, 0]), closed = 0;
  for (const fr of Array.from(window.frames)) {
    try { const off = fr.performance.timeOrigin - performance.timeOrigin; entries = entries.concat(fr.performance.getEntriesByType('resource').map(e => [e, off])); } catch (x) { closed++; }
  }
  if (closed) out.notes.push(`${closed} iframe di altri domini non leggibili: le loro chiamate non sono incluse (usa la lista rete del browser MCP)`);
  if (entries.length >= 250) out.notes.push('buffer delle richieste pieno prima della sonda: alcune chiamate possono mancare, confronta con la lista rete del browser MCP');
  if (!mk) out.notes.push('nessun marcatore di consenso: se la sonda gira prima di toccare il banner (Fase 1), TUTTE le chiamate elencate sono pre-consenso');
  const P = k => out.pixels[k] || (out.pixels[k] = { name: V.find(v => v.k === k).n, ids: [], events: [], hits: 0, scripts: 0, pre: 0, post: 0, firstMs: null, userData: [], emailInUrl: [], consent: [], integration: [], samples: [] });
  const add = (a, x) => { if (x && !a.includes(x) && a.length < 12) a.push(String(x).slice(0, 80)); };
  for (const [e, off] of entries) {
    let u; try { u = new URL(e.name); } catch (x) { continue; }
    const hp = u.hostname + u.pathname;
    const fp = reg(u.hostname) === site;
    const v = V.find(v => v.re.test(hp));
    if (!v) {
      if (fp && /(^|\/)(gtm\.js|gtag\/js)$/.test(u.pathname)) add(out.serverSide, `loader GTM servito dal dominio del sito: ${u.hostname}${u.pathname}`);
      else if (!fp && ['img', 'beacon', 'ping', 'other'].includes(e.initiatorType) && u.search.length > 30) add(out.unknownBeacons, `${u.hostname}${u.pathname.slice(0, 40)}`);
      if (!fp && (u.hostname in out.otherHosts || Object.keys(out.otherHosts).length < 40)) out.otherHosts[u.hostname] = (out.otherHosts[u.hostname] || 0) + 1;
      continue;
    }
    if (fp) add(out.serverSide, `${v.n} via dominio del sito (${u.hostname}): tagging lato server o proxy`);
    const p = P(v.k), q = u.searchParams, t = Math.round(e.startTime + off), ph = phase(t);
    const lib = /\.js$/.test(u.pathname) || /signals\/config\/|\/gtag\/js$|clarity\.ms\/tag\//.test(hp);
    if (lib) p.scripts++; else p.hits++;
    if (ph === 'pre') p.pre++; else if (ph) p.post++;
    if (p.firstMs === null || t < p.firstMs) p.firstMs = t;
    (v.id || []).forEach(k => add(p.ids, q.get(k)));
    if (v.idRe) { const m = (u.pathname + u.search).match(v.idRe); if (m) add(p.ids, m[1]); }
    (v.ev || []).forEach(k => {
      const val = q.get(k); if (!val) return;
      if (v.k === 'x') { try { JSON.parse(val).forEach(x => add(p.events, Array.isArray(x) ? x[0] : x)); } catch (z) { add(p.events, val); } }
      else add(p.events, val);
    });
    for (const [k, val] of q) {
      if (UD.test(k) && val) add(p.userData, k);
      if (v.k === 'pinterest' && k === 'pd' && /"em"|hashed/.test(val)) add(p.userData, 'pd.em');
      if (EMAIL.test(dec(val))) add(p.emailInUrl, k);
      if (['gcs', 'gcd', 'npa', 'dma', 'dma_cps', 'us_privacy'].includes(k)) {
        const g = k === 'gcs' ? (val.match(/^G1([01-])([01-])$/) || []) : [];
        add(p.consent, k === 'gcs' && g.length ? `gcs=${val} (ad_storage ${g[1] === '1' ? 'concesso' : g[1] === '0' ? 'negato' : 'n/d'}, analytics_storage ${g[2] === '1' ? 'concesso' : g[2] === '0' ? 'negato' : 'n/d'})` : `${k}=${val}`);
      }
      if (k === 'gdpr_consent' || k === 'gdpr') add(p.consent, `${k}=${k === 'gdpr' ? val : (val ? 'stringa TCF presente' : 'vuota')}`);
    }
    if (v.k === 'meta') { add(p.integration, q.get('a')); if (q.get('eid')) add(p.integration, 'eid (ID evento per deduplica con Conversions API)'); }
    if (p.samples.length < 2 && !lib) {
      const s = new URL(u.href); for (const k of [...s.searchParams.keys()]) if (UD.test(k) || EMAIL.test(dec(s.searchParams.get(k)))) s.searchParams.set(k, '…');
      p.samples.push(s.href.slice(0, 220));
    }
  }
  // Inline code, <noscript> fallbacks, 1×1 images, third-party iframes
  for (const s of document.querySelectorAll('script:not([src])')) {
    const txt = s.textContent || '';
    for (const [k, guard, rx] of C) if (guard.test(txt)) for (const m of txt.matchAll(rx)) add(out.inlineIds[k] || (out.inlineIds[k] = []), m[1]);
  }
  for (const n of document.querySelectorAll('noscript')) for (const m of (n.textContent || '').matchAll(/(?:https?:)?\/\/[^"'\s<>]+/g)) {
    const v = V.find(v => v.re.test(m[0].replace(/^(https?:)?\/\//, '').split('?')[0])); if (v) add(out.noscript, `${v.n}: ${m[0].slice(0, 140)}`);
  }
  for (const i of document.images) {
    if (!i.src || !/^https?:/.test(i.src)) continue;
    const a = x => i.getAttribute(x), small = x => a(x) === '0' || a(x) === '1';
    const tiny = (i.complete && i.naturalWidth > 0 && i.naturalWidth <= 1 && i.naturalHeight <= 1) || (small('width') && small('height'))
      || (getComputedStyle(i).display === 'none' && new URL(i.src).search.length > 10);
    let h; try { h = new URL(i.src).hostname; } catch (x) { continue; }
    if (tiny && reg(h) !== site) { const v = V.find(v => v.re.test(h + new URL(i.src).pathname)); add(out.onePxImages, `${v ? v.n : 'non classificato'}: ${h}`); }
  }
  for (const f of document.querySelectorAll('iframe[src]')) { try { const h = new URL(f.src).hostname; if (reg(h) !== site) add(out.iframes, h); } catch (x) {} }
  // Globals defined by the pixel libraries (IDs where the library exposes them)
  try { const st = window.fbq && fbq.getState && fbq.getState(); if (st && st.pixels) out.globals.meta = st.pixels.map(x => ({ id: x.id, integrazione: x.agent || null, userData: Object.keys(x.userData || {}).filter(k => x.userData[k]), campiModuli: Object.keys(x.userDataFormFields || {}).filter(k => x.userDataFormFields[k]) })); else if (window.fbq) out.globals.meta = 'fbq presente (stato non leggibile)'; } catch (e) {}
  try { if (window.ttq) out.globals.tiktok = Object.keys(window.ttq._i || {}); } catch (e) {}
  try { const li = [].concat(window._linkedin_data_partner_ids || [], window._linkedin_partner_id || []); if (li.length) out.globals.linkedin = li.map(String); } catch (e) {}
  try { if (window.google_tag_manager) out.globals.google_tag_manager = Object.keys(window.google_tag_manager).filter(k => /^(GTM|G|AW|DC|GT)-/.test(k)); } catch (e) {}
  ['pintrk', 'twq', 'uetq', 'snaptr', 'rdt', 'criteo_q', '_tfa', 'obApi', 'ym', 'qp', 'adroll_adv_id', 'AWIN', 'hj', 'clarity', 'TTDUniversalPixelApi',
   'klaviyo', '_learnq', '_hsq', 'vgo', 'sendinblue', 'Brevo', 'omnisend']
    .forEach(g => { try { if (window[g] !== undefined) out.globals[g] = typeof window[g]; } catch (e) {} });
  return out;
}
```

## §6 — Corpo delle richieste (pixel che inviano i dati in POST)
TikTok (`analytics.tiktok.com/api/v2/pixel`), Snap (`tr.snapchat.com`), LinkedIn (`px.ads.linkedin.com/wa/`) e talvolta Meta (`facebook.com/tr/` in POST) mettono evento e dati utente nel **corpo**, che §5 non vede. Con chrome-devtools: `list_network_requests` (filtra per quei domini) → `get_network_request` sul singolo `reqid` → leggi il corpo. Cerca:
- nome dell'evento e ID del pixel (in TikTok il pixel code);
- **campi utente**: `email`, `phone`/`phone_number`, `external_id`, anche con prefissi `sha256_`/`hashed_`; in Snap campi come `u_hem` (email con hash) e `u_hpn` (telefono con hash);
- URL e titolo della pagina inviati: rivelano contenuti sensibili (salute, orientamenti, ecc.)?

Con claude-in-chrome `read_network_requests` riporta solo URL, metodo e stato: per il corpo serve chrome-devtools. Nel report indica solo i **nomi** dei campi, mai i valori.

## §7 — Modulo di iscrizione alla newsletter (informativa e consenso)
Per i siti con newsletter: cosa viene detto e chiesto PRIMA di raccogliere l'indirizzo (Linee guida Garante sui tracking pixel nelle e-mail, §4 e §6). Apri la pagina con il modulo (footer, pop-up, pagina «newsletter») ed esegui:

```js
() => {
  const TRACK = /pixel|tracciament|tracking|apertur|traccia/i;
  const PROVIDER = /list-manage\.com|sibforms\.com|brevo|mailup|mlsend|mailerlite|klaviyo|hsforms|hubspot|activehosted|getresponse|createsend|mailjet|zcsend|maillist-manage|convertkit|substack|beehiiv|mailpoet|newsletter/i;
  const vis = el => { const r = el.getBoundingClientRect(), s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const forms = [...document.querySelectorAll('form')].filter(f => f.querySelector('input[type="email"], input[name*="mail" i]'));
  const ctx = el => { let n = el; for (let i = 0; i < 3 && n; i++) { n = n.parentElement; const t = n && (n.innerText || '').replace(/\s+/g, ' ').trim(); if (t && t.length > 40) return t.slice(0, 500); } return ''; };
  const out = forms.slice(0, 6).map(f => {
    const text = (f.innerText || '').replace(/\s+/g, ' ').trim(), around = ctx(f);
    const email = f.querySelector('input[type="email"], input[name*="mail" i]');
    return {
      action: (f.action || '').slice(0, 160), visibile: vis(f),
      piattaforma: ((f.action || '').match(PROVIDER) || [''])[0],
      caselle: [...f.querySelectorAll('input[type="checkbox"]')].map(c => {
        const l = c.closest('label') || (c.id && f.querySelector(`label[for="${CSS.escape(c.id)}"]`)) || c.parentElement;
        return { testo: ((l && l.innerText) || '').replace(/\s+/g, ' ').trim().slice(0, 300), preselezionata: c.defaultChecked || c.checked, obbligatoria: c.required, name: c.name || '' };
      }),
      segnaposto: (email && email.placeholder) || '',
      pulsante: [...f.querySelectorAll('button, input[type="submit"]')].map(b => (b.innerText || b.value || '').trim()).filter(Boolean).slice(0, 3),
      citaTracciamento: TRACK.test(text + ' ' + around),
      linkInformativa: [...f.querySelectorAll('a[href]')].filter(a => /privacy|informativa|cookie/i.test(a.innerText + a.href)).map(a => ({ testo: a.innerText.trim().slice(0, 60), href: a.href })).slice(0, 5),
      testo: text.slice(0, 700),
      contesto: text.length > 40 ? '' : around
    };
  });
  const iframes = [...document.querySelectorAll('iframe[src]')].map(i => i.src).filter(u => PROVIDER.test(u)).slice(0, 5);
  return { moduli: out, iframeModuli: iframes, nota: out.length ? '' : 'nessun modulo con campo email in pagina: cerca pop-up (dopo qualche secondo o allo scroll), pagina dedicata o iframe' };
}
```

Valuta: informativa sintetica nel modulo con link a quella estesa (§4); se il tracciamento delle aperture si basa sul consenso, il testo della casella deve dirlo — il consenso al tracciamento può essere unico con quello al marketing, ma formulato in modo neutro (§6); nessuna casella **preselezionata**; consenso al marketing non obbligatorio per servizi diversi. Se il modulo sta in un iframe del fornitore (`iframeModuli`), apri quell'URL e ripeti la sonda.
