---
title: "Why a large database is a problem"
updated: 2026-10-31
sources:
  - https://www.postgresql.org/docs/17/routine-vacuuming.html
  - https://www.postgresql.org/docs/17/functions-admin.html
---

This article starts the problem track **Large database**. It explains what the problem is, then the impact and why you should care. Last it explains how to get the data that shows the problem. Later in the track you will see the potential root causes, and what more data is needed to tell whether each one is really the cause.

The track is about the **database**: its tables, indexes and the space they use. A server that is running out of disk is a different problem, about the instance, and is not covered here.

## What the problem is

A large database is not a problem by itself. Many healthy databases are very large because the business is large. The problem is **growth you did not expect**, and **space that holds nothing useful**. Both are cheap to prevent and expensive to find late.

## The impact: why you should care

Size costs you in three ways.

The animation shows how the copies add up, and what happens to them, and to the restore time, when the data doubles.

<iframe src="database-size-problem/demo.html" title="Animation: a database, a replica and seven daily backups make nine copies. When the data doubles every copy doubles, and the restore time doubles from about 4 to about 8 hours" width="800" height="450"></iframe>

*The animation repeats about every 24 seconds.*

### 1. It costs money

- **Disk.** Fast storage is the most expensive kind, and you pay for the size you reserved, not only what you use.
- **Copies.** Every replica holds the whole database. Every backup holds it too, often several times over, for as many days as you keep them.
- **Memory.** To keep queries fast you want the data that is used often to fit in memory. A larger database needs more memory for the same speed.

A database that doubles also doubles the copies. The bill grows faster than the data.

### 2. It makes routine work slow

- **Backup and restore.** Restoring a database takes about as long as copying it. A restore that takes ten hours is a ten-hour outage if you ever need it.
- **New replicas.** Building a replica, or rebuilding one after a failure, copies everything.
- **Upgrades and migrations.** Moving to a new major version or to a new provider takes longer the more there is to move.
- **Maintenance.** [Vacuum](topic:vacuum) has to look through the tables. Index builds take longer. Schema changes that rewrite a table need time and space.

The size that matters for each task is the part that task has to touch. This is one reason very large tables are split with [partitioning](topic:partitioning).

### 3. It slows queries

When the data that queries need no longer fits in memory, more reads go to disk, and queries slow down. Scans read more pages. Indexes get taller and larger. If a lot of the size is waste, such as [dead rows](topic:dead-rows), every scan reads that waste too.

This usually shows up as a slow decline, not a sudden break, which is why it is easy to miss.

## How to get the data

| What you look at | Where it comes from | What it tells you |
|---|---|---|
| Size of each database, and of each table, split into the table, large values and indexes | System functions such as `pg_database_size` and `pg_total_relation_size`. See [Monitoring table size](topic:table-size) | Where the space is |
| Free space on the volume | The operating system, or the cloud provider's monitoring | How much room is left |
| Growth per day and per week | The same numbers recorded over time. The database does not keep this history, so a monitoring product or a scheduled job has to | How fast it grows, and when the rate changed |
| Live rows against dead rows | System view `pg_stat_user_tables` | How much of the size is waste |

### Three questions to ask

Before you try to shrink anything, answer these:

1. **How big is it, and where?** Which databases, which tables, and how much of each is table, large values and indexes. See [Monitoring table size](topic:table-size).
2. **How fast is it growing?** Per day and per week, and when did the rate change.
3. **How much of it is useful?** Live rows against dead rows, used indexes against unused ones, current data against data nobody reads.

The first tells you where to look. The second tells you how much time you have. The third tells you whether to grow the disk or to clean up.

### What to watch

- **Size per database and per table over time,** so a sudden change is visible. The database does not keep this history, so something has to record it.
- **Growth per week,** and when the rate changed.
- **The share that is waste.** A table that grows while its number of rows does not is a warning.

## Common mistakes

- Looking at the total only, and missing that one table is most of it.
- Adding disk space as the first reaction, and paying for waste.
- Looking only when something has already gone wrong, with no history to compare with.
- Assuming that deleting rows makes the database smaller. It usually does not. See [Why a database suddenly grows](topic:database-growth-causes).

## Checklist

- Know the size of the database and of its biggest tables.
- Know the growth per week.
- Know how much of the size is dead space and unused indexes.
- Know how long a restore takes, and whether it fits your recovery target.
- Record the sizes regularly, so you can compare them.
