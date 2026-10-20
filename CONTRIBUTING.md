# Contributing

Thank you for helping. Contributions are topics, prerequisite fixes, better descriptions and articles.

## Before you start

- Topics live in `data/*.yaml`. See [DEVELOPING.md](DEVELOPING.md) for the fields.
- Articles live in `content/<topic-id>.md`. Read `content/_prompt.md` first. It describes the style: short sentences, real-world usage, and the performance angle.

## The process

1. Make your change on a branch and open a pull request. Committing to `main` also works, but a pull request shows check results before anything goes live.
2. Optional: check locally with `python3 scripts/build.py --serve`.
3. The checks run automatically: unit tests, a strict build and a browser test that opens every topic. Fix anything they report. The messages say which file and what to change.
4. After the merge to `main`, the site deploys by itself.

Do not commit `_site/` or generated JSON.

## Content rules

- Verify technical claims against the official documentation for a stated version, and list the pages in `sources`.
- Do not invent numbers, parameter names or catalog columns.
- Run the SQL you include with `python3 scripts/verify_sql.py` (see [DEVELOPING.md](DEVELOPING.md)). If a block cannot run, mark it `-- not run: <reason>` and say so in the article.
- Mark rules of thumb as rules of thumb.
- Explain in your own words. Do not copy documentation text.
- Images go in `content/<topic-id>/` with alt text. A live demo is one HTML file in the same folder, embedded with an iframe (see [DEVELOPING.md](DEVELOPING.md)). Demos are code: they are copied as written, so review them carefully.
- Link to other topics by id: `[GIN](topic:gin)`. An unknown id fails the build.

## Learning tracks

A track is a file in `data/tracks/` (see [DEVELOPING.md](DEVELOPING.md)). Keep it to one goal, 3 to 10 steps, ordered from basic to advanced, and give every step a one-line reason. Prefer topics that already have an article, and add the missing articles in the order of the track.

## Topic rules

- One teachable idea per topic.
- Give every prerequisite a `reason`.
- Write `evidence` as something checkable, such as "explain why X".
- Never rename an `id`. Links and article file names depend on it.
