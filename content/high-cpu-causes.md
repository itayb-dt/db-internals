---
title: "Common root causes of high CPU"
updated: 2026-11-01
sources:
  - https://www.postgresql.org/docs/17/monitoring-stats.html
  - https://www.postgresql.org/docs/17/pgstatstatements.html
  - https://www.postgresql.org/docs/17/using-explain.html
  - https://www.postgresql.org/docs/17/runtime-config-autovacuum.html
  - https://www.postgresql.org/docs/17/tutorial-arch.html
---

The CPU of the database host is far above its usual level. That part is easy to see. This article answers the next question: what are the common reasons? It starts with a few quick checks, and then walks through the causes. It is about **PostgreSQL 17**.

> **How this was checked:** The facts about the activity view, statistics and plans come from the PostgreSQL 17 documentation, listed in the sources. The causes, and the remarks about hosts, virtual machines and containers, are common operating practice. The article has no SQL, and the thresholds are rules of thumb.

## First, three quick checks

A few facts rule most causes in or out, so look at them before you guess.

**Where does the CPU go?** The host splits CPU time into parts:

| Part | What a high value suggests |
|---|---|
| **User** | The database is computing: statements, sorts, joins, functions |
| **System** | The kernel is busy: heavy I/O, many connections, or many processes switching |
| **Waiting for disk** | Not computation. The CPU is idle while processes wait for the disk, so the graph misleads |
| **Stolen** | On a virtual machine, a noisy neighbour took the CPU |

**One process, or many?** PostgreSQL uses one process for each connection, so the operating system shows each session as a process. One process at a full core means one session is expensive or stuck. Many processes at 5% to 20% each means the whole workload is too big.

**Which sessions are on the CPU?** In the activity view, a session that is **active with no wait event** is running, so it uses the CPU. A session with a wait event, such as a lock or the disk, is waiting and uses none. Compare the number of running sessions with the number of cores.

Add the trend and the events: did the CPU rise slowly or jump, and what changed at that moment (a deployment, a scheduled job, a restart, a new feature)? The animation shows the first two checks.

<iframe src="high-cpu-causes/first-checks.html" title="Animation: the CPU of the host split into user, system, waiting for disk and idle. Then a process list where one process uses almost a whole core, and another where many processes each use a little" width="800" height="450"></iframe>

*The animation repeats about every 26 seconds.*

## A tree of hypotheses

Think of the diagnosis as a tree. At the top is "the CPU is high". It splits into branches, and each branch has a check that confirms or rejects it. Test one branch at a time and reject it, until one is confirmed. The animation shows a tree and a diagnosis that confirms one cause.

<iframe src="high-cpu-causes/demo.html" title="Animation: a tree of hypotheses for high CPU. One session at a full core is rejected. The host waiting is rejected. Many sessions using a little each is confirmed. Under it, costly statements is confirmed and the other causes are rejected" width="800" height="450"></iframe>

*The animation repeats about every 30 seconds.*

## Branch 1: one session hogs a core

A single session runs a statement that uses a full core for a long time: a join that multiplies rows, a huge sort, a loop inside a function, or an analytical query on a big table. **Check:** one process at about 100% of a core, one session running the same statement for a long time. **Fix:** find the statement and see why it is expensive ([the execution plan](topic:execution-plan)). PostgreSQL can cancel a statement, or end a session, with a function built for that, and a timeout on statements stops runaways for users that run reports.

## Branch 2: many sessions, each using a little

This is the most common branch. The workload as a whole is too big.

