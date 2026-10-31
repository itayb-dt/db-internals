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

## Level of detail

Keep it high level. The reader wants to know what the thing is, when to use it, and which problem it solves. They do not need to learn how to build it.

- **No setup commands.** Do not show `CREATE`, `ALTER` or `DROP` statements to build the example. Say it in words: "an index on `customer_id`", "a table with a `tags` array". The tables and indexes the examples assume go in `tests/sql_setup/<article>.sql`, and the article describes them in one sentence.
- **Extensions.** Say that it is an extension and that it is installed like any other. Do not show `CREATE EXTENSION`.
- **Creating an object.** Say it in a sentence: "create a bloom index on these columns". Do not show `CREATE INDEX` or other DDL just to show how to type it.
- **Exception.** Show a DDL statement or a `SELECT` only when there is a very good reason: the statement itself is what the article explains, or the reader cannot understand the point without it. Keep it to one short block, and ask yourself whether a sentence would do.
- **A `SELECT` to make a point is welcome.** So are `EXPLAIN` and queries on system views and catalog tables, such as `pg_stat_user_indexes`, `pg_stats` or `pg_class`. Every query must answer a question the reader has, such as "is it used?", "how big is it?" or "is it keeping up?".
- **Name the lever, not the syntax.** When the advice is to change something, say what it is ("lower `pages_per_range`", "rebuild the index online", "turn off fast update") and its downside. Do not paste the full command.
- **Ask of every code block:** does it help the reader decide or understand, or does it only show how to type something? Remove the second kind.

## Performance

Every article must answer, for its topic:

- What does it cost? Name the cost: reads, writes, memory, CPU, WAL, locks, disk space.
- When does that cost show up? Under which workload or data size.
- How do I measure it? Give a query or tool, and how to read the result.
- When should I worry? Give a rough threshold and say it is a rule of thumb.
- What can I change? List the settings or design choices, with their downside.

## Structure

- Frontmatter: `title`, `updated`, `sources` (URLs), optional `reviewed_by`. No "How this was checked" note in the text.
- Open with a scope line: which engine, and how other engines differ in one or two sentences. **Do not name a version** ("PostgreSQL 17") in the scope line or the introduction. Name a version only for a real difference, and say it where it applies: "from PostgreSQL 13", "in 16 and earlier this view is called ...". See "Versions" below.
- Use `##` headings, short paragraphs, fenced code blocks with a language, and at most one comparison table.
- End with a short practical checklist. The `sources` from the frontmatter are shown in the Metadata of the topic, not in the text.
- Target 900-1400 words plus small code blocks.

## Visuals

Hard ideas need a picture. Add one when the text alone makes the reader work too hard.

- Use a static **image** for structure: a tree, a page layout, a plan. Use a **live demo** for something that happens over time: a wait, a split, a retry.
- Keep each article about one idea. If an article grows long, split it into sub topics and give each its own visual.
- Images: PNG in `content/<topic-id>/`, small (aim for under 200 KB), with alt text. Author diagrams as SVG in `content/<topic-id>/src/` and render them with `python3 scripts/render_images.py`.
- Demos: one plain HTML file, `content/<topic-id>/<name>.html`, embedded with `<iframe src="<topic-id>/<name>.html" ...>`. No libraries and no network requests. Loop by itself, give each step about 2 seconds so a reader can follow it (a whole demo of 20 to 30 seconds for a process with several steps, less for a simple idea), use simple motion, and show the state in words as it changes. Draw the scene as a function of time so the loop restarts cleanly. Respect `prefers-reduced-motion` with one still frame.
- One demo shows one idea. If it needs more than about 30 seconds, split it into several demos (for example one for a search and one for an insert) and embed each where its idea is explained. An article may embed more than one demo.
- **Use an animation for something complicated that happens over time**, such as a chain of causes and effects. Example: the CPU reaches 100%, the health check gets no answer, the load balancer marks the server down, the standby is promoted with a cold cache, and the standby overloads too. **Do not animate a list, a table or a checklist** (for example a list of root causes being ticked off). If the content is a list, write the list.
- Show a visual only for what the article explains. Do not decorate.

## Accuracy

- Verify every claim against the official PostgreSQL documentation for a recent version. Put the pages in `sources`. Do not repeat the version of the documentation in the text.
- Do not invent numbers, parameter names or catalog columns.
- Run every SQL snippet with `python3 scripts/verify_sql.py`. Add sample tables in `tests/sql_setup/<article>.sql`. Mark any block that cannot run with `-- not run: <reason>`. Do **not** put a "How this was checked" note in the article: the reader does not need it. Record what was run and on which version, which claims come from the documentation or from general practice, and what could not be checked, in `Product/article-review-notes.md`.
- Mark rules of thumb as rules of thumb.
- Say what you are not sure about.

## Versions

These articles are about basic, common problems and mechanisms. Write them so they hold for all recent PostgreSQL versions, and **do not mention a version** unless there is a real difference.

- Do not write "This article is about PostgreSQL 17" or "the PostgreSQL 17 documentation". It suggests that 16 or 18 behave differently, and usually they do not.
- When a feature, a setting, a column, a view or a default **changed between versions**, say so where it applies, in a few words: "from PostgreSQL 13", "in PostgreSQL 15 and later", "before PostgreSQL 10". Check the release notes before you write it.
- If a command or view is different in older versions, name the old form once, and then use the current one.
- Links in `sources` may point to a specific version of the documentation. That is a reference, not a claim about the article.

## Files

- `content/<topic-id>.md` must match a topic `id` in `data/*.yaml`.
- Images go in `content/<topic-id>/` and are referenced as `<topic-id>/file.png`. Add alt text.
- Link to other topics by id, for example `[B-Tree](topic:btree)`, the first time you mention them. Do not link by name or URL.
- Raw HTML is sanitised. Scripts, event handlers and iframes (except YouTube and Vimeo) are removed.
