# Change log

Notable changes to the Database Internals map. Newest first. Topic names are the ones shown on the map.

## 2026-10-26

### Changes
- **GIN animation split in two and slowed down.** `gin/select.html` shows a search for one tag and for two tags (19 seconds). `gin/insert.html` shows an insert, the pending list and the later merge (17 seconds). Each step now lasts about 2 seconds. The article embeds each one where its idea is explained.
- **Writing guide:** demos are paced at about 2 seconds a step and run 10 to 20 seconds. A demo shows one idea, so a longer story is split into several demos.

## 2026-10-25

### New
- **Animations for the five index articles**: Index (a sequential scan against an index lookup), B-Tree (a lookup, then a range along the linked leaves), Hash index (an equality lookup, and why a range cannot work), GIN (key to row lists, two keys combined, an insert) and BRIN (skipping block ranges, and what happens when the rows are not in order). Each runs about 10 seconds and is embedded in its article.

### Changes
- **Index articles are high level.** The Index, B-Tree, Hash index, GIN and BRIN articles no longer show `CREATE INDEX` or `CREATE TABLE`. They say what each type is, when to use it and how to see it in the system. `SELECT` queries and system views stay. The setup the examples need moved to `tests/sql_setup/`.
- **Writing guide.** `content/_prompt.md` has a new "Level of detail" section, and `DEVELOPING.md` and `CONTRIBUTING.md` carry the same rule: no setup commands, and a `SELECT` or system view only to make a point.

### Fixes
- Index article: removed a note about sample plan output, because the article has none.
- GIN article: the pending list is flushed by vacuum or auto-analyze (it said "analyzed").

## 2026-10-24

### Viewer
- **Search.** A box under the header finds topics by name, subject, domain or description. Press `/` to focus it. The matches get a yellow ring on the map, and choosing one opens the topic and centres it.
- **Subjects window.** It has a close button, with a small "Subjects" button to bring it back (remembered). Clicking a subject name lists its topics, sorted by level, with a ring for those that have an article. Clicking the coloured dot hides or shows the subject on the map, which the whole row used to do.
- **Subject cards on the home page** expand to the same topic lists and show the number of articles.
- **About tab** next to Database Internals and Learning tracks. The text is in `content/_about.md`.
- **The map fits the screen** when it loads. Names that would overlap are left out, so a crowded map stays readable. Hovering a dot shows its name.

### Fixes
- Choosing a search result with the mouse opened the topic and then closed it again, so the article never showed. The map now ignores a mouse release that did not start on the map. The browser test clicks a result.

### Documentation
- New `Product/functional-requirements.md`: the requirements for the viewer, articles and tracks, with IDs and QA checks.

### New
- **Load balancers and connection pooling** (new topic in Architecture): the difference between a pooler and a load balancer, why PostgreSQL connections are expensive, PgBouncer's pooling modes and their limits, routing to the primary and to replicas, and how to see your own connections.
- **Sharding** (new topic in Partitions): how it differs from partitioning and replication, shard key choice, what gets harder (cross-shard queries, transactions, resharding), what PostgreSQL offers (foreign tables, Citus), and when not to shard. Includes an animation of a query with and without the shard key.

## 2026-10-22

### New
- **Observability** subject and the track **Database Monitoring Overview** (4 steps): What database monitoring means, What a good DB observability system gives you, Dynatrace Observability Platform, and The Dynatrace Databases app. All four have articles.

### Changes
- The track "My table is huge" is now **PostgreSQL Storage**.

## 2026-10-21

### Fixes
- Eight articles (Dead rows, Partition metrics, Vacuum, Monitoring vacuum, Visibility map, Wraparound, Buffer pool settings and the new Buffer pool) had a list placed directly after a bold lead-in line, which rendered as one run-on paragraph. Each now has a blank line before the list. The build now fails on this mistake, with the line number.

### Documentation
- The README now explains the project for a general reader: what it is, what a topic is and how topics connect, what learning tracks are, why it was built, and that it is an early experimental project. The technical guide moved, unchanged, to `DEVELOPING.md`.