- **More requests than usual.** Traffic grew, or retries piled up after a failure. *Check:* statements per second are above a normal day. *Fix:* cache results, fetch in one query instead of one per row, add capacity, and fix whatever caused the retries.
- **Jobs overlap.** Reports, imports and scheduled jobs start together and compete with the normal load. *Check:* the CPU jumps at the same clock time, and the busy sessions belong to the jobs. *Fix:* stagger them, or run reports on a replica.
- **Costly statements.** A few statements use most of the CPU: scans of big tables because an index is missing, a poor plan after the statistics went stale, big sorts and joins, or heavy work such as text matching or JSON handling. *Check:* rank the statements by total time ([Query metrics](topic:query-metrics)). The top few dominate, and their plans scan far more rows than they return. *Fix:* the right [index](topic:index), a rewritten statement, fresh statistics. See [Common root causes of slow queries](topic:slow-query-causes).
- **Too many active sessions for the cores.** When more sessions run than the host has cores, they take turns, and the operating system spends CPU switching between them. A burst of new connections costs CPU too, because each one starts a process. *Check:* running sessions are a few times the cores, the system share is high, and connections open and close often. *Fix:* a pooler, so only as many sessions run as the host can serve. See [load balancers and connection pooling](topic:load-balancer).
- **Parallel queries.** One statement can use several processes. A few of them can occupy many cores, which is intended but can crowd out the rest under load. *Check:* several parallel workers per statement in the activity view. *Fix:* limit the workers per statement and in total.
- **Background work.** Autovacuum, analyze, index builds, checkpoints, replication. *Check:* the busy processes are background workers, not client sessions. *Fix:* build indexes in quiet hours, and tune vacuum ([Vacuum configuration](topic:vacuum-configuration)).

## Branch 3: the CPU is high, but not from query work

- **The host waits on disk, or switches between processes.** Little real computation happens. Usually the data is not in memory, so queries read from disk, or too many processes compete. *Check:* high waiting or system share, low user share, and I/O wait events in the activity view. *Fix:* look at I/O and the cache, not at the CPU: more memory, better indexes, faster storage.
- **Something else on the host.** On a system you run, a backup, an agent or another application uses the CPU. On a virtual machine, stolen time takes it. In a container, a CPU limit can throttle the database so it looks busy and slow. *Check:* the busy processes are not PostgreSQL, or stolen or throttled time is high. *Fix:* move or limit the other software, or change the limit or the host.

## A branch you can reject: locks

Sessions that wait for a lock do **not** use CPU. They show a wait event and sit idle. If most sessions wait on locks, the problem is blocking, not the CPU.

## From symptom to cause

| What you see | Likely cause | The check that confirms it |
|---|---|---|
| One process at a full core | A runaway statement | One long-running session |
| Statement rate up, same statements | More requests | Calls per second against a normal day |
| CPU jumps at a fixed time | Overlapping jobs | The time, and who the sessions are |
| A few statements dominate | Costly statements | Ranking by total time, plans with scans |
| Running sessions far above the cores | Too many active sessions | Sessions on the CPU, connection rate |
| Several workers on one statement | Parallel queries | Parallel workers in the activity view |
| Background workers busy | Vacuum, builds, replication | The worker names, the logs |
| Waiting for disk, low user time | The disk, not the CPU | The CPU split, I/O waits |
| Busy processes that are not PostgreSQL | Something else on the host | The process list |

## Why it matters for performance

**What it costs.** At high CPU every statement runs slower, even cheap ones. Near 100% the instance cannot keep up, queues build, and requests time out. A wrong diagnosis costs time while it stays high: more cores do not fix a runaway statement, and tuning a query does not fix too many connections.

**When it shows up.** At peaks, when jobs overlap, after a change, and when data growth makes a once-cheap statement costly.

**How to measure.** The CPU split, the process list, the running sessions against the cores, the connection rate, and the ranking of statements.

**When to worry.** As a rule of thumb, when the CPU stays above 80% for long periods, or when more sessions run than there are cores.

**What you can change.** The fixes in the branches above, each with its cost.

## Common mistakes

- Adding cores before finding the cause.
- Reading a high CPU graph as proof that queries are the cause, when the time is spent waiting for disk.
- Tuning queries when the problem is the number of connections.
- Forgetting jobs, backups and background work.
- Treating a lock pile-up as a CPU problem.

## Checklist

- Split the CPU into user, system, waiting and stolen.
- One process or many? Count the sessions on the CPU against the cores.
- What changed, and since when?
- Rank the statements and read the top plans.
- Check the schedule, parallel workers and background workers.
- Confirm one cause before you change anything, then measure again.
