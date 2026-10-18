---
title: "Actual execution plan: what really happened"
updated: 2026-10-18
sources:
  - https://www.postgresql.org/docs/17/using-explain.html
  - https://www.postgresql.org/docs/17/sql-explain.html
  - https://www.postgresql.org/docs/17/runtime-config-query.html
---

This article is about **PostgreSQL 17**. In SQL Server the same idea is the "actual execution plan", and in Oracle it is the plan with runtime statistics. In PostgreSQL you get it with `EXPLAIN ANALYZE`.

> **Draft status:** the SQL in this article has been written against the documentation but **not yet run**. Treat every snippet as untested until this note is removed.

## Estimated versus actual

A plain `EXPLAIN` shows the [execution plan](topic:execution-plan) the planner chose, with **estimates**. The query is not run. It is a prediction based on [statistics](topic:statistics).

`EXPLAIN ANALYZE` plans the query and then **executes** it. The output is the same tree, with measurements added next to the estimates:

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT o.id, c.name
FROM orders o
JOIN customers c ON c.id = o.customer_id
WHERE o.created_at >= now() - interval '1 day';
```

Illustrative output:

```
Nested Loop  (cost=0.86..540.10 rows=40 width=36) (actual time=0.040..95.200 rows=48210 loops=1)
  Buffers: shared hit=151200 read=3100
  ->  Index Scan using orders_created_idx on orders o  (cost=0.43..120.00 rows=40 width=12) (actual time=0.020..18.000 rows=48210 loops=1)
  ->  Index Scan using customers_pkey on customers c  (cost=0.43..8.30 rows=1 width=28) (actual time=0.001..0.001 rows=1 loops=48210)
Planning Time: 0.9 ms
Execution Time: 96.1 ms
```

Here the planner expected 40 rows and got 48,210. That mismatch is the finding.

## What the actual plan adds

The estimated plan has costs, estimated rows and widths. The actual plan adds:

- **Actual rows.** How many rows each node really returned.
- **Actual time.** Two numbers in milliseconds: the time to the first row and the time to the last row. Unlike cost, these are real time.
- **Loops.** How often the node ran. The inner side of a nested loop runs once per outer row. The actual time and rows shown are **averages per loop**, so multiply by `loops` for the total. In the example, the customers lookup is 0.001 ms times 48,210 loops, about 48 ms.
- **Planning Time and Execution Time.** Total time to plan and to run.
- **Extra node details.** For example, how many rows a filter removed, how many heap fetches an index-only scan still needed, which sort method was used and whether it spilled to disk, and how many batches a hash used. These appear only where relevant.
- **Buffers** (with `BUFFERS`). Pages found in shared buffers (`hit`), read from outside them (`read`), dirtied and written, plus temporary file blocks used by sorts and hashes.
- **WAL** (with `WAL`). Records, full-page images and bytes written, for statements that change data.

Two options change the cost of measuring. `TIMING false` skips per-node timing, which avoids clock-reading overhead on some systems when you only need row counts. The `SERIALIZE` option includes the time to convert the result to the output format, which can be large for expensive types or for values fetched from [TOAST](topic:toast).

## Options that only work with ANALYZE

`TIMING`, `WAL` and `SERIALIZE` can be used only together with `ANALYZE`. The options that also work on a plain estimated plan (`COSTS`, `VERBOSE`, `SETTINGS`, `GENERIC_PLAN`, `SUMMARY`, `MEMORY`, `FORMAT`) are described in the [execution plan](topic:execution-plan) article. `GENERIC_PLAN` is the one that cannot be combined with `ANALYZE`, because a generic plan with placeholders cannot be run.

With `FORMAT JSON` the actual figures appear as fields next to the estimates, for example `Actual Rows` and `Actual Loops` beside `Plan Rows`, so a script can compute the estimate error for every node. A practical default for analysis tools is `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`. For reading by eye, plain text is easier.

## Important: it runs the statement

`EXPLAIN ANALYZE` really executes the query. For a `SELECT` the output rows are discarded, but for `INSERT`, `UPDATE`, `DELETE`, `MERGE` and `CREATE TABLE AS` the changes happen. To measure without keeping the effect:

```sql
BEGIN;
EXPLAIN (ANALYZE, BUFFERS) UPDATE orders SET status = 'shipped' WHERE id < 1000;
ROLLBACK;
```

Locks are still taken and the work is still done, so be careful on production. A query that runs for an hour will take an hour to explain.

## How to read it

1. **Compare estimated rows to actual rows**, node by node. A large difference is the most useful signal. Start at the deepest node where they diverge, because errors compound upward. Fix it with [statistics](topic:statistics).
2. **Find where the time goes.** Take actual time times loops for each node and subtract the children's time.
3. **Check the loops.** A node with a high loop count and a small per-loop time can dominate the total.
4. **Check buffers.** Many `read` pages means disk or OS cache. Many `hit` pages means the work is in memory but still large. See the [buffer pool](topic:buffer).
5. **Check for spills.** A sort or hash that uses temporary files is slower than one that fits in `work_mem`.

## Why it matters for performance

**What it costs.** Measuring adds overhead, mostly from timing, so times can look slightly worse than a normal run. More importantly the query runs in full, with its side effects and load.

**When it shows up.** When a query is slow and the estimated plan looks reasonable, or when a plan changed after data growth or a statistics refresh.

**How to measure.** Use `EXPLAIN (ANALYZE, BUFFERS)` as the default. Run it twice, because the first run may include cold-cache reads. For statements you cannot run safely, use `EXPLAIN` alone and reason from estimates.

**When to worry.** Estimates off by 10x or more on a node (a rule of thumb). A nested loop with a huge loop count. A sort or hash spilling to disk. Execution time dominated by a node reading far more buffers than it returns rows.

**What you can change.**

- Refresh or improve [statistics](topic:statistics) when estimates are wrong.
- Add or adjust an [index](topic:index) when a scan reads far more than it returns.
- Raise `work_mem` for specific sessions when sorts or hashes spill.
- Rewrite the query when the shape forces the bad plan.

## Practical checklist

- Use `EXPLAIN (ANALYZE, BUFFERS)` and run it twice.
- Wrap data-changing statements in `BEGIN` ... `ROLLBACK`.
- Compare estimated and actual rows first.
- Multiply per-loop numbers by `loops`.
- Check buffer reads and disk spills.
- Change one thing at a time, then compare the new plan.
