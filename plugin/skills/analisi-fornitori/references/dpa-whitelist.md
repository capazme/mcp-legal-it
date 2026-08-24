# Whitelist DPA — fornitori con DPA proprio standard

Per i RESPONSABILI: se il fornitore mette a disposizione un proprio DPA
standard (tipicamente incorporato nei termini di servizio), impostare
`dpa_proprio: "si"` — di norma NON serve una nomina del titolare, ma va
verificato che il DPA sia effettivamente accettato/richiamato nel contratto.
Verificare sempre la versione vigente al link.

| Fornitore | DPA |
|-----------|-----|
| Google (Workspace, Cloud, Ads) | https://business.safety.google/adsprocessorterms/ e https://cloud.google.com/terms/data-processing-addendum |
| Microsoft (365, Azure) | https://www.microsoft.com/licensing/docs/view/Microsoft-Products-and-Services-Data-Protection-Addendum-DPA |
| Amazon AWS | https://aws.amazon.com/it/compliance/gdpr-center/ |
| Meta (Business Tools) | https://www.facebook.com/legal/terms/dataprocessing |
| LinkedIn | https://www.linkedin.com/legal/l/dpa |
| Stripe | https://stripe.com/legal/dpa |
| PayPal | https://www.paypal.com/us/legalhub/paypal/data-protection |
| Shopify | https://www.shopify.com/legal/dpa |
| Mailchimp (Intuit) | https://mailchimp.com/legal/data-processing-addendum/ |
| HubSpot | https://legal.hubspot.com/dpa |
| Salesforce | https://www.salesforce.com/en-us/wp-content/uploads/sites/4/documents/legal/Agreements/data-processing-addendum.pdf |
| Zoom | https://www.zoom.com/en/trust/gdpr/ |
| Dropbox | https://www.dropbox.com/security/GDPR |
| Slack | https://slack.com/intl/it-it/terms-of-service/data-processing |
| Atlassian | https://www.atlassian.com/legal/data-processing-addendum |
| Aruba | https://www.aruba.it/termini-condizioni.aspx (NON pubblica un DPA autonomo: la nomina è una clausola interna alle condizioni generali del singolo servizio — es. art. 21 Sez. I Aruba Cloud. Verificare il servizio effettivamente acquistato) |
| Register.it | https://www.register.it/company/legal/ |
| TeamSystem | https://www.teamsystem.com/dpa/ (MDPA + schede "condizioni speciali" per singolo prodotto) |
| Zucchetti | https://www.zucchetti.com/privacy/Data_Processing_Agreement.pdf (designazione a responsabile ex art. 28; il registro del trattamento del servizio è nell'area riservata) |

PMI locale / fornitore non in lista e senza DPA pubblicato → quasi sempre
`dpa_proprio: "no"` (serve la nomina del titolare, tool `legal-it:genera_dpa`).
Nel dubbio: `da_verificare`.

**Attenzione**: una pagina che parla di GDPR non è un DPA. Prima di impostare
`dpa_proprio: "si"` il link deve portare a un testo contrattuale che designa il
fornitore responsabile ex art. 28 — non all'informativa privacy del sito, non a
una pagina divulgativa sulla conformità. È l'errore che ha tenuto in lista per
mesi due voci sbagliate (Zucchetti puntava alla propria informativa; TeamSystem
a un hub che redirigeva su una pagina prodotto).

Link verificati uno per uno il 30/07/2026 (status HTTP + presenza effettiva del
documento). Meta risponde 400 ai client non-browser: la pagina è valida, va
controllata da browser.
