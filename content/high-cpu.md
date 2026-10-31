---
title: "High CPU: the problem"
updated: 2026-11-01
sources:
  - https://www.postgresql.org/docs/17/monitoring-stats.html
  - https://www.postgresql.org/docs/17/pgstatstatements.html
  - https://www.postgresql.org/docs/17/tutorial-arch.html
---

This article starts the problem track **High CPU**. It says what the problem is, how it is detected, and why it matters. The next article lists the potential root causes, and the rest of the track discusses each one. It is about **PostgreSQL 17**.

> **How this was checked:** The facts about the activity view and the statistics come from the PostgreSQL 17 documentation, listed in the sources. The description of CPU time on a host, and of cloud monitoring, is general operating knowledge. The article has no SQL, and the thresholds are rules of thumb.

## What it is

The CPU of the database host is far above its usual level, or close to 100%, for a longer time than a short spike. It can be a sign of a healthy system that is simply busy, or of a problem. This track helps you tell which.

## How it is detected

Some signals come from the **operating system or the cloud monitoring**, and some from **PostgreSQL system views**. You need both, because they answer different questions.

| What you look at | Where it comes from | What it tells you |
|---|---|---|
| CPU use of the host or instance | Operating system tools, or the cloud provider's monitoring (for example CloudWatch on AWS) | How high it is, and since when |
| The split of the CPU: user, system, waiting for disk, stolen | Operating system tools, or the cloud monitoring | Whether it is real computation, or waiting |
| CPU of each process | Operating system tools only. PostgreSQL uses one process for each connection | One process or many |
| Number of cores, and the load | Operating system, or the cloud monitoring | Whether more sessions run than there are cores |
| Sessions running on the CPU | System view `pg_stat_activity`. A session that is active with no wait event is running | What is running now |
| Statements that use the most time | System view `pg_stat_statements` | Which statements cost the most |
| Transactions and connections per second | System views such as `pg_stat_database` and `pg_stat_activity` | Whether the workload grew |

On a **managed service** you usually get the CPU of the instance from the provider's monitoring, and sometimes only as one number. The PostgreSQL views are still yours. The per-process view of the operating system is often not available, so use the activity view instead.

The animation shows the first two checks: the split of the CPU, and one process against many.

<iframe src="high-cpu/demo.html" title="Animation: the CPU of the host split into user, system, waiting for disk and idle. Then a process list where one process uses almost a whole core, and another where many processes each use a little" width="800" height="450"></iframe>

*The animation repeats about every 26 seconds.*

The CPU split matters most. Mostly **user** time means the database is computing. A large share of **waiting for disk** means the CPU graph misleads, because the processes wait for the disk and compute little. **Stolen** time, on a virtual machine, means another tenant took the CPU.

## Why you should care

When the CPU stays high, bad things follow:

- **Every statement gets slower.** Even cheap statements wait for CPU time, so latency rises for everyone.
- **Requests queue, then time out.** Clients retry, and the retries add load. Each new connection costs CPU too, so a pile of them makes it worse.
- **Replication falls behind.** A standby needs CPU to replay changes, so its lag grows.
- **Maintenance falls behind.** Autovacuum slows down, and dead rows and bloat grow.
- **You may not be able to get in.** At 100% even an administrator's connection can be slow.
- **There is no room left.** A traffic spike, a failover or a restart under that load can tip the instance over.
- **It costs money.** If the answer is more capacity, the bill rises, so it is worth finding out whether the work is wasted first.

As a rule of thumb, a CPU that stays above 80% for long periods needs attention before it reaches 100%.

## What next

Do not guess the cause. The next article, [Common root causes of high CPU](topic:high-cpu-causes), lists the usual ones with a short explanation of each.

## Checklist

- What is the CPU use now, and what is normal for this time of day?
- Is it user time, waiting for disk, or stolen time?
- One process or many? How many sessions run, compared with the cores?
- Since when, and what changed?
