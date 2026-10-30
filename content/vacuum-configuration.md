---
title: "Vacuum configuration: making autovacuum keep up"
updated: 2026-10-31
sources:
  - https://www.postgresql.org/docs/17/runtime-config-autovacuum.html
  - https://www.postgresql.org/docs/17/routine-vacuuming.html
---

This article continues from [Vacuum](topic:vacuum). It covers the settings that decide when autovacuum starts, how many workers run, how fast they go, and when a table needs settings of its own. It is about **PostgreSQL 17**.

> **How this was checked:** The settings and their defaults come from the PostgreSQL 17 documentation, listed in the sources. The article has no SQL. Suggested values are rules of thumb that depend on your workload.

## Why configure it

Autovacuum works well with its defaults on small and medium tables. On a large table with many updates and deletes, the defaults can let dead rows pile up for a long time, and then vacuum has a lot to do. The result is a growing table, as the [previous articles](topic:database-growth-causes) explained.

The settings answer four questions: **when** does vacuum start, **how many** run at once, **how fast** do they go, and **which tables** need different rules.

The animation shows when autovacuum starts on a small table and on a table of 100 million rows, what a lower scale factor changes, and how workers share the speed budget.

<iframe src="vacuum-configuration/demo.html" title="Animation: autovacuum starts after 250 dead rows on a table of 1,000 rows and after about 20 million on a table of 100 million rows. A scale factor of 0.02 starts it after about 2 million. Three workers share one speed budget" width="800" height="450"></iframe>

*The animation repeats about every 30 seconds.*

## When does vacuum start?

Autovacuum starts on a table when the dead rows pass a trigger:

**trigger = threshold + scale factor × number of rows**

The defaults are a threshold of 50 rows and a scale factor of 0.2, which is 20% of the table.

For a table of 1,000 rows, that is 250 dead rows, which is quick. For a table of **100 million rows**, it is about **20 million dead rows** before vacuum even starts. By then the table has grown by a fifth, and the vacuum that follows has a lot of work. A percentage that suits small tables is far too lax for big ones.

There is a similar trigger for **inserts**, with a threshold of 1,000 rows and a scale factor of 0.2 by default. It makes vacuum run on tables that only receive new rows, which keeps their visibility information current and prepares old rows for freezing. See [Visibility map](topic:visibility-map).

Autovacuum also refreshes the planner's [statistics](topic:statistics) with its own trigger, a threshold of 50 and a scale factor of 0.1.

## How often does it look?

A launcher wakes up regularly and checks the tables. The default delay between runs on a database is **one minute** (`autovacuum_naptime`). This rarely needs changing.

## How many run at once?

`autovacuum_max_workers` sets how many workers can run at the same time. The default is **3**, and changing it needs a restart.

More workers help when you have **many tables** that need vacuuming at once. They do not help when you have one huge table, because only one worker vacuums a table at a time.

## How fast do they go?

Vacuum is slowed on purpose, so it does not take the disk away from your queries. It does a limited amount of work, then sleeps. Two settings control it:

- **`autovacuum_vacuum_cost_delay`**: how long a worker sleeps. The default is 2 milliseconds.
- **`autovacuum_vacuum_cost_limit`**: how much work it does before sleeping. The default is -1, which means it uses the general `vacuum_cost_limit`.

The budget is **shared by all running workers**. Starting more workers divides the same budget, so each one goes slower. If vacuum cannot keep up and the disk has spare capacity, the usual fix is to raise the cost limit, not to add workers.

## Which tables need their own rules?

Most of the settings above can be set **for one table** with storage parameters. A value set on a table is used for that table, and the global value is used for the others.

This is the main tool for big, busy tables. A table with a hundred million rows and constant updates can get a much smaller scale factor, so vacuum starts after a small share of the table has died. Common starting points are scale factors of a couple of percent or less for such tables. Treat those as rules of thumb, and adjust by watching the results.

You can also set a table to be vacuumed more often, with a lower threshold, when it is small but extremely hot, such as a queue table.

## What not to do

- **Do not turn autovacuum off to "save resources".** Dead rows pile up and the cost comes back larger. Even with it off, PostgreSQL still forces vacuums to prevent [transaction ID wraparound](topic:wraparound).
- **Do not use `VACUUM FULL` as the regular answer.** It rewrites the table into a new copy, needs extra disk space, and takes a lock that blocks all use of the table. Autovacuum never does it.
- **Do not change everything at once.** Change one thing, watch the result, then continue.

## Why it matters for performance

**What it costs.** Vacuum uses disk and some CPU. A faster setting finishes sooner but competes with queries. A lazier setting leaves more dead rows, which cost queries and disk.

**When it shows up.** On big, update-heavy or delete-heavy tables, where the defaults let too much accumulate, or when a workload changes.

**How to measure.** See how far each table is from its trigger, how long vacuum runs take, and whether dead rows grow between runs. [Monitoring vacuum](topic:vacuum-monitoring) shows how.

**When to worry.** As a rule of thumb, when dead rows keep rising between vacuum runs, when a vacuum runs for hours and the next one starts at once, or when a table's size grows with no new rows.

**What you can change.**

- Lower the scale factor on big hot tables, so vacuum starts earlier.
- Raise the cost limit, or lower the delay, if vacuum is held back too much and the disk has room.
- Raise the number of workers when many tables wait, knowing it needs a restart and shares the budget.
- Give small, extremely hot tables a lower threshold.

## Common mistakes

- Keeping the default scale factor on a huge table.
- Adding workers to speed up one big table.
- Raising the speed without checking the disk, and slowing the queries.
- Disabling autovacuum on a table and forgetting it.
- Fixing symptoms with `VACUUM FULL` while the settings stay the same.

## Checklist

- Work out when autovacuum will start on your biggest tables.
- Give big, hot tables their own, lower scale factor.
- Raise the cost limit before adding workers.
- Leave autovacuum on.
- Change one setting at a time, and watch [the monitoring](topic:vacuum-monitoring).
