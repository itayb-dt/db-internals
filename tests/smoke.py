"""Browser smoke test for a built site.

Usage: python3 tests/smoke.py [URL]     (default: build _site/ is served locally)
Opens every topic, and the article of every topic that has one, and fails on any
console error, page error, failed request or empty article.
Needs: pip install playwright && playwright install chromium
"""
import functools, http.server, json, os, sys, threading
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(Quiet, directory=os.path.join(ROOT, "_site"))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def main(url=None, screenshot=None):
    srv = None
    if url is None:
        srv, url = serve()
    url = url if url.endswith("/") else url + "/"
    graph = json.load(urlopen(url + "graph.json"))
    problems = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("PW_CHROMIUM") or None)
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.on("console", lambda m: m.type == "error" and problems.append(f"console error: {m.text}"))
        page.on("pageerror", lambda e: problems.append(f"page error: {e}"))
        page.on("requestfailed", lambda r: problems.append(f"request failed: {r.url}"))
        page.on("response", lambda r: r.status >= 400 and problems.append(f"HTTP {r.status}: {r.url}"))
        page.goto(url)
        page.wait_for_function("window.dbmap && window.dbmap.ids.length > 0", timeout=15000)
        n_loaded = page.evaluate("window.dbmap.ids.length")
        if n_loaded != len(graph["topics"]):
            problems.append(f"viewer loaded {n_loaded} of {len(graph['topics'])} topics")
        with_content = 0
        for t in graph["topics"]:
            page.evaluate("id => window.dbmap.open(id)", t["id"])
            if page.inner_text("#pt").strip() != t["name"]:
                problems.append(f"{t['id']}: panel did not open")
                continue
            if t["has_content"]:
                with_content += 1
                try:
                    page.wait_for_selector("#artbody .article", timeout=10000)
                except Exception:
                    problems.append(f"{t['id']}: article did not load: {page.inner_text('#artbody')[:120]}")
                    continue
                if page.locator("#artbody script, #artbody [onclick], #artbody [onerror]").count():
                    problems.append(f"{t['id']}: executable markup in article")
                if len(page.inner_text("#artbody")) < 200:
                    problems.append(f"{t['id']}: article looks empty")
                for href in page.evaluate("[...document.querySelectorAll('#artbody a[href^=\"#topic=\"]')].map(a=>a.getAttribute('href'))"):
                    target = next((x for x in graph["topics"] if x["id"] == href[7:]), None)
                    if not target:
                        problems.append(f"{t['id']}: link {href} names no topic")
                        continue
                    page.click(f"#artbody a[href='{href}']")
                    if page.inner_text("#pt").strip() != target["name"]:
                        problems.append(f"{t['id']}: link {href} did not open '{target['name']}'")
                    page.evaluate("id => window.dbmap.open(id)", t["id"])
                    page.wait_for_selector("#artbody .article", timeout=10000)
                if page.locator("#artbody img").count():
                    bad = page.evaluate("[...document.querySelectorAll('#artbody img')].filter(i=>!i.complete||!i.naturalWidth).length")
                    if bad:
                        problems.append(f"{t['id']}: {bad} image(s) did not render")
            elif page.locator("#art").is_visible():
                problems.append(f"{t['id']}: article section shown for a topic without content")
        if screenshot:
            page.evaluate("window.dbmap.open('toast')")
            page.wait_for_selector("#artbody .article")
            page.screenshot(path=screenshot)
        browser.close()
    if srv:
        srv.shutdown()
    print(f"Smoke test: {len(graph['topics'])} topics opened, {with_content} articles loaded, {len(problems)} problem(s)")
    for pr in dict.fromkeys(problems):
        print("  - " + pr)
    return 1 if problems else 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--shot=")]
    shot = next((a[7:] for a in sys.argv[1:] if a.startswith("--shot=")), None)
    sys.exit(main(args[0] if args else None, shot))
