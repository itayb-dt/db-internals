# Database Internals: functional requirements

**Version:** 0.22 draft for review  **Date:** 2026-10-24  **Owner:** Itay Braun

This document describes what the product must do: the viewer (UI), the articles, and the learning tracks. It is the plan to review and edit. It is also the source for QA: every requirement has an ID, a status and a way to check it.

## How to read this document

- **Status** is one of:
  - **Built**: implemented today. Written from the code in this repository, as of the date above.
  - **Partial**: implemented in part. The gap is stated.
  - **Proposed**: not built. This is a suggestion for you to accept, change or drop.
- **Check** says how QA verifies it: **Auto** (the build, the unit tests or the browser smoke test already fails on it), **Manual** (a person looks), or **None yet** (no check exists).
- Section 9 lists the decisions I need from you. Section 10 lists where the product is not yet specified.
- IDs never change. Retired requirements are marked **Dropped**, not deleted.

## 1. Product summary

**What it is.** An open, interactive map of how databases work, built around PostgreSQL. A static website, with no server and no accounts.

**Who it is for.**

| User | Need |
|---|---|
| Solution Architect (primary) | Learn database internals deeply enough to explain them to customers, and share a link |
| Customer engineer or DBA | Understand why something happens, and why a suggested fix should work |
| Contributor | Add or fix a topic, an article or a track with a pull request |

**Why it exists** (from the README): help Solution Architects explain deep database internals, help customers solve problems with confidence, and show Dynatrace as a company that helps customers understand the technology beneath their problems.

**Principles.**

1. Plain language for people who know SQL but not internals.
2. Every claim comes from official documentation, and every SQL snippet is run or marked as not run.
3. Everything is connected: no topic stands alone, and every link has a reason.
4. Everything is plain files in Git. Anyone can contribute with a pull request.
5. Performance is the angle: what it costs, how to measure it, what to change.

**Status of the product:** early and experimental. Public, but not announced.

## 2. Concepts and vocabulary

| Term | Meaning |
|---|---|
| **Subject** | A colour-coded group of topics, such as Storage or Indexing. Defined by one file in `data/`. |
| **Topic** | One teachable idea, such as Page, MVCC or Deadlock. The unit of the map. |
| **Level** | How deep a topic is: 0 Concept, 1 Core structure, 2 Mechanism, 3 Implementation, 4 Operational. |
| **Prerequisite** | A link from one topic to another that must be understood first. Has a reason, and a strength: **hard** (default) or **soft**. |
| **Evidence** | Checkable statements that show someone understands a topic ("explain why X"). |
| **Article** | The long-form text for a topic. A topic may have none. |
| **Demo** | An animation, one self-contained HTML file embedded in an article. |
| **Track** | An ordered path of 3 to 10 topics around one goal, each step with a one-line reason. |
| **Map** | The 3D graph of topics on the left half of the screen. |
| **Panel** | The right half of the screen, which shows the home page or one topic. |

## 3. Content inventory (snapshot)

As of this version: **57 topics**, **48 articles**, **7 subjects**, **7 tracks**, **28 demos**.

| Subject | Topics | Articles |
|---|---|---|
| Storage | 14 | 11 |
| Indexing | 8 | 6 |
| Query planning | 4 | 4 |
| Partitions | 3 | 3 |
| Concurrency | 3 | 3 |
| Architecture | 10 | 8 |
| Observability | 7 | 7 |

| Track | Steps | Steps with an article |
|---|---|---|
| PostgreSQL Storage | 10 | 7 (missing: Page, Tuple, Heap table) |
| Anatomy of PostgreSQL | 10 | 7 (missing: Databases, Files and tablespaces, Heap table) |
| Database Monitoring Overview | 4 | 4 |
| Problem: Slow query | 7 | 7 |
| Problem: Large database | 9 | 9 |
| Problem: Low free disk space | 8 | 8 |
| Problem: High CPU | 10 | 8 (replication and the host are planned) |

## 4. User stories

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| US-1 | Solution Architect | open the site and see what it is in ten seconds | I know whether it helps me |
| US-2 | Solution Architect | follow a track from basic to advanced | I learn a subject in the right order |
| US-3 | Solution Architect | send a customer a link to one topic | we discuss the same thing |
| US-4 | Customer engineer | explore the map and see what a topic builds on | I find the gap in my understanding |
| US-5 | Customer engineer | read how to measure and what to change | I can act on a real problem |
| US-6 | Customer engineer | see a short animation of a hard idea | I understand it faster than from text |
| US-7 | Contributor | add a topic or an article and get clear errors | I do not break the site |
| US-8 | Owner | know that published content is accurate | the project is trusted |

## 5. Viewer (UI) requirements

### 5.1 Layout and loading

| ID | Requirement | Status | Check |
|---|---|---|---|
| UI-01 | The page has two halves: the map on the left (50% width) and the panel on the right (50% width). | Built | Manual |
| UI-02 | Below 900 px width the layout stacks: the map on top (45% height) and the panel below (55%). The drag hint is hidden. | Built | Manual |
| UI-03 | A header at the top left shows the Dynatrace icon and the title "Database Internals". The icon links to the Dynatrace Databases documentation and opens in a new tab. | Built | Manual |
| UI-04 | On load the viewer fetches the graph data. If that fails, a full-screen error says the data could not be loaded and how to run the site over HTTP. | Built | None yet |
| UI-05 | The page is a single static page that works from any web host. It needs no server code. | Built | Auto (live-site check after deploy) |
| UI-06 | Dark theme only. | Built | Manual |

### 5.2 The map

