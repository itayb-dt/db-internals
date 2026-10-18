#!/usr/bin/env python3
"""Render content/<topic-id>/src/*.svg to content/<topic-id>/<name>.png (2x).

Authors edit the SVG sources; the PNGs are what the build publishes (SVG files are not
published because an SVG opened directly can run scripts).
Needs: pip install playwright && playwright install chromium
Set PW_CHROMIUM to use an existing Chromium binary.
Usage: python3 scripts/render_images.py [topic-id ...]
"""
import glob, os, re, sys

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(only):
    sources = sorted(glob.glob(os.path.join(ROOT, "content", "*", "src", "*.svg")))
    sources = [s for s in sources if not only or s.split(os.sep)[-3] in only]
    if not sources:
        print("No SVG sources found in content/<topic-id>/src/")
        return 0
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=os.environ.get("PW_CHROMIUM") or None)
        for src in sources:
            svg = open(src, encoding="utf-8").read()
            m = re.search(r'width="(\d+)" height="(\d+)"', svg)
            w, h = int(m.group(1)), int(m.group(2))
            page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
            page.set_content(f'<body style="margin:0">{svg}</body>')
            out = os.path.join(os.path.dirname(os.path.dirname(src)), os.path.basename(src)[:-4] + ".png")
            page.screenshot(path=out, clip={"x": 0, "y": 0, "width": w, "height": h})
            page.close()
            print("wrote", os.path.relpath(out, ROOT))
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
