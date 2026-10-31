---
title: "Common root causes of high CPU"
updated: 2026-11-01
sources:
  - https://www.postgresql.org/docs/17/monitoring-stats.html
  - https://www.postgresql.org/docs/17/pgstatstatements.html
  - https://www.postgresql.org/docs/17/using-explain.html
---

This article continues from [High CPU: the problem](topic:high-cpu). It is a quick overview of the potential root causes, with a short explanation of each. The rest of the track discusses the causes one by one.

## Potential root causes

Two quick questions narrow the list. Is the CPU used by **one process or many**? (PostgreSQL uses one process for each connection.) And are the sessions **running** (active, with no wait event) or **waiting**? A waiting session uses no CPU.

1. **Not enough resources for the workload** ([details](topic:cpu-capacity)). The instance has too few cores for the steady load, or the load has grown. The CPU is high all through the busy hours and the trend rises over weeks. Reduce the work first, then add capacity.
2. **A runaway query** ([details](topic:runaway-query)). One session uses a full core for a long time: a join that multiplies rows, a huge sort, a loop inside a function. One process sits at about 100% of a core. Find it, read its [plan](topic:execution-plan), and cancel it if needed.
3. **More requests than usual** ([details](topic:cpu-workload-spikes)). A campaign, a busy hour, or a retry storm after a failure. Statements per second are well above a normal day.
4. **Jobs overlap** ([details](topic:cpu-workload-spikes)). Reports, imports and scheduled jobs start together. The CPU jumps at the same clock time every day or week.
5. **Costly statements** ([details](topic:slow-query-causes)). A few statements use most of the CPU: scans because an index is missing, a poor plan after the statistics went stale, big sorts, heavy functions, or parallel queries that use several cores at once. Rank the statements by total time ([Query metrics](topic:query-metrics)), then fix them with an [index](topic:index) or a rewrite. See [Common root causes of slow queries](topic:slow-query-causes).
6. **Too many active sessions** ([details](topic:load-balancer)). More sessions run than the host has cores, so they queue and the operating system spends CPU switching between them. A burst of new connections costs CPU too. A pooler fixes it: see [load balancers and connection pooling](topic:load-balancer).
7. **Maintenance work** ([details](topic:vacuum-configuration)). Autovacuum, analyze or an index build on a big table. The busy processes are server workers, not client sessions. Tune vacuum ([Vacuum configuration](topic:vacuum-configuration)) and run builds in quiet hours.
8. **A replication problem** ([details](topic:cpu-replication)). A replica that fell behind or was rebuilt, many replicas, or logical decoding keep the processes that send and replay changes busy. Replication lag is large or changing.
9. **Waiting on disk** ([details](topic:cpu-host)). The graph shows waiting for disk, or system time, not real work. The data is not in memory, so queries read from disk. Look at I/O and the cache, not at the CPU.
10. **Something else on the host** ([details](topic:cpu-host)). A backup, an agent or another application. On a virtual machine, other tenants can take CPU away. In a container, a CPU limit can throttle the database.

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
