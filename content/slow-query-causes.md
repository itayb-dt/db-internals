---
title: "Common root causes of slow queries"
updated: 2026-10-31
sources:
  - https://www.postgresql.org/docs/17/using-explain.html
  - https://www.postgresql.org/docs/17/indexes-intro.html
  - https://www.postgresql.org/docs/17/planner-stats.html
  - https://www.postgresql.org/docs/17/routine-vacuuming.html
  - https://www.postgresql.org/docs/17/explicit-locking.html
  - https://www.postgresql.org/docs/17/runtime-config-resource.html
  - https://www.postgresql.org/docs/17/sql-prepare.html
---

This article continues from [Query metrics](topic:query-metrics), which found the query that costs the most. It answers one question: why does a query become slow? Knowing the usual reasons turns a long list of suspects into a short one. The details of each fix are in the topics it links to. The examples use **PostgreSQL 17**, but these causes are the same in most relational databases.

> **How this was checked:** The article has no SQL. The causes and the way to confirm them come from the PostgreSQL 17 documentation listed in the sources, and from common practice. Thresholds are rules of thumb.

## The four reasons

A query does three things: it finds rows, it combines them, and it returns them. It can be slow for one of four reasons:

1. **It reads too much.** The database looks at far more data than the answer needs.
2. **It chose a poor path.** A better way existed, but the planner did not pick it.
3. **It waits.** The work is small, but it has to wait for a lock, the disk, the CPU or a free connection.
4. **It runs too often or too late.** Each run is fine, but there are too many, or they collide with something heavy.

Almost every slow query is one of these. The sections below split each into its usual forms.

The animation shows the four reasons one at a time: too many pages read, a wrong estimate, a wait, and too many calls.

<iframe src="slow-query-causes/demo.html" title="Animation: the four usual reasons a query is slow. It reads far more pages than it needs, it plans for 10 rows and gets 500,000, it waits for a lock, or it is called 400 times" width="800" height="450"></iframe>

*The animation repeats about every 30 seconds.*

## 1. It reads too much

**No usable index.** The table is scanned from start to finish to find a few rows. On 100 million rows this is the textbook case. It shows in the plan as a sequential scan with most rows thrown away. See [Index](topic:index).

**An index exists, but is not used.** Some common reasons: the query applies a function to the column, so the index on the plain column no longer matches; the types differ, for example text compared with a number; the query asks for a large share of the table, where a scan really is cheaper; or the index is on `(a, b)` and the query filters only on `b`.

**Too many rows come back.** `SELECT *` on wide rows, no `LIMIT`, or a result of a million rows that the application then filters. The database does the work honestly, and the cost is in moving the rows.

**The table is bigger than its data.** Many [dead rows](topic:dead-rows) or bloat make a scan read more pages than the live data needs, and an index to point to rows that are gone. Vacuum has to keep up.

**The table is simply huge.** Even good access paths read a lot when each query touches one giant table. Splitting by time or tenant with [partitioning](topic:partitioning) lets a query skip most of it.

## 2. It chose a poor path

The planner picks a plan from estimates. When the estimates are wrong, the plan can be wrong.

**Stale or missing statistics.** After a big load or delete the planner still believes the old row counts. It picks a nested loop for a million rows, or a scan where an index would win. See [Statistics](topic:statistics).

**Columns that move together.** The planner multiplies selectivities as if the columns were independent. For a city and a postal code, which depend on each other, it underestimates the rows, and the plan is wrong. Extended statistics address this.

**Values that behave differently.** A plan that is right for a rare value is wrong for a common one. Prepared statements can reuse a plan that suits some parameter values and not others. The query is fast for one customer and slow for another.

**Hard-to-estimate expressions.** Complex conditions, functions and large joins give the planner little to work with.

How to confirm: compare the estimated rows with the actual rows in the [actual execution plan](topic:actual-plan). A large gap, such as an estimate of 10 and an actual of 500,000, is the signature.

