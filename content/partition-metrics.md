---
title: "Partition metrics: observing a table that is many tables"
updated: 2026-10-19
sources:
  - https://www.postgresql.org/docs/17/ddl-partitioning.html
  - https://www.postgresql.org/docs/17/functions-admin.html
  - https://www.postgresql.org/docs/17/monitoring-stats.html
  - https://www.postgresql.org/docs/17/sql-analyze.html
  - https://www.postgresql.org/docs/17/routine-vacuuming.html
  - https://www.postgresql.org/docs/17/pgstatstatements.html
---

This article is about **PostgreSQL 17**, and continues from [Table partitioning](topic:partitioning). The queries use the `events` table from that article.

> **How this was checked:** the queries were run on PostgreSQL 16.2. The one for `pg_stat_statements` was not run, because that extension was not available.

## Why metrics are per partition

PostgreSQL tracks activity per table, and each partition is a table. Reads, writes, dead rows, vacuum runs and cache hits are counted on the partition that did the work. The logical parent table is a virtual shell, so it has nothing of its own to report:

- `pg_total_relation_size('events')` returns 0 bytes.
- In `pg_stat_user_tables` the parent has a row, but its counters stay at 0 in my test. The activity is on the partitions.

So there is no single "events" row to look at. You observe each partition, then add them up yourself to get the logical table.

## List the partitions and their sizes

`pg_partition_tree` lists the partitions of a table. Use `isleaf` to get only the real ones, because sub-partitioned tables have inner levels.

```sql
SELECT t.relid::regclass AS partition,
       pg_size_pretty(pg_total_relation_size(t.relid)) AS total
FROM pg_partition_tree('events') t
WHERE t.isleaf
ORDER BY t.relid::regclass::text;
```

`pg_total_relation_size` includes the partition's indexes and its TOAST data. A big difference between partitions is normal (this month against an empty future one). A partition much larger than its peers can mean skewed data, or a default partition that is filling up.

## Per-partition activity and vacuum health

```sql
SELECT t.relid::regclass AS partition,
       s.seq_scan, s.idx_scan, s.n_live_tup, s.n_dead_tup, s.last_autovacuum
FROM pg_partition_tree('events') t
JOIN pg_stat_user_tables s ON s.relid = t.relid
WHERE t.isleaf
ORDER BY t.relid::regclass::text;
```

How to read it:

- **`seq_scan` and `idx_scan`** show how queries reach each partition. In my test, a query filtered on the date key scanned only the partition for that day. A query on `user_id` added a sequential scan to every partition. If a key-filtered query raises the counters on all partitions, pruning is not working.
- **`n_live_tup` and `n_dead_tup`** show how many rows each partition has and how many are waiting for vacuum.
- **`last_autovacuum`** shows whether vacuum has reached the partition. Autovacuum treats each partition like any other table.

## Cache behavior per partition

```sql
SELECT t.relid::regclass AS partition,
       s.heap_blks_read, s.heap_blks_hit, s.idx_blks_read, s.idx_blks_hit
FROM pg_partition_tree('events') t
JOIN pg_statio_user_tables s ON s.relid = t.relid
WHERE t.isleaf
ORDER BY t.relid::regclass::text;
```

`hit` means the block was already in shared buffers, and `read` means it had to be read from outside them. The current partition usually has the best hit rate, and old partitions get colder. That is expected, and it is one of the benefits of partitioning.

## Summing up the logical table

Because the parent shows nothing, build the total yourself by summing over the leaf partitions:

```sql
SELECT sum(s.seq_scan) AS seq_scan, sum(s.idx_scan) AS idx_scan,
       sum(s.n_live_tup) AS live_rows, sum(s.n_dead_tup) AS dead_rows,
       pg_size_pretty(sum(pg_total_relation_size(s.relid))) AS total_size
FROM pg_partition_tree('events') t
JOIN pg_stat_user_tables s ON s.relid = t.relid
WHERE t.isleaf;

SELECT round(100.0 * sum(s.heap_blks_hit)
             / nullif(sum(s.heap_blks_hit) + sum(s.heap_blks_read), 0), 1) AS heap_hit_pct
FROM pg_statio_user_tables s
JOIN pg_partition_tree('events') t ON t.relid = s.relid
WHERE t.isleaf;
```

Sums work for counts and sizes. For ratios such as the hit percentage, sum the numerator and the denominator first and divide at the end. Do not average the partitions' percentages, because a small, busy partition would count as much as a huge one.

Counters are cumulative since the last statistics reset or server start, so sample twice and compare to get a rate. Statistics are also reported with a short delay, so a query you just ran may take a moment to show up.

## Statistics for the planner

The planner's statistics are separate from these counters. Autovacuum does not process the partitioned table itself, so it does not analyze it. Run `ANALYZE` on the parent after loading data and whenever the distribution of data across partitions changes. That call also updates every partition.

```sql
ANALYZE events;

SELECT t.relid::regclass AS partition, s.last_analyze, s.last_autoanalyze
FROM pg_partition_tree('events') t
JOIN pg_stat_user_tables s ON s.relid = t.relid
WHERE t.isleaf;
```

## Query-level metrics

Extensions such as `pg_stat_statements` report per query, not per table. To find out which partitions a slow query used, run it under `EXPLAIN` and read the partition names in the plan. See the [actual plan](topic:actual-plan) for how.

```sql
-- not run (needs the pg_stat_statements extension)
SELECT left(query, 80) AS query, calls, mean_exec_time, shared_blks_read
FROM pg_stat_statements
WHERE query ILIKE '%events%'
ORDER BY total_exec_time DESC
LIMIT 10;
```

## Why it matters for performance

**What it costs.** Monitoring that watches only the parent sees nothing. Dashboards need to be built over the partition list, and the list changes every month as partitions come and go.

**When it shows up.** When a single hot partition takes most of the load, when a new partition has no statistics yet, and when a retention job falls behind and old partitions stay.

**When to worry.** Rules of thumb, not documented limits:
- A key-filtered query that increases `seq_scan` on many partitions. Pruning is off or the filter does not use the key.
- A partition with a large `n_dead_tup` and an old `last_autovacuum`.
- One partition far larger than its peers.
- A parent whose `ANALYZE` is old, with plans that estimate the wrong number of rows.
- The oldest partition older than your retention policy.

**What you can change.** Filter on the partition key. Run `ANALYZE` on the parent on a schedule. Tune autovacuum per partition for the busiest ones. Fix the retention job. Add a new partition before it is needed.

## Practical checklist

- Monitor per partition, and sum to the logical table yourself.
- Use `pg_partition_tree(...)` with `isleaf` as the base of every query.
- Add numerators and denominators for ratios, never average percentages.
- Run `ANALYZE` on the partitioned table on a schedule.
- Check that key-filtered queries scan only a few partitions.
- Alert on the oldest partition age and on partitions with many dead rows.
