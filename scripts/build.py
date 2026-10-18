#!/usr/bin/env python3
"""Validate data/ and content/, then build the static site into _site/.

Usage:
  python3 scripts/build.py                 build into _site/
  python3 scripts/build.py --serve         build, then serve _site/ on http://localhost:8000
  python3 scripts/build.py --serve --port 9000
"""
import argparse, datetime, functools, glob, html, http.server, json, os, re, shutil, sys
from urllib.parse import urlsplit

import markdown
import nh3
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
CONTENT_DIR = os.path.join(ROOT, "content")
SITE_SRC = os.path.join(ROOT, "site")
OUT = os.path.join(ROOT, "_site")

LEVELS = ["Concept", "Core structure", "Mechanism", "Implementation", "Operational"]
REQUIRED = ["id", "name", "domain", "level", "description"]
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

# Files that may sit next to an article in content/<id>/. SVG is left out on purpose:
# an SVG opened directly can run scripts.
ASSET_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".pdf", ".txt", ".sql", ".csv"}

ALLOWED_TAGS = {
    "a", "abbr", "b", "blockquote", "br", "code", "del", "details", "em", "figcaption", "figure",
    "h1", "h2", "h3", "h4", "h5", "h6", "hr", "i", "iframe", "img", "kbd", "li", "ol", "p", "pre",
    "s", "span", "strong", "sub", "summary", "sup", "table", "tbody", "td", "tfoot", "th", "thead",
    "tr", "ul",
}
ALLOWED_ATTRS = {
    "a": {"href", "title"},
    "abbr": {"title"},
    "code": {"class"},  # fenced code blocks emit class="language-xyz"
    "img": {"src", "alt", "title", "width", "height"},
    "iframe": {"src", "width", "height", "title"},
    "td": {"align"},
    "th": {"align"},
}
URL_SCHEMES = {"http", "https", "mailto"}
EMBED_PREFIXES = (
    "https://www.youtube.com/embed/",
    "https://www.youtube-nocookie.com/embed/",
    "https://player.vimeo.com/video/",
)
FORCED_ATTRS = {
    "iframe": {
        "sandbox": "allow-scripts allow-same-origin allow-presentation",
        "loading": "lazy",
        "referrerpolicy": "strict-origin-when-cross-origin",
        "allowfullscreen": "",
    },
    "a": {"target": "_blank"},
}
FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?\r?\n)?---[ \t]*(?:\r?\n|\Z)", re.S)


def is_external(url):
    parts = urlsplit(url)
    return bool(parts.scheme) or url.startswith("//") or url.startswith("#")


def sanitize(raw_html, source_dir, topic_id, errors, where):
    """Sanitize HTML, rewrite relative URLs to site paths, and validate them.

    source_dir is the directory the article file lives in (relative URLs resolve against it).
    """
    allowed_root = os.path.join(CONTENT_DIR, topic_id)

    def attr_filter(tag, attr, value):
        if tag == "iframe" and attr == "src":
            return value if value.startswith(EMBED_PREFIXES) else None
        if attr not in ("src", "href") or is_external(value):
            return value
        path = urlsplit(value).path
        if not path:
            return value
        target = os.path.normpath(os.path.join(source_dir, path))
        shown = f"'{value}' ({attr} in <{tag}>)"
        if os.path.commonpath([target, allowed_root]) != allowed_root or target == allowed_root:
            errors.append(f"{where}: {shown} must point into content/{topic_id}/")
            return None
        if not os.path.isfile(target):
            errors.append(f"{where}: {shown} does not exist (looked for {os.path.relpath(target, ROOT)})")
            return None
        if os.path.splitext(target)[1].lower() not in ASSET_EXT:
            errors.append(f"{where}: {shown} has a file type that is not allowed "
                          f"(allowed: {', '.join(sorted(ASSET_EXT))})")
            return None
        rel = os.path.relpath(target, CONTENT_DIR).replace(os.sep, "/")
        return "content/" + rel + urlsplit(value)._replace(scheme="", netloc="", path="").geturl()

    cleaned = nh3.clean(
        raw_html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        url_schemes=URL_SCHEMES,
        link_rel="noopener noreferrer nofollow",
        set_tag_attribute_values=FORCED_ATTRS,
        attribute_filter=attr_filter,
    )
    # An iframe whose src was rejected is an empty shell; drop it and say so.
    def drop_empty_iframe(m):
        if re.search(r"\ssrc=", m.group(0)):
            return m.group(0)
        errors.append(f"{where}: <iframe> removed; only YouTube and Vimeo embeds are allowed "
                      f"({', '.join(EMBED_PREFIXES)})")
        return ""
    return re.sub(r"<iframe\b[^>]*>\s*</iframe>", drop_empty_iframe, cleaned)


