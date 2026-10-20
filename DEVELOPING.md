# Developing the project

The technical guide: how the repository is organised, how to add topics, articles, tracks and demos, how to run and check everything, and how it is deployed. For what the project is and who it is for, see the [README](README.md). For the contribution process, see [CONTRIBUTING.md](CONTRIBUTING.md).

## How it works

The content is plain YAML and Markdown. A Python script validates it and builds a static site into `_site/`. There is no backend. GitHub Actions builds, tests and deploys on every push to `main`, so committing is the only step.

```
data/*.yaml      ->                      -> _site/graph.json
content/*.md     ->  scripts/build.py    -> _site/content/<id>.html (sanitised) + images
site/index.html  ->                      -> _site/index.html (the viewer)
```

In the viewer, dot colour is the subject and height is the level, from concept at the bottom to operational detail at the top. Dashed links are soft prerequisites. A ring on a dot means the topic has a full article.

## Repository layout

```
data/                one YAML file per subject; the source of truth for topics
content/             long-form articles, one per topic (see "Add a content article")
  _prompt.md         guidelines for writing articles (ignored by the build)
  <topic-id>.md      article for a topic; <topic-id>/ holds its images
site/                the viewer (static, no dependencies)
scripts/build.py     validates everything and writes _site/
tests/               unit tests and a browser smoke test
.github/workflows/   build, test and deploy to GitHub Pages
_site/               build output; git-ignored, never commit it
```

## Add or edit a topic

1. Open the YAML file for the subject, or create a new file in `data/`.
2. Add a topic:

   ```yaml
   - id: gin                       # unique, lowercase, never changes
     name: GIN
     domain: Specialised indexes   # group inside the subject
     level: 2                      # 0-4, see below
     description: Inverted index. One row can appear under many keys.
     evidence:                     # how you know someone understands it
       - Explain why GIN fits "array contains" queries
     prerequisites:
       - {id: index, reason: A GIN is a kind of index}
       - {id: toast, reason: Large key lists use out-of-line storage, strength: soft}
   ```

3. Open a pull request (or commit to `main`). The checks run automatically. To try it locally first:

   ```
   pip install -r requirements.txt
   python3 scripts/build.py --serve
   ```

A new subject file starts with:

```yaml
subject: Transactions
color: "#c78bff"
order: 6                       # position in the legend and on the home page (optional)
description: "One sentence about the subject, shown on the home page."   # required
topics:
  - ...
```

Put the `description` in quotes. A colon inside an unquoted value breaks the YAML, and the build reports it.

### Fields

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Stable unique identifier. Links refer to it, so don't rename it. |
| `name` | yes | Label shown on the dot. |
| `domain` | yes | Group within the subject, shown in the panel. |
| `level` | yes | 0 Concept, 1 Core structure, 2 Mechanism, 3 Implementation, 4 Operational. Sets the height. |
| `description` | yes | One or two plain sentences. |
| `details` | no | A few lines of Markdown shown under the description. |
| `evidence` | no | Observable statements that show understanding. |
| `prerequisites` | no | List of `{id, reason, strength}`. `strength` is `hard` (default) or `soft`. |

The build fails on missing fields, duplicate ids, unknown prerequisites and cycles.

### Writing good topics

- One teachable idea per topic. If the description needs "and", split it.
- Write prerequisites for understanding, not for chronology. Ask "could someone follow this without knowing that?"
- Give every prerequisite a `reason`. It makes the link reviewable.
- Write `evidence` as something you could check, such as "explain why X", not "know about X".

## Add a content article

Create `content/<topic-id>.md`. If the file name matches a topic `id`, the topic is linked to it automatically. No YAML change is needed.

```markdown
---
title: "TOAST: how PostgreSQL stores large values"   # optional, defaults to the topic name
updated: 2026-10-17                                   # optional
sources:                                              # optional, http(s) URLs, listed at the end
  - https://www.postgresql.org/docs/17/storage-toast.html
reviewed_by: Jane Doe                                 # optional
---

Text, `code`, tables and images.

![Chunking](toast/chunks.png)
```

Rules:

