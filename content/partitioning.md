---
title: "Table partitioning: one logical table, many physical ones"
updated: 2026-10-19
sources:
  - https://www.postgresql.org/docs/17/ddl-partitioning.html
  - https://www.postgresql.org/docs/17/sql-createtable.html
  - https://www.postgresql.org/docs/17/sql-altertable.html
  - https://www.postgresql.org/docs/17/functions-admin.html
  - https://www.postgresql.org/docs/17/sql-analyze.html
  - https://www.postgresql.org/docs/17/routine-vacuuming.html
---

This article is about PostgreSQL declarative partitioning. MySQL, SQL Server and Oracle all offer partitioning too, with different syntax and some different limits. The idea is the same.

## What partitioning is

A partitioned table is **one logical table stored as several smaller physical tables**, called partitions. You choose a **partition key**, such as a date, and PostgreSQL decides which partition each row belongs to. Your queries still use the one logical name.

```sql
CREATE TABLE events (
    id         bigint GENERATED ALWAYS AS IDENTITY,
    created_at timestamptz NOT NULL,
    user_id    bigint,
    payload    text,
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

CREATE TABLE events_2026_01 PARTITION OF events FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE events_2026_02 PARTITION OF events FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE events_2026_03 PARTITION OF events FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

CREATE INDEX events_created_idx ON events (created_at);
```

There are three methods. **Range** splits by intervals (a month of dates). **List** splits by explicit values (a region or a tenant). **Hash** spreads rows evenly by a hash of the key.

## Real-world examples

- **Logs and events by month.** Billions of rows arrive over time and you keep only the last 13 months. Each month is a partition, and retention means dropping the oldest one.
- **Orders by month, with archiving.** Current orders are queried all day. Old months are queried rarely, and can be detached and moved to cheaper storage.
- **Multi-tenant data by list.** Each large customer, or each region, gets a partition. A query for one tenant touches one partition.
- **A very large table by hash.** There is no natural date, but one table is too big to vacuum and index comfortably. Hashing the key into 16 partitions gives you 16 smaller tables.

The documentation suggests partitioning is worthwhile when a table would otherwise be very large. As a rule of thumb, it points to tables larger than the server's memory.

## How PostgreSQL sees partitions

PostgreSQL does not see one large table. The partitioned table is a **virtual** parent with no storage of its own. Each partition is an **ordinary table** with its own files, its own indexes and its own statistics.

```sql
SELECT * FROM pg_partition_tree('events');
```

```
     relid      | parentrelid | isleaf | level
----------------+-------------+--------+-------
 events         |             | f      |     0
 events_2026_01 | events      | t      |     1
 events_2026_02 | events      | t      |     1
 events_2026_03 | events      | t      |     1
```

What follows from this:

- Rows you insert into `events` are routed to the right partition. Updating the partition key moves the row to another partition.
- An index declared on the parent is also virtual. PostgreSQL creates a matching index on every partition, including partitions you add later.
- The parent has no size of its own: `pg_total_relation_size('events')` returns 0 bytes. Size, vacuum and statistics belong to the partitions.
- Partitions are linked to the parent behind the scenes, and you can add or remove them without touching the others.

## Why dropping a partition beats deleting rows

Say you must remove January. In one big table, `DELETE FROM events WHERE created_at < '2026-02-01'` has to find every January row, even though they are mixed in among newer rows. For each row it then:

1. Marks the row version as dead. The row is not removed yet, and the space is not freed.
2. Writes a WAL record, so the delete is crash-safe and reaches replicas.
3. Leaves the table with [dead rows](topic:dead-rows) and index entries that `VACUUM` has to clean later.

A partition drop does none of this. January is its own table, so removing it removes the files:

```sql
BEGIN;
ALTER TABLE events DETACH PARTITION events_2026_01;
DROP TABLE events_2026_01;
COMMIT;
```

<iframe src="partitioning/demo.html" title="Animation: deleting January's rows from one big table visits every row and leaves dead rows, while dropping January's partition removes it at once" width="800" height="450"></iframe>

*The animation repeats about every 10 seconds.*

I measured it on a laptop with PostgreSQL 16.2: a table of 1.2 million rows, four months of 300,000 rows each, with one index on the date. Your numbers will differ, but the ratio shows the effect.

| | `DELETE` of one month | `DROP` of one partition |
|---|---|---|
| Time | about 0.9 s | about 10 ms |
| WAL written | 187 MB | 99 kB |
| Table size afterwards | 204 MB (unchanged) | 214 MB down to 161 MB |
| [Dead rows](topic:dead-rows) left | 300,000 | 0 |

The documentation says the same: dropping or detaching a partition is far faster than a bulk operation, and it avoids the `VACUUM` overhead of a bulk delete. Detaching first has an extra benefit: the data is still there as a standalone table, so you can back it up or aggregate it before dropping it. `DROP TABLE` and a plain `DETACH` take an ACCESS EXCLUSIVE lock on the parent. Use `DETACH PARTITION ... CONCURRENTLY` to reduce the lock level, with the restrictions described in the documentation.

```sql
-- not run
ALTER TABLE events DETACH PARTITION events_2026_01 CONCURRENTLY;
```

## Partition pruning

The planner can skip partitions that cannot contain matching rows. This is **partition pruning**, and it works when your query filters on the partition key.

```sql
EXPLAIN SELECT * FROM events WHERE created_at >= '2026-02-10' AND created_at < '2026-02-11';
```

