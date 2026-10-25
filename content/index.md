---
title: "Indexes: why every database needs them"
updated: 2026-10-25
sources:
  - https://www.postgresql.org/docs/17/indexes-intro.html
  - https://www.postgresql.org/docs/17/indexes-types.html
  - https://www.postgresql.org/docs/17/sql-createindex.html
  - https://www.postgresql.org/docs/17/monitoring-stats.html
---

This article explains the idea of an index in general. The syntax and details are checked against the **PostgreSQL 17** documentation. Other relational engines use the same idea, mostly with B-trees by default, and differ in details such as clustered indexes (SQL Server, InnoDB), where the table itself is stored in index order.

> **How this was checked:** The SQL in this article was run on PostgreSQL 16.2.

## The problem: finding one row among millions

Imagine an `orders` table with 100 million rows. A customer opens "my order 8841234" and the application runs:

```sql
SELECT * FROM orders WHERE order_id = 8841234;
```

Without an index, the database has no way to know where that row is. It reads the [heap table](topic:heap) page by page and checks every row. That is a sequential scan. If the rows average 100 bytes, the table is on the order of 10 GB (an illustrative figure), and you read all of it to return one row.

Now the same for `WHERE customer_id = 42` on a busy shop. The customer has 30 orders. You still read 100 million rows to find 30.

An **index** is a separate, smaller structure that maps column values to row locations. It works like the index at the back of a book: you look up the term, then jump to the page. For a B-tree, the default type, the database walks a tree a few levels deep instead of scanning the table:

```sql
CREATE INDEX orders_customer_id_idx ON orders (customer_id);
```

After that, the same query touches a handful of index pages and about 30 table rows. You do not have to change the query. PostgreSQL keeps the index up to date and decides by itself when to use it.

The animation runs the same query twice. First on the table alone, then with an index.

<iframe src="index/demo.html" title="Animation: without an index the database reads all 24 pages of the table to find one customer. With an index it reads the index root, one index leaf and then one table page" width="800" height="450"></iframe>

*The animation repeats about every 10 seconds.*

## What an index does not do for free

An index is a trade. You pay for the speed.

- **Writes get slower.** Every `INSERT`, and every `UPDATE` or `DELETE` that touches indexed columns, must also change each index on the table.
- **Disk and memory.** An index takes space, and its pages compete with table pages for the buffer cache.
- **Fewer cheap updates.** The documentation notes that indexes can prevent the creation of heap-only tuples, which are the cheap kind of update.
- **Maintenance.** Indexes bloat over time and need vacuum.
- **Not always used.** If a query returns a large share of the table, a sequential scan can be faster. The planner decides using statistics, so run `ANALYZE` (autovacuum usually does it).

Rule of thumb: index the columns you filter, join and sort on, in your most frequent and slowest queries. Drop indexes nobody uses.

## Different physical index types

"Index" is the concept. Under it sit several physical structures, each good at a different kind of question. `CREATE INDEX` builds a B-tree unless you choose another with `USING`:

| Type | Good for | Covered in this map |
|---|---|---|
| B-tree | Equality, ranges, sorting on ordered data | [B-Tree](topic:btree) |
| Hash | Equality only | [Hash index](topic:hash) |
| GIN | Values with many parts: arrays, `jsonb`, full-text | [GIN](topic:gin) |
| BRIN | Huge tables whose values follow the physical row order | [BRIN](topic:brin) |
| GiST, SP-GiST | Geometry, nearest-neighbour, trees and tries | Not covered yet |

Each has its own cost profile. A B-tree is the safe default. The others earn their place when the data or the query does not fit a B-tree.

```sql
CREATE INDEX docs_tags_gin ON docs USING gin (tags);
CREATE INDEX events_created_brin ON events USING brin (created_at);
```

## Why it matters for performance

**What it costs.** Reads from an index are cheap. The cost moves to writes, disk space and cache. Creating an index on a large table can take a long time. By default, writes to the table are blocked while it builds.

**When it shows up.** On write-heavy tables with many indexes, each row change turns into several index changes. On large tables, unused indexes still cost every write.

**How to measure.** First, check that the query uses the index:

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM orders WHERE customer_id = 42;
```

Look for `Index Scan` or `Bitmap Index Scan` instead of `Seq Scan`, and compare the number of buffers read. Then find indexes that are never used:

```sql
SELECT schemaname, relname, indexrelname, idx_scan,
       pg_size_pretty(pg_relation_size(indexrelid)) AS size
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC, pg_relation_size(indexrelid) DESC
LIMIT 20;
```

**When to worry.** An index with `idx_scan = 0` over a long period (counters reset with a statistics reset, so check the period) and a large size is a candidate for removal. Do not drop indexes that enforce unique or primary key constraints.

**What you can change.** Use `CREATE INDEX CONCURRENTLY` on busy tables, so writes can continue (it takes longer and has caveats). Use partial indexes for a small subset of rows. Use multicolumn indexes for queries that filter on the same columns together. Remove duplicates and unused indexes.

## Practical checklist

- Find slow queries first, then add the index that serves them.
- Check with `EXPLAIN (ANALYZE, BUFFERS)` before and after.
- Index foreign key columns that you join or delete by.
- Keep the number of indexes on write-heavy tables small.
- Review unused and duplicate indexes regularly.
- Build on busy tables with `CONCURRENTLY`.
