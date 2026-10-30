---
title: "Monitoring table size: where the space goes"
updated: 2026-10-31
sources:
  - https://www.postgresql.org/docs/17/functions-admin.html
  - https://www.postgresql.org/docs/17/storage-toast.html
  - https://www.postgresql.org/docs/17/routine-vacuuming.html
---

This article continues from [Why a database suddenly grows](topic:database-growth-causes). It shows how to find where the space goes: which tables, and inside each table, the rows, the large values and the indexes. It is about **PostgreSQL 17**.

> **How this was checked:** The names and meanings of the size functions come from the PostgreSQL 17 documentation, listed in the sources. The page on these functions was long, so please confirm the exact wording of each function there. The two queries below were **not run**, because there is no server here. They only use the functions named in the documentation.

## What a table is made of

A table is more than its rows. Its space is split into parts:

| Part | What it holds |
|---|---|
| **The table itself** (heap) | The rows, including dead rows that vacuum has not yet reused |
| **Large values** ([TOAST](topic:toast)) | Big values moved out of the rows |
| **Small helper files** | The free space map and the visibility map, a few percent at most |
| **Indexes** | One structure per [index](topic:index), stored separately |

A quick look at the table can mislead. A table with large text or `jsonb` values looks small and holds most of its data in the large-values part. A table with many indexes can be mostly index.

## The functions that measure it

PostgreSQL has a small family of size functions. They differ in what they include:

| Function | What it counts |
|---|---|
| `pg_relation_size` | One part of one object. By default, the main file of the table. It does **not** include large values or indexes. |
| `pg_table_size` | The table, its large values and the helper files. **No** indexes. |
| `pg_indexes_size` | All indexes of the table |
| `pg_total_relation_size` | Everything: the table size plus the indexes |
| `pg_database_size` | A whole database |

The most common mistake is to use `pg_relation_size` and conclude that the table is small. For a table with large values it can be a fraction of the real size. Use `pg_total_relation_size` for the true cost.

The animation shows one table split into its parts, and which parts each size function counts.

<iframe src="table-size/demo.html" title="Animation: a table of 100 GB made of 40 GB of rows, 17 GB of large values, 3 GB of helper files and 40 GB of indexes. Four size functions each count a different part, and only the total counts all of it" width="800" height="450"></iframe>

*The animation repeats about every 28 seconds.*

## Look from the top down

**1. The database.** Check the size of each database. This tells you where to look, and whether the growth is in the data or somewhere else on the disk.

**2. The biggest tables.** List the tables by total size, split into the table, the large values and the indexes:

```sql
-- not run: needs a live server
SELECT relname,
       pg_size_pretty(pg_total_relation_size(oid)) AS total,
       pg_size_pretty(pg_relation_size(oid)) AS table_only,
       pg_size_pretty(pg_table_size(oid) - pg_relation_size(oid)) AS large_values_and_helpers,
       pg_size_pretty(pg_indexes_size(oid)) AS indexes
FROM pg_class
WHERE relkind = 'r' AND relnamespace = 'public'::regnamespace
ORDER BY pg_total_relation_size(oid) DESC
LIMIT 10;
```

How to read it:

- **`indexes` close to or above `table_only`:** there are many indexes, or large ones. Look for indexes that are not used.
- **`large_values_and_helpers` large:** the table holds big values, which is [TOAST](topic:toast) at work.
- **`table_only` large for the number of rows:** suspect dead rows, as the next step shows.

**3. Rows against size.** For the biggest tables, compare the number of live rows with the size. A table whose size per row keeps growing is wasting space.

```sql
-- not run: needs a live server
SELECT relname, n_live_tup, n_dead_tup,
       round(100.0 * n_dead_tup / nullif(n_live_tup + n_dead_tup, 0), 1) AS dead_pct,
       pg_size_pretty(pg_relation_size(relid)) AS table_only
FROM pg_stat_user_tables
ORDER BY pg_relation_size(relid) DESC
LIMIT 10;
```

A high share of dead rows means [dead rows](topic:dead-rows) are taking the space. The counts are estimates, so treat them as a guide.

**4. The exact number.** When you need to know exactly how much of a table is empty space, an extension for this purpose can scan the table and report it. It reads the whole table, so use it with care on a production system.

## Size over time

The database does not remember how big a table was last week. To see growth, **record the sizes regularly**, for example daily, and compare. A monitoring product keeps this history for you. With it you can answer the questions that matter:

- Which ten tables grew the most this week?
- Did the growth rate change, and on which day?
- Does the size grow in step with the row count?

Without history, a growing table is only noticed when the disk is already filling.

## Why it matters for performance

**What it costs.** Measuring is cheap: the size functions read file sizes, not data. Scanning a table for exact bloat is expensive.

**When it shows up.** Size problems show late. The signs are slower scans, longer backups and a disk that fills faster than expected.

**How to measure.** The two queries above, run regularly, and the results stored.

**When to worry.** As a rule of thumb, when indexes are larger than the table without a reason, when a table's size per row keeps rising, or when the dead rows are a large share of the table.

**What you can change.** Drop indexes that are not used, make vacuum keep up ([Vacuum configuration](topic:vacuum-configuration)), move expiring data to partitions, and avoid storing very large values in the table.

## Common mistakes

- Using `pg_relation_size` and missing large values and indexes.
- Looking at the database total, and not at the tables.
- Reading estimated row counts as exact.
- Having no history, so growth cannot be compared.
- Running an exact-bloat scan on a busy production table at peak hours.

## Checklist

- Know the total size of each database.
- List the top tables by `pg_total_relation_size`, split into table, large values and indexes.
- Compare size with rows and with dead rows.
- Record the sizes regularly and compare them.
- Use the exact scan sparingly.
