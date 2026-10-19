# Prompt: how to write a content article

Use this when an AI (or a person) writes `content/<topic-id>.md`. Files starting with `_` are ignored by the build.

## Audience

Backend engineers and DBAs who know SQL but not database internals. Assume no knowledge of the topic. Do not assume knowledge of the engine's source code.

## Style

- Write short, clear sentences. One idea per sentence.
- Prefer plain words. Define a term the first time you use it.
- Use the active voice. Say what the database does, not what "is done".
- Keep paragraphs to 2-4 sentences.
- No marketing language, no emojis, no filler such as "powerful" or "simply".
- Explain in your own words. Do not copy text from the documentation.

## Real-world usage

- Start each section from a situation the reader recognises: a slow query, a table that grew, a failed backup, a surprising bill.
- Show how the concept appears in daily work: which query, which setting, which catalog view.
- Give a realistic example before the general rule.
- Say when the advice does not apply. Name the trade-off.
- Cover the common mistake and how to spot it.

## Performance

Every article must answer, for its topic:

- What does it cost? Name the cost: reads, writes, memory, CPU, WAL, locks, disk space.
- When does that cost show up? Under which workload or data size.
- How do I measure it? Give a query or tool, and how to read the result.
- When should I worry? Give a rough threshold and say it is a rule of thumb.
- What can I change? List the settings or design choices, with their downside.

## Structure

- Frontmatter: `title`, `updated`, `sources` (URLs), optional `reviewed_by`.
- Open with a scope line: which engine, which version, and how other engines differ in one or two sentences.
- Use `##` headings, short paragraphs, fenced code blocks with a language, and at most one comparison table.
- End with a short practical checklist. The build adds the Sources list from the frontmatter.
- Target 900-1400 words plus small code blocks.

## Visuals

Hard ideas need a picture. Add one when the text alone makes the reader work too hard.

- Use a static **image** for structure: a tree, a page layout, a plan. Use a **live demo** for something that happens over time: a wait, a split, a retry.
- Keep each article about one idea. If an article grows long, split it into sub topics and give each its own visual.
- Images: PNG in `content/<topic-id>/`, small (aim for under 200 KB), with alt text. Author diagrams as SVG in `content/<topic-id>/src/` and render them with `python3 scripts/render_images.py`.
- Demos: one plain HTML file, `content/<topic-id>/<name>.html`, embedded with `<iframe src="<topic-id>/<name>.html" ...>`. No libraries and no network requests. Loop by itself, run about 10 seconds or less, use simple motion, and show the state in words as it changes. Draw the scene as a function of time so the loop restarts cleanly. Respect `prefers-reduced-motion` with one still frame.
- Show a visual only for what the article explains. Do not decorate.

## Accuracy

- Verify every claim against the official documentation for the stated version. Put the pages in `sources`.
- Do not invent numbers, parameter names or catalog columns.
- Run every SQL snippet with `python3 scripts/verify_sql.py`. Add sample tables in `tests/sql_setup/<article>.sql`. Mark any block that cannot run with `-- not run: <reason>`, and start the article with a "How this was checked" line that says what was run and on which version.
- Mark rules of thumb as rules of thumb.
- Say what you are not sure about.

## Files

- `content/<topic-id>.md` must match a topic `id` in `data/*.yaml`.
- Images go in `content/<topic-id>/` and are referenced as `<topic-id>/file.png`. Add alt text.
- Link to other topics by id, for example `[B-Tree](topic:btree)`, the first time you mention them. Do not link by name or URL.
- Raw HTML is sanitised. Scripts, event handlers and iframes (except YouTube and Vimeo) are removed.
