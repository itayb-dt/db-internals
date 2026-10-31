---
title: "Analyzing slow queries: a method"
updated: 2026-10-31
sources:
  - https://www.postgresql.org/docs/17/monitoring-stats.html
  - https://www.postgresql.org/docs/17/pgstatstatements.html
  - https://www.postgresql.org/docs/17/using-explain.html
  - https://www.postgresql.org/docs/17/runtime-config-logging.html
---

This article starts the problem track **Slow query**. It describes a method, not a tool, so it applies to any relational database.

## Start with the complaint

"The database is slow" is where most investigations start, and it says very little. Before looking at any tool, ask a few questions:

- **Slow for whom?** One user, one report, one batch job, or everyone?
- **Since when?** A slow query that was always slow is a design problem. One that got slow last Tuesday is a change problem.
- **What changed?** A deployment, a new index, a setting, a bigger customer, or just more data.
- **Always, or sometimes?** A query that is slow only at peak hours points to contention. One that is slow only for some inputs points to the plan.
- **Slow in the database, or slow in the application?** The database may answer in 20 ms while the application waits 2 seconds for the rows to arrive, or runs the query a hundred times.

These questions often remove half of the possible causes before you open a single view.

## Two kinds of slow

It helps to separate two shapes of the problem:

| Shape | What you see | Where the time goes |
|---|---|---|
| **One run takes long** | A single statement of 8 seconds | Inside that statement: reading, joining, sorting, waiting |
| **Too many cheap runs** | A statement of 2 ms, run 400 times per page view | In the sum: calls multiplied by a small time |

The first is fixed by changing the query, the plan or the data layout. The second is fixed by changing the caller, for example by fetching in one query instead of one per row. A tool that sorts only by the slowest run will miss the second kind completely.

## The loop

Every successful analysis follows the same steps:

1. **Find** the query that costs the most. Use measurements, not a hunch. See [Query metrics](topic:query-metrics).
2. **Understand** how the database ran it, using its [execution plan](topic:execution-plan) and the [actual plan](topic:actual-plan).
3. **Name the cause.** Match what you saw to one of the [common root causes](topic:slow-query-causes).
4. **Fix** it. Often this is an [index](topic:index), a rewritten query, fresh statistics, or splitting a huge table with [partitioning](topic:partitioning).
5. **Measure again** with the same numbers you started with. A fix you did not measure is a guess.

Then go back to step 1. The next query on the list is now the biggest one.

The animation follows one query through the five steps, and then starts again with the next one.

<iframe src="analyzing-slow-queries/demo.html" title="Animation: a query moves through five steps, find, understand, name the cause, fix and measure, and then the loop starts again with the next query" width="800" height="450"></iframe>

*The animation repeats about every 28 seconds.*

## Why the order matters

Skipping a step is how time is lost:

- Jumping to a fix without a cause ("let's add an index") produces indexes that are never used, and they slow every write.
- Looking at the plan of the wrong query is wasted work. Find the biggest cost first.
- Fixing without measuring leaves you unsure that anything improved, or that something else did not get worse.

## What looking costs

Investigating is not free, and it can make a slow system slower:

- Collecting statement statistics uses some CPU and memory. It is usually small, but measure it on your own system.
- `EXPLAIN ANALYZE` **runs the statement**. On a slow, write-heavy query on production, think before you run it, or run it inside a transaction you roll back.
- Logging every statement fills disks. Log only statements slower than a threshold.

Rule of thumb: collect continuously what is cheap (counters and statistics), and run the expensive checks only on the one query you chose.

## Built-in monitoring

Collecting the numbers by hand is possible, and the track shows how. Database monitoring products also collect statements and their plans out of the box. The Dynatrace Databases app, for example, does this and lets you filter statements by time, CPU, disk or waits. See [the Dynatrace Databases app](topic:dt-databases-app).

## Common mistakes

- Starting with the tool instead of the question.
- Optimising the slowest single query when a cheap query that runs constantly costs more.
- Fixing several things at once, so you cannot tell which one helped.
- Testing a fix on a small copy of the data. Many problems only show at full size.
- Stopping after one fix, while the next query in line costs almost as much.

## Checklist

- Write down who, since when, what changed, and always or sometimes.
- Decide whether it is one slow run or too many cheap ones.
- Find the biggest cost with numbers.
- Read the plan before you change anything.
- Name the cause, then fix it.
- Measure with the same numbers, and look at the next query.
