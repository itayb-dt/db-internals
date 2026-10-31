# Article review notes

What was checked in each article, what was not, and what needs a reviewer. This used to be a "How this was checked" note at the top of each article. It was removed from the articles on 2026-11-01, because it is for the owner and the reviewers, not for the reader. Keep the notes here when you write or change an article.

Rules of the notes: say what was run and on which version a test ran, which claims come from the documentation, which are general practice, and what could not be checked.

## Actual execution plan: what really happened

File: `content/actual-plan.md`

- The SQL in this article was run on PostgreSQL 16.2. Sample plan output is illustrative.

## Analyzing slow queries: a method

File: `content/analyzing-slow-queries.md`

- The facts come from the PostgreSQL documentation, listed in the sources. The article has no SQL of its own. The queries are in Query metrics.

## Bloom filters and the bloom index: a cheap way to say no

File: `content/bloom-filter.md`

- The facts about the `bloom` index and its numbers come from the PostgreSQL documentation, listed in the sources. The description of Bloom filters and of the real systems that use them is general knowledge, not from those pages. The article has no SQL of its own.

## BRIN indexes: tiny indexes for huge, ordered tables

File: `content/brin.md`

- The SQL in this article was run on PostgreSQL 16.2.

## B-Tree indexes: the default index

File: `content/btree.md`

- The SQL in this article was run on PostgreSQL 16.2. The `pgstatindex` function mentioned in the text comes from the `pgstattuple` extension and was not run.

## Buffer pool settings: sizing the cache and writing dirty pages

File: `content/buffer-settings.md`

- The SQL in this article was run on PostgreSQL 16.2. Defaults shown were read from that server and match the documentation. Examples that change the server, or need an extension or a 17-only view, are marked `-- not run`.

## The buffer pool: PostgreSQL's cache of pages

File: `content/buffer.md`

- The SQL in this article was run on PostgreSQL 16.2. The numbers shown come from those runs. The `pg_buffercache` example is marked `-- not run`, because that extension was not available on the test server.

## Cost Based Optimization: how the planner picks a plan

File: `content/cost-based-optimization.md`

- The SQL in this article was run on PostgreSQL 16.2.

## High CPU cause: not enough resources for the workload

File: `content/cpu-capacity.md`

- The names of the statistics views come from the PostgreSQL documentation, listed in the sources. The advice on capacity and headroom is common operating practice. The article has no SQL, and the numbers are rules of thumb.

## High CPU cause: more requests and overlapping jobs

File: `content/cpu-workload-spikes.md`

- The names of the statistics views come from the PostgreSQL documentation, listed in the sources. The causes and the advice are common operating practice. The article has no SQL.

## Why a database suddenly grows

File: `content/database-growth-causes.md`

- The facts about vacuum and replication slots come from the PostgreSQL documentation, listed in the sources. The rest is common operating practice. The article has no SQL, and the thresholds are rules of thumb.

## Why a large database is a problem

File: `content/database-size-problem.md`

- The facts about vacuum come from the PostgreSQL documentation, listed in the sources. The rest is general operating practice. The article has no SQL, and the thresholds are rules of thumb.

## Dead rows: the old versions that stay behind

File: `content/dead-rows.md`

- The SQL in this article was run on PostgreSQL 16.2. The long-transaction example was run with two real sessions. Output shown is from those runs.

## Deadlock: when transactions wait for each other

File: `content/deadlock.md`

- The SQL in this article was run on PostgreSQL 16.2. The deadlock example was run with two real sessions, and the ordered-locking version was run to confirm it does not deadlock.

## Managed or self-managed: what else uses the disk

File: `content/disk-outside-postgres.md`

- The facts about files that PostgreSQL writes come from the PostgreSQL documentation, listed in the sources. Everything about cloud services, virtual machines and Kubernetes is **general operating knowledge**, not from the documentation, and details differ between providers and tools. Check your own provider's documentation. The article has no SQL.

## Common root causes of low free disk space

File: `content/disk-space-causes.md`

- The facts about the write-ahead log, logging and temporary files come from the PostgreSQL documentation, listed in the sources. The remarks about managed services, backups and snapshots are common operating practice. The article has no SQL.

## The Dynatrace Databases app

File: `content/dt-databases-app.md`

- Everything about the app comes from the Dynatrace documentation listed in the sources. The app changes often, so confirm details in the current documentation.

## Dynatrace Observability Platform: the database needs context

File: `content/dt-platform.md`

- The statements about Dynatrace come from its public documentation, listed in the sources. Product names and features change, so check the documentation for the current state.

## The error log: what the instance says about itself

File: `content/error-log.md`

- The settings, defaults and severity levels come from the PostgreSQL documentation, listed in the sources. The article has no SQL. The examples of what to look for are common operating practice.

## Execution plan: how PostgreSQL decides to run a query

File: `content/execution-plan.md`

- The SQL in this article was run on PostgreSQL 16.2. Sample plan output is illustrative.

## GIN indexes: searching inside values

File: `content/gin.md`

- The SQL in this article was run on PostgreSQL 16.2, except the `pgstatginindex` call, which needs the `pgstattuple` extension (marked `-- not run`).

## Hash indexes: equality lookups only

File: `content/hash.md`

- The SQL in this article was run on PostgreSQL 16.2. The `pgstathashindex` function mentioned in the text comes from the `pgstattuple` extension and was not run.

## Common root causes of high CPU

File: `content/high-cpu-causes.md`

