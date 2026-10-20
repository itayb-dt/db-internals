---
title: "The visibility map: which pages need no checking"
updated: 2026-10-21
sources:
  - https://www.postgresql.org/docs/17/storage-vm.html
  - https://www.postgresql.org/docs/17/indexes-index-only-scans.html
  - https://www.postgresql.org/docs/17/routine-vacuuming.html
  - https://www.postgresql.org/docs/17/pgvisibility.html
  - https://www.postgresql.org/docs/17/functions-admin.html
  - https://www.postgresql.org/docs/17/catalog-pg-class.html
---

This article is about **PostgreSQL 17**. Other engines solve "is this row visible to me?" differently, mostly with undo information or by locking, so they have nothing exactly like this file. PostgreSQL needs it because its index entries carry no visibility information at all.

> **How this was checked:** The SQL in this article was run on PostgreSQL 16.2. The plans and sizes shown come from that run. The `pg_visibility` extension was not available on the test server, so its example is marked `-- not run`.

## What it is

Every table has a **visibility map (VM)**: a small companion file stored next to the table's main data file. It is a separate "fork" of the same relation, named after the table's file number with a `_vm` suffix, for example `12345_vm`. The map stores **two bits for every page** of the table (the [heap](topic:heap)):

- **All-visible.** Every row version on the page is visible to every current and future transaction. The page has nothing for [vacuum](topic:vacuum) to clean.
- **All-frozen.** All rows on the page are frozen, so not even a wraparound-protection vacuum needs to revisit it.

Instead of reading the rows of a page to find out what is true about them, PostgreSQL asks the map. Indexes do not have a visibility map, only tables do.

The map is **conservative**. If a bit is set, it is certainly true. If a bit is clear, the page might still be all-visible, the system just does not know. Bits are set **only by vacuum**, and cleared by **any** change to the page: an insert, update or delete.

## Why it exists: two jobs

**1. Vacuum can skip pages.** Pages marked all-visible have no dead rows, so vacuum does not read them. On a big table where most pages are unchanged, this turns a full scan into a quick one. The all-frozen bit lets even an aggressive, anti-wraparound vacuum skip a page.

**2. Index-only scans can skip the table.** An index entry points to a row, but it does not say whether the row version is visible to your [snapshot](topic:mvcc). That information lives only in the table. Normally every index hit needs a table visit just to check visibility. If the page's all-visible bit is set, the answer is known from the map, and the table visit is skipped.

A real example: an orders table where you often run `SELECT customer_id, total FROM orders WHERE customer_id BETWEEN ...`. With a covering index on `customer_id INCLUDE (total)` the query can be answered from the index alone, but only for pages the map marks all-visible.

## The idea in motion

Each square is a table page, and the bar under it is its bit in the visibility map. A query that uses an index sends one hit to the table for every row. Watch what changes after vacuum sets the bits, and what an update does to them.

<iframe src="visibility-map/demo.html" title="Animation: an index-only scan visits the table for every index hit until VACUUM sets the visibility map bits, then skips the table, and an UPDATE clears the bits of the pages it changed" width="800" height="450"></iframe>

*The animation repeats about every 10 seconds.*

## See it work

I created a table of 200,000 rows with a covering index, on a test server where autovacuum was turned off to make the effect visible:

```sql
CREATE TABLE orders_vm (id int PRIMARY KEY, customer_id int, total numeric) WITH (autovacuum_enabled = off);
INSERT INTO orders_vm SELECT g, g % 1000, g % 500 FROM generate_series(1, 200000) g;
CREATE INDEX orders_vm_cust_total ON orders_vm (customer_id) INCLUDE (total);
ANALYZE orders_vm;

SELECT pg_size_pretty(pg_relation_size('orders_vm', 'main')) AS heap,
       pg_size_pretty(pg_relation_size('orders_vm', 'vm'))   AS vm,
       pg_size_pretty(pg_relation_size('orders_vm', 'fsm'))  AS fsm;
SELECT relpages, relallvisible FROM pg_class WHERE relname = 'orders_vm';

EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF)
SELECT customer_id, total FROM orders_vm WHERE customer_id BETWEEN 10 AND 12;
```

Nothing has been vacuumed yet, so nothing is marked. The map file is empty and the planner chose a **Bitmap Heap Scan**, reading 205 table blocks (210 buffers in total). Now vacuum, and run the same query:

