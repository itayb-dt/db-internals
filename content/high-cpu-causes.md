---
title: "Common root causes of high CPU"
updated: 2026-11-01
sources:
  - https://www.postgresql.org/docs/17/monitoring-stats.html
  - https://www.postgresql.org/docs/17/pgstatstatements.html
  - https://www.postgresql.org/docs/17/using-explain.html
---

The CPU of the database host is far above its usual level. This article says why that matters and lists the common root causes, each with a short explanation. It is about **PostgreSQL 17**.

> **How this was checked:** The facts about the activity view, statistics and plans come from the PostgreSQL 17 documentation, listed in the sources. The causes themselves, and the remarks about hosts, virtual machines and containers, are common operating practice. The article has no SQL.

## Why a high CPU is a problem

- **Everything gets slower.** Every statement needs CPU time, so even the cheap ones wait.
- **Near 100% the instance cannot keep up.** Requests queue, clients time out and retry, and the retries add load.
- **There is no room left** for a traffic spike, a maintenance job or a failover.

As a rule of thumb, a CPU that stays above 80% for long periods needs attention before it reaches 100%.

## Potential root causes

Two quick questions narrow the list. Is the CPU used by **one process or many**? (PostgreSQL uses one process for each connection.) And are the sessions **running** (active, with no wait event) or **waiting**? A waiting session uses no CPU.

1. **Not enough resources for the workload.** The instance has too few cores for the steady load, or the load has grown. The CPU is high all through the busy hours and the trend rises over weeks. Reduce the work first, then add capacity.
2. **A runaway query.** One session uses a full core for a long time: a join that multiplies rows, a huge sort, a loop inside a function. One process sits at about 100% of a core. Find it, read its [plan](topic:execution-plan), and cancel it if needed.
3. **More requests than usual.** A campaign, a busy hour, or a retry storm after a failure. Statements per second are well above a normal day.
4. **Jobs overlap.** Reports, imports and scheduled jobs start together. The CPU jumps at the same clock time every day or week.
5. **Costly statements.** A few statements use most of the CPU: scans because an index is missing, a poor plan after the statistics went stale, big sorts, heavy functions, or parallel queries that use several cores at once. Rank the statements by total time ([Query metrics](topic:query-metrics)), then fix them with an [index](topic:index) or a rewrite. See [Common root causes of slow queries](topic:slow-query-causes).
6. **Too many active sessions.** More sessions run than the host has cores, so they queue and the operating system spends CPU switching between them. A burst of new connections costs CPU too. A pooler fixes it: see [load balancers and connection pooling](topic:load-balancer).
7. **Maintenance work.** Autovacuum, analyze or an index build on a big table. The busy processes are server workers, not client sessions. Tune vacuum ([Vacuum configuration](topic:vacuum-configuration)) and run builds in quiet hours.
8. **A replication problem.** A replica that fell behind or was rebuilt, many replicas, or logical decoding keep the processes that send and replay changes busy. Replication lag is large or changing.
9. **Waiting on disk.** The graph shows waiting for disk, or system time, not real work. The data is not in memory, so queries read from disk. Look at I/O and the cache, not at the CPU.
10. **Something else on the host.** A backup, an agent or another application. On a virtual machine, other tenants can take CPU away. In a container, a CPU limit can throttle the database.

**Not a cause: locks.** Sessions that wait for a lock use no CPU. If most sessions wait on locks, the problem is blocking, not the CPU.

## Checking them

The animation checks the causes one at a time. Each has a question that confirms or rejects it, and the search stops at the first one that is confirmed.

<iframe src="high-cpu-causes/demo.html" title="Animation: a list of causes of high CPU checked one at a time. Not enough resources, a runaway query, more requests and overlapping jobs are each rejected by a question. Costly statements is confirmed because a few statements dominate the total time" width="800" height="450"></iframe>

*The animation repeats about every 30 seconds.*

## Checklist

- One process or many? Running sessions or waiting ones?
- What changed, and since when?
- Rank the statements and read the top plans.
- Check jobs, maintenance and replication.
- Confirm one cause before you change anything, then measure again.