| ID | Requirement | Status | Check |
|---|---|---|---|
| MAP-01 | Every topic is a dot, positioned in 3D. Height shows the level (concept at the bottom, operational detail at the top). Topics of one subject cluster together. | Built | Manual |
| MAP-02 | Dot colour is the subject. Dot size grows with the number of topics that depend on it (capped). | Built | Manual |
| MAP-03 | Every prerequisite is a line with a moving dot along it. **Hard** prerequisites are solid. **Soft** ones are dashed. | Built | Manual |
| MAP-04 | A topic with an article has a ring around its dot. A legend line explains it ("Ring = has a full article"). | Built | Manual |
| MAP-05 | The topic name is drawn under each dot. | Built | Manual |
| MAP-06 | Drag rotates the map. Scroll zooms between 0.4x and 3x. Vertical rotation is limited so the map cannot flip. | Built | Manual |
| MAP-07 | The map rotates slowly by itself. It stops when a topic is selected and resumes when the selection is cleared. | Built | Manual |
| MAP-08 | A click (not a drag) on a dot within 28 px selects the nearest topic. A click on empty space clears the selection. | Built | Manual |
| MAP-09 | Selecting a topic highlights it and all its direct and indirect prerequisites. Everything else fades. Links between highlighted topics are emphasised. | Built | Manual |
| MAP-10 | The map layout is computed in the browser and is not stored. It is different on each load. | Built | n/a |
| MAP-11 | The map responds to window resizing, and to high-density screens. | Built | Manual |
| MAP-12 | The map shows a count of concepts and prerequisite links ("38 concepts and 76 prerequisite links"). | Built | Manual |
| MAP-13 | Touch support (pinch to zoom, one-finger rotate) on tablets and phones. | Proposed | None yet |
| MAP-14 | Moved to section 5.3a (search). | Dropped here | n/a |
| MAP-15 | A "reduce motion" setting that stops the auto-rotation and the moving dots. | Proposed | None yet |
| MAP-16 | On load the whole map fits in its half of the screen, whatever the number of topics. The default zoom is computed from the size of the layout, and the reader can still zoom between 0.3x and 3x. | Built | Manual |
| MAP-17 | Not every dot needs a visible name. Names are placed in order of importance (the selected topic, search matches and the hovered topic first, then topics with an article, then topics with more dependents) and a name that would overlap one already shown is left out. Zooming in does not reveal more names, so use hover or search. | Built | Manual |
| MAP-18 | Hovering a dot shows its name and changes the cursor to a pointer. | Built | Manual |
| MAP-19 | Choosing a topic from search or from a topic list moves the map so the dot is in the centre. Going back to the home page moves it back. | Built | Manual |
| MAP-20 | The map stays readable with 50 or more topics. | Partial: designed for it (MAP-16, MAP-17) but only tested with 38 | None yet |

### 5.3 Legend and subject filter

| ID | Requirement | Status | Check |
|---|---|---|---|
| LEG-01 | A legend window at the bottom left lists every subject with its colour and its number of topics, in subject order. | Built | Manual |
| LEG-02 | Clicking the **coloured dot** of a subject hides or shows its dots and the links that touch them. Hidden subjects are dimmed in the legend. (Changed in 0.2: before, clicking the whole row did this.) | Built | Manual |
| LEG-03 | If the selected topic belongs to a subject that becomes hidden, the selection is cleared and the home page is shown. | Built | Manual |
| LEG-04 | A hint at the bottom of the map explains the controls ("Drag to spin, Scroll to zoom, Click a dot"). | Built | Manual |
| LEG-05 | The legend window has a close button. When closed, a small "Subjects" button at the same place brings it back. | Built | Auto |
| LEG-06 | The choice (open or closed) is remembered in the browser for the next visit. | Built | Manual |
| LEG-07 | Clicking the **name** of a subject expands it to the list of its topics. Clicking again collapses it. | Built | Auto |
| LEG-08 | A listed topic opens in the panel and is centred on the map. If its subject was hidden, the subject is shown again. | Built | Auto (opens) |
| LEG-09 | Each listed topic shows a ring if it has an article, and "soon" and a dimmed name if not, and its level. | Built | Manual |
| LEG-10 | Topics in a list are sorted by level (basic to advanced), then by name. This follows the order in which a reader would learn them. | Built (see D-11) | Manual |
| LEG-11 | The list scrolls inside the window when it is long, and never grows past the screen. | Built | Manual |

### 5.3a Search

| ID | Requirement | Status | Check |
|---|---|---|---|
| SRCH-01 | A search box sits at the top left of the map, under the header. Pressing `/` anywhere on the page puts the cursor in it (unless a text field has focus). | Built | Manual |
| SRCH-02 | Typing shows up to 8 matching topics as a list of name, subject and "article" or "soon". The list updates on every key. | Built | Auto |
| SRCH-03 | A topic matches when every word typed is found in its name, id, subject, domain or description. It does not search article text. | Built | Auto (every topic is found by its name) |
| SRCH-04 | Results are ranked: a word that starts a word of the name first, then a word inside the name or id, then subject or domain, then description. Ties: topics with an article first, then alphabetical. | Built | Manual |
| SRCH-05 | The matches are ringed in yellow on the map while the list is open, and their names are always shown. | Built | Manual |
| SRCH-06 | Up and Down move through the list, Enter opens the highlighted topic, Escape clears the box. Clicking a result opens it. | Built | Auto (Enter) |
| SRCH-07 | Opening a result shows the topic in the panel and centres it on the map. If its subject was hidden, it is shown again. | Built | Auto (opens) |
| SRCH-08 | A query with no match shows the message "No topic matches ...". | Built | Auto |
| SRCH-09 | Search also finds words inside article text. | Proposed | None yet |
| SRCH-10 | Search tolerates a typing mistake ("shrading" finds Sharding) and synonyms ("pool" finds connection pooling). | Proposed | None yet |
| SRCH-11 | The search box is also reachable on a phone, and the results list fits the screen. | Partial: the box is shown below the header on small screens, not tested on a phone | Manual |

