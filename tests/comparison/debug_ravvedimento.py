"""Debug script: dump form structure and test submission on avvocatoandreani.it ravvedimento page.

Run: cd /path/to/mcp-legal-it && .venv/bin/python tests/comparison/debug_ravvedimento.py
"""

from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        url = "https://www.avvocatoandreani.it/servizi/calcolo-ravvedimento-operoso.php"
        print(f"Navigating to {url}")
        page.goto(url, timeout=15000)
        page.wait_for_load_state("networkidle")

        # Remove cookie overlay
        page.evaluate(
            'document.querySelectorAll("#qc-cmp2-container, .qc-cmp2-container").forEach(el => el.remove())'
        )
        page.wait_for_timeout(1000)

        # --- Dump all select elements ---
        selects = page.evaluate("""() => {
            const result = [];
            document.querySelectorAll('select').forEach(sel => {
                const opts = [];
                sel.querySelectorAll('option').forEach(opt => {
                    opts.push({value: opt.value, text: opt.textContent.trim()});
                });
                result.push({
                    name: sel.name,
                    id: sel.id,
                    optionCount: opts.length,
                    firstOptions: opts.slice(0, 8),
                    lastOptions: opts.slice(-3),
                });
            });
            return result;
        }""")

        print("\n=== SELECT ELEMENTS ===")
        for sel in selects:
            print(f"\nname={sel['name']!r} id={sel['id']!r} ({sel['optionCount']} options)")
            print(f"  First options: {sel['firstOptions']}")
            if sel['lastOptions']:
                print(f"  Last options:  {sel['lastOptions']}")

        # --- Dump all input elements ---
        inputs = page.evaluate("""() => {
            const result = [];
            document.querySelectorAll('input').forEach(inp => {
                result.push({
                    name: inp.name, id: inp.id, type: inp.type,
                    value: inp.value, placeholder: inp.placeholder,
                });
            });
            return result;
        }""")

        print("\n=== INPUT ELEMENTS ===")
        for inp in inputs:
            print(f"  name={inp['name']!r} id={inp['id']!r} type={inp['type']!r} value={inp['value']!r}")

        # --- Dump all buttons ---
        buttons = page.evaluate("""() => {
            const result = [];
            document.querySelectorAll('button, input[type=submit], input[type=button], [role=button]').forEach(btn => {
                result.push({
                    tag: btn.tagName, id: btn.id, type: btn.type,
                    text: btn.textContent?.trim().slice(0, 50),
                    className: btn.className?.slice(0, 80),
                    onclick: btn.getAttribute('onclick')?.slice(0, 100),
                    name: btn.name,
                });
            });
            return result;
        }""")

        print("\n=== BUTTONS ===")
        for btn in buttons:
            print(f"  tag={btn['tag']} id={btn['id']!r} type={btn['type']!r} name={btn.get('name', '')!r} class={btn['className']!r}")
            print(f"    text={btn['text']!r} onclick={btn.get('onclick')!r}")

        # --- Check for #create specifically ---
        create_el = page.evaluate("""() => {
            const el = document.querySelector('#create');
            if (!el) return null;
            return {
                tag: el.tagName, type: el.type, name: el.name,
                visible: el.offsetParent !== null,
                text: el.textContent?.trim().slice(0, 50),
                className: el.className?.slice(0, 80),
            };
        }""")
        print(f"\n=== #create element ===\n  {create_el}")

        # --- Try filling form and submitting ---
        print("\n=== ATTEMPTING FORM FILL ===")
        try:
            page.select_option("select[name='IdTributo']", "1_2")
            print("  IdTributo -> 1_2 OK")
        except Exception as e:
            print(f"  IdTributo FAILED: {e}")

        try:
            page.fill("input[name='Importo']", "1000")
            print("  Importo -> 1000 OK")
        except Exception as e:
            print(f"  Importo FAILED: {e}")

        # Scadenza: 2024-06-16
        for name, val in [("GiornoScad", "16"), ("MeseScad", "06"), ("AnnoScad", "2024")]:
            try:
                page.select_option(f"select[name='{name}']", val)
                print(f"  {name} -> {val} OK")
            except Exception as e:
                print(f"  {name} -> {val} FAILED: {e}")

        # Ravvedimento: 2024-07-16
        for name, val in [("GiornoRavv", "16"), ("MeseRavv", "07"), ("AnnoRavv", "2024")]:
            try:
                page.select_option(f"select[name='{name}']", val)
                print(f"  {name} -> {val} OK")
            except Exception as e:
                print(f"  {name} -> {val} FAILED: {e}")

        # Screenshot before submit
        page.screenshot(path="/tmp/ravvedimento_before_submit.png", full_page=True)
        print("  Screenshot saved: /tmp/ravvedimento_before_submit.png")

        # Try submit
        print("\n=== ATTEMPTING SUBMIT ===")
        try:
            page.click("#create", force=True)
            page.wait_for_load_state("load")
            page.wait_for_timeout(3000)
            print("  Submit OK")
        except Exception as e:
            print(f"  Submit via #create FAILED: {e}")
            # Try alternatives
            for sel in ['button[type=submit]', 'input[type=submit]', '.btn-calc', '#btn-calc', 'button.btn']:
                try:
                    page.click(sel, force=True)
                    page.wait_for_load_state("load")
                    page.wait_for_timeout(2000)
                    print(f"  Submit via {sel} OK")
                    break
                except Exception:
                    pass

        # Screenshot after submit
        page.screenshot(path="/tmp/ravvedimento_after_submit.png", full_page=True)
        print("  Screenshot saved: /tmp/ravvedimento_after_submit.png")

        # Dump body text after submit
        body = page.inner_text("body")
        print(f"\n=== BODY TEXT (first 2000 chars) ===\n{body[:2000]}")

        # Check URL after submit
        print(f"\n=== CURRENT URL ===\n{page.url}")

        browser.close()


if __name__ == "__main__":
    main()