- Use Markdown (tables and fenced code are supported) or a raw `.html` file. Both go through the same sanitiser: scripts, event handlers and styles are removed, and iframes are allowed only for YouTube and Vimeo embeds.
- Put images in `content/<topic-id>/` and reference them relative to `content/`, for example `toast/chunks.png`. Diagrams can be authored as SVG in `content/<topic-id>/src/` and rendered to PNG with `python3 scripts/render_images.py` (needs Playwright). Commit both. The PNG is published, the SVG source is not. Allowed files: png, jpg, gif, webp, avif, pdf, txt, sql, csv. SVG is not allowed.
- Link to another topic with `[B-Tree](topic:btree)`, using the topic id. The build fails on an unknown id. In the viewer a click opens that topic, and the address bar gets a shareable link such as `#topic=btree`. The same links work in `details`.
- A file that matches no topic id is an error. Topics without an article are only listed in the build output.
- Live demos are single, dependency-free HTML files next to the topic's images: `content/<topic-id>/<name>.html`. Embed one in the article with `<iframe src="<topic-id>/<name>.html" title="..." width="800" height="450"></iframe>`. A demo can only be embedded by its own topic's article. It runs in a sandbox (scripts allowed, no access to the page) and is copied as written, so review it like code. The build fails if the file is missing, and the browser test opens every demo and fails on console errors. Keep demos short, looping, and independent of any CDN.
- `content/_home.md` is the start page shown on the right when nobody has selected a topic. It supports the same frontmatter and `topic:` links. Below its first part the viewer lists the subjects, each with the `description` from its data file, and your "About the project" heading comes after them. The home pane has two tabs: the intro and the learning tracks.
- Other files and folders starting with `_` are ignored. Read `content/_prompt.md` before writing an article.

## Run locally

```
pip install -r requirements.txt
python3 scripts/build.py --serve      # builds, then serves http://localhost:8000
python3 -m unittest discover -s tests # unit tests
```

Opening `site/index.html` directly from disk won't work, because browsers block loading `graph.json` from a local file.

The browser smoke test needs `pip install -r requirements-dev.txt` and `playwright install chromium`, then `python3 tests/smoke.py`.

## Learning tracks

A learning track is an ordered path of 3 to 10 topics, from basic to advanced. It is shown on the home page, where a click expands its steps, and inside each topic as "step 3 of 9" with Previous and Next links. Add one as a file in `data/tracks/<name>.yaml`:

```yaml
order: 1                       # position on the home page
name: My table is huge
title: How big tables are stored, grow, get cleaned up and get split
steps:
  - topic: page                # a topic id from data/*.yaml
    why: The unit of disk I/O and caching.
```

Each step needs a `topic` and a one-line `why`. The build fails on an unknown topic, a duplicate, or a wrong number of steps. Steps whose topic has no article yet are labelled "coming soon".

Write the steps in block style as above. In the one-line `{...}` style a comma ends the value, so the rest of the sentence would be lost. The build reports this as an unexpected key.

## Checking the SQL in the articles

`python3 scripts/verify_sql.py` runs every `sql` block from `content/*.md` against a real PostgreSQL, one throwaway database per article, with sample tables from `tests/sql_setup/<article>.sql`. The examples that need two sessions (deadlock, MVCC visibility, vacuum held back by an old snapshot) are run with two real sessions. Point it at a throwaway server with the usual `PGHOST`, `PGPORT` and `PGUSER` variables. It needs `psql`. It is not part of CI.

If a block cannot run, because it needs a contrib extension, two sessions or a shell, start it with `-- not run: <reason>` and say so in the article's "How this was checked" line.

## Checks and deployment

- **Pull requests:** unit tests, a strict build and a browser smoke test (every topic and article is opened). Any problem fails the check.
- **Push to `main`:** the same checks, then deploy to GitHub Pages, then a browser check of the live site. On `main`, an article with a problem is skipped with a warning (see the run summary) so one bad article does not block the others. Data errors, such as cycles or unknown prerequisites, still stop the deploy.
- **Rollback:** revert the commit on `main`. The site redeploys.

## Publish on GitHub Pages

Settings, then Pages, then Source: **GitHub Actions**. The workflow does the rest.