### Articles
- **The instance** (first article of the Architecture subject, and step 1 of "Anatomy of PostgreSQL"): a high-level overview with no SQL. What an instance is, a table of the main components with their articles, an overview picture, a looping animation that moves from the instance level (processes, buffer pool, WAL, logs) to the databases and then to one table (heap, indexes, TOAST), and a sentence or two on each part, including files and tablespaces. It also covers how it compares to SQL Server and MySQL, and where to look for each kind of problem.
- **Buffer pool** (existing topic, now with an article and a looping animation): what the pool is, and that everything happens in whole pages and never in single rows, shown with the row location `ctid` and a measured update (one row changed, one page dirtied, 8,213 bytes of log because the first change after a checkpoint writes a full page copy). The animation shows a hit, a miss with an eviction, the whole page read from disk, an update that dirties the page after the log record, and the write-back. A cold run read 1,692 of 1,725 pages from outside the pool and the second run read none.
- **Buffer pool settings** (new topic under Storage): `shared_buffers` and the 25% starting point from the documentation, `effective_cache_size` as a planner hint and not memory, the background writer and checkpoint settings, what is not a buffer setting (`work_mem`, `maintenance_work_mem`, `temp_buffers`), and how to check the cache and the checkpoints. The "Anatomy of PostgreSQL" track step for the buffer pool now has an article.
- **Visibility map** (new topic under Storage, with a looping animation): the two bits per page and the `_vm` file, what sets and clears them, and why index-only scans depend on it. A measured example on 200,000 rows: before `VACUUM` the map file was empty and the query read 210 buffers with a Bitmap Heap Scan, after `VACUUM` it was an Index Only Scan with 0 heap fetches and 6 buffers. Updating 5% of the rows, spread over almost every page, pushed heap fetches back to 600, so changed pages matter more than changed rows.
- **Transaction ID wraparound** (new topic in Concurrency): what the 32-bit circular counter is, why wraparound would hide data, how freezing prevents it, the escalation from the forced autovacuum to the point where the server refuses writes, how fast it can happen at different transaction rates, how to monitor it, and the documented recovery steps. A real run shows autovacuum forcing a wraparound vacuum on a table with autovacuum turned off.
- Vacuum and Monitoring vacuum now link to Wraparound, and Vacuum links to the visibility map.

### Learning tracks
- Second track, **Anatomy of PostgreSQL** (10 steps): The instance, Databases schemas and roles, Files and tablespaces, Heap table, Index, TOAST, Table partitioning, Buffer pool, WAL and checkpoints, Server logs.
- New subject **Architecture** with five topics, descriptions only so far, articles to follow: **The instance**, **Databases, schemas and roles**, **Files and tablespaces**, **WAL and checkpoints**, **Server logs**.
- A topic that is in two tracks (Heap table, TOAST, Table partitioning) shows one progress bar for each.

## 2026-10-20

### Articles
- **Vacuum:** what vacuum does (four jobs), the manual variants and their locks, how autovacuum decides to start (with a table showing why 20% is too lazy for a 100-million-row table), why it is throttled on purpose, freezing and wraparound, and what to change.
- **Monitoring vacuum** (new topic under Storage, not part of the track): which tables need attention, how far each is from its autovacuum trigger, what a running vacuum is doing (`pg_stat_progress_vacuum`, with real output), how to read an autovacuum log entry (real excerpt), what holds it back, and wraparound age. The track stays at 10 steps and links to Vacuum only.
- **MVCC** (new topic in Concurrency): why readers and writers do not block each other, what `xmin`, `xmax` and `ctid` show after an `UPDATE`, how snapshots decide what a statement sees, Read Committed against Repeatable Read, and what MVCC costs. A two-session example is checked by `scripts/verify_sql.py`.
- **Dead rows:** what they are, real cases (sessions, orders, queues, big deletes), a measured example (a 9 MB table that became 36 MB after three updates of every row, and stayed 36 MB after a plain `VACUUM`), how to see them, what holds cleanup back (old transactions, replication slots, prepared transactions, shown with real `VACUUM VERBOSE` output), heap-only updates and fillfactor, and what to change.
- The "PostgreSQL Storage" track (formerly "My table is huge") now has 10 steps: MVCC was added after Tuple (row).
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
