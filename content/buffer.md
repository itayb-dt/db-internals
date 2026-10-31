---
title: "The buffer pool: PostgreSQL's cache of pages"
updated: 2026-10-21
sources:
  - https://www.postgresql.org/docs/17/runtime-config-resource.html
  - https://www.postgresql.org/docs/17/wal-configuration.html
  - https://www.postgresql.org/docs/17/wal-intro.html
  - https://www.postgresql.org/docs/17/sql-explain.html
  - https://www.postgresql.org/docs/17/monitoring-stats.html
  - https://www.postgresql.org/docs/17/pgbuffercache.html
---

This article is about PostgreSQL. Every database engine has a cache like this: SQL Server calls it the buffer pool, and MySQL/InnoDB calls it the buffer pool as well. The names match, and so does the idea. The details of the settings are in [Buffer pool settings](topic:buffer-settings).

## What it is

Reading from disk is slow and reading from memory is fast. So PostgreSQL keeps a large area of shared memory, the **buffer pool** (also called shared buffers), that holds copies of table and index **pages**. Every connection uses the same pool. A page that is already in the pool can be used at once. A page that is not has to be read from disk first.

The pool is made of **buffers**. A buffer is one slot that holds one page, which is 8 kB by default. When people say "cache hit ratio" they mean how often a needed page was already in a buffer.

## It works in pages, never in rows

This is the most important thing to understand about the pool, and about storage in general: **PostgreSQL never reads or writes a single row**. The smallest unit is a [page](topic:page). A page holds many [rows](topic:tuple), and every access goes through the page.

- To read one row, PostgreSQL brings its whole page into the pool, and then finds the row inside it.
- To change one value in one row, there is no such thing as changing only that value. PostgreSQL loads the page, writes a **new version of the row** into it (see [MVCC](topic:mvcc)), and marks the whole page as **dirty**. The row's location is its page number and its position in the page. It is the `ctid`: `(1724,11)` means page 1,724, position 11.
- To write the change to disk later, PostgreSQL writes the whole page.

## What happens on a hit and on a miss

<iframe src="buffer/demo.html" title="Animation: a page already in the buffer pool is a hit; a page that is not is a miss, so a page nobody needs is evicted and the whole page is read from disk; an update marks the whole page dirty after a log record is written; a checkpoint later writes the whole page back" width="800" height="450"></iframe>

*The animation repeats about every 10 seconds.*

**Hit.** The page is in the pool. The query uses it in memory. No disk access.

**Miss.**

1. The page is not in the pool, so PostgreSQL needs a free buffer.
2. If the pool is full, it picks a page that nobody is using and that has not been used recently, and evicts it. (PostgreSQL uses a usage counter on each buffer for this, a clock-sweep scheme described in the source code rather than the user documentation.) If the evicted page was dirty, it has to be written to disk first.
3. The whole page is read from disk into the buffer.
4. The query uses it. The page now stays in the pool for the next query.

Note that "from disk" means from the operating system. Linux and other systems have their own page cache, so a PostgreSQL miss may still be served from the operating system's memory without touching the physical disk. PostgreSQL relies on that second cache, and that is why giving all the memory to the pool does not help.

## What happens on a change

1. A **WAL record** describing the change is written first. This is the log that makes the change durable, see [WAL](topic:wal).
2. The change is made **in the buffer, in memory**. The page is marked dirty.
3. The transaction can commit once its log record is safe. **The data file is not written at commit.**
4. Later, the **background writer** or a **checkpoint** writes the dirty page to the data file. A checkpoint flushes all dirty pages, so that crash recovery only has to replay the log after it.

A dirty page can stay in memory for minutes after the commit. If the server crashes, recovery rebuilds it from the log.

## See it work

I created a table of 100,000 rows (13 MB, 1,725 pages), restarted the server so the pool was empty, and ran a query that scans the table, twice:

```sql
CREATE TABLE buf_demo (id int PRIMARY KEY, v int, pad text);
INSERT INTO buf_demo SELECT g, 0, repeat('x', 100) FROM generate_series(1, 100000) g;
ANALYZE buf_demo;

EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF) SELECT sum(v) FROM buf_demo;
```

