---
title: "Vacuum: how PostgreSQL cleans up after itself"
updated: 2026-10-20
sources:
  - https://www.postgresql.org/docs/17/routine-vacuuming.html
  - https://www.postgresql.org/docs/17/sql-vacuum.html
  - https://www.postgresql.org/docs/17/runtime-config-autovacuum.html
  - https://www.postgresql.org/docs/17/runtime-config-resource.html
  - https://www.postgresql.org/docs/17/storage-vm.html
---

This article is about **PostgreSQL 17**. Every engine has to clean up old row versions. MySQL/InnoDB and Oracle purge old versions from their undo space, and SQL Server cleans up in the background too. PostgreSQL keeps old versions in the table itself, so cleaning up is a separate job with a name: vacuum. How to watch it is in [Monitoring vacuum](topic:vacuum-monitoring).

> **How this was checked:** The SQL in this article was run on PostgreSQL 16.2. The output shown comes from those runs.

## What vacuum does

An `UPDATE` or `DELETE` leaves the old version of a row behind (see [MVCC](topic:mvcc) and [dead rows](topic:dead-rows)). Vacuum does four jobs, which the documentation lists as the reasons for routine vacuuming:

1. **Recover or reuse space.** It removes dead row versions from the table and its indexes and marks the space as free for new rows.
2. **Update planner statistics.** With the `ANALYZE` option, or when autovacuum also runs an analyze, the [statistics](topic:statistics) are refreshed.
3. **Update the [visibility map](topic:visibility-map).** For each page it records whether all rows are visible to everyone. Vacuum skips those pages next time, and index-only scans can answer without visiting the table.
4. **Prevent transaction ID wraparound.** It marks very old rows as frozen, so they stay visible forever. More on this below.

## The manual variants

```sql
CREATE TABLE jobs (id int PRIMARY KEY, state text) WITH (autovacuum_enabled = off);
INSERT INTO jobs SELECT g, 'new' FROM generate_series(1, 100000) g;
UPDATE jobs SET state = 'done';

VACUUM (VERBOSE) jobs;
```

The `VERBOSE` output of a similar run on my test server, shortened:

```
pages: 0 removed, 492 remain, 492 scanned (100.00% of total)
tuples: 50000 removed, 50000 remain, 0 are dead but not yet removable
index scan needed: 222 pages from table (45.12% of total) had 50000 dead item identifiers removed
```

Read it like this: 50,000 dead versions were removed, and none were "not yet removable". If that last number is above zero, something is [holding the cleanup back](topic:dead-rows).

| Command | What it does | Lock | Gives space back to the OS? |
|---|---|---|---|
| `VACUUM` | Removes dead rows, marks space reusable, updates the visibility map | No exclusive lock, runs alongside reads and writes | Usually not, only free pages at the very end of the table |
| `VACUUM (ANALYZE)` | The same, then refreshes statistics | Same | Same |
| `VACUUM (FREEZE)` | Aggressive freezing of old rows | Same | Same |
| `VACUUM (FULL)` | Writes a new copy of the table with no dead space | ACCESS EXCLUSIVE, blocks everything on the table | Yes |

```sql
VACUUM (ANALYZE) jobs;
VACUUM (FULL) jobs;
```

A plain vacuum does not make the file smaller, as the [Dead rows](topic:dead-rows) example showed: the space is reused by later rows. `VACUUM FULL` shrinks it, but it takes an exclusive lock, needs extra disk space for the copy, and runs much longer. The documentation's advice is to vacuum often enough that you rarely need it.

## Autovacuum: vacuum on its own

You do not run vacuum by hand. The **autovacuum** daemon wakes up regularly (every minute by default, `autovacuum_naptime`), checks each table and starts a vacuum where enough has changed. Up to three workers run at once by default (`autovacuum_max_workers`).

A table is vacuumed when its dead rows exceed:

```
autovacuum_vacuum_threshold + autovacuum_vacuum_scale_factor × number of rows
```

The defaults are 50 and 0.2. So by default a table gets vacuumed after **20% of it** is dead, plus 50 rows. Analyze uses the same idea with 50 and 0.1. There is also an insert-based trigger (1,000 rows and 20% by default), so that tables that are only appended to still get their visibility map and old rows frozen.