## 3. It waits

The query does little, but it spends its time waiting.

**Lock waits.** Another session holds a lock the query needs. It can be a long transaction left open, a schema change, or a [deadlock](topic:deadlock). The query looks slow but uses no CPU. In `pg_stat_activity` it shows a wait on a lock.

**Disk reads.** The data is not in memory, so each page comes from disk. This happens after a restart, when the working set is larger than the [buffer pool](topic:buffer), or when a big scan pushes useful pages out. A low cache hit ratio suggests it.

**Spilling to disk.** A sort or hash that does not fit in the memory allowed for it (`work_mem`) writes temporary files. Temporary file counters grow, and the query becomes much slower.

**CPU saturation.** The host is busy with other work. The query is not slow by itself, everything is.

**No free connection.** Requests queue because the connection limit is reached. The time is spent before the query even starts. See [load balancers and connection pooling](topic:load-balancer).

## 4. It runs too often or at the wrong time

**Too many cheap runs.** A page that runs one query per row (the "N plus one" pattern) turns a 2 ms query into a second of work. Look at the number of calls, not only at the time per call. See [Query metrics](topic:query-metrics).

**Collisions.** A report that is fine on its own runs at the same time as a backup, a vacuum, a bulk load or a batch job. It is slow only at certain hours.

**Growth.** The query was fast at a million rows and is slow at a hundred million. Nothing changed except the size.

**A change.** A deployment, a new version, a changed setting, a dropped index or a new query shape. The question "what changed?" belongs at the start of every analysis.

## From symptom to likely cause

| What you see | Likely cause | How to confirm |
|---|---|---|
| Fast on a small table, slow on the real one | Missing index, or table too large | Plan shows a sequential scan with many rows removed |
| Slow only for some values or customers | Plan depends on the value | Compare plans for a fast and a slow value |
| Estimates far from actual rows | Stale or weak statistics | Actual plan, and when statistics were last updated |
| Little CPU used, long duration | Waiting for a lock, disk or connection | Wait events in `pg_stat_activity` |
| Slow after a restart, then better | Cold cache | Cache hit ratio over time |
| Many temporary files | Sort or hash spills to disk | Temporary file counters |
| Total time high, time per call low | Too many calls | Call counts in the query metrics |
| Gets worse as the table grows, vacuum behind | Dead rows and bloat | Dead row counts and last vacuum time |

## Why it matters for performance

**What it costs.** Wrong guesses cost time, and wrong fixes cost twice: an unused index slows every write, and a larger memory setting for one query can exhaust memory under many sessions.

**When it shows up.** At full data size, at peak load, and after changes. Many causes are invisible on a development database.

**How to measure.** Rank queries by total and mean time ([Query metrics](topic:query-metrics)), read the plan ([execution plan](topic:execution-plan)), then compare estimated and actual rows. Use wait events for the "waiting" group.

**When to worry.** A rule of thumb: an estimate that is off by 10 times or more, a cache hit ratio that drops well below its normal level, or temporary files on a query that runs often.

**What you can change.** Add or fix an index, rewrite the query, refresh statistics, tune vacuum, change memory settings for the sessions that need them, reduce the number of calls, or split a huge table. Each has a downside, so match the fix to the confirmed cause.

## Common mistakes

- Adding an index before checking what the plan shows.
- Assuming the database is the problem when the query is run thousands of times by the application.
- Raising `work_mem` for the whole server to fix one query.
- Ignoring waits, and tuning a query that is only blocked.
- Fixing the plan but leaving the dead rows that made the scan slow.

## Checklist

- Group the cause: reads too much, poor plan, waits, or too often.
- Check calls and total time before you judge a single run.
- Compare estimated and actual rows.
- Look at wait events when the CPU is quiet and the query is slow.
- Ask what changed, and whether the data grew.
- Fix the confirmed cause, then measure again.
