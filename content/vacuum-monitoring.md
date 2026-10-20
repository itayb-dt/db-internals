---
title: "Monitoring vacuum: is it keeping up?"
updated: 2026-10-20
sources:
  - https://www.postgresql.org/docs/17/routine-vacuuming.html
  - https://www.postgresql.org/docs/17/monitoring-stats.html
  - https://www.postgresql.org/docs/17/progress-reporting.html
  - https://www.postgresql.org/docs/17/runtime-config-autovacuum.html
  - https://www.postgresql.org/docs/17/runtime-config-logging.html
  - https://www.postgresql.org/docs/17/sql-createtable.html
---

This article is about **PostgreSQL 17** and continues from [Vacuum](topic:vacuum). It answers one question: is vacuum keeping up with the dead rows your workload creates, and if not, why?

> **How this was checked:** The SQL in this article was run on PostgreSQL 16.2. The progress table and the log excerpt come from real runs on that server. The progress view has more columns in 17 than in 16, so the queries here use only columns that exist in both.

## 1. Which tables need attention

Start with the statistics view. For each table it shows dead rows and when vacuum last ran:

```sql
SELECT relname, n_live_tup, n_dead_tup,
       round(100.0 * n_dead_tup / nullif(n_live_tup + n_dead_tup, 0), 1) AS dead_pct,
       last_autovacuum, autovacuum_count, last_vacuum
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 20;
```

How to read it:

- **High `dead_pct` and an old `last_autovacuum`:** vacuum is not reaching the table, or is slower than the changes.
- **High `dead_pct` and a recent `last_autovacuum`:** vacuum ran but could not remove the rows. Something is [holding the cleanup back](topic:dead-rows), see section 5.
- **`autovacuum_count` stuck at 0 on a busy table:** autovacuum never starts there. Check the next section.

The counters are estimates and are updated with a short delay. They reset on a statistics reset, so compare two samples to see a trend, not one number.

## 2. When will autovacuum start?

Autovacuum starts on a table once its dead rows pass `threshold + scale factor × rows`. This query shows how far each table is from that point, using the server-wide settings:

```sql
SELECT s.relname, s.n_dead_tup,
       round(current_setting('autovacuum_vacuum_threshold')::int
             + current_setting('autovacuum_vacuum_scale_factor')::float8 * greatest(c.reltuples, 0)) AS trigger_at,
       round((100.0 * s.n_dead_tup
              / nullif(current_setting('autovacuum_vacuum_threshold')::int
                       + current_setting('autovacuum_vacuum_scale_factor')::float8 * greatest(c.reltuples, 0), 0))::numeric, 1) AS pct_of_trigger
FROM pg_stat_user_tables s
JOIN pg_class c ON c.oid = s.relid
ORDER BY pct_of_trigger DESC NULLS LAST
LIMIT 20;
```

A table close to 100% is about to be vacuumed. (A table that has never been analyzed has an unknown row count, shown as -1, and is treated as empty here.) A table far above 100% that is not being vacuumed has a problem. Tables with their own settings are left out of this calculation, so list the overrides too:

```sql
SELECT relname, reloptions FROM pg_class WHERE reloptions IS NOT NULL;
```

## 3. What is vacuum doing right now?

Autovacuum workers show up in `pg_stat_activity`. A running vacuum reports its progress in `pg_stat_progress_vacuum`:

```sql
SELECT p.relid::regclass AS table_name, p.phase,
       p.heap_blks_total, p.heap_blks_scanned, p.heap_blks_vacuumed, p.index_vacuum_count,
       round(100.0 * p.heap_blks_scanned / nullif(p.heap_blks_total, 0), 1) AS scanned_pct
FROM pg_stat_progress_vacuum p;

SELECT pid, backend_type, now() - xact_start AS running_for, left(query, 60) AS query
FROM pg_stat_activity
WHERE backend_type = 'autovacuum worker' OR query ILIKE 'vacuum%';
```

The first query returns nothing when no vacuum is running. This is what it printed for a manual vacuum of a 400,000-row table that I throttled on purpose, sampled every two seconds:

| table_name | phase | heap_blks_total | heap_blks_scanned | scanned_pct |
|---|---|---|---|---|
| big | scanning heap | 20690 | 2533 | 12.2 |
| big | scanning heap | 20690 | 6229 | 30.1 |
| big | scanning heap | 20690 | 7035 | 34.0 |

