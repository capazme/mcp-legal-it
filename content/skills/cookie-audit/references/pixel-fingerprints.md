# Fingerprint — pixel, beacon e tracciamento delle piattaforme email

Tabella di riferimento per leggere i risultati della sonda §5 (`browser-probes.md`), di `scripts/inspect_container.py` e della lista rete. Le chiavi (`meta`, `tiktok`, …) sono le stesse nei due strumenti. Un pixel è uno strumento di tracciamento **anche quando non scrive cookie**: conta la chiamata che trasmette dati dal terminale al fornitore.

## Pixel di marketing sul sito

| Chiave | Strumento | Libreria / endpoint | ID (dove e formato) | Cookie tipici (verificali sempre nel browser) |
|--------|-----------|---------------------|---------------------|---------------|
| `meta` | Meta Pixel | `connect.facebook.net/<lingua>/fbevents.js`, `connect.facebook.net/signals/config/<ID>`, `www.facebook.com/tr` | `id=` · 15-16 cifre · `fbq('init','<ID>')` | `_fbp`, `_fbc` (90 gg); `fr` su facebook.com |
| `tiktok` | TikTok Pixel | `analytics.tiktok.com/i18n/pixel/events.js?sdkid=`, `analytics.tiktok.com/api/v2/pixel` (POST) | `sdkid=` · 20 caratteri maiuscoli/cifre · `ttq.load('<CODE>')` | `_ttp` |
| `linkedin` | LinkedIn Insight Tag | `snap.licdn.com/li.lms-analytics/insight.min.js`, `px.ads.linkedin.com/collect` e `/wa/` (POST) | `pid=` · `_linkedin_partner_id` | `li_fat_id`; su linkedin.com `bcookie`, `lidc`, `UserMatchHistory` |
| `pinterest` | Pinterest Tag | `s.pinimg.com/ct/core.js`, `ct.pinterest.com/v3/` | `tid=` · 13 cifre · `pintrk('load','<ID>')` | `_pin_unauth`, `_epik`, `_derived_epik` |
| `x` | X (Twitter) Pixel | `static.ads-twitter.com/uwt.js`, `analytics.twitter.com/i/adsct`, `t.co/i/adsct` | `txn_id=` · `twq('config','<ID>')` | `_twclid`; su x.com `muc_ads`, `personalization_id` |
| `microsoft` | Microsoft Advertising UET | `bat.bing.com/bat.js`, `bat.bing.com/action/0` | `ti=` · `ti:"<ID>"` | `_uetsid` (1 g), `_uetvid` (13 mesi); `MUID` su bing.com |
| `snap` | Snap Pixel | `sc-static.net/scevent.min.js`, `tr.snapchat.com` (POST) | UUID in `snaptr('init','<ID>')` | `_scid` |
| `reddit` | Reddit Pixel | `redditstatic.com/ads/pixel.js`, `alb.reddit.com/rp.gif` | `id=` · `t2_…`/`a2_…` · `rdt('init','<ID>')` | `_rdt_uuid` |
| `criteo` | Criteo OneTag | `dynamic.criteo.com/js/ld/ld.js?a=`, `sslwidget.criteo.com`, `gum.criteo.com` (sincronizzazione utenti) | `a=` · account numerico | `cto_bundle`; `uid` su criteo.com |
| `taboola` | Taboola Pixel | `cdn.taboola.com/libtrc/unip/<ID>/tfa.js`, `trc.taboola.com` | numero nel percorso · `_tfa.push({…id:<ID>})` | `t_gid` su taboola.com |
| `outbrain` | Outbrain Pixel | `amplify.outbrain.com/cp/obtp.js`, `tr.outbrain.com/unifiedPixel` | `marketerId=` · `OB_ADV_ID` | `obuid` su outbrain.com |
| `google_ads` | Google Ads (conversioni, remarketing) | `googleadservices.com/pagead/conversion/<ID>`, `googleads.g.doubleclick.net/pagead/viewthroughconversion/<ID>`, `google.<tld>/pagead/1p-user-list/<ID>`, `google.<tld>/ccm/collect` | `AW-` + 8-12 cifre | `_gcl_au`, `_gcl_aw`; `IDE` su doubleclick.net |
| `floodlight` | Floodlight (CM360/DV360) | `ad.doubleclick.net/activity;src=<ID>;…`, `fls.doubleclick.net` | `DC-` + cifre · `src=` | `IDE`, `_gcl_dc` |
| `yandex` | Yandex Metrica | `mc.yandex.ru/metrika/tag.js`, `mc.yandex.ru/watch/<ID>` | `ym(<ID>,'init')` | `_ym_uid`, `_ym_d` — **trasferimento in Russia** |
| `quora` · `adroll` · `amazon` · `adform` | Quora Pixel · AdRoll · Amazon Ads · Adform | `q.quora.com` · `d.adroll.com` · `amazon-adsystem.com` · `track.adform.net` | `qp('init',…)` · `adroll_adv_id` · `pid=` · `pm=` | vari, di terza parte |
| `thetradedesk` · `teads` · `rtbhouse` | The Trade Desk · Teads · RTB House | `adsrvr.org` · `teads.tv` · `creativecdn.com` | `adv=` · `buyer_pixel_id` · `id=` | di terza parte |
| `awin` · `tradedoubler` | Affiliazione | `dwin1.com/<ID>.js` · `tbs.tradedoubler.com` | ID inserzionista | cookie dell'affiliazione (es. `awc`) |
| `hotjar` · `clarity` | Registrazione delle sessioni | `static.hotjar.com` · `clarity.ms/tag/<ID>` | `hjid` · ID progetto | `_hj*` · `_clck`, `_clsk` |
| `stape` | Tagging lato server (server GTM) | `stapecdn.com`, sottodomini del sito | — | cookie di prima parte impostati dal server |
| `ga4` | Google Analytics 4 (solo per i segnali di consenso) | `…/g/collect` (anche su sottodominio del sito = lato server) | `tid=G-…` | `_ga`, `_ga_<ID>` |

