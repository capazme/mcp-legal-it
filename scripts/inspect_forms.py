"""Script to inspect form fields on avvocatoandreani.it pages."""
from playwright.sync_api import sync_playwright

JS_CODE = """() => {
    const result = [];
    document.querySelectorAll('input, select').forEach(el => {
        if (el.type !== 'hidden') {
            result.push({
                tag: el.tagName,
                type: el.type || '',
                name: el.name || '',
                id: el.id || '',
            });
        }
    });
    return result;
}"""

pages = [
    'calcolo_danno_biologico.php',
    'calcolo_quote_ereditarie.php',
    'calcolo-prescrizione-reati.php',
    'calcolo-compenso-avvocati-parametri-civili-2014.php',
    'calcolo_pignoramento_stipendio_pensione.php',
    'calcolo-ravvedimento-operoso.php',
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for path in pages:
        ctx = browser.new_context()
        page = ctx.new_page()
        try:
            url = f'https://www.avvocatoandreani.it/servizi/{path}'
            page.goto(url, timeout=15000)
            page.wait_for_load_state('networkidle')
            page.wait_for_timeout(2000)

            fields = page.evaluate(JS_CODE)

            print(f'\n=== {path} ===')
            for f in fields:
                if f['name'] and f['type'] not in ('password',):
                    print(f"  {f['tag']} type={f['type']} name={f['name']} id={f['id']}")
        except Exception as e:
            print(f'\n=== {path} === ERROR: {e}')
        finally:
            page.close()
            ctx.close()
    browser.close()