- The facts about the activity view, statistics and plans come from the PostgreSQL documentation, listed in the sources. The causes themselves, and the remarks about hosts, virtual machines and containers, are common operating practice. The article has no SQL.

## High CPU: the problem

File: `content/high-cpu.md`

- The facts about the activity view and the statistics come from the PostgreSQL documentation, listed in the sources. The description of CPU time on a host, and of cloud monitoring, is general operating knowledge. The article has no SQL, and the thresholds are rules of thumb.

## Indexes: why every database needs them

File: `content/index.md`

- The SQL in this article was run on PostgreSQL 16.2.

## Low free disk space: the problem

File: `content/instance-disk-space.md`

- The facts about the write-ahead log and the size functions come from the PostgreSQL documentation, listed in the sources. The page on the size functions was partly summarised, so please confirm those against the live page. The description of monitoring, and the advice on order, are common operating practice. The article has no SQL, and the thresholds are rules of thumb.

## Load balancers and connection pooling

File: `content/load-balancer.md`

- The facts come from the PostgreSQL, PgBouncer and Pgpool-II documentation and one published analysis, listed in the sources. The SQL below was not run against a server for this article, and is marked so. Product features change, so check the current documentation of the tool you choose.

## MVCC: how PostgreSQL lets readers and writers work together

File: `content/mvcc.md`

- The SQL in this article was run on PostgreSQL 16.2. The two-session example was run with two real sessions.

## Partition metrics: observing a table that is many tables

File: `content/partition-metrics.md`

- the queries were run on PostgreSQL 16.2. The one for `pg_stat_statements` was not run, because that extension was not available.

## Table partitioning: one logical table, many physical ones

File: `content/partitioning.md`

- the facts come from the PostgreSQL documentation. The SQL was run on PostgreSQL 16.2, and the measurements below come from that run. Snippets marked `-- not run` were not executed.

## Query metrics: the numbers that describe a query

File: `content/query-metrics.md`

- The column names and settings come from the PostgreSQL documentation. The SQL below was **not run**, because it needs a live server with the `pg_stat_statements` extension. Each block is marked. Thresholds are rules of thumb.

## High CPU cause: a runaway query

File: `content/runaway-query.md`

- The names of the activity view, the functions that cancel a statement or end a session, and the statement timeout setting come from the PostgreSQL documentation, listed in the sources. The causes and the advice are common operating practice. The article has no SQL.

## Server logs: what the instance writes, and where it goes

File: `content/server-logs.md`

- The settings and defaults come from the PostgreSQL documentation, listed in the sources. The article has no SQL. The advice on thresholds is common practice and not from the documentation.

## Sharding: one logical database on many servers

File: `content/sharding.md`

- The facts come from the PostgreSQL and Citus documentation, and from general knowledge where marked. The one SQL example was not run, because it needs several servers.

## Common root causes of slow queries

File: `content/slow-query-causes.md`

- The article has no SQL. The causes and the way to confirm them come from the PostgreSQL documentation listed in the sources, and from common practice. Thresholds are rules of thumb.

## The slow query log: the statements that took too long

File: `content/slow-query-log.md`

- The settings, defaults and warnings come from the PostgreSQL documentation, listed in the sources. The article has no SQL. Example thresholds are rules of thumb. The mention of a log analysis tool is general knowledge.

## Statistics: what the planner knows about your data

File: `content/statistics.md`

- The SQL in this article was run on PostgreSQL 16.2.

## Monitoring table size: where the space goes

File: `content/table-size.md`

- The names and meanings of the size functions come from the PostgreSQL documentation, listed in the sources. The page on these functions was long, so please confirm the exact wording of each function there. The two queries below were **not run**, because there is no server here. They only use the functions named in the documentation.

## TOAST: how PostgreSQL stores large values

File: `content/toast.md`

- The SQL in this article was run on PostgreSQL 16.2, except the lz4 setting, the `lo` extension example with `vacuumlo`, and the `pg_stat_statements` query, which need things that test server did not have. They are marked `-- not run`.

## Vacuum configuration: making autovacuum keep up

File: `content/vacuum-configuration.md`

- The settings and their defaults come from the PostgreSQL documentation, listed in the sources. The article has no SQL. Suggested values are rules of thumb that depend on your workload.

## Monitoring vacuum: is it keeping up?

File: `content/vacuum-monitoring.md`

- The SQL in this article was run on PostgreSQL 16.2. The progress table and the log excerpt come from real runs on that server. The progress view has more columns in 17 than in 16, so the queries here use only columns that exist in both.

## Vacuum: how PostgreSQL cleans up after itself

File: `content/vacuum.md`

- The SQL in this article was run on PostgreSQL 16.2. The output shown comes from those runs.

## The visibility map: which pages need no checking

File: `content/visibility-map.md`

- The SQL in this article was run on PostgreSQL 16.2. The plans and sizes shown come from that run. The `pg_visibility` extension was not available on the test server, so its example is marked `-- not run`.

## WAL and checkpoints: the log written before the data

File: `content/wal.md`

- The settings, defaults and behaviours of the log, archiving and slots come from the PostgreSQL documentation, listed in the sources. The basic description of the log is from the documentation's introduction, which I did not re-read for this version. The pages for the size function and for the archiver view were partly summarised, so please confirm those two against the live pages. The three queries below were **not run**, because there is no server here.

## Transaction ID wraparound: the failure vacuum exists to prevent

File: `content/wraparound.md`

- The facts come from the PostgreSQL documentation. The SQL was run on PostgreSQL 16.2, and the forced-vacuum demonstration below was run on that server, with deliberately low settings so it takes seconds instead of days.
