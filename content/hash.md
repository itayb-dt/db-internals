---
title: "Hash indexes: equality lookups only"
updated: 2026-10-18
sources:
  - https://www.postgresql.org/docs/17/indexes-types.html
  - https://www.postgresql.org/docs/17/hash-index.html
  - https://www.postgresql.org/docs/17/sql-createindex.html
  - https://www.postgresql.org/docs/17/indexes-multicolumn.html
  - https://www.postgresql.org/docs/17/indexes-unique.html
  - https://www.postgresql.org/docs/release/10.0/
---

This article is about the **PostgreSQL 17** hash index. Yes, PostgreSQL supports hash indexes. Engines differ here: MySQL's InnoDB builds an adaptive hash index internally and does not let you create one, while the MEMORY engine does offer hash indexes. Oracle and SQL Server use hash structures for clusters and in-memory tables, not as a general `CREATE INDEX` type.

> **How this was checked:** The SQL in this article was run on PostgreSQL 16.2. The `pgstathashindex` function mentioned in the text comes from the `pgstattuple` extension and was not run.

## What a hash index is

A hash index applies a hash function to the indexed value and uses the result to pick a **bucket page**. To find a row, the database hashes the search value and goes straight to that bucket, instead of descending a tree like a [B-tree](topic:btree) does. Inside a bucket, entries are sorted by hash code, so a page can be searched with binary search.

```sql
CREATE INDEX sessions_token_hash ON sessions USING hash (token);

SELECT * FROM sessions WHERE token = 'f3a9c1d4e8b27a60';
```

A hash index stores only a 4-byte hash code per row, not the column value. This has consequences:

- Only the `=` operator can use it. `<`, `>`, `BETWEEN`, `ORDER BY` and `LIKE` cannot.
- The index is lossy. Two different values can have the same hash, so the executor rechecks the table row.
- It cannot return the column value, because the value is not in the index.
- Size does not depend on the value size. A hash index on long values (URLs, UUIDs, tokens) can be much smaller than a B-tree on the same column, and there is no limit on the length of the indexed value.
- Any data type can be indexed, even types without a sort order.

The documentation lists two more limits: hash indexes support only single-column indexes and cannot enforce uniqueness. A unique constraint always needs a B-tree.

## Are they safe to use?

Yes. The advice to avoid hash indexes is outdated. Before PostgreSQL 10, hash indexes were not written to the write-ahead log, which meant they were not crash-safe and not replicated. PostgreSQL 10 added WAL logging, so they are now crash-safe and work with replication. Version 10 also improved their performance.

## How buckets grow

Each bucket is a page. When it fills up, PostgreSQL chains **overflow pages** to it. When the index grows, it adds buckets by splitting one existing bucket at a time. This split happens in the foreground, during the insert that triggers it.

Two situations hurt:

- **Many rows with the same value.** All of them land in the same bucket and its overflow chain, and a lookup must scan the whole chain. The documentation says an unbalanced hash index can be worse than a B-tree. Hash indexes suit unique or nearly unique data.
- **Fast-growing tables.** Bucket splits happen during inserts and add latency.

An index does not shrink. Vacuum removes dead entries and compacts overflow pages, and empty overflow pages are reused, but the only way to reduce the size is `REINDEX`.

## When a hash index is the right choice

The documentation says hash indexes are best optimised for `SELECT` and `UPDATE`-heavy workloads with equality lookups on larger tables. A typical case is a lookup by a long, nearly unique key that you never sort or range-scan: session tokens, API keys, URLs, content hashes.

In practice, a B-tree is often good enough, and it also gives you ranges, ordering, uniqueness and multiple columns. Choose hash when the key is long, the queries are equality only, and a smaller index matters.

## Why it matters for performance

**What it costs.** Writes maintain the index like any other. Bucket splits add latency to inserts as the table grows. Every lookup is lossy, so the heap row is always checked. Skewed data creates long overflow chains.

**When it shows up.** On tables where many rows share one value, and on tables that grow quickly.

**How to measure.** Compare sizes and plans against a B-tree on the same column:

```sql
CREATE INDEX sessions_token_btree ON sessions (token);

SELECT indexrelname, pg_size_pretty(pg_relation_size(indexrelid)) AS size, idx_scan
FROM pg_stat_user_indexes
WHERE relname = 'sessions';

EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM sessions WHERE token = 'f3a9c1d4e8b27a60';
```

Look at the buffers read for the lookup, and at the size difference. To see how evenly values are spread, check duplicates:

```sql
SELECT count(*) AS rows, count(DISTINCT token) AS distinct_values FROM sessions;
```

The `pgstattuple` extension also provides `pgstathashindex('index_name')` with bucket, overflow and dead-tuple counts.

**When to worry.** A distinct-value count far below the row count (a rough rule: many rows per value). An index that grows while the table does not, which can mean dead entries and overflow pages. A hash index that is not faster than a B-tree in your own test, in which case the B-tree is the better choice.

**What you can change.**

- Use a B-tree if you need ranges, ordering, uniqueness or several columns.
- Exclude very frequent values with a partial index, if the queries allow it.
- Rebuild a bloated hash index with `REINDEX INDEX CONCURRENTLY`.
- Avoid them on tables with a fast insert rate and no real benefit from the smaller index.

## Practical checklist

- Use hash only for `=` lookups on long, nearly unique keys.
- Test against a B-tree on real data before choosing.
- Do not use it for unique constraints or multicolumn indexes.
- Check how many rows share each value.
- Rebuild with `REINDEX` if the index grows without need.
- See [Index](topic:index) for how the types compare.
