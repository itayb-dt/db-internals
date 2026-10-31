"""Unit tests for scripts/build.py.  Run: python3 -m unittest discover -s tests -v"""
import contextlib, io, os, shutil, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import build  # noqa: E402

TOPICS = """subject: Test
color: "#123456"
description: A test subject
topics:
  - {id: a, name: A, domain: D, level: 0, description: First}
  - id: b
    name: B
    domain: D
    level: 1
    description: Second
    prerequisites: [{id: a, reason: needs a}]
  - {id: c, name: C, domain: D, level: 2, description: Third}
"""


TRACK3 = """name: Basics
title: From a to c
steps:
  - {topic: a, why: first}
  - {topic: b, why: second}
  - {topic: c, why: third}
"""


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb" if isinstance(data, bytes) else "w") as f:
        f.write(data)


def read(path):
    with open(path) as f:
        return f.read()


class Site:
    """A throwaway repo layout; build.py's path constants are pointed at it."""

    def __init__(self, topics=TOPICS, content=None, tracks=None):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "data"))
        os.makedirs(os.path.join(self.root, "content"))
        os.makedirs(os.path.join(self.root, "site"))
        write(os.path.join(self.root, "site", "index.html"), "<html></html>")
        write(os.path.join(self.root, "data", "t.yaml"), topics)
        for name, text in (tracks or {}).items():
            write(os.path.join(self.root, "data", "tracks", name + ".yaml"), text)
        for name, text in (content or {}).items():
            write(os.path.join(self.root, "content", name), text)
        self.saved = (build.ROOT, build.DATA_DIR, build.CONTENT_DIR, build.SITE_SRC, build.OUT)
        build.ROOT, build.DATA_DIR = self.root, os.path.join(self.root, "data")
        build.CONTENT_DIR, build.SITE_SRC = os.path.join(self.root, "content"), os.path.join(self.root, "site")
        build.OUT = os.path.join(self.root, "_site")

    def run(self, lenient=False):
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            try:
                build.build(lenient=lenient)
                code = 0
            except SystemExit as e:
                code = e.code
        return code, err.getvalue()

    def out(self, *parts):
        return os.path.join(self.root, "_site", *parts)

    def close(self):
        build.ROOT, build.DATA_DIR, build.CONTENT_DIR, build.SITE_SRC, build.OUT = self.saved
        shutil.rmtree(self.root)


class BuildTestCase(unittest.TestCase):
    def site(self, **kw):
        s = Site(**kw)
        self.addCleanup(s.close)
        return s


