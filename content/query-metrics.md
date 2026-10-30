---
title: "Query metrics: the numbers that describe a query"
updated: 2026-10-31
sources:
  - https://www.postgresql.org/docs/17/pgstatstatements.html
  - https://www.postgresql.org/docs/17/monitoring-stats.html
  - https://www.postgresql.org/docs/17/runtime-config-logging.html
  - https://www.postgresql.org/docs/17/runtime-config-statistics.html
  - https://docs.dynatrace.com/docs/observe/infrastructure-observability/databases
---

This article continues from [Common root causes of slow queries](topic:slow-query-causes). It covers the main numbers that describe a query, and how to read them to find the one that costs the most. It uses **PostgreSQL 17**. Other databases keep similar numbers under other names.

> **How this was checked:** The column names and settings come from the PostgreSQL 17 documentation. The SQL below was **not run**, because it needs a live server with the `pg_stat_statements` extension. Each block is marked. Thresholds are rules of thumb.

## Two questions: how long, and how often

A query costs the database its **time per run** multiplied by **how many runs**. A 3-second report that runs once a day costs less than a 2 ms lookup that runs 50 times per second. Both numbers are needed.

## The main metrics

| Metric | What it tells you | Where it comes from in PostgreSQL |
|---|---|---|
| **Calls** | How often the statement ran | `calls` in `pg_stat_statements` |
| **Total time** | The overall cost: calls times mean | `total_exec_time` |
| **Mean time** | A typical run | `mean_exec_time` |
| **Spread** | Whether runs differ a lot: the fastest, the slowest and the standard deviation | `min_exec_time`, `max_exec_time`, `stddev_exec_time` |
| **Rows** | Rows returned or changed. Divide by calls for rows per call | `rows` |
| **Cache hits and reads** | How much came from memory and how much from disk | `shared_blks_hit`, `shared_blks_read` |
| **Temporary blocks** | Whether sorts or hashes spilled to disk | `temp_blks_read`, `temp_blks_written` |
| **I/O time** | Time spent waiting for the disk (only if `track_io_timing` is on) | `shared_blk_read_time` |
| **Waits** | What a running statement is waiting for right now | `wait_event_type`, `wait_event` in `pg_stat_activity` |

The statistics view is the extension `pg_stat_statements`. It needs to be loaded at server start and created in the database. It groups statements by their shape, with constants replaced by parameters, so `WHERE id = 7` and `WHERE id = 9` count as one statement. Waits are different: they are a live snapshot, so you sample them several times.

The animation ranks four statements first by total time and then by mean time, and then checks the cache hit ratio and temporary files.

<iframe src="query-metrics/demo.html" title="Animation: four statements ranked by total time, where a cheap lookup run 90,000 times is first, and then by mean time, where a slow report run 20 times is first. Then cache hits and temporary files are checked" width="800" height="450"></iframe>

*The animation repeats about every 28 seconds.*

## How to analyse them

**1. Rank by total time.** This finds the biggest cost overall.

```sql
-- not run: needs the pg_stat_statements extension
SELECT calls, round(total_exec_time) AS total_ms, round(mean_exec_time::numeric, 2) AS mean_ms,
       rows, left(query, 60) AS query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
```

The top row is often not the slowest query. It is the one that adds up the most, frequently a cheap query called a huge number of times.

**2. Rank by mean time, with a minimum number of calls.** This finds the slowest single runs, and the minimum hides noise from statements that ran once.

```sql
-- not run: needs the pg_stat_statements extension
SELECT calls, round(mean_exec_time::numeric, 2) AS mean_ms, round(max_exec_time::numeric, 2) AS max_ms,
       left(query, 60) AS query
FROM pg_stat_statements
WHERE calls >= 10
ORDER BY mean_exec_time DESC
LIMIT 10;
```

**3. Look at rows per call.** A query that should return a handful of rows but returns thousands may be missing a filter. A query that returns few rows but reads huge numbers of blocks is scanning too much. See [the plan](topic:execution-plan).

