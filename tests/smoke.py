"""Browser smoke test for a built site.

Usage: python3 tests/smoke.py [URL]     (default: build _site/ is served locally)
Opens every topic, and the article of every topic that has one, and fails on any
console error, page error, failed request or empty article.
Needs: pip install playwright && playwright install chromium
"""
import functools, glob, http.server, json, os, sys, threading
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    handler = functools.partial(Quiet, directory=os.path.join(ROOT, "_site"))
    class Server(http.server.ThreadingHTTPServer):
        def handle_error(self, request, client_address):
            if not isinstance(sys.exc_info()[1], (BrokenPipeError, ConnectionResetError)):  # browser cancelled a download
                super().handle_error(request, client_address)

    srv = Server(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def main(url=None, screenshot=None):
    srv = None
    url_is_local = url is None
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
        page.on("requestfailed", lambda r: "ERR_ABORTED" in (r.failure or "") or problems.append(f"request failed: {r.url}"))  # aborted = we moved on while it loaded
        page.on("response", lambda r: r.status >= 400 and problems.append(f"HTTP {r.status}: {r.url}"))
        page.goto(url)
        page.wait_for_function("window.dbmap && window.dbmap.ids.length > 0", timeout=15000)
        n_loaded = page.evaluate("window.dbmap.ids.length")
        if n_loaded != len(graph["topics"]):
            problems.append(f"viewer loaded {n_loaded} of {len(graph['topics'])} topics")
        # the start page is shown first, with the editable home article and the topic index
        if not page.locator("#homeview").is_visible():
            problems.append("home view is not shown on load")
        if graph.get("home"):
            try:
                page.wait_for_selector("#homebody .article", timeout=10000)
            except Exception:
                problems.append("home article did not load")
        cards = page.locator("#subjects .scard")
        if cards.count() != len(graph["subjects"]):
            problems.append(f"home lists {cards.count()} subjects, expected {len(graph['subjects'])}")
        for k in range(cards.count()):
            if not cards.nth(k).locator("p").inner_text().strip():
                problems.append(f"subject card {k + 1} has no description")
        if not page.locator("#tabHome").is_visible() or page.locator("#tabTracks").is_visible():
            problems.append("home should open on the Database Internals tab")
        for href in page.evaluate("[...document.querySelectorAll('#homebody a[href^=\"#topic=\"]')].map(a=>a.getAttribute('href'))"):
            target = next((x for x in graph["topics"] if x["id"] == href[7:]), None)
            if not target:
                problems.append(f"home: link {href} names no topic")
                continue
            page.click(f"#homebody a[href='{href}']")
            if page.inner_text("#pt").strip() != target["name"]:
                problems.append(f"home: link {href} did not open '{target['name']}'")
            page.click("#homebtn")
            if not page.locator("#homeview").is_visible():
                problems.append("Home button did not return to the start page")
        # search: every topic is found by its own name, and the box opens the chosen topic
        for t in graph["topics"]:
            found = page.evaluate("n => window.dbmap.search(n)", t["name"])
            if t["id"] not in found:
                problems.append(f"search: '{t['name']}' does not find its own topic")
        probe = next((t for t in graph["topics"] if t["has_content"]), graph["topics"][0])
        page.fill("#q", probe["name"])
        if not page.locator("#res .rs").count():
            problems.append("search: typing a topic name shows no result")
        page.press("#q", "Enter")
        if page.inner_text("#pt").strip() != probe["name"]:
            problems.append(f"search: Enter did not open '{probe['name']}'")
        page.click("#homebtn")
        # a mouse click on a result must keep the topic open and show its article (the click used to fall through to the map)
        page.fill("#q", probe["name"])
        page.locator("#res .rs").first.click()
        try:
            page.wait_for_selector("#artbody .article", timeout=8000)
        except Exception:
            problems.append("search: clicking a result did not show the article")
        if not page.locator("#topicview").is_visible():
            problems.append("search: clicking a result did not keep the topic open")
        page.click("#homebtn")
        page.fill("#q", "zzzz-no-such-topic")
        if "No topic matches" not in page.inner_text("#res"):
            problems.append("search: no 'No topic matches' message for a bad query")
        page.fill("#q", "")
        # subject window: expand a subject to its topics, open one, hide and show the window
        first = graph["subjects"][0]["name"]
        n_first = sum(1 for t in graph["topics"] if t["subject"] == first)
        page.locator("#legbody .leg", has_text=first).click()
        if page.locator("#legbody .lt:visible").count() != n_first:
            problems.append(f"legend: expanding '{first}' should list {n_first} topics")
        page.locator("#legbody .lt:visible").first.click()
        if not page.inner_text("#pt").strip():
            problems.append("legend: a listed topic did not open")
        page.click("#homebtn")
        page.click("#legx")
        if page.locator("#legend").is_visible() or not page.locator("#legpill").is_visible():
            problems.append("legend: the close button did not hide the window")
        page.click("#legpill")
        if not page.locator("#legend").is_visible():
            problems.append("legend: the Subjects button did not bring the window back")
        # subject cards on the home page expand to their topics too
        page.locator("#subjects .scard").first.click()
        if page.locator("#subjects .scard").first.locator(".lt:visible").count() != n_first:
            problems.append(f"home: expanding the '{first}' card should list {n_first} topics")
        page.locator("#subjects .scard").first.locator(".lt:visible").first.click()
        if not page.inner_text("#pt").strip():
            problems.append("home: a topic listed in a subject card did not open")
        page.click("#homebtn")
        # About tab
        if graph.get("about"):
            page.click("#tabAboutBtn")
            try:
                page.wait_for_selector("#aboutbody .article", timeout=10000)
            except Exception:
                problems.append("About page did not load")
            page.click("#tabs .tab[data-tab=home]")
        elif page.locator("#tabAboutBtn").is_visible():
            problems.append("About tab is shown but there is no About page")
        # learning tracks: each expands, every step opens its topic, prev/next walk the track
        tracks = graph.get("tracks", [])
        if tracks:
            page.click("#tabTracksBtn")
            if not page.locator("#tabTracks").is_visible():
                problems.append("Learning tracks tab did not open")
        if page.locator("#tracks .track").count() != len(tracks):
            problems.append("home page does not list every learning track")
        for ti, tr in enumerate(tracks):
            card = page.locator("#tracks .track").nth(ti)
            card.locator("summary").click()
            steps = card.locator(".tstep")
            if steps.count() != len(tr["steps"]):
                problems.append(f"track '{tr['name']}': {steps.count()} steps shown, {len(tr['steps'])} expected")
                continue
            for si, st in enumerate(tr["steps"]):
                topic = next(x for x in graph["topics"] if x["id"] == st["topic"])
                page.locator("#tracks .track").nth(ti).locator(".tstep").nth(si).click()
                if page.inner_text("#pt").strip() != topic["name"]:
                    problems.append(f"track '{tr['name']}': step {si + 1} did not open '{topic['name']}'")
                    break
                bar = page.inner_text("#trackbar")
                if f"step {si + 1} of {len(tr['steps'])}" not in bar or tr["name"] not in bar:
                    problems.append(f"track '{tr['name']}': step {si + 1} shows no track bar")
                if si < len(tr["steps"]) - 1:
                    page.locator("#trackbar .tbar").filter(has_text=tr["name"]).locator("a[data-dir=next]").click()
                    nxt = next(x for x in graph["topics"] if x["id"] == tr["steps"][si + 1]["topic"])
                    if page.inner_text("#pt").strip() != nxt["name"]:
                        problems.append(f"track '{tr['name']}': Next after step {si + 1} did not open '{nxt['name']}'")
                if si > 0:
                    page.evaluate("id => window.dbmap.open(id)", st["topic"])
                    page.locator("#trackbar .tbar").filter(has_text=tr["name"]).locator("a[data-dir=prev]").click()
                    prv = next(x for x in graph["topics"] if x["id"] == tr["steps"][si - 1]["topic"])
                    if page.inner_text("#pt").strip() != prv["name"]:
                        problems.append(f"track '{tr['name']}': Prev at step {si + 1} did not open '{prv['name']}'")
                page.click("#homebtn")
        if tracks:
            page.click("#tabs .tab[data-tab=home]")
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
        # every live demo must load and run for a moment without errors
        demos = sorted(os.path.relpath(f, os.path.join(ROOT, "_site"))
                       for f in glob.glob(os.path.join(ROOT, "_site", "content", "*", "*.html")))
        if url_is_local:
            for d in demos:
                dp = browser.new_page(viewport={"width": 800, "height": 450})
                dp.on("console", lambda m, d=d: m.type == "error" and problems.append(f"demo {d}: console error: {m.text}"))
                dp.on("pageerror", lambda e, d=d: problems.append(f"demo {d}: page error: {e}"))
                dp.goto(url + d)
                dp.wait_for_timeout(1500)
                if not dp.locator("svg, canvas").count():
                    problems.append(f"demo {d}: nothing drawn")
                dp.close()
        if screenshot:
            page.evaluate("window.dbmap.close()")
            page.wait_for_timeout(500)
            page.screenshot(path=screenshot.replace(".png", "-home.png"))
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