### 5.4 Home page (panel with nothing selected)

| ID | Requirement | Status | Check |
|---|---|---|---|
| HOME-01 | The panel opens on the home page, with three tabs: **Database Internals** (default), **Learning tracks** and **About**. | Built | Auto |
| HOME-02 | The first tab shows the intro written in `content/_home.md`: what the map is and how to use it. | Built | Auto |
| HOME-03 | Below the first part of the intro, the page lists one card per subject: colour, name, the number of topics and of articles, and the subject description. Every subject needs a description. | Built | Auto |
| HOME-04 | The text after the subject cards (for example "About the project") comes from `_home.md`. | Built | Manual |
| HOME-05 | If the intro cannot be loaded, a plain title is shown and the subject cards still appear. | Built | Manual |
| HOME-06 | Topic links in the intro open that topic. | Built | Auto |
| HOME-07 | The Learning tracks tab lists every track as a collapsed card (name, title, number of steps). It is hidden if there are no tracks. | Built | Auto |
| HOME-08 | The Home button on the topic bar returns to the home page, on the tab that was open before. | Built | Auto (returns to the home page) |
| HOME-11 | Clicking a subject card expands it to the list of its topics, in the same format and order as the legend (LEG-07 to LEG-10). Clicking a topic opens it. | Built | Auto |
| HOME-12 | The **About** tab shows the page written in `content/_about.md`: what the project is, why it exists, how it is organised, what an article gives you, who it is for, how it is built, and where it stands. It may repeat the first tab. It is hidden if the file does not exist. | Built | Auto |
| HOME-13 | The About page is plain text that the owner can edit. It supports the same Markdown, safety rules and topic links as an article, but it is not a topic and is not counted as an article. | Built | Unit test |
| HOME-09 | The home page shows the three most recent additions or a "what is new" list. | Proposed | None yet |
| HOME-10 | The home page shows a "start here" call to action that opens the recommended first track. | Proposed | None yet |

### 5.5 Topic view (panel with a topic selected)

| ID | Requirement | Status | Check |
|---|---|---|---|
| TOP-01 | A topic view shows, in order: a track bar (if the topic is in a track), a meta line (subject, domain, level), the topic name, the description, and optional details. The number of prerequisites is not shown. | Built | Auto (opens every topic) |
| TOP-02 | Dropped in 0.11: the topic view no longer shows the total number of prerequisites. | Dropped | n/a |
| TOP-13 | **A topic in a problem track has two tabs** under the track header: the article, and **Metadata**. The first tab is named after the step: "The Problem" for the problem articles, "Root causes" for the overview and "Root cause" for the articles on each cause. It opens first on every topic, and shows the article title and the content immediately, with no repeated title or summary above it. | Built | Auto |
| TOP-14 | The **Metadata** tab holds what used to sit above the article: the subject, domain and level, the topic name, its description and details, what it builds on, what it unlocks next, what you can do when you understand it, and the **Sources** of the article. | Built | Auto |
| TOP-15 | A topic in a problem track that has no article yet shows its title, its description and "This article is coming soon" in the first tab. | Built | Auto |
| TOP-16 | A topic that is not in a problem track (a general track, or none) has no tabs, and shows the metadata first and the article below it, as before. | Built | Manual |
| TOP-03 | **Builds directly on** lists the direct prerequisites. **Unlocks next** lists the topics that depend on this one. Each entry shows the subject colour. Hovering shows the reason for the link. An empty list shows "none". | Built | Manual |
| TOP-04 | Clicking an entry in those lists opens that topic. | Built | Manual |
| TOP-05 | **You understand it when you can** lists the evidence statements. | Built | Manual |
| TOP-06 | The details text (a few lines of Markdown) is shown under the description. It supports topic links. It is hidden when empty. | Built | Unit test |
| TOP-07 | A topic with an article shows a "Read the full article" section below, loaded on demand. A topic without one shows no article section. | Built | Auto |
| TOP-08 | The panel scrolls to the top when the view changes. | Built | Manual |
| TOP-09 | A sticky bar at the top of the topic view has the Home button. | Built | Auto |
| TOP-10 | If a topic cannot be displayed, an error message is shown in the panel and the viewer keeps working. | Built | None yet |
| TOP-11 | The topic view says when it was last reviewed by a person. | Partial: article footer shows "Reviewed by" only when the author fills it in | None yet |
| TOP-12 | The prerequisite and unlock lists can be reached with the keyboard (Tab and Enter). | Proposed | None yet |

### 5.6 Article view (inside a topic)

| ID | Requirement | Status | Check |
|---|---|---|---|
| AV-01 | The article loads when a topic is opened. While loading, the panel shows "Loading article...". | Built | Manual |
| AV-02 | If the article fails to load, the panel shows an error with a **Retry** link. A slow response for an earlier topic never overwrites the topic now shown. | Built | None yet |
| AV-03 | A loaded article is cached for the rest of the visit. | Built | n/a |
| AV-04 | Article tables scroll sideways when too wide. Images and demos never overflow the panel. | Built | Manual |
| AV-05 | Embedded demos fill the panel width at a 16:9 shape and load lazily. | Built | Manual |
| AV-06 | Links to other topics (`topic:`) open that topic in the panel. External links open in a new tab. | Built | Auto |
| AV-07 | Images are checked to render in the browser. | Built | Auto |
| AV-08 | The article footer shows "Updated <date>" and optionally "Reviewed by <name>". The **Sources** are not in the article text: they are shown in the Metadata of the topic (TOP-14). Links to external resources may still appear in the body of the article. | Built | Unit test |
| AV-09 | Code blocks are shown in a monospace block, with horizontal scrolling. | Built | Manual |
| AV-10 | A "copy" button on code blocks. | Proposed | None yet |
| AV-11 | A "table of contents" for long articles. | Proposed | None yet |

