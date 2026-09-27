"""Render every golden diagram in real mermaid v11; screenshot for visual review."""
import json
import sys

from playwright.sync_api import sync_playwright

ids = sys.argv[1:] or ["pytorch", "openclaw", "requests"]
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 900})
    pg.set_content("<html><body style='background:#0c0f14'><div id=h></div></body></html>")
    pg.add_script_tag(url="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js")
    pg.evaluate("mermaid.initialize({startOnLoad:false, theme:'dark'})")
    for gid in ids:
        doc = json.load(open(f"src/storage/golden_fixtures/{gid}.json"))
        for k in ("hld_mermaid", "lld_mermaid", "flow_mermaid"):
            v = pg.evaluate(
                """async (c) => { try { const r = await mermaid.render('x'+Math.floor(Math.random()*1e6), c);
                   document.getElementById('h').innerHTML = r.svg; return 'OK'; }
                   catch(e){ return 'FAIL: ' + String((e&&e.message)||e).slice(0,200); } }""",
                doc[k],
            )
            print(gid, k, v, flush=True)
            if v == "OK":
                pg.locator("#h").screenshot(path=f"/tmp/g_{gid}_{k}.png")
    b.close()