class SanitizerTests(BuildTestCase):
    def clean(self, html, tid="a"):
        self.site()
        errors = []
        return build.sanitize(html, build.CONTENT_DIR, tid, errors, "t"), errors

    def test_script_and_handlers_removed(self):
        out, _ = self.clean('<p onclick="x()">hi</p><script>alert(1)</script><img src="http://x/y.png" onerror="x()">')
        self.assertNotIn("script", out)
        self.assertNotIn("alert", out)
        self.assertNotIn("onclick", out)
        self.assertNotIn("onerror", out)

    def test_javascript_urls_removed(self):
        out, _ = self.clean('<a href="javascript:alert(1)">x</a>')
        self.assertNotIn("javascript", out)

    def test_iframe_allowlist(self):
        ok, errs = self.clean('<iframe src="https://www.youtube.com/embed/abc"></iframe>')
        self.assertIn("youtube.com/embed/abc", ok)
        self.assertIn("sandbox", ok)
        self.assertEqual(errs, [])
        bad, errs = self.clean('<iframe src="https://evil.example/x"></iframe>')
        self.assertNotIn("iframe", bad)
        self.assertTrue(errs)

    def test_demo_iframe_is_sandboxed_without_same_origin(self):
        s = self.site(content={"a/d.html": "<html></html>"})
        errors = []
        out = build.sanitize('<iframe src="a/d.html" sandbox="allow-same-origin"></iframe>',
                             build.CONTENT_DIR, "a", errors, "t")
        self.assertIn('src="content/a/d.html"', out)
        self.assertIn('sandbox="allow-scripts"', out)
        self.assertNotIn("same-origin", out)
        self.assertEqual(errors, [])
        self.assertTrue(s)

    def test_demo_iframe_must_exist_and_stay_in_own_folder(self):
        self.site(content={"b/other.html": "<html></html>", "a/x.js": "x"})
        for src in ("a/missing.html", "b/other.html", "a/../index.html", "../data/t.yaml", "/etc/passwd",
                    "a/x.js", "//evil.example/x", "demos/x.html"):
            errors = []
            out = build.sanitize(f'<iframe src="{src}"></iframe>', build.CONTENT_DIR, "a", errors, "t")
            self.assertNotIn("<iframe", out, src)
            self.assertTrue(errors, src)

    def test_html_only_allowed_as_link_or_iframe_not_image(self):
        self.site(content={"a/d.html": "<html></html>"})
        errors = []
        out = build.sanitize('<a href="a/d.html">open</a><img src="a/d.html">', build.CONTENT_DIR, "a", errors, "t")
        self.assertIn('href="content/a/d.html"', out)
        self.assertEqual(len(errors), 1)

    def test_style_and_unknown_tags_removed(self):
        out, _ = self.clean('<style>p{}</style><form action="x"><input></form><p style="color:red">t</p>')
        self.assertNotIn("<style", out)
        self.assertNotIn("<form", out)
        self.assertNotIn("style=", out)

    def test_topic_links(self):
        self.site()
        errors = []
        out = build.sanitize('<a href="topic:a">A</a>', build.CONTENT_DIR, "b", errors, "t", {"a": {}, "b": {}})
        self.assertIn('href="#topic=a"', out)
        self.assertEqual(errors, [])
        out = build.sanitize('<a href="topic:zzz">Z</a>', build.CONTENT_DIR, "b", errors, "t", {"a": {}})
        self.assertNotIn("zzz", out)
        self.assertTrue(any("unknown topic id" in e for e in errors))

    def test_relative_image_rewritten_and_checked(self):
        s = self.site(content={"a/pic.png": b"\x89PNG"})
        errors = []
        out = build.sanitize('<img src="a/pic.png" alt="x">', build.CONTENT_DIR, "a", errors, "t")
        self.assertIn('src="content/a/pic.png"', out)
        self.assertEqual(errors, [])
        build.sanitize('<img src="a/nope.png">', build.CONTENT_DIR, "a", errors, "t")
        self.assertTrue(any("does not exist" in e for e in errors))
        errors.clear()
        build.sanitize('<img src="../data/t.yaml">', build.CONTENT_DIR, "a", errors, "t")
        self.assertTrue(any("must point into" in e for e in errors))
        self.assertTrue(s)


class DataTests(BuildTestCase):
    def test_valid_build(self):
        s = self.site(content={"a.md": "---\ntitle: T\n---\nHello"})
        self.assertEqual(s.run()[0], 0)
        self.assertTrue(os.path.isfile(s.out("graph.json")))
        self.assertIn("Hello", read(s.out("content", "a.html")))
        self.assertIn('"has_content": true', read(s.out("graph.json")))

    def test_cycle_fails_even_when_lenient(self):
        bad = TOPICS.replace("level: 0, description: First}", "level: 0, description: First, prerequisites: [{id: b}]}")
        s = self.site(topics=bad)
        code, err = s.run(lenient=True)
        self.assertEqual(code, 1)
        self.assertIn("cycle", err)

    def test_unknown_prerequisite_and_duplicate_id_fail(self):
        s = self.site(topics=TOPICS + "  - {id: a, name: A2, domain: D, level: 0, description: dup}\n"
                      "  - {id: c, name: C, domain: D, level: 0, description: x, prerequisites: [{id: zzz}]}\n")
        code, err = s.run(lenient=True)
        self.assertEqual(code, 1)
        self.assertIn("duplicate id", err)
        self.assertIn("unknown prerequisite 'zzz'", err)

    def test_subject_needs_a_description(self):
        s = self.site(topics=TOPICS.replace("description: A test subject\n", ""))
        code, err = s.run()
        self.assertEqual(code, 1)
        self.assertIn("missing top-level 'description'", err)

    def test_subjects_are_ordered_by_the_order_key(self):
        import json
        s = self.site(topics=TOPICS.replace("subject: Test", "order: 2\nsubject: Zed"))
        write(os.path.join(s.root, "data", "u.yaml"), TOPICS.replace("subject: Test", "order: 1\nsubject: Beta").replace("id: a", "id: a2").replace("id: b", "id: b2").replace("id: c", "id: c2").replace("{id: a2, reason", "{id: a2, reason"))
        self.assertEqual(s.run()[0], 0)
        self.assertEqual([x["name"] for x in json.loads(read(s.out("graph.json")))["subjects"]], ["Beta", "Zed"])

    def test_missing_field_fails(self):
        s = self.site(topics='subject: T\ncolor: "#fff"\ndescription: d\ntopics:\n  - {id: a, name: A}\n')
        code, err = s.run()
        self.assertEqual(code, 1)
        self.assertIn("missing 'domain'", err)


