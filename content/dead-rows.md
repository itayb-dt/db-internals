---
title: "Dead rows: the old versions that stay behind"
updated: 2026-10-20
sources:
  - https://www.postgresql.org/docs/17/routine-vacuuming.html
  - https://www.postgresql.org/docs/17/mvcc-intro.html
  - https://www.postgresql.org/docs/17/ddl-system-columns.html
  - https://www.postgresql.org/docs/17/storage-hot.html
  - https://www.postgresql.org/docs/17/monitoring-stats.html
  - https://www.postgresql.org/docs/17/view-pg-replication-slots.html
  - https://www.postgresql.org/docs/17/runtime-config-client.html
---

This article is about PostgreSQL. Other engines also leave old versions behind after changes, but they keep them elsewhere (undo or rollback space), so the table itself does not grow the same way. In PostgreSQL the old versions stay in the table. Read [MVCC](topic:mvcc) first if "row version" is new to you.

## What a dead row is

When you `UPDATE` or `DELETE` a row, PostgreSQL does not remove the old [version](topic:tuple). It marks it as deleted and, for an update, writes a new version next to it. The old version is **dead** once no transaction can still see it. It still sits in the page and takes space until [vacuum](topic:vacuum) recycles it. A rolled-back insert leaves a dead version too.

The documentation says why: the old version must not be deleted while another transaction may still see it. Eventually nobody does, and then the space must be reclaimed or the table would grow without limit.

## Real-world examples

- **A sessions table** updated on every request to set `last_seen`. Each request writes a new version of the same row, so the table holds many versions of every live session.
- **An orders table** where status changes five times in an order's life: `new`, `paid`, `packed`, `shipped`, `delivered`. Each change is a new version.
- **A job queue** where rows are inserted, updated to `done` and deleted. Almost every row ends up dead.
- **A big cleanup** such as `DELETE FROM events WHERE created_at < now() - interval '90 days'`. Millions of rows become dead at once.

## What it looks like

I created a table of 100,000 rows and updated every row three times, on a test server with autovacuum turned off so the effect is easy to see:

```sql
CREATE TABLE jobs (id int PRIMARY KEY, balance int, payload text) WITH (autovacuum_enabled = off);
INSERT INTO jobs SELECT g, 100, repeat('x', 50) FROM generate_series(1, 100000) g;

SELECT pg_size_pretty(pg_relation_size('jobs')) AS size;
UPDATE jobs SET balance = balance + 1;
UPDATE jobs SET balance = balance + 1;
UPDATE jobs SET balance = balance + 1;
SELECT pg_size_pretty(pg_relation_size('jobs')) AS size;
```

| Step | Table size | Dead rows |
|---|---|---|
| After loading 100,000 rows | 9 MB | 0 |
| After 3 updates of every row | 36 MB | about 300,000 |
| After a plain `VACUUM` | 36 MB | 0 |
| After one more update of every row | 36 MB | 100,000 |

The live data never grew, but the table is four times larger. A plain `VACUUM` does not shrink the file. It marks the dead space as reusable, so the next update filled it instead of growing the table. The documentation says the same: standard vacuum does not return space to the operating system, except when whole pages at the end of the table are free. `VACUUM FULL` rewrites the table and does shrink it, but it needs an ACCESS EXCLUSIVE lock and extra disk space during the rewrite.

## Why it matters for performance

**What it costs.**

- **Space.** The table and its indexes grow beyond the live data. This is called **bloat**.
- **Slower scans.** A sequential scan reads every page, dead rows included, so it reads more pages for the same answer. Index entries that point to dead rows make index scans do wasted work too.
- **Cache.** Dead rows share the buffer cache with live ones, so less useful data fits.
- **Vacuum work.** The bigger the pile, the longer each vacuum run takes and the more I/O it uses.

**Why they are not cleaned at once.** Vacuum can only remove a dead version when no open snapshot can still see it. A long transaction holds that line back for the whole database. The next section shows it.