**4. Check the cache.** The hit ratio is hits divided by hits plus reads for the statement. A low ratio means the data comes from disk.

```sql
-- not run: needs the pg_stat_statements extension
SELECT left(query, 60) AS query, shared_blks_hit, shared_blks_read,
       round(100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0), 1) AS hit_pct
FROM pg_stat_statements
ORDER BY shared_blks_read DESC
LIMIT 10;
```

As a rule of thumb, a transactional workload usually sits well above 90%, and a drop from its normal level is the signal. A reporting query that scans a big table will legitimately read from disk.

**5. Look for temporary files.** Non-zero `temp_blks_written` on a statement that runs often means its sorts or hashes do not fit in memory.

**6. Look at the spread.** A standard deviation large compared with the mean means the statement is sometimes fast and sometimes slow. Suspect the parameters, a lock, or load at certain hours. See [the causes](topic:slow-query-causes).

**7. Sample the waits.** For a statement that is slow while the CPU is quiet, sample what the active sessions wait for. The most common wait names the cause: a lock, a disk read, a connection.

```sql
-- not run: depends on live activity, run it several times
SELECT wait_event_type, wait_event, count(*)
FROM pg_stat_activity
WHERE state = 'active' AND backend_type = 'client backend'
GROUP BY wait_event_type, wait_event
ORDER BY count(*) DESC;
```

A session that is `active` with no wait event is working, using CPU.

## Compare two samples, not one

The counters only grow. They count from the server start, or from the last reset. One reading mixes today with last month. To see a trend, take a sample, wait, take another, and subtract. The view also records when its statistics started, so you know what period they cover.

## What `pg_stat_statements` cannot show

- **Single executions.** It keeps totals, so a rare 30-second run is hidden inside the mean. It keeps the slowest run time, but not when it happened or with which values.
- **Plans.** It tells you which statement is expensive, not why. For the plan, use `EXPLAIN`.
- **Percentiles.** It keeps the mean, the minimum, the maximum and the standard deviation, not the 95th percentile.
- **Old data.** By default it keeps up to 5,000 distinct statements. Rarely used ones are dropped, and a reset clears everything.

To catch individual slow executions, the server can log every statement slower than a threshold. See [The slow query log](topic:slow-query-log).

## Built-in monitoring

You can do all of this by hand, and it is worth knowing how. Monitoring products collect it for you and keep history. The Dynatrace Databases app, for example, collects statements and their execution plans out of the box, lets you filter resource-intensive statements by time, CPU, disk or waits, and shows blocking queries and deadlocks. See [the Dynatrace Databases app](topic:dt-databases-app).

## Why it matters for performance

**What it costs.** The statistics view uses shared memory, whether or not anyone reads it, and adds some work to each statement. Planning statistics (`track_planning`) add more. Measure the effect on your own system. Temporary files and disk reads are costs that the metrics expose, not costs of collecting them.

**When it shows up.** The metrics matter most in a busy system, where the slowest query is not the most expensive one.

**How to measure.** The queries above, run twice with a pause between them.

**When to worry.** A statement with a large share of the total time, a hit ratio far below normal, temporary files on a frequent query, or a spread that is many times the mean.

**What you can change.** Raise the limit of tracked statements if useful ones are dropped, turn on I/O timing to see disk time, keep the history outside the database, and fix the statements the numbers point to.

## Common mistakes

- Sorting only by mean time, and missing the cheap query that runs constantly.
- Reading one sample of counters that cover a month.
- Trusting a hit ratio for a query that is supposed to scan.
- Looking at the query text and ignoring its calls.
- Forgetting that the view does not keep plans or single executions.

## Checklist

- Rank by total time first, then by mean time with a minimum of calls.
- Check rows per call and the cache hit ratio.
- Look for temporary files and a large spread.
- Sample the waits when the CPU is quiet.
- Compare two samples, and know when the counters were last reset.
- Take the chosen statement to its [execution plan](topic:execution-plan).
