---
title: "High CPU cause: a runaway query"
updated: 2026-11-01
sources:
  - https://www.postgresql.org/docs/17/monitoring-stats.html
  - https://www.postgresql.org/docs/17/functions-admin.html
  - https://www.postgresql.org/docs/17/runtime-config-client.html
---

This is one of the root causes listed in [Common root causes of high CPU](topic:high-cpu-causes). It is about **PostgreSQL 17**.

> **How this was checked:** The names of the activity view, the functions that cancel a statement or end a session, and the statement timeout setting come from the PostgreSQL 17 documentation, listed in the sources. The causes and the advice are common operating practice. The article has no SQL.

## What it is

One session runs a statement that uses a full core for a long time. Typical sources:

- **A join that multiplies rows,** for example a missing join condition, so every row meets every row.
- **A huge sort or aggregation** over a very large table.
- **A loop inside a function,** or a recursive query that does not end.
- **An analytical query** run on the production database by a person or a report.

## How to recognise it

- **One process uses about 100% of a core,** while the others are quiet. PostgreSQL uses one process for each connection, so the operating system shows it as a single process.
- **In the activity view, one session has been running the same statement for a long time,** and it is active with no wait event, so it is running, not waiting.
- **The CPU is high even though the request rate is normal.**

On a managed service the per-process view may not be available. The activity view still shows the long-running active session.

## What to do

1. **Find the statement and see why it is expensive.** Read its [plan](topic:execution-plan) to see the join or the scan that explodes.
2. **Stop it if it hurts now.** PostgreSQL can **cancel** a statement, which stops the statement and leaves the session connected, or **end the session**, which closes the connection. Cancelling is the gentler first step. Either way the work the statement did is rolled back, so a long write can take time to undo.
3. **Fix the cause.** Correct the join, add a limit, rewrite the query, or add the [index](topic:index) it lacks.
4. **Prevent the next one.** Set a **timeout for statements** for the users who run reports or ad hoc queries, so a runaway stops by itself. Send analytical work to a replica. Review what the application sends.

## Why it matters

A runaway statement can fill a core for hours and, with parallel workers, several. On a small instance one is enough to push the CPU to the limit and slow everyone. It is also the cause that is easiest to fix once found.

## Common mistakes

- Ending the session when cancelling the statement would do.
- Restarting the database, which hides the problem and loses the cache.
- Killing it without finding the statement, so it returns.
- Giving people direct access to the production database with no timeout.

## Checklist

- One process at a full core? One long-running active session?
- What is the statement, and what does its plan do?
- Cancel it, or end the session if needed.
- Set a statement timeout for report and ad hoc users.