| | `shared hit` | `shared read` |
|---|---|---|
| First run, empty pool | 33 | 1,692 |
| Second run | 1,725 | 0 |

`shared hit` counts pages found in the pool, and `shared read` counts pages that had to be brought in. The second run read the same 1,725 pages and found them all in memory.

Now change one row. `CHECKPOINT` makes the pool start clean, and needs superuser rights:

```sql
CHECKPOINT;

SELECT ctid, id, v FROM buf_demo WHERE id = 43;

EXPLAIN (ANALYZE, BUFFERS, WAL, COSTS OFF, TIMING OFF) UPDATE buf_demo SET v = v + 1 WHERE id = 43;
```

```
Update on buf_demo (actual rows=0 loops=1)
  Buffers: shared hit=5 dirtied=1
  WAL: records=1 fpi=1 bytes=8213
```

One row changed. One page was **dirtied**. And the log got **8,213 bytes**, about a whole page. That is because the first change to a page after a checkpoint writes a full copy of the page into the log (`full_page_writes`, on by default), to protect against a partly written page after a crash. The change to the row itself is tiny, but PostgreSQL works with the page.

## How to see the cache working

Per database, as a share of pages found in the pool:

```sql
SELECT datname, blks_hit, blks_read,
       round(100.0 * blks_hit / nullif(blks_hit + blks_read, 0), 1) AS hit_pct
FROM pg_stat_database
WHERE datname = current_database();
```

Per table:

```sql
SELECT relname, heap_blks_hit, heap_blks_read, idx_blks_hit, idx_blks_read
FROM pg_statio_user_tables
WHERE relname = 'buf_demo';
```

The cluster-wide I/O picture (PostgreSQL 16 and later), including who writes pages: backends, the background writer or the checkpointer:

```sql
SELECT backend_type, object, context, reads, writes, hits
FROM pg_stat_io
WHERE (reads > 0 OR writes > 0) AND object = 'relation'
ORDER BY reads DESC
LIMIT 10;
```

To see what is in the pool right now, the `pg_buffercache` extension shows one row per buffer:

```sql
-- not run: needs the pg_buffercache extension
SELECT c.relname, count(*) AS buffers, sum(b.isdirty::int) AS dirty_buffers
FROM pg_buffercache b JOIN pg_class c ON b.relfilenode = pg_relation_filenode(c.oid)
GROUP BY c.relname ORDER BY buffers DESC LIMIT 10;
```

## Why it matters for performance

**What it gives.** Queries on a working set that fits in the pool run at memory speed. In my example, the same scan went from 1,692 reads to none.

**What it costs.** Memory taken from the operating system, and the work of writing dirty pages back: checkpoints cause bursts of I/O, and the log grows with full-page images.

**When it shows up.** When the working set is bigger than the pool, pages are constantly evicted and re-read. After a restart the pool is empty ("cold"), so the first queries are slow. A big scan or a big update can push out pages that other queries needed.

**How to measure.** The hit percentage, `shared read` in `EXPLAIN (ANALYZE, BUFFERS)`, and `pg_stat_io`. Remember that a "read" may still come from the operating system cache.

**When to worry** (rules of thumb, not documented limits): an OLTP database whose hit percentage stays well below about 99%, or a plan with a large `shared read` number for a query that you run often.

**What you can change.** Size the pool and tune checkpoints, see [Buffer pool settings](topic:buffer-settings). Read fewer pages: [indexes](topic:index), narrower queries, and [partitions](topic:partitioning) all reduce the pages a query touches.

## Practical checklist

- Everything happens in whole pages. There is no such thing as changing one value alone.
- A hit is a page in memory. A miss reads the whole page from disk, after evicting another.
- A change dirties the page in memory. The log record comes first and the data file is written later.
- Read `shared hit`, `read` and `dirtied` in `EXPLAIN (ANALYZE, BUFFERS)`.
- A cold pool after a restart explains slow first queries.
- A "read" can still be a hit in the operating system cache.