### 5.7 Navigation, links and history

| ID | Requirement | Status | Check |
|---|---|---|---|
| NAV-01 | Selecting a topic sets the address to `#topic=<id>`. Opening that address opens the topic. | Built | Auto |
| NAV-02 | Opening the Learning tracks tab sets the address to `#tracks`, and the About tab sets `#about`. Opening either address opens that tab. | Built | Manual |
| NAV-03 | An unknown topic id in the address shows the home page. | Built | None yet |
| NAV-04 | The address changes without adding browser history entries (the Back button leaves the site). | Built | Manual |
| NAV-05 | Browser Back and Forward move between topics. | Proposed | None yet |
| NAV-06 | Each topic has its own address that works as a link in Slack or email, and shows a title and description in the preview. | Proposed | None yet |

### 5.8 Accessibility and compatibility

| ID | Requirement | Status | Check |
|---|---|---|---|
| A11Y-01 | Text colour contrast meets WCAG AA. | Proposed | None yet |
| A11Y-02 | Everything that can be clicked can also be reached with the keyboard. Today, only the search box (with `/`, arrows, Enter, Escape) and the tabs work this way. Topic entries, track steps, legend rows and topic lists are clickable lines, not links or buttons. | Partial | None yet |
| A11Y-03 | The map has a text alternative: the list of topics by subject (the home page subject cards are a start). | Partial | None yet |
| A11Y-04 | Demos have a text label and respect "reduce motion" with one still frame. | Built | Manual |
| COMP-01 | Works in current Chrome, Edge, Safari and Firefox on desktop. | Proposed (only Chromium is tested) | Auto (Chromium only) |
| COMP-02 | Usable on a tablet and a phone. | Partial: layout stacks, touch gestures untested | Manual |

## 6. Article requirements

### 6.1 Purpose and audience

| ID | Requirement | Status | Check |
|---|---|---|---|
| ART-01 | An article explains one topic for backend engineers and DBAs who know SQL but not internals. It assumes no knowledge of the topic and none of the engine's source code. | Built (style guide) | Manual (review) |
| ART-02 | An article opens with a scope line that states the engine, and how other engines differ in one or two sentences. It does **not** name a version. | Built (style guide) | Manual |
| ART-04 | **Versions.** An article holds for all recent PostgreSQL versions and does not say "PostgreSQL 17". A version is named only for a real difference ("from PostgreSQL 13", "in 16 and earlier"), at the place where it applies. | Built (rule). All articles were updated in 0.16 | Manual |
| ART-03 | The reference engine is **PostgreSQL**. Articles name differences in other engines. Product articles (for example the Dynatrace track) state their own scope. | Built | Manual |

### 6.2 Structure

| ID | Requirement | Status | Check |
|---|---|---|---|
| ART-10 | An article is a file `content/<topic-id>.md` (or `.html`). The file name must equal a topic id. A file with no matching topic is an error. Having both `.md` and `.html` for one id is an error. | Built | Auto |
| ART-11 | Frontmatter fields: `title` (optional, defaults to the topic name), `updated` (date), `sources` (list of http or https URLs), `reviewed_by` (optional). | Built | Auto |
| ART-12 | Body uses `##` headings, short paragraphs, fenced code with a language, and at most one comparison table. | Built (style guide) | Manual |
| ART-13 | An article ends with a short practical checklist. The build adds the Sources list. | Built (style guide) | Manual |
| ART-14 | Target length: 900 to 1400 words plus small code blocks. | Built (style guide) | None yet |
| ART-15 | Files and folders starting with `_` are ignored by the build. | Built | Unit test |

### 6.3 Content rules

| ID | Requirement | Status | Check |
|---|---|---|---|
| ART-20 | Short, clear sentences. One idea per sentence. Plain words. Active voice. Paragraphs of 2 to 4 sentences. No marketing language, emojis or filler. | Built (style guide) | Manual |
| ART-21 | Each section starts from a situation the reader recognises, shows the query, setting or view used in daily work, gives a realistic example before the general rule, and says when advice does not apply. | Built (style guide) | Manual |
| ART-22 | Every article answers the **performance questions**: what does it cost, when does that cost show up, how do I measure it, when should I worry (a rule of thumb), what can I change and what is the downside. | Built (style guide) | Manual |
| ART-23 | The article is written in the author's own words and does not copy documentation text. | Built (style guide) | Manual |
| ART-24 | The article names common mistakes and how to spot them. | Built (style guide) | Manual |
| ART-25 | A topic is linked on first mention with `[Name](topic:id)`. An unknown id fails the build. | Built | Auto |
| ART-26 | **High level.** An article explains what the thing is, when to use it and which problem it solves. It does not teach how to build it: no `CREATE`, `ALTER` or `DROP` statements to set up the example. Extensions are described as extensions, installed like any other, with no `CREATE EXTENSION`. Creating an index is a sentence ("create a bloom index on these columns"). A DDL statement or a `SELECT` is shown only for a very good reason, such as when the statement itself is the subject, in one short block. | Built (rule, in the style guide). The five index articles follow it. Other articles do not yet (see D-14). | Manual |
| ART-27 | A `SELECT`, an `EXPLAIN` or a query on a system view or catalog table (`pg_stat_*`, `pg_stats`, `pg_class`) is welcome when it makes a point, such as "is it used?", "how big is it?" or "is it keeping up?". | Built (rule) | Manual |
| ART-28 | When advice is to change something, the article names the lever and its downside ("lower `pages_per_range`", "rebuild the index online") and does not paste the full command. | Built (rule) | Manual |
| ART-29 | Setup that the examples assume (tables, indexes) lives in `tests/sql_setup/<article>.sql`, not in the article. | Built | Manual |

