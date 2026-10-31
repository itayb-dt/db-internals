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
---

This is the starting point: a map of the whole server. Each part gets a few lines here and has its own article. It is about PostgreSQL, and the facts come from its documentation.

## What an instance is

An **instance** is one running PostgreSQL server, together with the one directory where it keeps all its data, the **data directory**. The documentation calls this a **database cluster**. The word is misleading: it does not mean a group of servers, only one server and its data. SQL Server also says "instance", and MySQL says "server".

An instance holds several **databases**. Some things are shared by all of them, and some belong to one database.

## The main components

| Level | Component | In one line | Article |
|---|---|---|---|
| Instance | Processes | A supervisor, one process for each connection, and background workers | below |
| Instance | Buffer pool | Shared memory that caches pages | [Buffer pool](topic:buffer) |
| Instance | WAL | The log that is written before the data files | [WAL and checkpoints](topic:wal) |
| Instance | Server logs | Where the server reports errors and slow statements | [Server logs](topic:server-logs) |
| Instance | Roles, tablespaces, configuration | Defined once, for all databases | [Databases, schemas and roles](topic:databases) |
| Database | Databases and schemas | Separate worlds that share one server | [Databases, schemas and roles](topic:databases) |
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

**Processes.** A supervisor process, the **postmaster**, waits for connections and starts a new **backend** process for each one. Background workers do the housekeeping, such as writing dirty pages to disk, writing the log, and running autovacuum.

**Shared memory.** The [buffer pool](topic:buffer) keeps copies of table and index pages in memory, and every connection uses it.

**WAL.** Every change is written to the write-ahead log before it reaches the data files. There is **one WAL for the whole instance**, however many databases it has.

**Server logs.** The server writes errors, slow statements and other events to its log.

**Databases.** A connection works in **one database**, chosen when it connects, and cannot reach into another. Roles, which are the users and their rights, are shared by the whole instance.

**Tables.** A table is a heap that holds the rows, its indexes, and a TOAST table for large values. A table can also be split into many with [partitioning](topic:partitioning).

**Files and tablespaces.** Everything is stored as files in the data directory. It has a folder `base` with a subfolder for each database, a folder `pg_wal` for the log, and a few more for the shared parts. A **tablespace** is another place on disk where you can put tables and indexes, for example on faster storage.

## How it compares

- **SQL Server.** An instance also holds several databases, but **each database has its own transaction log**. In PostgreSQL there is one WAL for all.
- **MySQL.** One server holds several "databases", which are what PostgreSQL calls schemas. A PostgreSQL database is a stronger boundary.
- **Connections.** PostgreSQL starts a process for each connection, so many short connections are costly, and a connection pooler in front of the server is common. Other servers use threads.

These comparisons are from general knowledge, not from the PostgreSQL documentation.

## Where to look when something is wrong

| Symptom | Level | Part to look at |
|---|---|---|
| Queries read from disk a lot | Instance | The buffer pool |
| Commits are slow, or logs fill the disk | Instance | The WAL and checkpoints |
| One statement is slow | Table | The plan, the indexes and the heap |
| Disk space keeps growing | Table and disk | Table size, dead rows and TOAST |
| One database slows another | Instance | Memory, WAL and connections are shared |
| You need to know what happened | Instance | The server log |

## Why it matters for performance

Many performance questions are really "which level is this?" Knowing what is shared tells you how one busy database or query can hurt another: they share the buffer pool, the WAL, the disk and the connection limit.

The price of this sharing is that there are no separate memory or log limits per database. As a rule of thumb, when two databases have unrelated heavy workloads, consider putting them on separate instances.

## Practical checklist

- An instance is one server and one data directory.
- Memory, the WAL, the logs, roles and tablespaces are shared by all databases.
- A connection uses one database.
- A table is a heap, indexes and TOAST, stored as files.
- When something is slow, first ask which level it is at.
