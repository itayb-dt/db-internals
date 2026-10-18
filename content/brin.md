---
title: "BRIN indexes: tiny indexes for huge, ordered tables"
updated: 2026-10-18
sources:
  - https://www.postgresql.org/docs/17/indexes-types.html
  - https://www.postgresql.org/docs/17/brin.html
  - https://www.postgresql.org/docs/17/sql-createindex.html
  - https://www.postgresql.org/docs/17/view-pg-stats.html
---

This article is about the **PostgreSQL 17** BRIN index (Block Range INdex). Other engines have similar ideas under other names: zone maps or min/max indexes in column stores and warehouses (Snowflake, ClickHouse, Oracle Exadata storage indexes).

> **Draft status:** the SQL in this article has been written against the documentation but **not yet run**. Treat every snippet as untested until this note is removed.

## The problem: a B-tree is too big for some tables

Take an `events` table with billions of rows, append-only, with a `created_at` column. Queries ask for "the last hour" or "yesterday". A B-tree on `created_at` would work, but it needs an entry per row. On a table this size, the index itself is huge, and every insert has to maintain it.

But look at the data. New rows arrive in time order, so rows with similar timestamps sit next to each other in the table. Most of the table clearly does not match "yesterday", and we only need to know which parts to skip.

## How BRIN works

BRIN stores a small summary for each **block range**, a group of pages next to each other in the table. For a column with a sort order, the summary is the minimum and maximum value in the range. The default range is 128 pages (`pages_per_range`).

To answer `WHERE created_at >= '2026-10-17'`, the database reads the summaries and skips every range whose maximum is below that date. It then scans the pages in the remaining ranges. The index is lossy: it returns whole ranges, and the executor rechecks each row and discards the ones that do not match.

```sql
CREATE INDEX events_created_brin ON events USING brin (created_at);

-- a smaller range is more precise, and a bigger index
CREATE INDEX events_created_brin32 ON events USING brin (created_at) WITH (pages_per_range = 32);
```

The number of index entries is the table size in pages divided by `pages_per_range`. For a table of many gigabytes this is a very small index, which is cheap to scan and cheap to maintain.

## The condition: physical order must match logical order

BRIN only works when values are correlated with the physical position of rows. A timestamp on an append-only table is the classic case. A ZIP code, where one city is stored together, is another. If values are scattered randomly, every range contains almost every value, nothing can be skipped, and the index is useless.

PostgreSQL measures this correlation in `pg_stats`. It ranges from -1 to +1, and values near either end mean the order matches.

```sql
SELECT attname, correlation
FROM pg_stats
WHERE schemaname = 'public' AND tablename = 'events' AND attname = 'created_at';
```

Updates and deletes followed by inserts into freed space can mix old and new values into the same ranges, which weakens the summaries over time.

## Keeping the index current

A range gets its summary when the table is vacuumed. New ranges at the end of the table have no summary until then, and unsummarized ranges are always scanned. With `autosummarize` (off by default), summarization of filled ranges happens whenever autovacuum runs in the database. You can also summarize on demand:

```sql
SELECT brin_summarize_new_values('events_created_brin');
```

## Why it matters for performance

**What it costs.** Very little to maintain and store. The cost is precision: queries read whole ranges, so a selective query reads more than a B-tree would. BRIN is a poor fit for point lookups.

**When it shows up.** On range queries over big tables, where skipping most of the table is the goal. It hurts when the correlation is low.

**How to measure.** Compare sizes and plans:

```sql
SELECT pg_size_pretty(pg_relation_size('events_created_brin')) AS brin_size,
       pg_size_pretty(pg_relation_size('events')) AS table_size;

EXPLAIN (ANALYZE, BUFFERS)
SELECT count(*) FROM events WHERE created_at >= now() - interval '1 day';
```

In the plan, look for a `Bitmap Index Scan` on the BRIN index followed by a `Bitmap Heap Scan`, and check `Rows Removed by Index Recheck` and the buffers read. Many rows removed by recheck mean ranges are too wide or the data is not ordered.

**When to worry.** A correlation far from -1 and +1 (rough rule: below about 0.9 in absolute value on the column you rely on). A heap scan that reads most of the table despite the index. Recent data missing summaries because vacuum is behind.

**What you can change.**

- Lower `pages_per_range` for more precision, at the cost of a larger index.
- Enable `autosummarize`, or run summarization after bulk loads.
- Restore physical order, for example by loading data in order, or by rewriting the table sorted by the column (this takes locks and time, so plan it).
- Use a B-tree if the correlation is poor or you need point lookups.
- PostgreSQL also ships other BRIN operator classes (such as minmax-multi and bloom) that cope better with less ordered data.

## Practical checklist

- Use BRIN for very large tables with naturally ordered columns, mostly appended.
- Check `pg_stats.correlation` before you create it.
- Compare index size and plan with a B-tree on a copy of the data.
- Make sure vacuum or autosummarize keeps new ranges summarized.
- Tune `pages_per_range` to balance size against precision.