def render_markdown(text):
    return markdown.markdown(text, extensions=["tables", "fenced_code"], output_format="html")


def split_frontmatter(text, where, errors):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1) or "") or {}
    except yaml.YAMLError as e:
        errors.append(f"{where}: invalid YAML frontmatter: {e}")
        return {}, text[m.end():]
    if not isinstance(meta, dict):
        errors.append(f"{where}: frontmatter must be a mapping of keys to values")
        return {}, text[m.end():]
    return meta, text[m.end():]


def article_footer(meta, where, errors):
    parts = []
    if meta.get("reviewed_by") or meta.get("updated"):
        bits = []
        if meta.get("updated"):
            bits.append("Updated " + html.escape(str(meta["updated"])))
        if meta.get("reviewed_by"):
            rb = meta["reviewed_by"]
            rb = ", ".join(map(str, rb)) if isinstance(rb, list) else str(rb)
            bits.append("Reviewed by " + html.escape(rb))
        parts.append('<p class="article-meta">' + " &middot; ".join(bits) + "</p>")
    sources = meta.get("sources") or []
    if not isinstance(sources, list):
        errors.append(f"{where}: 'sources' must be a list of URLs")
        sources = []
    items = []
    for s in sources:
        if not isinstance(s, str) or urlsplit(s).scheme not in ("http", "https"):
            errors.append(f"{where}: source {s!r} is not an http(s) URL")
            continue
        items.append(f'<li><a href="{html.escape(s, quote=True)}" target="_blank" '
                     f'rel="noopener noreferrer nofollow">{html.escape(s)}</a></li>')
    if items:
        parts.append('<section class="article-sources"><h2>Sources</h2><ul>' + "".join(items) + "</ul></section>")
    return "".join(parts)


def load_topics(errors):
    subjects, topics, edges = [], {}, []
    for path in sorted(glob.glob(os.path.join(DATA_DIR, "*.yaml"))):
        fname = os.path.basename(path)
        try:
            doc = yaml.safe_load(open(path, encoding="utf-8"))
        except yaml.YAMLError as e:
            errors.append(f"{fname}: invalid YAML: {e}")
            continue
        for k in ("subject", "color", "topics"):
            if not isinstance(doc, dict) or k not in doc:
                errors.append(f"{fname}: missing top-level '{k}'")
                break
        else:
            subjects.append({"name": doc["subject"], "color": doc["color"]})
            for t in doc["topics"]:
                where = f"{fname}:{t.get('id', '?')}"
                missing = [k for k in REQUIRED if k not in t]
                for k in missing:
                    errors.append(f"{where}: missing '{k}'")
                if missing:
                    continue
                if not ID_RE.match(str(t["id"])):
                    errors.append(f"{where}: id must be lowercase letters, digits and dashes")
                if t["id"] in topics:
                    errors.append(f"{where}: duplicate id")
                if not isinstance(t["level"], int) or not 0 <= t["level"] < len(LEVELS):
                    errors.append(f"{where}: level must be an integer 0-{len(LEVELS)-1}")
                    continue
                topics[t["id"]] = {
                    "id": t["id"], "name": t["name"], "subject": doc["subject"], "domain": t["domain"],
                    "level": t["level"], "description": t["description"],
                    "evidence": t.get("evidence", []),
                    "has_content": False,
                }
                if t.get("details"):
                    topics[t["id"]]["details_html"] = sanitize(
                        render_markdown(t["details"]), os.path.join(CONTENT_DIR, t["id"]), t["id"], errors,
                        f"{where}: details")
                for p in t.get("prerequisites") or []:
                    edges.append({"topic": t["id"], "prerequisite": p["id"],
                                  "strength": p.get("strength", "hard"), "reason": p.get("reason", "")})
    return subjects, topics, edges