class TrackTests(BuildTestCase):
    def test_valid_track_is_in_graph(self):
        s = self.site(tracks={"basics": TRACK3})
        self.assertEqual(s.run()[0], 0)
        import json
        tracks = json.loads(read(s.out("graph.json")))["tracks"]
        self.assertEqual([t["name"] for t in tracks], ["Basics"])
        self.assertEqual([x["topic"] for x in tracks[0]["steps"]], ["a", "b", "c"])

    def test_no_tracks_is_fine(self):
        s = self.site()
        self.assertEqual(s.run()[0], 0)
        self.assertIn('"tracks": []', read(s.out("graph.json")))

    def test_track_errors(self):
        cases = {
            "unknown topic": (TRACK3.replace("topic: c", "topic: zzz"), "unknown topic 'zzz'"),
            "too short": ("name: X\ntitle: T\nsteps:\n  - {topic: a, why: w}\n  - {topic: b, why: w}\n", "needs 3-10 steps"),
            "missing why": (TRACK3.replace(", why: third", ""), "needs a 'why'"),
            "duplicate": (TRACK3.replace("topic: c", "topic: a"), "appears twice"),
            "no name": (TRACK3.replace("name: Basics\n", ""), "missing 'name'"),
        }
        for label, (text, expected) in cases.items():
            s = self.site(tracks={"t": text})
            code, err = s.run(lenient=True)  # track errors are graph errors: fatal even when lenient
            self.assertEqual(code, 1, label)
            self.assertIn(expected, err, label)

    def test_comma_in_flow_style_why_is_an_error_not_silent_truncation(self):
        text = TRACK3.replace("{topic: c, why: third}", "{topic: c, why: third, and more}")
        s = self.site(tracks={"t": text})
        code, err = s.run()
        self.assertEqual(code, 1)
        self.assertIn("unexpected key(s)", err)

    def test_comma_in_flow_style_prerequisite_reason_is_an_error(self):
        bad = TOPICS.replace("{id: c, name: C, domain: D, level: 2, description: Third}",
                             "{id: c, name: C, domain: D, level: 2, description: Third, prerequisites: "
                             "[{id: a, reason: needs a, and also more}]}")
        s = self.site(topics=bad)
        code, err = s.run()
        self.assertEqual(code, 1)
        self.assertIn("unexpected key(s)", err)

    def test_problem_track_reaches_the_graph(self):
        track = ("name: T\ntitle: x\nkind: problem\nproblem: Something is wrong. It costs you.\nsteps:\n"
                 "  - {topic: a, why: first, phase: problem}\n  - {topic: b, why: second, phase: causes}\n  - {topic: c, why: third, phase: cause}\n")
        s = self.site(tracks={"t": track})
        self.assertEqual(s.run()[0], 0)
        g = read(s.out("graph.json"))
        self.assertIn("Something is wrong. It costs you.", g)
        self.assertIn('"kind": "problem"', g)
        self.assertIn('"phase": "cause"', g)

    def test_a_track_is_general_by_default(self):
        s = self.site(tracks={"t": TRACK3})
        self.assertEqual(s.run()[0], 0)
        self.assertIn('"kind": "general"', read(s.out("graph.json")))

    def test_problem_track_rules(self):
        head = "name: T\ntitle: x\nkind: problem\nproblem: A problem.\nsteps:\n"
        bad = {
            "partial": "  - {topic: a, why: one, phase: problem}\n  - {topic: b, why: two}\n  - {topic: c, why: three, phase: cause}\n",
            "unknown": "  - {topic: a, why: one, phase: problem}\n  - {topic: b, why: two, phase: later}\n  - {topic: c, why: three, phase: cause}\n",
            "order": "  - {topic: a, why: one, phase: cause}\n  - {topic: b, why: two, phase: problem}\n  - {topic: c, why: three, phase: causes}\n",
            "no overview": "  - {topic: a, why: one, phase: problem}\n  - {topic: b, why: two, phase: cause}\n  - {topic: c, why: three, phase: cause}\n",
            "must start with the problem": "  - {topic: a, why: one, phase: causes}\n  - {topic: b, why: two, phase: cause}\n  - {topic: c, why: three, phase: cause}\n",
        }
        for name, steps in bad.items():
            s = self.site(tracks={"t": head + steps})
            code, err = s.run()
            self.assertEqual(code, 1, name)
            self.assertIn("phase", err, name)

    def test_problem_track_needs_a_problem_statement(self):
        track = ("name: T\ntitle: x\nkind: problem\nsteps:\n  - {topic: a, why: one, phase: problem}\n"
                 "  - {topic: b, why: two, phase: causes}\n  - {topic: c, why: three, phase: cause}\n")
        code, err = self.site(tracks={"t": track}).run()
        self.assertEqual(code, 1)
        self.assertIn("'problem'", err)

    def test_general_track_has_no_phases_and_kind_is_checked(self):
        phased = TRACK3.replace("{topic: a, why: first}", "{topic: a, why: first, phase: problem}")
        code, err = self.site(tracks={"t": phased}).run()
        self.assertEqual(code, 1)
        self.assertIn("general track has no phases", err)
        code, err = self.site(tracks={"t": "kind: odd\n" + TRACK3}).run()
        self.assertEqual(code, 1)
        self.assertIn("'kind'", err)

    def test_too_many_steps(self):
        steps = "".join("  - {topic: a, why: w}\n" for _ in range(11))
        s = self.site(tracks={"t": "name: X\ntitle: T\nsteps:\n" + steps})
        code, err = s.run()
        self.assertEqual(code, 1)
        self.assertIn("needs 3-10 steps", err)