**Pixel generico**: immagine 1×1 (o nascosta) verso un dominio terzo con una query string lunga, oppure `navigator.sendBeacon`. Se il dominio non è in tabella, la sonda lo elenca in `unknownBeacons` / `onePxImages`: va qualificato a mano.

## Piattaforme email sul sito (il ponte newsletter → sito)
Le piattaforme di invio installano spesso uno script sul sito che riconosce chi arriva da un link della newsletter e ne registra la navigazione (prodotti visti, carrello, «attivo sul sito»): è il punto in cui il tracciamento della newsletter si salda a quello del sito.

| Chiave | Piattaforma | Script / endpoint sul sito | Parametro che arriva dai link della newsletter | Cookie |
|--------|-------------|----------------------------|-----------------------------------------------|--------|
| `klaviyo` | Klaviyo | `static.klaviyo.com/onsite/js/klaviyo.js?company_id=`, `a.klaviyo.com` | `_kx` | `__kla_id` |
| `hubspot` | HubSpot | `js.hs-scripts.com/<ID>.js`, `track.hubspot.com/__ptq.gif` | `_hsenc`, `_hsmi` | `hubspotutk`, `__hstc`, `__hssc` |
| `mailchimp` | Mailchimp (sito collegato) | `chimpstatic.com/mcjs-connected/js/users/<ID>/…` | `mc_eid` (destinatario), `mc_cid` (campagna) | — |
| `activecampaign` | ActiveCampaign | `diffuser-cdn.app-us1.com`, `trackcmp.net/visit` | `vgo_ee` (email codificata) | `prism_*` |
| `brevo` | Brevo (ex Sendinblue) | `sibautomation.com/sa.js`, `cdn.brevo.com` | — | `sib_cuid` |
| `omnisend` | Omnisend | `omnisnippet1.com`, `omnisrv.com` | `omnisendContactID` | `omnisendContactID` |

