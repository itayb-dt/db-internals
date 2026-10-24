#!/usr/bin/env python3
"""Validate data/ and content/, then build the static site into _site/.

Usage:
  python3 scripts/build.py                 build into _site/
  python3 scripts/build.py --serve         build, then serve _site/ on http://localhost:8000
  python3 scripts/build.py --serve --port 9000
  python3 scripts/build.py --lenient       skip broken articles instead of failing (used for deploys)
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
HOME_ID = "_home"  # content/_home.md is the start page shown in the viewer
ABOUT_ID = "_about"  # content/_about.md is the About tab
SPECIAL_IDS = (HOME_ID, ABOUT_ID)
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
URL_SCHEMES = {"http", "https", "mailto", "topic"}
EMBED_PREFIXES = (
    "https://www.youtube.com/embed/",
    "https://www.youtube-nocookie.com/embed/",
    "https://player.vimeo.com/video/",
)
# Live demos are single HTML files next to the article's images: content/<topic-id>/<name>.html,
# embedded as <iframe src="<topic-id>/<name>.html">.
DEMO_RE = re.compile(r"^([a-z0-9][a-z0-9-]*)/([A-Za-z0-9][A-Za-z0-9._-]*\.html)$")
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


def sanitize(raw_html, source_dir, topic_id, errors, where, known_ids=()):
    """Sanitize HTML, rewrite relative URLs to site paths, and validate them.

    source_dir is the directory the article file lives in (relative URLs resolve against it).
    Links of the form topic:<id> must name a topic in known_ids; they become #topic=<id>,
    which the viewer turns into navigation to that topic.
    """
    allowed_root = os.path.join(CONTENT_DIR, topic_id)

    def attr_filter(tag, attr, value):
        if tag == "iframe" and attr == "src":
            if value.startswith(EMBED_PREFIXES):
                return value
            m = DEMO_RE.match(value)
            if m:
                if m.group(1) != topic_id:
                    errors.append(f"{where}: demo '{value}' must be in this topic's own folder content/{topic_id}/")
                    return None
                if not os.path.isfile(os.path.join(CONTENT_DIR, value)):
                    errors.append(f"{where}: demo '{value}' does not exist (looked for content/{value})")
                    return None
                return "content/" + value
            return None
        if attr == "href" and value.startswith("topic:"):
            target_id = value[len("topic:"):]
            if target_id not in known_ids:
                errors.append(f"{where}: link '{value}' names an unknown topic id "
                              f"(ids are listed in data/*.yaml)")
                return None
            return "#topic=" + target_id
        if attr == "src" and value.startswith("topic:"):
            errors.append(f"{where}: 'topic:' links work only for links, not images ('{value}')")
            return None
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
        if os.path.splitext(target)[1].lower() not in (ASSET_EXT | {".html"} if tag == "a" else ASSET_EXT):
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
    # Demos are our own scripts: run them in a sandbox without access to the surrounding page.
    cleaned = re.sub(
        r"<iframe\b[^>]*>",
        lambda m: re.sub(r'sandbox="[^"]*"', 'sandbox="allow-scripts"', m.group(0))
        if 'src="content/' in m.group(0) else m.group(0),
        cleaned)
    # An iframe whose src was rejected is an empty shell; drop it and say so.
    def drop_empty_iframe(m):
        if re.search(r"\ssrc=", m.group(0)):
            return m.group(0)
        errors.append(f"{where}: <iframe> removed; only YouTube/Vimeo embeds "
                      f"({', '.join(EMBED_PREFIXES)}) and <topic-id>/<name>.html demos are allowed")
        return ""
    return re.sub(r"<iframe\b[^>]*>\s*</iframe>", drop_empty_iframe, cleaned)


LIST_ITEM_RE = re.compile(r"^(\d+\. |- |\* )")


def lint_markdown(body, where, errors):
    """A list that follows a text line without a blank line renders as plain text. Report it."""
    in_code = False
    lines = body.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("```"):
            in_code = not in_code
        if in_code or i == 0 or not LIST_ITEM_RE.match(line):
            continue
        prev = lines[i - 1]
        if prev.strip() and not LIST_ITEM_RE.match(prev) and not prev.startswith((" ", "\t", "|", "#", "```", ">", "---")):
            errors.append(f"{where}: line {i + 1} starts a list right after a text line. "
                          f"Put a blank line before the list, or it will render as one paragraph.")


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


def load_topics(errors, raw_details):
    subjects, topics, edges = [], {}, []
    for path in sorted(glob.glob(os.path.join(DATA_DIR, "*.yaml"))):
        fname = os.path.basename(path)
        try:
            with open(path, encoding="utf-8") as fh:
                doc = yaml.safe_load(fh)
        except yaml.YAMLError as e:
            errors.append(f"{fname}: invalid YAML: {e}")
            continue
        for k in ("subject", "color", "description", "topics"):
            if not isinstance(doc, dict) or k not in doc:
                errors.append(f"{fname}: missing top-level '{k}'")
                break
        else:
            subjects.append({"name": doc["subject"], "color": doc["color"], "description": doc["description"],
                             "order": doc.get("order", 100)})
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
                    raw_details[t["id"]] = (where, t["details"])
                for p in t.get("prerequisites") or []:
                    extra = [k for k in p if k not in ("id", "reason", "strength")]
                    if extra:
                        errors.append(f"{where}: prerequisite '{p.get('id')}' has unexpected key(s) {sorted(map(str, extra))}. "
                                      f"A comma or colon inside 'reason' must be quoted.")
                    edges.append({"topic": t["id"], "prerequisite": p["id"],
                                  "strength": p.get("strength", "hard"), "reason": p.get("reason", "")})
    subjects.sort(key=lambda x: (x["order"], x["name"]))
    for x in subjects:
        del x["order"]
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


def load_tracks(topics, errors):
    """data/tracks/*.yaml: an ordered learning track of 3-10 topics, each with a one-line reason."""
    tracks, seen = [], set()
    for path in sorted(glob.glob(os.path.join(DATA_DIR, "tracks", "*.yaml"))):
        fname = "tracks/" + os.path.basename(path)
        tid = os.path.splitext(os.path.basename(path))[0]
        try:
            doc = yaml.safe_load(open(path, encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            errors.append(f"{fname}: invalid YAML: {e}")
            continue
        for k in ("name", "title", "steps"):
            if not doc.get(k):
                errors.append(f"{fname}: missing '{k}'")
        steps = doc.get("steps") or []
        if not isinstance(steps, list):
            errors.append(f"{fname}: 'steps' must be a list")
            continue
        if not 3 <= len(steps) <= 10:
            errors.append(f"{fname}: a track needs 3-10 steps, found {len(steps)}")
        ok = []
        for i, st in enumerate(steps, 1):
            extra = sorted(str(k) for k in st) if isinstance(st, dict) else []
            extra = [k for k in extra if k not in ("topic", "why")]
            if extra:
                errors.append(f"{fname}: step {i} has unexpected key(s) {extra}. "
                              f"If the 'why' text contains a comma or colon, write the step in block style or quote the text.")
            t = st.get("topic") if isinstance(st, dict) else None
            if t not in topics:
                errors.append(f"{fname}: step {i} names unknown topic '{t}'")
            elif t in [s["topic"] for s in ok]:
                errors.append(f"{fname}: topic '{t}' appears twice")
            elif not st.get("why"):
                errors.append(f"{fname}: step {i} ('{t}') needs a 'why' line")
            else:
                ok.append({"topic": t, "why": st["why"]})
        if tid in seen:
            errors.append(f"{fname}: duplicate track id")
        seen.add(tid)
        tracks.append({"id": tid, "order": doc.get("order", 100), "name": doc.get("name", tid),
                       "title": doc.get("title", ""), "steps": ok})
    tracks.sort(key=lambda t: (t["order"], t["name"]))
    for t in tracks:
        del t["order"]
    return tracks


def build_details(topics, raw_details, problems):
    for tid, (where, md) in raw_details.items():
        local = []
        details = sanitize(render_markdown(md), os.path.join(CONTENT_DIR, tid), tid, local,
                           f"{where}: details", topics)
        if local:
            problems.extend(local)
        elif tid in topics:
            topics[tid]["details_html"] = details


def build_content(topics, problems):
    """Render content/<id>.md|html into {id: html fragment}; mark topics; copy assets.

    Problems are per article: the caller decides whether they are fatal or skip the article.
    """
    errors = problems
    rendered, assets, skipped = {}, [], set()
    if not os.path.isdir(CONTENT_DIR):
        return rendered, assets
    files = {}
    for name in sorted(os.listdir(CONTENT_DIR)):
        if os.path.splitext(name)[0] in SPECIAL_IDS and name.endswith((".md", ".html")):
            sid = os.path.splitext(name)[0]
            if sid in files:
                errors.append(f"content/{name}: {sid} already has {files[sid]}; keep only one")
            else:
                files[sid] = name
            continue
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
        local = []
        try:
            text = open(os.path.join(CONTENT_DIR, name), encoding="utf-8").read()
            meta, body = split_frontmatter(text, where, local)
            if name.endswith(".md"):
                lint_markdown(body, where, local)
            body_html = render_markdown(body) if name.endswith(".md") else body
            clean = sanitize(body_html, CONTENT_DIR, tid, local, where, topics)
            title = html.escape(str(meta.get("title") or (topics[tid]["name"] if tid in topics else
                                                          "About" if tid == ABOUT_ID else "Database Internals")))
            if isinstance(meta.get("updated"), (datetime.date, datetime.datetime)):
                meta["updated"] = meta["updated"].isoformat()[:10]
            frag = (f'<article class="article"><h1>{title}</h1>{clean}'
                    f'{article_footer(meta, where, local)}</article>')
        except Exception as e:  # one broken article must not take the rest down
            local.append(f"{where}: could not be processed ({type(e).__name__}: {e})")
        if local:
            problems.extend(local)
            skipped.add(tid)
            continue
        rendered[tid] = frag
        if tid in topics:
            topics[tid]["has_content"] = True
        asset_dir = os.path.join(CONTENT_DIR, tid)
        if os.path.isdir(asset_dir):
            for dp, _, fns in os.walk(asset_dir):
                for fn in sorted(fns):
                    if os.path.splitext(fn)[1].lower() in ASSET_EXT | {".html"}:  # .html = live demos
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


def report(title, items):
    text = "\n".join("  - " + i for i in dict.fromkeys(items))
    print(f"{title}\n{text}", file=sys.stderr)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"### {title}\n" + "\n".join("- " + i for i in dict.fromkeys(items)) + "\n")


def build(lenient=False):
    errors, problems, raw_details = [], [], {}
    subjects, topics, edges = load_topics(errors, raw_details)
    check_graph(topics, edges, errors)
    build_details(topics, raw_details, problems)
    tracks = load_tracks(topics, errors)
    rendered, assets = build_content(topics, problems)
    if not lenient:
        errors.extend(problems)
    if errors:
        report(f"Build failed with {len(set(errors))} problem(s):", errors)
        sys.exit(1)
    if problems:
        report(f"WARNING: {len(set(problems))} content problem(s); the affected articles were skipped "
               f"and the rest of the site was built:", problems)
    graph = {"levels": LEVELS, "subjects": subjects, "topics": list(topics.values()), "edges": edges,
             "home": HOME_ID in rendered, "about": ABOUT_ID in rendered, "tracks": tracks}
    write_site(graph, rendered, assets)
    print(f"OK: {len(topics)} topics, {len(edges)} links, {len(subjects)} subjects, "
          f"{len([r for r in rendered if r not in SPECIAL_IDS])} articles"
          f"{' + home page' if HOME_ID in rendered else ''}{' + about page' if ABOUT_ID in rendered else ''} -> _site/")
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
    ap.add_argument("--lenient", action="store_true",
                    help="skip articles with problems (warn) instead of failing; data/graph errors still fail")
    args = ap.parse_args()
    build(lenient=args.lenient)
    if args.serve:
        serve(args.port)