### 6.4 Accuracy and review

| ID | Requirement | Status | Check |
|---|---|---|---|
| ACC-01 | Every technical claim is verified against the official PostgreSQL documentation for a recent version. The pages are listed in `sources`. | Built (rule) | Manual |
| ACC-02 | No invented numbers, parameter names or catalog columns. | Built (rule) | Manual |
| ACC-03 | Every `sql` block is run against a real PostgreSQL by `scripts/verify_sql.py`. A block that cannot run starts with `-- not run: <reason>`. | Built | Auto (when run locally) |
| ACC-04 | An article has **no** "How this was checked" note in its text (removed in 0.17). What was run, on which version, which claims come from the documentation, and what could not be checked are recorded in `Product/article-review-notes.md`. Blocks that cannot run keep their `-- not run: <reason>` comment. | Built | Manual |
| ACC-05 | Rules of thumb are marked as rules of thumb. Uncertainty is stated. | Built (rule) | Manual |
| ACC-06 | Product claims (for example about Dynatrace) come from public product documentation, listed in `sources`, with a note that features change. | Built (practice) | Manual |
| ACC-07 | Every article is reviewed by a named person before it is marked reviewed. The review covers technical accuracy. | Proposed | None yet |
| ACC-08 | The SQL check runs in the pull request checks. Today it must be run by hand, on a server the author provides. | Proposed | None yet |
| ACC-09 | Each article shows the date of its last accuracy check, separate from its "Updated" date. | Proposed | None yet |

### 6.5 Visuals and demos

| ID | Requirement | Status | Check |
|---|---|---|---|
| VIS-01 | Add a picture only when the text makes the reader work too hard. One idea per article. | Built (style guide) | Manual |
| VIS-02 | Use a static image for structure (a tree, a layout, a plan) and a live demo for something that happens over time. | Built (style guide) | Manual |
| VIS-03 | Images are PNG, JPG, GIF, WebP or AVIF in `content/<topic-id>/`, with alt text, preferably under 200 KB. SVG is not allowed as a published file. | Built | Auto (type), Manual (size, alt) |
| VIS-04 | Diagrams are authored as SVG in `content/<topic-id>/src/` and rendered to PNG by `scripts/render_images.py`. Both are committed. | Built | Manual |
| VIS-05 | A demo is one dependency-free HTML file in `content/<topic-id>/`, embedded with an iframe. No libraries or network requests. It loops by itself, shows its state in words, and shows one still frame under "reduce motion". Length: see VIS-12. | Built | Auto (loads, no console errors), Manual (rest) |
| VIS-06 | A demo can only be embedded by its own topic's article. It runs sandboxed with scripts allowed and no access to the page. | Built | Unit test |
| VIS-07 | An iframe is allowed only for a local demo, or a YouTube or Vimeo embed. | Built | Unit test |
| VIS-08 | A missing demo file fails the build. | Built | Unit test |
| VIS-09 | Every demo is reviewed like code, because it is copied as written. | Built (rule) | Manual |
| VIS-10 | A diagram or a demo is visually checked in a browser before publishing. | Proposed (today the smoke test only checks that a demo loads) | None yet |
| VIS-11 | Every article in the Indexing subject that explains a mechanism (Index, B-Tree, Hash index, GIN, BRIN) has at least one demo. Other articles get one when the idea happens over time (see D-13). | Built for Indexing, Proposed for the rest | Auto (loads), Manual (content) |
| VIS-13 | An animation explains something **complicated that happens over time**, such as a chain of causes and effects (a busy primary misses its health check, the load balancer switches to the standby, and the standby overloads). It does not animate a list, a table or a checklist. | Built (rule, in the style guide) | Manual |
| VIS-12 | **Pace.** A demo gives each step about 2 seconds, so a reader can follow it. A whole demo is 20 to 30 seconds for a process with several steps, and shorter for a simple idea. A demo shows one idea. If it needs more time, it is split into several demos, each embedded where its idea is explained. An article can embed more than one demo. | Built for the GIN demos (19 s and 17 s). The other index demos are about 10 s with steps of about 1 s (see D-15). | Manual |

### 6.6 Safety of article content

| ID | Requirement | Status | Check |
|---|---|---|---|
| SAF-01 | Article HTML goes through a sanitiser. Scripts, event handlers and styles are removed. Only a fixed list of tags and attributes survives. | Built | Unit test |
| SAF-02 | Only the schemes http, https, mailto and `topic:` are allowed in links. `javascript:` is removed. | Built | Unit test |
| SAF-03 | External links open in a new tab and carry `noopener`. Source links also carry `nofollow`. | Built | Manual |
| SAF-04 | Relative images and assets are checked: the file exists, stays in the article's folder and has an allowed type. | Built | Unit test |
| SAF-05 | A list placed directly after a text line (without a blank line) is an error, because it would render as one run-on paragraph. | Built | Unit test |

## 7. Learning track requirements

### 7.1 Definition

| ID | Requirement | Status | Check |
|---|---|---|---|
| TRK-01 | A track is a file `data/tracks/<id>.yaml`. The id is the file name and does not change. | Built | Auto |
| TRK-02 | A track has: `order` (position on the home page), `kind` (`general`, the default, or `problem`), `name`, `title` (one line saying what you learn) and 3 to 10 `steps`. A problem track also has a `problem` of one or two sentences. | Built | Auto |
| TRK-03 | A step has a `topic` (an existing topic id) and a one-line `why`. A topic cannot appear twice in a track. | Built | Auto |
| TRK-04 | A track has one goal and is ordered from basic to advanced. | Built (rule) | Manual |
| TRK-05 | A topic may be in several tracks. | Built | Auto |
| TRK-06 | A step whose topic has no article yet is labelled "coming soon". A step with an article is labelled "article". | Built | Auto |
| TRK-07 | A track should not be published with more than a few "coming soon" steps. Today two tracks have 4 and 5. | Proposed | None yet |
| TRK-08 | Track order follows each step's prerequisites: a topic is never placed before one of its hard prerequisites. | Proposed | None yet |

