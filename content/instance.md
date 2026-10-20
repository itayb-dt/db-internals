---
title: "The instance: the parts of a PostgreSQL server"
updated: 2026-10-21
sources:
  - https://www.postgresql.org/docs/17/creating-cluster.html
  - https://www.postgresql.org/docs/17/tutorial-arch.html
  - https://www.postgresql.org/docs/17/storage-file-layout.html
  - https://www.postgresql.org/docs/17/manage-ag-overview.html
  - https://www.postgresql.org/docs/17/manage-ag-tablespaces.html
  - https://www.postgresql.org/docs/17/database-roles.html
  - https://www.postgresql.org/docs/17/monitoring-stats.html
  - https://www.postgresql.org/docs/17/runtime-config-logging.html
---

This article is the map of the whole server. It is short on purpose: each part gets a few lines here and its own article. It is about **PostgreSQL 17**.

> **How this was checked:** The facts come from the PostgreSQL 17 documentation. The SQL was run on PostgreSQL 16.2, and the output shown comes from that server. Database and file numbers are examples and differ on every server.

## What an instance is

An **instance** is one running PostgreSQL server together with the one directory where it keeps everything, the **data directory**. The documentation calls this a **database cluster**: "a collection of databases that is managed by a single instance of a running database server". The word is misleading, because it has nothing to do with clustering many servers. SQL Server also says "instance", and MySQL says "server".

An instance holds several **databases**. Everything below them, such as tables and indexes, lives inside one database. Everything above them is shared by all.

## The main components

| Level | Component | In one line | Article |
|---|---|---|---|
| Instance | Processes | A supervisor, one process per connection, and background workers | below |
| Instance | Buffer pool | Shared memory cache of pages | [Buffer pool](topic:buffer) |
| Instance | WAL | The log written before the data files | [WAL and checkpoints](topic:wal) |
| Instance | Server logs | Where the server reports errors and slow statements | [Server logs](topic:server-logs) |
| Instance | Roles, tablespaces, configuration | Defined once, for all databases | [Databases, schemas and roles](topic:databases) |
| Database | Databases and schemas | Separate worlds that share the server | [Databases, schemas and roles](topic:databases) |
| Table | Heap | The rows of a table | [Heap table](topic:heap) |
| Table | Indexes | Structures that find rows fast | [Index](topic:index) |
| Table | TOAST | A hidden table for large values | [TOAST](topic:toast) |
| Disk | Files and tablespaces | How all of it is stored on disk | [Files and tablespaces](topic:files-tablespaces) |

## The picture

[![The components of a PostgreSQL instance: processes, shared memory with the buffer pool, WAL and logs shared by all databases, several databases, and inside a database the tables with heap, indexes and TOAST, all stored as files in the data directory and tablespaces](instance/instance-overview.png)](instance/instance-overview.png)

*Click the image to open it full size.*

## Moving between the levels

The animation starts at the instance, goes into the databases, and then into one table.

<iframe src="instance/demo.html" title="Animation: the view moves from the instance level (processes, buffer pool, WAL and logs) to the databases inside it, and then to one table with its heap, indexes and TOAST" width="800" height="450"></iframe>

*The animation repeats about every 10 seconds.*

## Each part in a few lines

**Processes.** A supervisor process, called the **postmaster**, waits for connections and starts a new **backend** process for each one. Background workers do the housekeeping: the checkpointer, the background writer, the WAL writer, autovacuum and others. The postmaster itself does not appear in `pg_stat_activity`. On my test server:

```sql
SELECT backend_type, count(*) FROM pg_stat_activity GROUP BY 1 ORDER BY 2 DESC;
```

```
client backend              1
walwriter                   1
autovacuum launcher         1
logical replication launcher 1
background writer           1
checkpointer                1
```

**Shared memory.** The [buffer pool](topic:buffer) caches the pages that every connection reads and changes. A smaller area holds WAL buffers.

**WAL.** Every change is written to the write-ahead log before the data files. There is **one WAL for the whole instance**, whatever the number of databases.

