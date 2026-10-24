---
title: "Load balancers and connection pooling"
updated: 2026-10-24
sources:
  - https://www.postgresql.org/docs/17/runtime-config-connection.html
  - https://www.postgresql.org/docs/17/libpq-connect.html
  - https://www.postgresql.org/docs/17/high-availability.html
  - https://www.pgbouncer.org/features.html
  - https://www.pgbouncer.org/config.html
  - https://www.pgpool.net/docs/latest/en/html/intro-whatis.html
  - https://www.citusdata.com/blog/2020/10/08/analyzing-connection-scalability/
---

This article is about **PostgreSQL 17** and the software that sits between the application and the server. It starts from a problem you may have met: the application grows, you add servers, and the database falls over under connections, not under queries.

> **How this was checked:** The facts come from the PostgreSQL, PgBouncer and Pgpool-II documentation and one published analysis, listed in the sources. The SQL below was not run against a server for this article, and is marked so. Product features change, so check the current documentation of the tool you choose.

## Two jobs, often mixed up

People say "load balancer" for two different things:

| Job | What it does | Typical tools |
|---|---|---|
| **Connection pooling** | Keeps a small set of server connections open and lends them to many clients | PgBouncer, Odyssey, PgCat, Supavisor, RDS Proxy |
| **Load balancing and routing** | Sends traffic to the right server: writes to the primary, reads spread over replicas, and away from a failed node | HAProxy, Pgpool-II, cloud reader endpoints |

Some tools do both. Pgpool-II, for example, offers connection pooling, read load balancing and automatic failover in one product. Most teams use a small pooler and a separate routing layer, because each does one thing well.

## Why connections are expensive in PostgreSQL

PostgreSQL starts **one process for each connection**, as described in [the instance](topic:instance). That choice has costs:

- **Start-up.** A new connection forks a process, authenticates, and builds its own caches. For a short query this setup can take longer than the query. Applications that open a connection per request pay it every time.
- **Memory.** Each backend has private memory, and each sort or hash in a query can use up to `work_mem`. A general connection uses a small amount, but a busy one running several memory-hungry operations uses much more. Many connections multiplied by `work_mem` is a classic way to run out of memory.
- **Shared structures.** PostgreSQL sizes some shared resources, including shared memory, from `max_connections`. A higher limit allocates more of them, even if no one connects. The default is typically 100.
- **Snapshots.** Every transaction needs a snapshot of which transactions are visible ([MVCC](topic:mvcc)). In an analysis by Andres Freund, building snapshots was the main scaling limit, and **idle connections still added cost**: with 10,000 idle connections, throughput fell by nearly half compared with one. PostgreSQL 14 reduced this bottleneck, but it did not make connections free.
- **Scheduling.** If many more sessions are *active* than the host has CPU cores, they compete for CPU and locks. Total throughput can go down as you add concurrency.

The result is often surprising. A server that handles 50 busy connections well can slow down with 2,000 mostly idle ones, and fail at the limit with `too many clients already`.

A rule of thumb is that the number of **active** queries should be a small multiple of the CPU cores, not hundreds. It depends on how much time queries wait for disk and locks, so measure.

## See your own connections

This query shows how connections are used right now (not run: needs a live server):

```sql
-- not run: depends on live activity
SELECT state, count(*) AS connections,
       max(now() - state_change) AS longest_in_state
FROM pg_stat_activity
WHERE backend_type = 'client backend'
GROUP BY state
ORDER BY connections DESC;
```

How to read it:

- **Mostly `idle`:** many connections are held open and unused. A pooler helps most here.
- **`idle in transaction` for a long time:** a client opened a transaction and left. It holds locks and blocks [vacuum](topic:dead-rows). Fix the application, and consider `idle_in_transaction_session_timeout`.
- **Many `active`:** the server is genuinely busy. A pooler will not make queries faster. Look at the [plans](topic:execution-plan) instead.

Compare the total with the limit:

```sql
-- not run: depends on live activity
SELECT count(*) AS connections, current_setting('max_connections') AS max_connections
FROM pg_stat_activity;
```

A rule of thumb is to worry when you regularly pass about 80% of the limit.

## What a connection pooler does

The application connects to the pooler, which connects to PostgreSQL. Thousands of clients share a few dozen server connections. The server sees a small, steady load.

PgBouncer, the most widely used pooler, has three modes:

- **Session pooling.** A client keeps one server connection until it disconnects. Everything works, but there is little sharing if clients stay connected.
- **Transaction pooling.** A server connection is assigned only while a transaction runs, then returned. This gives the most reuse, and it is what lets thousands of clients use a few connections.
- **Statement pooling.** Like transaction pooling, but multi-statement transactions are not allowed. It is rare.

**The trade-off of transaction pooling:** consecutive transactions of one client may run on different server connections, so anything that lives in the *session* breaks. PgBouncer's documentation lists these as unsupported in transaction mode: `SET` and `RESET`, `LISTEN`, `WITH HOLD` cursors, session-level advisory locks, `LOAD`, and temporary tables that persist across transactions. Prepared statements are handled by the `max_prepared_statements` setting, which defaults to 200 in the current documentation. Check that your PgBouncer version has it.

Typical sizing: pool size is a small number per database and user (PgBouncer's default is 20), far below the number of clients. Start low and raise it only if clients queue.

## What a load balancer does

A balancer in front of several PostgreSQL servers solves different problems:

- **Routing to the primary.** After a failover the primary changes. A balancer such as HAProxy, using health checks, always sends writes to the current primary. Failover tools such as Patroni provide the health information for this. Many drivers can also do it themselves: libpq accepts several hosts and `target_session_attrs=read-write` to find the primary.
- **Spreading reads.** Read-only queries can go to replicas, which adds capacity. Pgpool-II can tell reads from writes and balance the reads.
- **Hiding failures.** A broken node is removed from rotation.

**The catch with replicas:** replication is usually asynchronous, so a replica can be a little behind. A user who saves a change and then reads from a replica may not see it. Route reads that must be fresh to the primary, and watch replication lag.

A balancer does not reduce the number of connections reaching one server. Put a pooler in front of each server, or use a tool that does both.

## When it helps and when it does not

| Symptom | Will pooling or balancing help? |
|---|---|
| Thousands of idle connections, high memory | Yes, a pooler |
| Connection storms after a deploy or restart | Yes, a pooler absorbs them |
| `too many clients` errors | Yes, but also find why clients hold connections |
| One slow query | No. Fix the query, the index or the plan |
| Primary is saturated by reads | Yes, replicas, if stale reads are acceptable |
| Primary is saturated by writes | No. Replicas do not take writes |

## Common mistakes

- Raising `max_connections` to "fix" connection errors. It uses more resources and can make things worse.
- Using transaction pooling with an application that relies on `SET` or session locks, and getting random behaviour.
- Putting a pooler in place but leaving the application pool settings unchanged, so the total still grows.
- Sending reads that need fresh data to a lagging replica.
- Making the pooler or balancer a single point of failure.

## Checklist

- Count connections by state, and compare with `max_connections`.
- Fix `idle in transaction` sessions first.
- Choose session or transaction pooling after checking which session features the application uses.
- Keep server connections far fewer than clients, and the active ones near the CPU count.
- Route writes to the primary and reads that must be fresh too.
- Monitor replication lag and pool queueing.
- Run more than one pooler or balancer, so it is not a single point of failure.