### 7.2 Behaviour in the viewer

| ID | Requirement | Status | Check |
|---|---|---|---|
| TRK-10 | The Learning tracks tab lists the tracks by `order`, then by name. Each card shows the route icon, the track name in gold type with its subtitle **under** it (not beside it), a pill with the number of steps, and a chevron. Clicking expands the numbered steps with the reason. | Built | Auto |
| TRK-11 | Clicking a step opens its topic. | Built | Auto |
| TRK-12 | A topic in a track shows a **track header** that says where the reader is: a route icon and the track name in large gold type, a line with the phase and "Step N of M", a ring with the percentage of the track (N of M), and **Previous** and **Next** arrows to the neighbouring steps. The first step has a dimmed Previous. The last has a dimmed Next. The next step is not named twice. | Built | Auto |
| TRK-23 | A problem track has a **problem statement**: one short sentence that says what the problem is (for example "The CPU of the database instance has been close to 100% for too long."). The header shows it under the track bar of every step as "**The problem:** ...", followed by the fixed sentence "In this track we will review the impact, the potential root causes and how to analyze them." The build requires the field. | Built | Auto |
| TRK-24 | Every step of a problem track has a **phase**: `problem` (what it is, how it is detected, why it matters), `causes` (the overview of the potential root causes) or `cause` (one root cause in detail), in that order. The first step is `problem` and there is a `causes` step. The header shows the phase of the current step ("The problem", "Potential root causes", "Root cause in detail"), and a wider gap in the segments marks where a phase ends. A general track has no phases. The build rejects anything else. | Built | Auto (unit tests) |
| TRK-25 | The rules for writing a problem track are in `content/_track_prompt.md`. | Built | Manual |
| TRK-27 | **Two kinds of track.** A general track shows a route icon and a gold name. A problem track shows a warning icon and an orange name, and its title is prefixed "Problem:" (for example "Problem: High CPU"). This applies to the header and to the Learning tracks list, which has a heading for each kind. | Built | Manual |
| TRK-28 | **The flow of a problem track:** one or two articles on the problem, in this order: what the problem is, the impact (why you should care), and last how to get the data (from the operating system or cloud monitoring, or from a PostgreSQL system view). Then one overview of the potential root causes, and then one article for each root cause, which says what more data is needed to confirm that it is the cause. | Built (rule, in the track guide) | Manual |
| TRK-20 | Below the title the header shows one **segment** for each step: steps before this one filled, the current one in gold and taller, the steps still ahead dim. A step whose topic has no article yet is fainter. | Built | Manual |
| TRK-21 | Clicking a segment opens that step. Hovering shows its number and name, and "coming soon" when it has no article. | Built | Manual |
| TRK-22 | The header stays at the top of the panel while the article scrolls, so the reader always sees where they are. | Built | Manual |
| TRK-26 | The header shows **one track at a time**, the one the reader is following. A topic that is in several tracks (for example Monitoring table size) shows the track that the reader came from, through a step in the Learning tracks list, an arrow or a segment. A topic opened from the map, from search or from a link shows the first track that contains it, and a topic in no track shows no header. The progress is always the progress in that one track. | Built | Auto (one header on every step) |
| TRK-13 | A topic in several tracks shows one bar for each. | Built | Manual |
| TRK-14 | Previous and Next work for every step of every track. | Built | Auto |
| TRK-15 | The track bar shows the "why" of the current step. | Proposed | None yet |
| TRK-16 | The viewer remembers how far the reader has got in a track (stored in the browser). | Proposed | None yet |
| TRK-17 | A track shows an estimated reading time. | Proposed | None yet |
| TRK-18 | A track has its own address (for example `#track=postgres-storage`) to share. | Proposed | None yet |
| TRK-19 | A track has a final step that says what to do next (another track, or a practice task). | Proposed | None yet |

### 7.3 Tracks today

| Track | Goal | Order |
|---|---|---|
| PostgreSQL Storage | How PostgreSQL stores tables on disk, how they grow, get cleaned up and get split | 1 |
| Anatomy of PostgreSQL | The parts of a server and how they fit together | 2 |
| Database Monitoring Overview | What database monitoring means, what to expect from it, and how Dynatrace delivers it | 3 |
| Problem: Slow query | Find why a query is slow, read its plan and choose the fix. Steps: Analyzing slow queries, Query metrics (the problem), Common root causes of slow queries (the overview), Execution plan, Actual execution plan, Index, Table partitioning | 4 |
| Problem: Large database | Why a database is big, why it grows, and how to keep the growth under control. Steps: Why a large database is a problem, Monitoring table size (the problem), Why a database suddenly grows (the overview), Index, TOAST, Dead rows, Vacuum, Vacuum configuration, Monitoring vacuum | 5 |
| Problem: Low free disk space | Find what fills the disk of a PostgreSQL instance, and when to hand over to the database track. Steps: Low free disk space (the problem), Common root causes (the overview), WAL and checkpoints, Server logs, The error log, The slow query log, Managed or self-managed, Why a database suddenly grows (the hand-over to Large database) | 6 |
| Problem: High CPU | Find why the CPU of a PostgreSQL instance is high, and what to do about it. Steps: High CPU (the problem), Common root causes (the overview), then one article for each cause: not enough resources, a runaway query, more requests and overlapping jobs, costly statements, too many active sessions, maintenance work, a replication problem (planned), waiting on disk or something else on the host (planned) | 7 |

