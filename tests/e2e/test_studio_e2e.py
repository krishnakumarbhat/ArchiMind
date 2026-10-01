"""E2E studio workflows: landing -> golden workspace -> 5 tabs -> guardrail.

Skips cleanly without chromium (CI without browsers still passes).
"""
import threading

import pytest
from werkzeug.serving import make_server

pw = pytest.importorskip("playwright.sync_api", reason="playwright not installed")

VIEWPORTS = [(390, 844, "mobile"), (768, 1024, "tablet"), (1440, 900, "desktop"), (2560, 1440, "ultrawide")]


@pytest.fixture(scope="module")
def server():
    """Serve the Flask app in-process."""
    from app import create_app, db

    app = create_app()
    app.config.update(TESTING=True)
    with app.app_context():
        db.create_all()
    httpd = make_server("127.0.0.1", 5125, app)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:5125"
    httpd.shutdown()


def _browser(p):
    try:
        return p.chromium.launch()
    except Exception:
        pytest.skip("chromium unavailable")


@pytest.mark.parametrize("w,h,name", VIEWPORTS)
def test_landing_no_hscroll_and_cards(server, w, h, name):
    """Google-minimal landing renders cards with zero horizontal scroll."""
    with pw.sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page(viewport={"width": w, "height": h})
        page.goto(server + "/", wait_until="networkidle")
        assert page.locator("#landingUrl").count() == 1
        page.wait_for_selector(".card", timeout=15000)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), name
        browser.close()


@pytest.mark.parametrize("w,h,name", VIEWPORTS)
def test_golden_to_workspace_renders_diagram(server, w, h, name):
    """PyTorch + OpenClaw demos render all three diagrams with no blank/syntax-error canvas."""
    with pw.sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page(viewport={"width": w, "height": h})
        page.goto(server + "/", wait_until="networkidle")
        page.wait_for_selector(".card", timeout=15000)
        with page.expect_navigation():
            page.click(".card >> nth=0")
        assert "/workspace/" in page.url
        page.wait_for_selector("#mermaidHost svg", timeout=20000)
        for gid in ("pytorch", "openclaw"):
            page.goto(server + "/workspace/golden:" + gid, wait_until="networkidle")
            for tab in ("hld", "lld", "flow"):
                page.click(f'.diagram-tabs button[data-tab="{tab}"]')
                page.wait_for_selector("#mermaidHost svg", timeout=20000)
                text = page.inner_text("#mermaidHost")
                assert "Syntax error" not in text and "could not be rendered" not in text, (gid, tab)
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), (gid, name)
        browser.close()


def test_all_five_tabs_and_govern_trace(server):
    """Tab switching works; blast tracer returns a verdict."""
    with pw.sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(server + "/", wait_until="networkidle")
        page.wait_for_selector(".card", timeout=15000)
        with page.expect_navigation():
            page.click(".card >> nth=0")
        page.wait_for_selector("#mermaidHost svg", timeout=20000)
        for tab in ("handbook", "govern", "agent", "telemetry"):
            page.click(f'button[data-stab="{tab}"]')
            assert page.evaluate(
                f"document.querySelector('.tabpage[data-page=\"{tab}\"]').classList.contains('active')"
            ), tab
        page.click('button[data-stab="govern"]')
        page.fill("#blastSymbol", "Session")
        page.click("#blastBtn")
        page.wait_for_selector("#blastOut li, #blastOut p", timeout=15000)
        browser.close()


def test_challenge_and_guardrail_chat(server):
    """Challenge generates a puzzle; essay prompt trips the guardrail."""
    with pw.sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(server + "/", wait_until="networkidle")
        page.wait_for_selector(".card", timeout=15000)
        with page.expect_navigation():
            page.click(".card >> nth=0")
        page.wait_for_selector("#mermaidHost svg", timeout=20000)
        page.click('button[data-stab="agent"]')
        page.click("#challengeBtn")
        page.wait_for_selector("#challengeOut .challenge", timeout=15000)
        page.fill("#chatQ", "Write an essay about Napoleon")
        page.click('#chatForm button[type="submit"]')
        page.wait_for_function(
            "() => document.getElementById('chatLog').innerText.includes('Guardrail Triggered')",
            timeout=15000,
        )
        browser.close()


def test_canvas_drag_pans_viewport(server):
    """Mouse-drag on the canvas changes the stage transform (draw.io-style pan)."""
    with pw.sync_playwright() as p:
        browser = _browser(p)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(server + "/", wait_until="networkidle")
        page.wait_for_selector(".card", timeout=15000)
        with page.expect_navigation():
            page.click(".card >> nth=0")
        page.wait_for_selector("#mermaidHost svg", timeout=20000)
        before = page.evaluate("document.getElementById('stage').style.transform")
        box = page.evaluate("(() => { const r = document.getElementById('viewport').getBoundingClientRect(); return [r.x + r.width/2, r.y + r.height/2]; })()")
        page.mouse.move(box[0], box[1])
        page.mouse.down()
        page.mouse.move(box[0] + 120, box[1] + 80, steps=8)
        page.mouse.up()
        after = page.evaluate("document.getElementById('stage').style.transform")
        assert before != after, (before, after)
        browser.close()
