"""Debug script: inspect the prescrizione form on avvocatoandreani.it.

Run: cd /path/to/mcp-legal-it && .venv/bin/python tests/comparison/debug_prescrizione.py
"""

from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        url = "https://www.avvocatoandreani.it/servizi/calcolo-prescrizione-reati.php"
        print(f"Navigating to {url}")
        page.goto(url, timeout=15000)
        page.wait_for_load_state("networkidle")

        # Remove cookie overlay
        page.evaluate(
            'document.querySelectorAll("#qc-cmp2-container, .qc-cmp2-container").forEach(el => el.remove())'
        )
        page.wait_for_timeout(1000)

        # Check frames
        print(f"\n--- FRAMES ({len(page.frames)}) ---")
        for i, frame in enumerate(page.frames):
            print(f"  Frame {i}: url={frame.url[:120]}")

        # Determine form context
        ctx = page
        for frame in page.frames:
            if "utility.php" in frame.url or "calcolo-prescrizione" in frame.url:
                ctx = frame
                print(f"\n>>> Using frame: {frame.url[:120]}")
                break
        if ctx is page:
            iframe_el = page.query_selector("iframe")
            if iframe_el:
                f = iframe_el.content_frame()
                if f:
                    ctx = f
                    print(f"\n>>> Using iframe content_frame: {f.url[:120]}")

        # Dump all select elements
        print("\n--- SELECT ELEMENTS ---")
        selects = ctx.query_selector_all("select")
        for sel in selects:
            name = sel.get_attribute("name") or "(no name)"
            options = sel.query_selector_all("option")
            vals = []
            for opt in options[:5]:
                v = opt.get_attribute("value")
                t = opt.inner_text().strip()
                vals.append(f"value='{v}' text='{t}'")
            if len(options) > 5:
                last = options[-1]
                vals.append(f"... ({len(options)} total) ... last: value='{last.get_attribute('value')}' text='{last.inner_text().strip()}'")
            print(f"  <select name='{name}'> options: {vals}")

        # Dump buttons and inputs
        print("\n--- BUTTONS/INPUTS ---")
        for sel in ["input[type='submit']", "input[type='button']", "button", "input[name='Operazione']", ".btn-calc", "#btn-calc"]:
            els = ctx.query_selector_all(sel)
            for el in els:
                tag = el.evaluate("el => el.outerHTML")
                print(f"  [{sel}] {tag[:200]}")

        # Try to fill form
        print("\n--- FILLING FORM ---")
        try:
            ctx.select_option("select[name='GiornoReato']", "15")
            print("  GiornoReato='15' OK")
        except Exception as e:
            print(f"  GiornoReato='15' FAIL: {e}")
            try:
                ctx.select_option("select[name='GiornoReato']", label="15")
                print("  GiornoReato label='15' OK")
            except Exception as e2:
                print(f"  GiornoReato label='15' FAIL: {e2}")

        try:
            ctx.select_option("select[name='MeseReato']", label="Gennaio")
            print("  MeseReato label='Gennaio' OK")
        except Exception as e:
            print(f"  MeseReato label='Gennaio' FAIL: {e}")
            try:
                ctx.select_option("select[name='MeseReato']", "01")
                print("  MeseReato='01' OK")
            except Exception as e2:
                print(f"  MeseReato='01' FAIL: {e2}")

        try:
            ctx.select_option("select[name='AnnoReato']", "2018")
            print("  AnnoReato='2018' OK")
        except Exception as e:
            print(f"  AnnoReato='2018' FAIL: {e}")

        try:
            ctx.select_option("select[name='TipoPena']", label="Reclusione")
            print("  TipoPena label='Reclusione' OK")
        except Exception as e:
            print(f"  TipoPena label='Reclusione' FAIL: {e}")

        try:
            ctx.select_option("select[name='PenaEdittale']", "6")
            print("  PenaEdittale='6' OK")
        except Exception as e:
            print(f"  PenaEdittale='6' FAIL: {e}")

        # Try clicking submit
        print("\n--- SUBMIT ---")
        for sel in [
            "input[name='Operazione'][value='Calcola']",
            "input[type='submit']",
            "input[type='button'][value='Calcola']",
            "button:has-text('Calcola')",
            "a:has-text('Calcola')",
            "#btn-calc",
            ".btn-calc",
        ]:
            try:
                el = ctx.query_selector(sel)
                if el:
                    print(f"  Found: [{sel}] -> {el.evaluate('e => e.outerHTML')[:150]}")
                    el.click(force=True)
                    print(f"  Clicked [{sel}]")
                    page.wait_for_timeout(3000)
                    break
            except Exception as e:
                print(f"  [{sel}] error: {e}")
        else:
            print("  No submit button found with known selectors!")
            # Last resort: find anything with 'Calcola' text
            all_els = ctx.query_selector_all("*")
            for el in all_els:
                try:
                    txt = el.inner_text()
                    if "Calcola" in txt and len(txt) < 30:
                        tag = el.evaluate("e => e.tagName + ' ' + e.outerHTML.substring(0,150)")
                        print(f"  Found 'Calcola' in: {tag}")
                except Exception:
                    pass

        # Dump results
        print("\n--- RESULT BODY (first 2000 chars) ---")
        body = ctx.inner_text("body")
        print(body[:2000])

        # Take screenshot
        page.screenshot(path="/tmp/prescrizione_debug.png", full_page=True)
        print("\nScreenshot saved to /tmp/prescrizione_debug.png")

        browser.close()


if __name__ == "__main__":
    main()