The plan scans only `events_2026_02`. A query that does not filter on the key, such as `WHERE user_id = 7`, has to visit every partition. If you never filter on the partition key, partitioning will not speed up reads.

## Partitions and indexes: use both

A common question is whether partitioning replaces indexes. It does not, and the two do not compete. They do different jobs, and together they do more than either alone.

| | Index | Partition |
|---|---|---|
| What it does | Finds rows inside a table by value | Splits the table so whole chunks can be skipped or removed |
| How it cuts the work | Reads a few pages instead of the whole table | Reads only the partitions that can match |
| Retention | None: deleting rows still leaves dead rows | Drop or detach a partition |
| Maintenance | One big structure to vacuum and rebuild | Vacuum, analyze and rebuild one partition at a time |
| Cost | Slower writes, more disk | More tables to manage, the key in every unique constraint |

**They stack.** Take an `events` table partitioned by month, and ask for one user's events in February. Pruning removes every partition except February. An index on `(user_id, created_at)` inside that partition then finds the user's rows without scanning the month.

```sql
CREATE INDEX events_user_idx ON ONLY events (user_id, created_at);
CREATE INDEX CONCURRENTLY events_2026_02_user_idx ON events_2026_02 (user_id, created_at);
CREATE INDEX CONCURRENTLY events_2026_03_user_idx ON events_2026_03 (user_id, created_at);
ALTER INDEX events_user_idx ATTACH PARTITION events_2026_02_user_idx;
ALTER INDEX events_user_idx ATTACH PARTITION events_2026_03_user_idx;

EXPLAIN SELECT * FROM events
WHERE user_id = 42 AND created_at >= '2026-02-01' AND created_at < '2026-03-01';
```

The plan shows one index scan, on the February partition's index only. (The first three statements are the pattern from the documentation, explained below.)

**What each one brings**

- **Less data.** Pruning skips whole partitions, and each partition's index is a smaller, shallower tree than one index over the whole table. The documentation says partitioning effectively substitutes for the upper levels of an index, so the heavily used part of the index is more likely to stay in memory. When a query needs a large share of one partition, the planner can even choose a sequential scan of that partition instead of an index with scattered reads.
- **Fewer and shorter locks.**
  - **Retention:** dropping or detaching a partition replaces a long `DELETE`.
  - **Index builds:** `CREATE INDEX CONCURRENTLY` is not supported on a partitioned table directly. Create the parent index with `ON ONLY` (it starts invalid, and nothing is built), then build each partition's index concurrently, then attach them. Writes are blocked for much less time. The documentation describes exactly this pattern.
  - **Attaching a partition:** the table is scanned to check it fits, under an ACCESS EXCLUSIVE lock on that partition. Add a matching `CHECK` constraint first and the scan is skipped (documented, not run here).
- **Easier maintenance.** Vacuum, analyze and `REINDEX` work on one partition at a time, so each job is smaller and a bad index can be rebuilt on its own:

```sql
REINDEX INDEX CONCURRENTLY events_2026_02_user_idx;
```

**Where they do not help each other**

- A partition does not replace an index. If a query filters on `user_id` only, with no date, nothing is pruned, and PostgreSQL probes the index of every partition one after another. In my test the plan was an `Append` of one index scan per partition. The work grows with the number of partitions, where one big index would be probed once.
- Every partition has its own copy of each index. Ten indexes on fifty partitions are five hundred indexes to store, vacuum and watch.
- Unique indexes must include the partition key, so a lookup by `id` alone cannot be enforced as unique across partitions.

**Rule of thumb:** partition for the key you retire and prune by, usually time. Index for the columns you look rows up by. Use both on a big time-series table.

## Limits and costs

- **Unique and primary keys must include the partition key.** Each partition's index can only check uniqueness inside itself. That is why the example uses `PRIMARY KEY (id, created_at)`.
- **Partitions must exist before data arrives.** A row with no matching partition is an error, unless you define a default partition. Create next month's partition ahead of time, with a scheduled job or an extension such as `pg_partman` (a common tool, not part of PostgreSQL).
- **Statistics on the parent are manual.** Autovacuum processes partitions but not the partitioned table itself, so run `ANALYZE events` after loading data and when the distribution changes.
- **More objects to manage.** Hundreds of partitions mean hundreds of tables and indexes, and more planning work.

## Why it matters for performance

**What it costs.** More tables to manage, more planning work, and queries that skip the partition key become slower or stay the same. Cross-partition unique constraints are limited.

**What it gives.** Fast retention (drop instead of delete), pruned scans, smaller tables and indexes to vacuum and cache, and the option to keep recent partitions on fast storage. The documentation notes that partitioning can replace the upper levels of an index, so the hot partition's index is more likely to fit in memory.

**How to measure.** Check pruning with `EXPLAIN`. Compare per-partition size and activity. See [Partition metrics](topic:partition-metrics) for the queries.

**When to worry.** Plans that scan all partitions for a key-filtered query, partitions that never get vacuumed, a growing default partition, or retention jobs that still run big `DELETE`s.

## Practical checklist

- Partition by the column your queries and retention both use, usually time.
- Keep the key in every unique constraint.
- Create future partitions before they are needed.
- Retire data with `DETACH` and `DROP`, not `DELETE`.
- Run `ANALYZE` on the parent table yourself.
- Confirm pruning in `EXPLAIN` before and after.
- Build on [heap tables](topic:heap) and [indexes](topic:index): each partition is one of each.