class ContentTests(BuildTestCase):
    def test_content_without_topic_is_error(self):
        s = self.site(content={"zzz.md": "x"})
        code, err = s.run()
        self.assertEqual(code, 1)
        self.assertIn("no topic with id 'zzz'", err)

    def test_home_page_is_built_and_flagged(self):
        s = self.site(content={"_home.md": "---\ntitle: Home\n---\nWelcome, see [A](topic:a)."})
        self.assertEqual(s.run()[0], 0)
        self.assertIn('href="#topic=a"', read(s.out("content", "_home.html")))
        self.assertIn('"home": true', read(s.out("graph.json")))

    def test_no_home_page_is_fine(self):
        s = self.site()
        self.assertEqual(s.run()[0], 0)
        self.assertIn('"home": false', read(s.out("graph.json")))

    def test_broken_home_is_skipped_when_lenient(self):
        s = self.site(content={"_home.md": "[x](topic:nope)"})
        self.assertEqual(s.run()[0], 1)
        self.assertEqual(s.run(lenient=True)[0], 0)
        self.assertIn('"home": false', read(s.out("graph.json")))

    def test_about_page_is_built_and_flagged(self):
        s = self.site(content={"_about.md": "---\ntitle: About\n---\nSee [A](topic:a)."})
        self.assertEqual(s.run()[0], 0)
        self.assertIn('href="#topic=a"', read(s.out("content", "_about.html")))
        self.assertIn('"about": true', read(s.out("graph.json")))
        self.assertIn('"home": false', read(s.out("graph.json")))

    def test_no_about_page_is_fine(self):
        s = self.site()
        self.assertEqual(s.run()[0], 0)
        self.assertIn('"about": false', read(s.out("graph.json")))

    def test_about_page_is_not_counted_as_an_article(self):
        s = self.site(content={"_about.md": "About the project, long enough."})
        code, err = s.run()
        self.assertEqual(code, 0)
        self.assertNotIn("no topic with id '_about'", err)

    def test_underscore_files_are_ignored(self):
        s = self.site(content={"_prompt.md": "notes"})
        self.assertEqual(s.run()[0], 0)

    def test_broken_article_fails_strict_but_is_skipped_when_lenient(self):
        s = self.site(content={"a.md": "![x](a/missing.png)", "b.md": "fine"})
        code, err = s.run()
        self.assertEqual(code, 1)
        self.assertIn("a/missing.png", err)
        code, err = s.run(lenient=True)
        self.assertEqual(code, 0)
        self.assertIn("WARNING", err)
        self.assertFalse(os.path.exists(s.out("content", "a.html")))
        self.assertTrue(os.path.exists(s.out("content", "b.html")))
        self.assertIn('"has_content": false', read(s.out("graph.json")))

    def test_topic_link_in_article_and_details(self):
        t = TOPICS.replace("description: First}", "description: First, details: 'See [B](topic:b).'}")
        s = self.site(topics=t, content={"a.md": "Go to [B](topic:b)."})
        self.assertEqual(s.run()[0], 0)
        self.assertIn('href="#topic=b"', read(s.out("content", "a.html")))
        self.assertIn("#topic=b", read(s.out("graph.json")))

    def test_unknown_topic_link_is_an_error(self):
        s = self.site(content={"a.md": "Go to [X](topic:nope)."})
        code, err = s.run()
        self.assertEqual(code, 1)
        self.assertIn("unknown topic id", err)

    def test_list_right_after_a_text_line_is_an_error(self):
        s = self.site(content={"a.md": "**Title.**\n- one\n- two\n"})
        code, err = s.run()
        self.assertEqual(code, 1)
        self.assertIn("blank line before the list", err)
        ok = self.site(content={"a.md": "**Title.**\n\n- one\n- two\n\n```\ntext\n- not a list\n```\n"})
        self.assertEqual(ok.run()[0], 0)

    def test_bad_frontmatter_and_sources(self):
        s = self.site(content={"a.md": "---\nsources: [ftp://x]\n---\ntext"})
        code, err = s.run()
        self.assertEqual(code, 1)
        self.assertIn("not an http(s) URL", err)

    def test_raw_html_goes_through_sanitizer(self):
        s = self.site(content={"a.html": "<p>ok</p><script>bad()</script>"})
        self.assertEqual(s.run()[0], 0)
        out = read(s.out("content", "a.html"))
        self.assertIn("ok", out)
        self.assertNotIn("script", out)

    def test_both_md_and_html_is_error(self):
        s = self.site(content={"a.md": "x", "a.html": "y"})
        self.assertEqual(s.run()[0], 1)

    def test_demo_is_copied_unchanged(self):
        demo = "<html><script>var x=1</script></html>"
        s = self.site(content={"a.md": '<iframe src="a/d.html" title="t" width="800" height="450"></iframe>', "a/d.html": demo})
        self.assertEqual(s.run()[0], 0)
        self.assertEqual(read(s.out("content", "a", "d.html")), demo)
        self.assertIn('src="content/a/d.html"', read(s.out("content", "a.html")))

    def test_asset_copied_and_svg_not(self):
        s = self.site(content={"a.md": "![p](a/p.png)", "a/p.png": b"x", "a/evil.svg": "<svg/>"})
        self.assertEqual(s.run()[0], 0)
        self.assertTrue(os.path.exists(s.out("content", "a", "p.png")))
        self.assertFalse(os.path.exists(s.out("content", "a", "evil.svg")))


if __name__ == "__main__":
    unittest.main()