def check_graph(topics, edges, errors):
    for e in edges:
        if e["prerequisite"] not in topics:
            errors.append(f"{e['topic']}: unknown prerequisite '{e['prerequisite']}'")
    adj = {}
    for e in edges:
        adj.setdefault(e["topic"], []).append(e["prerequisite"])
    state = {}

    def visit(n, trail):
        if state.get(n) == 1:
            errors.append("cycle: " + " -> ".join(trail + [n]))
            return
        if state.get(n) == 2:
            return
        state[n] = 1
        for m in adj.get(n, []):
            if m in topics:
                visit(m, trail + [n])
        state[n] = 2

    for n in topics:
        visit(n, [])


def build_content(topics, errors):
    """Render content/<id>.md|html into {id: html fragment}; mark topics; copy assets."""
    rendered, assets = {}, []
    if not os.path.isdir(CONTENT_DIR):
        return rendered, assets
    files = {}
    for name in sorted(os.listdir(CONTENT_DIR)):
        if name.startswith(("_", ".")):  # _prompt.md and other helper files are not articles
            continue
        full = os.path.join(CONTENT_DIR, name)
        stem, ext = os.path.splitext(name)
        if os.path.isdir(full):
            if stem not in topics:
                errors.append(f"content/{name}/: no topic with id '{stem}'. Rename it or add the topic in data/.")
            continue
        if ext not in (".md", ".html"):
            errors.append(f"content/{name}: only .md and .html articles are supported")
            continue
        if stem not in topics:
            errors.append(f"content/{name}: no topic with id '{stem}'. "
                          f"Rename the file to match a topic id (see data/*.yaml).")
            continue
        if stem in files:
            errors.append(f"content/{name}: topic '{stem}' already has {files[stem]}; keep only one")
            continue
        files[stem] = name

    for tid, name in files.items():
        where = f"content/{name}"
        text = open(os.path.join(CONTENT_DIR, name), encoding="utf-8").read()
        meta, body = split_frontmatter(text, where, errors)
        body_html = render_markdown(body) if name.endswith(".md") else body
        clean = sanitize(body_html, CONTENT_DIR, tid, errors, where)
        title = html.escape(str(meta.get("title") or topics[tid]["name"]))
        if isinstance(meta.get("updated"), (datetime.date, datetime.datetime)):
            meta["updated"] = meta["updated"].isoformat()[:10]
        rendered[tid] = (f'<article class="article"><h1>{title}</h1>{clean}'
                         f'{article_footer(meta, where, errors)}</article>')
        topics[tid]["has_content"] = True
        asset_dir = os.path.join(CONTENT_DIR, tid)
        if os.path.isdir(asset_dir):
            for dp, _, fns in os.walk(asset_dir):
                for fn in sorted(fns):
                    if os.path.splitext(fn)[1].lower() in ASSET_EXT:
                        assets.append(os.path.join(dp, fn))
    return rendered, assets


def write_site(graph, rendered, assets):
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    shutil.copytree(SITE_SRC, OUT)
    with open(os.path.join(OUT, "graph.json"), "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    os.makedirs(os.path.join(OUT, "content"), exist_ok=True)
    for tid, frag in rendered.items():
        with open(os.path.join(OUT, "content", tid + ".html"), "w", encoding="utf-8") as f:
            f.write(frag)
    for src in assets:
        dst = os.path.join(OUT, "content", os.path.relpath(src, CONTENT_DIR))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)


def build():
    errors = []
    subjects, topics, edges = load_topics(errors)
    check_graph(topics, edges, errors)
    rendered, assets = build_content(topics, errors)
    if errors:
        print(f"Build failed with {len(errors)} problem(s):\n", file=sys.stderr)
        print("\n".join("  - " + e for e in dict.fromkeys(errors)), file=sys.stderr)
        sys.exit(1)
    graph = {"levels": LEVELS, "subjects": subjects, "topics": list(topics.values()), "edges": edges}
    write_site(graph, rendered, assets)
    print(f"OK: {len(topics)} topics, {len(edges)} links, {len(subjects)} subjects, "
          f"{len(rendered)} articles -> _site/")
    missing = [t for t in topics if t not in rendered]
    print(f"Topics without content yet ({len(missing)}): {', '.join(missing) if missing else 'none'}")


def serve(port):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=OUT)
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as srv:
        print(f"Serving _site/ at http://localhost:{port}  (Ctrl+C to stop; rebuild to see changes)")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--serve", action="store_true", help="serve _site/ on localhost after building")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    build()
    if args.serve:
        serve(args.port)
