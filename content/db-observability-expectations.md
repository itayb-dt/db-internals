---
title: "What a good database observability system gives you"
updated: 2026-10-22
sources:
  - https://docs.dynatrace.com/docs/observe/infrastructure-observability/databases
  - https://docs.dynatrace.com/docs/observe/infrastructure-observability/databases/concepts
  - https://www.postgresql.org/docs/17/monitoring-stats.html
---

This article continues from [What database monitoring means](topic:db-monitoring). It is a list of what to expect from a database observability system, whatever the vendor. Examples come from **PostgreSQL 17**.

## Built by database experts

A generic monitoring tool shows you counters and leaves the thinking to you. A good database tool starts from how databases fail, and from what the people who run them need.

That expertise shows up in practice:

- It **knows which signals matter** for each engine: wait events and locks, [vacuum](topic:vacuum-monitoring) health, replication lag, connection use.
- It **names things the way a DBA does**: blocking sessions, deadlocks, normalised statements, execution plans.
- It **ships with sensible defaults**, such as health checks and alerts per engine, so a new database is useful on day one.
- It **hides differences you should not care about**, so the same question works on PostgreSQL, MySQL or SQL Server.

The test is simple: could a team without a full-time DBA use it and still find a problem?

## What it should collect

Counters alone are not enough. Look for:

- **Statements.** The normalised text of each query with its calls, time, rows and I/O, so you can rank the expensive ones. In PostgreSQL this comes from the `pg_stat_statements` extension.
- **Execution plans.** The way the database ran the query. A query can become slow only because the [plan changed](topic:execution-plan).
- **Waits, locks and sessions.** What each session is waiting for, and who blocks whom. See [deadlocks](topic:deadlock).
- **Object detail.** Size, growth and health of databases, tables and [indexes](topic:index), including unused indexes.
- **Configuration.** The settings in force, and when they changed.
- **History.** The data must outlast the database's own counters, which reset on a restart.
- **Low overhead and least privilege.** It must not become the load it is trying to find.

## Root cause analysis: test several explanations

The most valuable part is going from a symptom to a cause. "The application is slow" has many possible explanations. A good system checks them and ranks the one the evidence supports best, the way an experienced DBA would:

| Hypothesis | What supports it |
|---|---|
| One statement got slower | Its time per call rose, or its plan changed |
| Lock contention | Sessions waiting on locks, a long transaction holding them |
| Saturated I/O or CPU | Host metrics high, many sessions waiting on I/O |
| Connections exhausted | Sessions near the limit, new connections failing |
| Maintenance falling behind | Dead rows growing, [autovacuum](topic:vacuum) not keeping up |
| Something changed | A deployment, a setting, or a data volume shift just before |
| Not the database | The database is quiet, but a service or the network is slow |

The last row matters. A system that always blames the database is as bad as one that never does. It needs the host, service and trace context from [outside the database](topic:dt-platform) to rule the database in or out.

The output should be a **ranked list with the evidence**, not a single confident claim. When two explanations fit, say so.

## Recommendations

Finding the cause is half the job. Where it can, the system should say what to do: look at this statement, this table needs an index, this setting is too low, this long transaction is blocking vacuum.

Treat recommendations as a starting point:

- A recommendation based on the data it has seen is reliable for the pattern it saw. It may not know your constraints, such as a write-heavy table where one more index has a cost.
- Prefer recommendations that explain why, so you can judge them.
- When the system cannot be sure, it should point to the cause and stop there.

## Alerts that fit the workload

A fixed threshold is wrong half the time. A good system learns the normal pattern, for example a busy hour every morning, and alerts on **deviation**. It also groups related alerts into one problem, so one blocked table does not page you forty times.

## Common mistakes

- Choosing a tool for its number of charts, not for the answers it gives.
- Trusting a single suggested root cause without looking at the evidence.
- Alerting on every counter instead of on health and impact.
- Collecting statements but not plans, then being unable to explain a regression.

## Checklist

- Does it understand your engines, or only show counters?
- Does it collect statements, plans, waits, locks and configuration, and keep history?
- Does it test several explanations and show the evidence?
- Can it rule the database out?
- Are recommendations explained and honest about uncertainty?
- Are alerts based on normal behaviour and grouped into problems?
- Is the overhead low and the account least-privilege?