The plan is that later tracks solve specific problems (for example "my query is slow" or "my database is running out of connections"). Those are not defined yet. See section 9.

## 8. Topic data and build requirements

These are the rules behind the content. They are what makes QA automatic.

| ID | Requirement | Status | Check |
|---|---|---|---|
| DATA-01 | A subject is a file `data/<subject>.yaml` with `subject`, `color`, `description` (required) and `order`, followed by its topics. | Built | Auto |
| DATA-02 | A topic requires `id`, `name`, `domain`, `level` (0 to 4) and `description`. Optional: `details`, `evidence`, `prerequisites`. | Built | Auto |
| DATA-03 | A topic id is lowercase letters, digits and hyphens, unique, and never renamed. | Built | Auto |
| DATA-04 | A prerequisite has `id`, `reason` (required) and `strength` (hard or soft). An unknown id, a missing reason or an unexpected key is an error. | Built | Auto |
| DATA-05 | A cycle in prerequisites is an error, even in lenient mode. | Built | Unit test |
| DATA-06 | A topic has one teachable idea. If its description needs "and", split it. | Built (rule) | Manual |
| DATA-07 | Evidence is written as something checkable ("explain why X"), not "know about X". | Built (rule) | Manual |
| DATA-08 | A subject's colour is unique. | Proposed | None yet |
| DATA-09 | A topic with no article for a long time is reported. | Proposed | None yet |
| BLD-01 | The build produces the static site and fails on any problem in strict mode. In lenient mode (used on `main`) a broken article is skipped with a warning, and data errors still fail. | Built | Unit test |
| BLD-02 | Unit tests, a strict build and a browser smoke test run on every pull request. | Built | Auto |
| BLD-03 | The smoke test opens every topic, every article, every topic link, every track step with Previous and Next, and every demo. It fails on a console error, a failed request or an empty article. | Built | Auto |
| BLD-04 | A push to `main` runs the same checks, deploys to GitHub Pages, and then runs a browser check of the live site. | Built | Auto |
| BLD-05 | Rollback is a revert of the commit on `main`. | Built | n/a |
| BLD-06 | The smoke test also compares each page with a stored screenshot to catch layout breaks. | Proposed | None yet |

## 9. Decisions for you

Please answer or edit these. I have listed my suggestion first.

| # | Question | Suggestion |
|---|---|---|
| D-1 | **Release gate for tracks.** Should a track be visible only when all its steps have articles? | Yes for GA. For now, keep "coming soon" visible, since you are moving fast. |
| D-2 | **Review status.** Who reviews an article, and what does "reviewed" mean? Most articles have no reviewer, and the Dynatrace ones have not been reviewed. | Add a `reviewed_by` and a date. Show a "Not yet reviewed" label on articles without one. |
| D-3 | **Problem-driven tracks.** Which are the first two? | "My query is slow" (plans, statistics, indexes) and "Too many connections" (instance, connection pooling, wait events). |
| D-4 | **Search.** Built in 0.2 (name, subject, description). Do we need article-text search and typo tolerance before GA (SRCH-09, SRCH-10)? | Text search yes, typo tolerance later. |
| D-5 | **Sharing.** Do topics need previews when a link is pasted in Slack or email? A single-page site cannot do it today. | Yes for GA. It needs one generated page per topic. |
| D-6 | **Dynatrace content.** Are the product topics part of this map, or a separate area? They share the viewer today. | Keep them in the map, but label them as product content, since the rest is vendor-neutral. |
| D-7 | **Other engines.** Articles are PostgreSQL-first. Do we add MySQL or SQL Server topics? | Not before GA. Keep "how it compares" notes. |
| D-8 | **Licence.** The README says a licence is still to be chosen. | Choose before making the project known beyond the team. |
| D-9 | **Measurement.** What counts as success? | Pick two numbers, for example Solution Architects who used a track, and links shared. This needs some form of usage data, which the site does not collect today. |
| D-11 | **Order of topics in a subject list.** Today: by level, then by name. Other options: articles first, newest first, or by the order of a track. | Keep level then name. It matches how a reader learns, and the ring shows which have an article. |
| D-12 | **"Articles" or "topics".** The lists show all topics and mark those without an article as "soon". Should they show only topics with an article? | Keep all, marked. A reader sees what is coming, and a topic page still explains the idea. |
| D-13 | **Which other articles need a demo?** Today 25 articles have one, including every article of the tracks added in October. Candidates still without: Execution plan (reading a plan from the leaves up), Vacuum, MVCC, Statistics, Dead rows, Index scan. | Add to MVCC, Vacuum and Execution plan first, since they are the hardest to picture. |
| D-14 | **Other articles with setup commands.** Partitioning, TOAST, Vacuum, Dead rows, Visibility map, Buffer pool and others still contain `CREATE`, `ALTER` or `INSERT` blocks. Review them against ART-26? | Yes, one at a time. Partitioning is the one where some DDL may be the point. |
| D-15 | **Slow down the other index demos?** Index, B-Tree, Hash and BRIN run about 10 seconds with steps of about one second, the same pace as the old GIN demo. | Yes. Review them one at a time, and split where an idea needs more time (for example B-Tree: lookup and range as two demos). |
| D-16 | **Anatomy of PostgreSQL has 10 steps, the maximum.** The error log and the slow query log are new topics, but the track still lists the single Server logs topic, and the two logs hang under it on the map. Options: raise the limit of a track to 12, replace a step, or merge two. | Raise the limit to 12 for this track only if you want both logs listed. Otherwise keep it as is. |
| D-10 | **Accessibility level.** Is WCAG AA a requirement for GA? | Yes. The keyboard gap (A11Y-02) is the biggest one. |