## Segnali di consenso nelle chiamate
- **`gcs`** (Google): `G1` + due cifre: la prima è `ad_storage`, la seconda `analytics_storage` (`1` concesso, `0` negato, `-` non impostato). `G100` = tutto negato: se la chiamata parte comunque, è un **ping senza cookie** della Consent Mode «avanzata».
- **`gcd`** (Google): codifica estesa dei quattro segnali di Consent Mode v2; **`npa=1`**: annunci non personalizzati; **`dma`/`dma_cps`**: segnali del Digital Markets Act.
- **`gdpr=1` + `gdpr_consent=`**: stringa IAB TCF passata al fornitore (la sonda ne segnala solo la presenza).
- **Meta**: il parametro `a=` indica l'integrazione che ha installato il pixel (plugin di e-commerce, modello GTM, partner); `eid=` è l'ID evento usato per deduplicare con la **Conversions API** (invio anche dal server).

## Tipi di tag nel container GTM (`inspect_container.py`)
`__awct` conversioni Google Ads · `__sp` remarketing Google Ads · `__awud` evento con dati forniti dall'utente · `__gclidw` Conversion Linker · `__flc`/`__fls` Floodlight · `__baut` Microsoft UET · `__bzi` LinkedIn Insight · `__twitter_website_tag` X · `__pntr` Pinterest · `__crto` Criteo · `__qpx` Quora · `__asp` AdRoll · `__awc`/`__awj` Awin · `__qcm` Quantcast · `__hjtc` Hotjar · `__img` immagine personalizzata (pixel generico) · `__html` HTML personalizzato · `__cvt_…` modello della galleria (il fornitore si riconosce dai domini e dalle variabili globali dichiarati nei permessi del modello) · `__paused` tag in pausa.

**Condizioni di consenso nel container**: le regole di attivazione di un tag sono alternative — il tag è legato al consenso solo se lo sono tutte, o se lo blocca una regola di eccezione sul consenso, o se ha i controlli di consenso di GTM. Contano le variabili che contengono la scelta (cookie della CMP come `OptanonConsent`/`CookieConsent`/`cmplz_*`, `dataLayer.OnetrustActiveGroups`…) e gli eventi che significano un'accettazione (`cookie_consent_marketing`, `CookiebotOnAccept`…); non bastano «Consent Initialization» (`gtm.init_consent`, parte prima di tutto), gli eventi della CMP inviati a ogni caricamento (`OneTrustGroupsUpdated`, `consent_update`) né parole come «marketing» in un URL. Anche con una condizione corretta, alla prima visita il cookie della CMP può non esistere ancora: conferma sempre in browser.

**Opzioni di consenso dei modelli — attenzione**: nel modello Meta della galleria `consent = true` **non** è un filtro: invia sempre `fbq('consent','grant')`. È un vincolo solo se il valore viene da una variabile (lo stato della CMP) o se il tag ha i «controlli di consenso aggiuntivi» di GTM (`consenso richiesto in GTM: ad_storage…`).

## Configurazione pubblicata dal fornitore (`inspect_pixel_config.py`)
Solo **Meta** pubblica una configurazione per pixel leggibile in modo affidabile (`connect.facebook.net/signals/config/<ID>`): Advanced Matching automatico e campi letti dai moduli (`em` email, `ph` telefono, `fn`/`ln` nome e cognome, `ge` genere, `db` data di nascita, `zp`/`ct`/`st`/`country` indirizzo, `external_id`), eventi automatici, parametri che Meta filtra come indesiderati. Il loader TikTok restituisce gli stessi flag per qualunque codice, anche inventato: per TikTok l'evidenza è il corpo delle richieste (§6 delle sonde).