**Server logs.** Errors, checkpoints, slow statements and autovacuum runs go to the server log. See [Server logs](topic:server-logs).

**Databases.** A client names the database in its connection request, and **cannot access more than one database per connection**. Roles are global across the instance, not per database. A new instance has the databases `postgres`, `template1` and `template0`.

```sql
SELECT oid, datname FROM pg_database ORDER BY oid;
```

```
  oid | datname
    1 | template1
    4 | template0
    5 | postgres
19183 | app
```

**Tables.** A table is a [heap](topic:heap) of pages that holds the rows, plus its [indexes](topic:index), plus a [TOAST](topic:toast) table for large values. Each of these is a separate set of files. A table can also be split into many with [partitioning](topic:partitioning).

**Files and tablespaces.** The data directory has one folder, `base/`, with a subfolder per database. A **tablespace** is another location on disk where you can put tables and indexes, for example faster storage. A new instance has two: `pg_default` and `pg_global`.

```sql
CREATE TABLE orders (id int PRIMARY KEY, note text);

SELECT 'table' AS part, pg_relation_filepath('orders') AS file
UNION ALL SELECT 'index', pg_relation_filepath('orders_pkey')
UNION ALL SELECT 'TOAST table', pg_relation_filepath(reltoastrelid) FROM pg_class WHERE relname = 'orders';
```

```
part         file
table        base/19183/19184
index        base/19183/19189
TOAST table  base/19183/19187
```

The folder name `19183` is the object ID of the database `app` from the list above. Every table, index and TOAST table has its own file number inside it. The top level of the data directory shows the shared parts (listing it needs superuser rights):

```sql
SELECT * FROM pg_ls_dir('.') AS entry
WHERE entry IN ('base', 'global', 'pg_wal', 'pg_tblspc', 'pg_xact', 'postgresql.conf', 'pg_hba.conf', 'PG_VERSION')
ORDER BY 1;

SELECT spcname, pg_tablespace_location(oid) AS location FROM pg_tablespace;
```

`base` holds the databases, `global` holds the instance-wide tables, `pg_wal` is the WAL, `pg_xact` records which transactions committed, and `pg_tblspc` links to the tablespaces you create.

## How it compares

- **SQL Server.** An instance also holds several databases, but **each database has its own transaction log**. In PostgreSQL there is one WAL for all.
- **MySQL.** One server holds several "databases", which are what PostgreSQL calls schemas. A PostgreSQL database is a stronger boundary.
- **Connections.** PostgreSQL starts a process per connection, so many short connections are costly. A connection pooler in front of the server is common. Other servers use threads.

These comparisons are from general knowledge, not from the PostgreSQL documentation.

## Where to look when something is wrong

| Symptom | Level | Look at |
|---|---|---|
| Queries read from disk a lot | Instance, shared memory | The buffer pool hit ratio |
| Commits are slow, or the disk fills with logs | Instance, WAL | WAL volume and checkpoints |
| A statement is slow | Table | The plan, indexes, the heap |
| Disk space grows | Table and disk | Table and index size, dead rows, TOAST |
| One database affects another | Instance | Shared memory, WAL and connections are shared |
| You need to find out what happened | Instance | The server log |

## Why it matters for performance

**What it gives.** A map. Many performance questions are really "which level?" Knowing which parts are shared tells you where one database, or one busy query, can hurt another: they share the buffer pool, the WAL, the disk and the connection limit.

**What it costs.** Sharing keeps the server simple and efficient, but there are no per-database memory or log limits.

**When to worry** (a rule of thumb): when two databases on one instance have unrelated workloads. A heavy report in one can evict pages another needs. If isolation matters, consider separate instances.

## Practical checklist

- An instance is one server and one data directory.
- Memory, WAL, logs, roles and tablespaces are shared by all databases.
- A connection uses one database. A database has its own files in `base/`.
- A table is heap, indexes and TOAST, each stored as files.
- Use `pg_relation_filepath()` to find a table's files.
- Ask first: which level is the problem at?
