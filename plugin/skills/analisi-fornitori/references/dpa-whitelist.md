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
| PayPal | https://www.paypal.com/legalhub/paypal/dataprotection-full |
| Shopify | https://www.shopify.com/legal/dpa |
| Mailchimp (Intuit) | https://mailchimp.com/legal/data-processing-addendum/ |
| HubSpot | https://legal.hubspot.com/dpa |
| Salesforce | https://www.salesforce.com/company/legal/agreements/ |
| Zoom | https://explore.zoom.us/en/gdpr/ |
| Dropbox | https://www.dropbox.com/security/GDPR |
| Slack | https://slack.com/intl/it-it/terms-of-service/data-processing |
| Atlassian | https://www.atlassian.com/legal/data-processing-addendum |
| Aruba | https://www.aruba.it/documenti-contrattuali.aspx (atto di nomina nei documenti contrattuali) |
| Register.it | https://www.register.it/company/legal/ |
| TeamSystem | https://www.teamsystem.com/legal (condizioni servizi cloud) |
| Zucchetti | https://www.zucchetti.it/website/cms/privacy.html (addendum servizi SaaS) |

PMI locale / fornitore non in lista e senza DPA pubblicato → quasi sempre
`dpa_proprio: "no"` (serve la nomina del titolare, tool `genera_dpa`).
Nel dubbio: `da_verificare`.
