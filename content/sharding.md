---
title: "Sharding: one logical database on many servers"
updated: 2026-10-24
sources:
  - https://www.postgresql.org/docs/17/ddl-partitioning.html
  - https://www.postgresql.org/docs/17/postgres-fdw.html
  - https://www.postgresql.org/docs/17/high-availability.html
  - https://docs.citusdata.com/en/stable/get_started/concepts.html
---

Sharding is **not a database internal**. You will not find it in the PostgreSQL storage code, and the server itself does not know it is being used. We include it because it decides how the database layer behaves as a whole once one server is no longer enough. It changes what a query costs, which transactions are possible and how you operate the system, so anyone who monitors or tunes databases should understand it.

## The problem it solves

You can make one server bigger for a long time: more memory, faster disks, more cores. Sooner or later one of these happens:

- The data does not fit on one machine, or backups and restores take too long.
- Write volume exceeds what one primary can commit.
- Connections, memory or CPU are saturated and the next size up is too expensive or does not exist.

[Replicas](topic:load-balancer) help with reads, but every replica holds a full copy and only the primary takes writes. To grow writes and data size, you must **split the data**.

## Three ideas that are easy to mix up

| Idea | What is split | Where | What it helps |
|---|---|---|---|
| [Partitioning](topic:partitioning) | One table into pieces | **One server** | Clean-up, pruning, manageability |
| Replication | Nothing, it is a full copy | Several servers | Reads, failover |
| **Sharding** | The data into disjoint sets | **Several servers** | Data size, write volume, total CPU and memory |

A shard is the same idea as a partition, placed on its own server. Each shard is an ordinary PostgreSQL [instance](topic:instance) holding part of the data. They are often combined: shards that are themselves partitioned and replicated.

## How it works

1. **Choose a shard key**, a column such as `tenant_id` or `user_id`.
2. A rule maps each key value to a shard. The common rule is a hash of the key, which spreads values evenly. A range or a lookup table also works.
3. A **router** sends each query to the shard that holds its key. In some systems this is a coordinator node, in others a library or proxy in the application.

A query that includes the shard key goes to **one** shard and behaves like a query on a small database. A query that does not has to ask **every** shard and merge the answers. That one difference drives most of the design.

The animation shows two queries. The first has the shard key and visits one shard. The second does not, and visits all three.

<iframe src="sharding/demo.html" title="Animation: a query with the shard key goes through the router to one shard, and a query without the key goes to all three shards, whose answers are merged" width="800" height="450"></iframe>

*The animation repeats about every 10 seconds.*

## The shard key is the decision that matters

A good key:

- **Appears in most queries**, so most go to one shard.
- **Has many distinct values** and spreads evenly, so no shard is hotter than the others.
- **Keeps related rows together.** If orders and order lines both use `customer_id`, a customer's data sits on one shard and joins stay local. Citus calls this *co-location*.
- **Does not change.** Moving a row to another shard is expensive.

Typical choices are the tenant in a multi-tenant application and the user in a consumer application. Bad choices are a low-cardinality column such as a country, or a timestamp, where all new writes land on the newest shard (a hot spot).

## What gets harder

Sharding trades simplicity for scale. After you shard:

- **Cross-shard queries are costly.** A join or an aggregate across shards moves data over the network, or runs on every shard and is merged. Latency is set by the slowest shard.
- **Transactions across shards are weaker or slower.** A transaction on one shard is a normal transaction. Across shards it needs a protocol such as two-phase commit, or it is not supported. The PostgreSQL `postgres_fdw` documentation states that it does not support two-phase commit of remote transactions.
- **Unique constraints and sequences** have to include the shard key, or be handled globally.
- **Resharding is hard.** Adding a shard means moving data while the system runs. Pick a plan, such as many small logical shards on few servers, before you need it.
- **Hot shards.** One very large tenant can overload its shard, however evenly the rest is spread.
- **Operations multiply.** There are more servers to back up, upgrade, monitor and keep consistent.

## What PostgreSQL gives you, and what it does not

PostgreSQL has **no built-in sharding**. It offers pieces:

- **Partitioning with foreign tables.** A partition can be a table on another server through `postgres_fdw`, which lets a local server read and write tables on remote PostgreSQL servers. This works as a basic form of sharding, but it has limits: for example, some conditions are only pushed down to the remote server under certain rules, so some queries move more data than expected.

```sql
-- not run: needs two servers and credentials
CREATE FOREIGN TABLE orders_shard1
  PARTITION OF orders FOR VALUES WITH (MODULUS 2, REMAINDER 0)
  SERVER shard1_server;
```

- **Extensions.** **Citus** is a PostgreSQL extension that turns servers into one shared-nothing cluster. A coordinator receives queries and sends each to one worker or runs it in parallel across several. Tables are distributed by a column you choose, small lookup tables can be copied to every worker, and related tables can be co-located.

Outside PostgreSQL the same idea appears elsewhere. **Vitess** adds a routing layer in front of sharded MySQL. **Distributed SQL databases** such as CockroachDB and YugabyteDB split data into ranges or tablets and place them automatically, so the application sees one database and does not choose shard keys by hand. (These last points are from general knowledge and secondary sources.) Cloud providers also offer managed sharded options. Check the provider's documentation.

## Why it matters for performance

Sharding is a performance tool for the **whole database layer**, treated as one logical unit:

- Writes and data size scale with the number of shards, as long as queries carry the shard key.
- Each shard is smaller, so [its buffer pool](topic:buffer) holds a larger share of the working set, and [vacuum](topic:vacuum) and backups are quicker.
- The price is that performance becomes a property of the **key and the query mix**, not only of one server. The same schema can be fast or slow depending on whether queries hit one shard.

That also changes monitoring. You watch shards separately and compare them, since a single average hides a hot shard. You also watch how many queries go to a single shard against how many fan out.

## When not to shard

Sharding is a one-way door that adds permanent complexity. Try these first, in roughly this order:

1. Fix queries and [indexes](topic:index).
2. Add a [pooler](topic:load-balancer) and tune the server.
3. Add read replicas for read-heavy load.
4. [Partition](topic:partitioning) big tables on one server.
5. Move to a bigger machine.

Shard when data size or write volume truly exceeds one machine, or when isolation per tenant is a requirement. A rule of thumb: if you cannot name the shard key and the share of queries that carry it, you are not ready.

## Common mistakes

- Sharding early, for load a bigger server would handle.
- Choosing a key that most queries do not use.
- Choosing a key with a hot spot, such as the time of creation.
- Assuming cross-shard joins and transactions behave like single-server ones.
- Having no resharding plan.
- Looking only at averages, and missing one overloaded shard.

## Checklist

- Have you exhausted tuning, replicas and partitioning on one server?
- Can you name the shard key, and does it appear in most queries?
- Is the key evenly distributed and stable?
- Do related tables share the key, so joins stay local?
- Do you know which cross-shard operations the application needs, and how they are handled?
- Is there a plan for adding shards?
- Do you monitor each shard, and the split between single-shard and fan-out queries?