Vacuum goes through phases: scanning the heap, vacuuming the indexes, vacuuming the heap, and cleaning up. `index_vacuum_count` shows how many passes over the indexes it has needed. A table with many indexes and many dead rows can take several passes. Because vacuum uses the visibility map to skip pages, the scanned counter can finish below the total.

## 4. What did it do? The log

Autovacuum can log every run. Turn it on for one table, or for all tables with `log_autovacuum_min_duration = 0` in the server settings (the default is 10 minutes, so short runs are not logged):

```sql
ALTER TABLE jobs SET (log_autovacuum_min_duration = 0);
```

A real log entry from a table where I updated 20,000 of 50,000 rows:

```
automatic vacuum of table "exp2.public.hot": index scans: 1
    pages: 0 removed, 310 remain, 310 scanned (100.00% of total)
    tuples: 20000 removed, 50000 remain, 0 are dead but not yet removable
    removable cutoff: 1358, which was 0 XIDs old when operation ended
    new relfrozenxid: 1356, which is 1 XIDs ahead of previous value
    index scan needed: 89 pages from table (28.71% of total) had 20000 dead item identifiers removed
    avg read rate: 0.000 MB/s, avg write rate: 1.372 MB/s
```

What to look for:

- **`tuples: N removed`:** how much it cleaned.
- **`M are dead but not yet removable`:** if M is large, an old snapshot is holding rows back.
- **`removable cutoff` and its age:** a large "XIDs old" value means the oldest open transaction is far behind.
- **`index scans`:** more than one means vacuum ran out of memory for the dead-row list and had to repeat the index passes.
- **The time and the read/write rates:** how long it took and how hard it worked.

## 5. What holds it back

When vacuum runs but the dead rows stay, look for the oldest open snapshots, replication slots and prepared transactions (see [Dead rows](topic:dead-rows) and [MVCC](topic:mvcc)):

```sql
SELECT pid, state, now() - xact_start AS open_for, age(backend_xmin) AS xmin_age,
       left(query, 60) AS query
FROM pg_stat_activity
WHERE backend_xmin IS NOT NULL
ORDER BY age(backend_xmin) DESC;

SELECT slot_name, active, xmin, catalog_xmin FROM pg_replication_slots;
SELECT gid, prepared, transaction FROM pg_prepared_xacts;
```

## 6. Wraparound

See [Transaction ID wraparound](topic:wraparound) for what the numbers mean and how close is too close.

Check how old the oldest unfrozen transaction ID is, per database and then per table, compared with `autovacuum_freeze_max_age` (200 million by default):

```sql
SELECT datname, age(datfrozenxid) AS xid_age FROM pg_database ORDER BY 2 DESC;

SELECT c.oid::regclass AS table_name, age(c.relfrozenxid) AS xid_age,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size
FROM pg_class c
WHERE c.relkind IN ('r', 'm', 't')
ORDER BY age(c.relfrozenxid) DESC
LIMIT 10;

SHOW autovacuum_freeze_max_age;
```

An autovacuum started to prevent wraparound runs even if autovacuum is otherwise off, and cannot be skipped. Tables near the limit that are very large take a long time to freeze, so you want to see them well before.

## Why it matters for performance

**What it costs.** The queries here read statistics views and are cheap. The log adds some lines. Not looking costs much more: bloated tables, slow scans and, in the worst case, a database that refuses writes.

**When it shows up.** After a change in workload, a bulk update or delete, a long transaction, or growth of a table past the point where the default 20% threshold is too lazy.

**When to worry** (rules of thumb, not documented limits):

- A dead-row share of 20% or more on a large table.
- `last_autovacuum` older than your normal interval while the dead rows grow.
- A vacuum that runs for hours.
- "Dead but not yet removable" counts that stay high after each run.
- A transaction age above about half of `autovacuum_freeze_max_age`.

**What you can change.**

- Lower `autovacuum_vacuum_scale_factor` on the busy big tables.
- Raise the cost limit if vacuum is throttled too hard, and the worker count if many tables wait.
- Fix the transactions, slots and prepared transactions that hold things back.
- Turn on `log_autovacuum_min_duration` and keep the log.

## Practical checklist

- Check dead rows and `last_autovacuum` per table, not only for the database.
- Compare each table to its autovacuum trigger point.
- When a vacuum runs but rows stay, read "not yet removable" and look for old snapshots.
- Log autovacuum runs, at least for the big tables.
- Watch the transaction age of databases and big tables.
- Set an alert on dead-row share and on the oldest transaction.