```sql
VACUUM orders_vm;

SELECT pg_size_pretty(pg_relation_size('orders_vm', 'vm')) AS vm;
SELECT relpages, relallvisible FROM pg_class WHERE relname = 'orders_vm';

EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF)
SELECT customer_id, total FROM orders_vm WHERE customer_id BETWEEN 10 AND 12;
```

| | Before `VACUUM` | After `VACUUM` |
|---|---|---|
| Visibility map file | 0 bytes | 8 kB |
| `relallvisible` of `relpages` | 0 of 1,082 | 1,082 of 1,082 |
| Plan | Bitmap Heap Scan | Index Only Scan |
| Table blocks read | 205 | 0 (`Heap Fetches: 0`) |
| Buffers touched | 210 | 6 |

The whole map for an 8.6 MB table is one 8 kB page. With two bits per heap page, one page of the map covers tens of thousands of heap pages, so the map is tiny and stays in memory.

Notice that the planner knew. `pg_class.relallvisible` is the planner's estimate of how many pages are all-visible. It is updated by vacuum and analyze. With it at 0 the planner did not choose an index-only scan, and with it at 100% it did. The documentation says an index-only scan is a win only if a significant fraction of the heap pages are marked.

## What clears the bits

Now change 5% of the rows (every twentieth id) and run the query again:

```sql
UPDATE orders_vm SET total = total + 1 WHERE id % 20 = 0;

EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF)
SELECT customer_id, total FROM orders_vm WHERE customer_id BETWEEN 10 AND 12;
```

The plan is still an Index Only Scan, but it now says **`Heap Fetches: 600`** and touches 606 buffers. All 600 rows needed a visit to the table. The reason is that the updated rows were spread across the whole table, with around 185 rows per page, so almost every page had at least one change, and one change clears the bit for the whole page. In the meantime `relallvisible` still reported 1,082, because only vacuum or analyze refreshes it. After a second `VACUUM`, `Heap Fetches` went back to 0.

The lesson: it is not the share of changed rows that matters, it is the share of changed **pages**.

## Why it matters for performance

**What it gives.** Vacuum that scans only what changed, and index-only scans that read the index alone. On the test table the same query went from 210 buffers to 6.

**What it costs.** Almost nothing in space: two bits per page. The cost is that the benefit depends on vacuum having run recently on that page.

**When it shows up.** Read-mostly and append-mostly tables benefit most. Tables with constant updates across all their pages rarely have many set bits. A new bulk load has no bits set until the first vacuum, so the first index-only scans after loading are not fast. Since autovacuum also runs after inserts (a documented insert-based trigger), append-only tables do get their bits set, but only once enough rows have been added.

**How to measure.**

```sql
SELECT relname, relpages, relallvisible,
       round(100.0 * relallvisible / nullif(relpages, 0), 1) AS all_visible_pct
FROM pg_class
WHERE relkind = 'r' AND relnamespace = 'public'::regnamespace
ORDER BY relpages DESC
LIMIT 20;
```

In a plan, look at `Heap Fetches` in an `Index Only Scan` node. A number close to the row count means the map is not helping. For exact counts per table, the `pg_visibility` extension reports them:

```sql
-- not run: needs the pg_visibility extension
SELECT * FROM pg_visibility_map_summary('orders_vm');
```

**When to worry** (rules of thumb, not documented limits): an `Index Only Scan` with `Heap Fetches` near the number of rows returned, a large table whose `all_visible_pct` is low, or a bulk-loaded table that was never vacuumed.

**What you can change.**

- Run `VACUUM` after a bulk load, so the first reports and index-only scans are fast.
- Make autovacuum reach the table sooner (a lower scale factor, see [Vacuum](topic:vacuum)).
- Keep long transactions short, because rows that an old snapshot may still need cannot be marked all-visible (see [Dead rows](topic:dead-rows)).
- Build covering indexes (`INCLUDE`) for the queries you run often, and expect the benefit on tables that change little.
- Do not rely on index-only scans for tables that are updated across all their pages all day.

## Practical checklist

- Two bits per page: all-visible and all-frozen, in a `_vm` file next to the table.
- Only vacuum sets them. Any change to a page clears them.
- A clear bit may still be true, a set bit is always true.
- Check `Heap Fetches` in index-only scans, and `relallvisible` against `relpages`.
- Vacuum after bulk loads.
- Watch pages changed, not rows changed.
