---
title: "What database monitoring means"
updated: 2026-10-22
sources:
  - https://www.postgresql.org/docs/17/monitoring-stats.html
  - https://www.postgresql.org/docs/17/runtime-config-logging.html
  - https://docs.dynatrace.com/docs/observe/infrastructure-observability/databases
---

This article is the start of the monitoring track. It is about the idea, not a product. The examples use **PostgreSQL 17**, but every database has the same kinds of signals under different names.

## Start with the questions

Nobody monitors a database for its own sake. People want answers to a few questions:

- **Is it up?** Can the application connect and run a query?
- **Is it healthy?** Are disk, memory, connections and replication in a good state?
- **Is it slow?** Which queries take the time, and is that new?
- **Why?** What changed, and what explains it?
- **What will break next?** A disk that fills in a week, a table nearing [transaction ID wraparound](topic:wraparound), a connection limit.

**Monitoring** collects data and raises an alert when something crosses a line. It answers "is something wrong?". **Observability** is the ability to ask a new question about a problem you did not expect, using data you already keep. A good setup does both.

## The signals

| Signal | What it is | Database example |
|---|---|---|
| Metrics | Numbers over time | Active sessions, cache hit ratio, replication lag |
| Logs | Text events | The slow query log, errors, [autovacuum entries](topic:vacuum-monitoring) |
| Traces | One request followed across components | A request from the web tier that waits 800 ms in a query |
| Events | Things that happened | A failover, a configuration change, a deployment |
| Topology | What depends on what | Which services use this database, and which host runs it |

Each signal answers a different part of the question. A metric tells you the database is busy. A log line tells you which statement was slow. A trace tells you which user request suffered. Topology tells you who is affected.

## Two points of view

**From the inside.** The database knows a lot about itself. PostgreSQL exposes counters and live state in its [statistics views](topic:statistics) and writes to the [server log](topic:server-logs). This is the only place that sees statements, locks, waits and [vacuum](topic:vacuum) work.

**From the outside.** The host knows CPU, memory, disk and network. The application knows how long its calls took and how often they failed. This view shows the effect on users, and it keeps working when the database cannot answer.

You need both. The inside view says why a query is slow. The outside view says whether anyone noticed, and whether the cause is the database at all. A slow disk, a full network link or a noisy neighbour on the same host look like a slow database from the application.

## What it costs

Monitoring is not free:

- **Load on the database.** Every query against the statistics views uses CPU. Collecting too often, or reading very large views, adds up. A rule of thumb is to collect statement statistics once a minute or so, not every second.
- **Privileges.** The collector needs a database account that can read the system views. Give it only that, not write access.
- **Storage and retention.** Metrics are small. Statements, plans and logs are large. Decide how long to keep them. The database's own counters are lost on a restart or a statistics reset, so history has to live outside it.
- **Attention.** Too many alerts teach people to ignore them.

## Common mistakes

- Watching only "is it up" and missing a database that is up but crawling.
- Alerting on a fixed number that is normal at noon and abnormal at 3 a.m.
- Collecting only the inside view, then discovering the problem is the host or the network.
- Keeping no history, so there is nothing to compare with when something changes.

## Checklist

- Write down the questions you need answered before choosing tools.
- Collect the four signals (metrics, logs, traces, events) and the topology.
- Look from both the database and the outside.
- Use a least-privilege account and a modest collection interval.
- Keep history outside the database.
- Alert on change from the normal pattern, not on one fixed number.