## How to see dead rows

The statistics views count dead rows per table. The counters are updated with a short delay, and they are estimates.

```sql
SELECT relname, n_live_tup, n_dead_tup,
       round(100.0 * n_dead_tup / nullif(n_live_tup + n_dead_tup, 0), 1) AS dead_pct,
       last_autovacuum
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 20;
```

Read it like this: a high `dead_pct` with an old `last_autovacuum` means vacuum is not keeping up, or is being blocked. A table with many dead rows and a recent vacuum points to something holding the cleanup back.

## What holds cleanup back

Run `VACUUM (VERBOSE)` on a table while an old transaction is open. In my test, one session opened a Repeatable Read transaction, then another updated 50,000 rows and ran vacuum. This is the real output:

```
tuples: 0 removed, 100000 remain, 50000 are dead but not yet removable
```

After the first transaction ended, the same vacuum printed:

```
tuples: 50000 removed, 50000 remain, 0 are dead but not yet removable
```

To find what is holding things back, look at the oldest snapshots, replication slots and prepared transactions:

```sql
SELECT pid, state, now() - xact_start AS open_for, age(backend_xmin) AS xmin_age,
       left(query, 60) AS query
FROM pg_stat_activity
WHERE backend_xmin IS NOT NULL
ORDER BY age(backend_xmin) DESC;

SELECT slot_name, active, xmin, catalog_xmin FROM pg_replication_slots;
SELECT gid, prepared, transaction FROM pg_prepared_xacts;
```

A replication slot with an old `xmin` keeps vacuum from removing rows deleted after it, as does a forgotten prepared transaction. The `idle in transaction` state is the usual culprit in applications that open a transaction and then wait.

## Heap-only updates

An update is cheaper when it is a **heap-only tuple (HOT)** update. The documentation gives the conditions: no column used by an index changed, and the page holding the old row has room for the new one. Then no new index entries are needed, and the old version can be cleaned up quickly. In my test almost no updates were HOT, because the pages were full. To check, and to leave room on the page:

```sql
SELECT relname, n_tup_upd, n_tup_hot_upd,
       round(100.0 * n_tup_hot_upd / nullif(n_tup_upd, 0), 1) AS hot_pct
FROM pg_stat_user_tables
WHERE n_tup_upd > 0
ORDER BY n_tup_upd DESC
LIMIT 20;

ALTER TABLE jobs SET (fillfactor = 80);
```

A lower fillfactor leaves free space in each page for new versions. It only affects pages written afterwards, and makes the table somewhat larger.

## What you can change

- **Keep transactions short.** This is the biggest lever. End sessions that idle inside a transaction:

```sql
SET idle_in_transaction_session_timeout = '5min';
```

- **Make autovacuum act sooner on hot tables.**

```sql
ALTER TABLE jobs SET (autovacuum_vacuum_scale_factor = 0.02, autovacuum_vacuum_threshold = 1000);
```

- **Do not update values that did not change,** and avoid updating an indexed column when you can avoid it, so more updates qualify as HOT.
- **Retire old data by partition,** not by `DELETE`. Dropping a [partition](topic:partitioning) leaves no dead rows.
- **For a table you empty regularly,** `TRUNCATE` removes everything at once with no vacuum needed.
- **Check [the size](topic:table-size)** of the table against the size of its live data.

**When to worry** (rules of thumb, not documented limits): a dead-row share of about 20% or more on a large table, a table that keeps growing while the row count does not, a dead-row count that does not fall after vacuum, or a transaction open for hours.

## Practical checklist

- An `UPDATE` or `DELETE` leaves a dead row. Plan for it.
- Watch `n_dead_tup`, `dead_pct` and `last_autovacuum`.
- If vacuum runs but the count stays high, look for old transactions, slots and prepared transactions.
- Keep transactions short and set `idle_in_transaction_session_timeout`.
- Tune autovacuum per table for the busy ones.
- Delete old data with partitions or `TRUNCATE` when you can.