This is fine for a small table and a problem for a big one:

| Table rows | Dead rows needed to trigger vacuum (defaults) |
|---|---|
| 10,000 | 2,050 |
| 1,000,000 | 200,050 |
| 100,000,000 | 20,000,050 |

On a 100-million-row table, twenty million dead rows pile up before autovacuum even starts. For big, busy tables, lower the factor on that table:

```sql
ALTER TABLE jobs SET (autovacuum_vacuum_scale_factor = 0.02, autovacuum_vacuum_threshold = 1000);

SELECT relname, reloptions FROM pg_class WHERE reloptions IS NOT NULL;
```

## Why vacuum can be slow on purpose

Vacuum is throttled so it does not starve your queries. It does a limited amount of I/O work, then sleeps. For autovacuum the pause is `autovacuum_vacuum_cost_delay` (2 ms by default). The work budget is `autovacuum_vacuum_cost_limit`, which by default follows `vacuum_cost_limit` (200), and that budget is **shared** between the running workers. The effect is that a big table can take hours, and adding workers does not make each one faster. On fast storage, a higher cost limit is the usual fix.

## Freezing and wraparound

This section is the short version. The full story is in [Transaction ID wraparound](topic:wraparound).

Transaction IDs are 32-bit numbers and are compared in a circle, so a row version can only be "in the past" for about two billion transactions. To keep very old rows visible, vacuum **freezes** them. This is the fourth job.

The documentation describes the safeguard. Autovacuum is started on any table that might hold unfrozen rows older than `autovacuum_freeze_max_age` (200 million by default), **even if autovacuum is disabled**. If that is ignored, the server first warns and, with fewer than three million transactions left, refuses to assign new transaction IDs. Ordinary tables are frozen along the way, but a table that is only ever appended to relies on this. Check the age with:

```sql
SELECT datname, age(datfrozenxid) AS xid_age FROM pg_database ORDER BY 2 DESC;
SHOW autovacuum_freeze_max_age;
```

## Why it matters for performance

**What it costs.** I/O to read the table and indexes, CPU, and WAL: vacuum writes WAL records for what it changes, and the `VERBOSE` output reports it. Throttling keeps the load small, at the price of speed.

**What happens without it.** Dead rows pile up, tables and indexes bloat, scans read more pages, index-only scans stop working because the visibility map is out of date, and in the worst case the database hits wraparound protection.

**When it falls behind.**

- **Held back:** a long transaction, an old replication slot or a prepared transaction keeps the dead rows alive (see [Dead rows](topic:dead-rows)).
- **Too lazy for big tables:** the 20% threshold above.
- **Too slow:** the shared cost limit on a very large table, or too few workers for many busy tables.

**How to measure.** See [Monitoring vacuum](topic:vacuum-monitoring) for the queries.

**When to worry** (rules of thumb, not documented limits): a table whose `last_autovacuum` is old while its dead rows keep growing, vacuum runs that take hours, or a transaction age moving toward `autovacuum_freeze_max_age`.

**What you can change.**

- Lower the scale factor and threshold on the biggest, busiest tables.
- Raise `autovacuum_vacuum_cost_limit` if vacuum is throttled too hard, and `autovacuum_max_workers` (needs a restart) if many tables wait.
- Keep transactions short so vacuum can remove what it finds.
- Use `VACUUM FULL` only as a last resort, outside busy hours, because of the exclusive lock. The documentation also names `CLUSTER` and table-rewriting `ALTER TABLE` variants. Extensions such as `pg_repack` rewrite a table with less locking (a commonly used tool, not part of PostgreSQL).
- For tables you empty periodically, `TRUNCATE` or dropping a [partition](topic:partitioning) needs no vacuum at all.

## Practical checklist

- Leave autovacuum on. Do not disable it to "save load".
- Know the 20% rule, and lower it for big tables.
- A plain `VACUUM` frees space for reuse, not for the operating system.
- Look at "dead but not yet removable" when dead rows will not go away.
- Watch the transaction age of your databases.
- Read [Monitoring vacuum](topic:vacuum-monitoring) to see all of it.
