---
title: "B-Tree indexes: the default index"
updated: 2026-10-18
sources:
  - https://www.postgresql.org/docs/17/indexes-types.html
  - https://www.postgresql.org/docs/17/btree.html
  - https://www.postgresql.org/docs/17/sql-createindex.html
  - https://www.postgresql.org/docs/17/monitoring-stats.html
---

This article is about the **PostgreSQL 17** B-tree index. B-trees are also the default or main index type in MySQL/InnoDB, SQL Server and Oracle. They differ in details, for example InnoDB stores the whole table as a B-tree on the primary key.

> **Draft status:** the SQL in this article has been written against the documentation but **not yet run**. Treat every snippet as untested until this note is removed.

## What a B-tree is

An [index](topic:index) of this kind is a balanced, sorted tree. Every node is one [page](topic:page). The bottom level, the leaf pages, holds the key values in sorted order, each with a pointer to the table row (a [tuple](topic:tuple) in the [heap](topic:heap)). Upper levels hold keys with links down to the pages below, so a search starts at the root and follows one link per level until it reaches a leaf.

The tree is balanced, so every lookup walks the same number of levels. Each page holds many entries, so the tree stays shallow. Even for a very large table, that is a few levels, which means a few page reads per lookup. That is why finding one order among 100 million rows takes milliseconds.

Because the leaves are sorted, a B-tree also finds a range (`BETWEEN`) by locating the start and reading along the leaf pages, and it can return rows in sorted order.

## What it can answer

PostgreSQL considers a B-tree for these operators: `<`, `<=`, `=`, `>=`, `>`. Constructs built from them also work: `BETWEEN`, `IN`, `IS NULL` and `IS NOT NULL`. It can serve `LIKE 'foo%'` (a constant pattern anchored at the start), but not `LIKE '%foo'`. If the database does not use the C locale, such a pattern index needs a special operator class (for example `text_pattern_ops`).

```sql
CREATE INDEX orders_customer_created_idx ON orders (customer_id, created_at);

SELECT * FROM orders
WHERE customer_id = 42 AND created_at >= now() - interval '30 days'
ORDER BY created_at DESC;
```

In a multicolumn index, column order matters. The index works best when the query constrains the leading columns. The index above serves the query for one customer and a date range, but is a poor fit for a query on `created_at` alone.

Any type that can be sorted can be indexed. One limit: an index entry cannot exceed about one-third of a page, after compression. This is why you cannot index very large text values directly (index a hash of the value instead).

## How it changes when data changes

An insert goes to the correct leaf page. If the page is full, it splits into two, and the parent gets a new link. Splits can cascade upwards, and when the root splits, the tree gains a level.

Two details keep the index healthy:

- **Fillfactor.** Leaf pages are filled to 90% by default, leaving space for later inserts. Lowering it leaves more room but makes the index larger.
- **Deduplication.** When many entries have the same key, the index stores the key once with a list of row pointers. It is on by default (`deduplicate_items`) and can shrink indexes on low-cardinality columns significantly.

PostgreSQL also removes some obsolete entries during normal work (bottom-up deletion), and vacuum removes the rest. An `UPDATE` creates a new row version, and any index on a changed column gets a new entry.

## Why it matters for performance

**What it costs.** Each insert, delete and indexed-column update writes to every B-tree on the table. Random keys (such as random UUIDs) spread inserts over all leaf pages, which touches more pages and causes more splits than ever-increasing keys. A larger index also uses more cache.

**When it shows up.** On write-heavy tables with many indexes, and with wide or random keys.

**How to measure.**

```sql
SELECT indexrelname, idx_scan, idx_tup_read, idx_tup_fetch,
       pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
WHERE relname = 'orders';
```

`idx_scan` shows how often the index is used, and `size` shows what it costs. For bloat, the `pgstattuple` extension provides `pgstatindex('index_name')`, with `avg_leaf_density` and `leaf_fragmentation`.

**When to worry.** An index that is large but has few scans. A size that keeps growing while the row count does not. A low `avg_leaf_density` (a rough rule: well under about 50% on an index that should be dense) points to bloat.

**What you can change.**

- Drop indexes that are not used.
- Put the most selective or most commonly filtered column first in multicolumn indexes.
- Use a partial index when queries touch only part of the table.
- Rebuild a bloated index without blocking writes: `REINDEX INDEX CONCURRENTLY orders_customer_created_idx;`
- Prefer ordered keys (sequence, time-ordered ids) over random ones when you can.

## Practical checklist

- B-tree is the right default. Reach for another type only with a clear reason.
- Match column order to the queries.
- Check plans with `EXPLAIN (ANALYZE, BUFFERS)`.
- Watch index size and `idx_scan` regularly.
- Rebuild bloated indexes with `REINDEX ... CONCURRENTLY`.
- Avoid indexing very large values directly.
