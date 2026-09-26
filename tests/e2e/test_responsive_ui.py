"""E2E responsiveness: Playwright across mobile/tablet/desktop/ultrawide.

Requires playwright + chromium; skips cleanly when unavailable so CI without
browsers still passes. Run via scripts/test_all.sh.
"""
import threading

import pytest
from werkzeug.serving import make_server

pw = pytest.importorskip("playwright.sync_api", reason="playwright not installed")

VIEWPORTS = [
    (390, 844, "mobile"),
    (768, 1024, "tablet"),
    (1440, 900, "desktop"),
    (2560, 1440, "ultrawide"),
]


@pytest.fixture(scope="module")
def server():
    """Serve the Flask app in-process on a fixed port."""
    from app import create_app, db

    app = create_app()
    app.config.update(TESTING=True)
    with app.app_context():
        db.create_all()
    httpd = make_server("127.0.0.1", 5123, app)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:5123"
    httpd.shutdown()


def _no_hscroll(page):
    return page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")


@pytest.mark.parametrize("w,h,name", VIEWPORTS)
def test_index_renders_without_hscroll(server, w, h, name):
    """Landing page has zero horizontal scroll at every target viewport."""
    with pw.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            pytest.skip("chromium unavailable")
        page = browser.new_page(viewport={"width": w, "height": h})
        page.goto(server + "/", wait_until="networkidle")
        assert _no_hscroll(page), f"hscroll at {name} {w}x{h}"
        browser.close()


@pytest.mark.parametrize("w,h,name", VIEWPORTS)
def test_golden_demo_instant_load(server, w, h, name):
    """Golden pill bar renders a diagram without any analysis run."""
    with pw.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            pytest.skip("chromium unavailable")
        page = browser.new_page(viewport={"width": w, "height": h})
        page.goto(server + "/", wait_until="networkidle")
        page.wait_for_selector(".pill", timeout=15000)
        page.click(".pill >> nth=0")
        page.wait_for_selector("#mermaidHost svg", timeout=20000)
        assert _no_hscroll(page), f"hscroll after render at {name}"
        browser.close()


def test_mobile_drawer_opens_and_navigates(server):
    """Off-canvas nav opens on mobile and chapter button switches tabs."""
    with pw.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            pytest.skip("chromium unavailable")
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(server + "/", wait_until="networkidle")
        page.click("#navToggle")
        assert page.evaluate("document.body.classList.contains('nav-open')")
        page.click('[data-goto="lld"]')
        assert page.evaluate("document.querySelector('.diagram-tabs button.active').dataset.tab") == "lld"
        browser.close()


def test_zoom_controls_change_transform(server):
    """Toolbar zoom mutates the stage transform (pan/zoom engine alive)."""
    with pw.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            pytest.skip("chromium unavailable")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(server + "/", wait_until="networkidle")
        page.wait_for_selector(".pill", timeout=15000)
        page.click(".pill >> nth=0")
        page.wait_for_selector("#mermaidHost svg", timeout=20000)
        before = page.evaluate("document.getElementById('stage').style.transform")
        page.click('[data-act="zin"]')
        after = page.evaluate("document.getElementById('stage').style.transform")
        assert before != after
        browser.close()