## 10. Not specified yet

These are the gaps I found while writing this. Each needs a requirement or an explicit "out of scope".

- **Usage data.** The site has no analytics, so nobody can tell which topics or tracks are used.
- **Feedback.** There is no way for a reader to report an error or ask for a topic, except through GitHub.
- **Versioning.** Articles say "PostgreSQL 17". There is no plan for updating to the next version, or for keeping old versions.
- **Language.** English only.
- **Print and offline use.** An article cannot be exported or printed in a good layout.
- **Ownership.** There is no owner list per subject.
- **Support promise.** No statement on how fast an error is fixed.
- **Content roadmap.** The 10 topics without an article (Databases, Files and tablespaces, WAL, Server logs, Index scan, Partial index, Page, Tuple, Heap table, Monitoring table size) have no priority order.

## 11. Out of scope

- Accounts, logins and personal progress stored on a server.
- Running SQL in the browser against a live database.
- Comments or discussion on the site.
- A hosted database for readers to practice on.

## 12. QA flow

1. **On every pull request**, the automatic checks must pass: unit tests, strict build, browser smoke test. These cover the requirements marked **Auto** or **Unit test**.
2. **Before an article is published**, a reviewer checks it against section 6: accuracy of claims against the sources, the SQL status, the performance questions, and the style.
3. **Before a demo is published**, someone watches the whole loop in a browser (VIS-10).
4. **Before a release**, one person walks through the **Manual** items in section 5 on desktop and on a phone.
5. **After deploy**, the live-site check runs. A red run means production is broken. Roll back first and investigate after.

To make QA repeatable, each requirement ID can become a test case. Requirements marked **None yet** are the first candidates for new automatic tests.

## 13. Change log of this document

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-10-24 | First draft, written from the current code, README, developer guide and style guide. |
| 0.2 | 2026-10-24 | Added and built: search (SRCH), hideable subject window with topic lists (LEG-05 to LEG-11), subject cards with topic lists (HOME-11), About tab (HOME-12, HOME-13), map fitted to the screen with label decluttering (MAP-16 to MAP-20). LEG-02 changed (the dot toggles, not the row). Decisions D-11 and D-12 added. |
| 0.3 | 2026-10-25 | Added the high-level rule for articles (ART-26 to ART-29) and decision D-14. |
| 0.4 | 2026-10-26 | Demo pace rule (VIS-12) and decision D-15. GIN demo split into search and insert. |
| 0.5 | 2026-10-26 | New track "My query is slow" with three new topics (section 3 and 7.3 updated). |
| 0.22 | 2026-11-01 | The Sources moved from the bottom of the article to the Metadata (AV-08, TOP-14). |
| 0.21 | 2026-11-01 | The animation that ticked off the root causes of high CPU was removed (VIS-13). A new one shows how high CPU leads to a failover that makes it worse. |
| 0.20 | 2026-11-01 | The problem statement of a track is one sentence, shown as "The problem: ..." with a fixed second sentence (TRK-23). |
| 0.19 | 2026-11-01 | The first article of a problem track says what the problem is, then the impact, and last how to get the data. Cause articles say what more data confirms the cause (TRK-28). |
| 0.18 | 2026-11-01 | Articles in problem tracks have two tabs, the article and Metadata (TOP-13 to TOP-16). |
| 0.17 | 2026-11-01 | The "How this was checked" note is removed from the articles (ACC-04). The notes moved to Product/article-review-notes.md. |
| 0.16 | 2026-11-01 | No PostgreSQL version in the text of the articles (ART-02, ART-04). Real version differences are named where they apply. |
| 0.15 | 2026-11-01 | Two kinds of track, general and problem, with different icons and the title "Problem: ..." (TRK-27). The new flow of a problem track: the problem, an overview of the potential root causes, then each cause (TRK-24, TRK-28). The phases are now problem, causes and cause. The four problem tracks were renamed and restructured, and High CPU and Low free disk space got new articles. |
| 0.14 | 2026-11-01 | The track header shows one track at a time (TRK-26), fixing stacked headers for topics that belong to two tracks. |
| 0.13 | 2026-11-01 | The Learning tracks cards show the icon, the name with the subtitle under it (TRK-10). |
| 0.12 | 2026-11-01 | New problem track "The DB Instance CPU is high" with one new topic and two animations (sections 3 and 7.3). The causes come second. The causes article is short: why a high CPU matters, then a list of ten root causes with a short explanation of each. |
| 0.11 | 2026-10-31 | Track header redone: icon, large gold name, phase and step, the problem statement, no prerequisite count. Problem tracks get a problem statement and phases now, why and fix (TRK-23 to TRK-25). The tracks My query is slow and My database is large were reordered to follow the phases. |
| 0.10 | 2026-10-31 | The track header shows step N of M, the track name, a percentage ring, segments for every step and arrows (TRK-12, TRK-20 to TRK-22). |
| 0.9 | 2026-10-31 | 13 new demos of 20 to 30 seconds for the articles of the last four tracks (VIS-12 pace updated, D-13 narrowed). |
| 0.8 | 2026-10-31 | New track "The DB Instance is running out of disk space" (7 steps). It hands over to "My database is large". New topics The error log and The slow query log; WAL and checkpoints and Server logs now have articles (sections 3 and 7.3). Open point: the Anatomy track is at its 10-step limit (see D-16). |
| 0.7 | 2026-10-31 | New track "My database is large" with three new topics and the article for Monitoring table size (sections 3 and 7.3). |
| 0.6 | 2026-10-31 | New advanced topic Bloom filter (Indexing, no track) with a 20-second demo. ART-26 tightened: no CREATE EXTENSION, creating an object is a sentence, a statement needs a very good reason. |
