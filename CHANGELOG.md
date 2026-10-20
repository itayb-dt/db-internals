# Change log

Notable changes to the Database Internals map. Newest first. Topic names are the ones shown on the map.

## 2026-10-20

### Articles
- **MVCC** (new topic in Concurrency): why readers and writers do not block each other, what `xmin`, `xmax` and `ctid` show after an `UPDATE`, how snapshots decide what a statement sees, Read Committed against Repeatable Read, and what MVCC costs. A two-session example is checked by `scripts/verify_sql.py`.
- **Dead rows:** what they are, real cases (sessions, orders, queues, big deletes), a measured example (a 9 MB table that became 36 MB after three updates of every row, and stayed 36 MB after a plain `VACUUM`), how to see them, what holds cleanup back (old transactions, replication slots, prepared transactions, shown with real `VACUUM VERBOSE` output), heap-only updates and fillfactor, and what to change.
- The "My table is huge" track now has 10 steps: MVCC was added after Tuple (row).
- Deadlock and Dead rows now list MVCC as a prerequisite.

## 2026-10-19

### SQL verified, draft status removed
- Every SQL example in the articles was run on PostgreSQL 16.2, and the "Draft status" notes are gone. Each article now has a "How this was checked" line that says what was run.
- New `scripts/verify_sql.py` runs the examples from `content/*.md` against a real PostgreSQL, one throwaway database per article, with sample data from `tests/sql_setup/`. The deadlock example is also run with two real sessions, and the ordered-locking fix is run to confirm it does not deadlock.
- Examples that cannot run on that server are marked `-- not run` with the reason: the lz4 compression setting, the `lo` extension and `vacuumlo`, `pg_stat_statements`, and `pgstatginindex` (`pgstattuple`). They were not tested.
- Fixed examples that were not valid SQL: the `EXPLAIN SELECT ...` placeholders in the Execution plan article are now real statements.
- The Deadlock article now shows the real error text from a run instead of an invented one.

### Subjects and topics
Five subjects, 19 topics. A star marks topics that have a full article.

- **Storage:** Page, Tuple (row), Heap table, Buffer pool, TOAST\*
- **Indexing:** Index\*, Index scan, B-Tree\*, Partial index, Hash index\*, GIN\*, BRIN\*
- **Query planning:** Statistics\*, Execution plan\*, Actual execution plan\*, Cost Based Optimization\*
- **Concurrency:** Deadlock\*
- **Partitions:** Table partitioning\*, Partition metrics\*

Storage and Indexing were the first two subjects. Query planning, Concurrency and Partitions are new. In the articles, topics link to each other with `topic:<id>` links, and the build checks that every link points to a real topic.

### Images and video
- **Images:** two diagrams in the B-Tree article, comparing a B-tree with a binary search tree (the same 15 keys, and why the B-tree stays shallow and balanced). Images live in `content/<topic-id>/`. Diagrams are authored as SVG in `content/<topic-id>/src/` and rendered to PNG with `scripts/render_images.py`.
- **Live demos (short looping animations, plain HTML):**
  - **Deadlock:** two sessions lock a row each, wait for each other, and PostgreSQL aborts one.
  - **Table partitioning:** deleting rows from one big table against dropping a partition.
- Demos are single HTML files in `content/<topic-id>/`, embedded with an iframe. They run in a sandbox, and the build and the browser test check them.
- Dynatrace icon in the top left corner, linking to the Databases app, with the title "Database Internals" next to it at the same height. The header has a dark background so the moving dots and labels do not cover it. The concept and link counts moved into the legend.

### Learning tracks
- New **Learning tracks** section on the home page. A track has a name and a short title, expands to its steps, and labels each step "article" or "coming soon". Inside a topic, a bar shows "step 5 of 9" with Previous and Next links.
- First track, **My table is huge** (9 steps): Page, Tuple (row), Heap table, TOAST, Dead rows, Monitoring table size, Vacuum, Table partitioning, Partition metrics.
- Three new topics under Storage, so far descriptions only, articles to follow: **Dead rows**, **Monitoring table size**, **Vacuum**.
- Tracks are files in `data/tracks/`. The build checks that every step names a real topic, that a track has 3 to 10 steps, and that each step has a reason. It also rejects a stray key, which catches a comma inside inline YAML that would otherwise cut a sentence short. This check also applies to topic prerequisites.

### Viewer
- The home pane has two tabs, **Database Internals** and **Learning tracks**. The first has the intro text and a card for each subject with a one-sentence description (a new required `description` in each subject file, plus an optional `order`). The list of every topic and the starting-point chips are gone.
- Split layout: the 3D map on the left, a reading pane on the right.
- Home page on the right by default (`content/_home.md`), with starting points and every topic by subject.
- Full articles open in the pane, with a ring on the dot of topics that have one.
- Links between topics, and shareable links such as `#topic=btree`.

### Build, checks and deployment
- The site is built into `_site/` and is no longer committed. `python3 scripts/build.py --serve` builds and serves it locally.
- Articles are Markdown or HTML, sanitized at build time, with checks for missing images, broken links and unknown topics.
- GitHub Actions runs unit tests, the build and a browser test that opens every topic, article and demo. It deploys from `main` and then checks the live site.
- One broken article is skipped with a warning on `main` instead of blocking the deploy. On pull requests it fails.
- `content/_prompt.md` has the writing guidelines. `CONTRIBUTING.md` describes the process.
