"""Debug script: inspect pignoramento stipendio calculator at avvocatoandreani.it."""

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    url = "https://www.avvocatoandreani.it/servizi/calcolo-pignoramento-stipendio-pensione.php"
    resp = page.goto(url, timeout=15000)
    print(f"URL: {url} -> status={resp.status}")

    page.wait_for_load_state("networkidle")

    # List all form fields
    fields = page.evaluate('''() => {
        const fields = [];
        document.querySelectorAll("input, select, button").forEach(el => {
            const opts = [];
            if (el.tagName === "SELECT") {
                el.querySelectorAll("option").forEach(o => {
                    opts.push({value: o.value, text: o.textContent.trim()});
                });
            }
            fields.push({
                tag: el.tagName,
                name: el.name || "",
                id: el.id || "",
                type: el.type || "",
                value: el.value || "",
                className: el.className || "",
                text: el.textContent?.trim()?.substring(0, 50) || "",
                options: opts.length ? opts : undefined,
            });
        });
        return fields;
    }''')
    for f in fields:
        print(f"  {f}")

    # Check for any clickable calc buttons
    buttons = page.evaluate('''() => {
        const result = [];
        document.querySelectorAll("button, input[type=submit], input[type=button], [onclick], .btn, [id*=calc], [id*=Calc], [class*=calc], [class*=Calc]").forEach(el => {
            result.push({
                tag: el.tagName,
                id: el.id,
                className: el.className,
                text: el.textContent?.trim()?.substring(0, 80),
                type: el.type,
                onclick: el.getAttribute("onclick")?.substring(0, 80),
            });
        });
        return result;
    }''')
    print("\n--- Buttons / Clickable elements ---")
    for b in buttons:
        print(f"  {b}")

    # Try filling form and triggering calc
    page.select_option("select[name='TipoImporto']", "1")  # Stipendio
    page.fill("input[name='Importo']", "2000")
    page.select_option("select[name='FreqImporto']", "mensile")
    page.select_option("select[name='Mensilita']", "12")
    page.select_option("select[name='AccreditoConto']", "No")
    page.select_option("select[name='CreditoAlimentare']", "No")
    page.select_option("select[name='TipoCreditore']", "Ordinario")
    page.wait_for_timeout(2000)

    # Check page text for any results
    body = page.inner_text("body")
    print("\n--- Full body text (last 2000 chars) ---")
    print(body[-2000:])

    browser.close()
