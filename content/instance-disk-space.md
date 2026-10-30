---
title: "The instance is running out of disk space"
updated: 2026-10-31
sources:
  - https://www.postgresql.org/docs/17/continuous-archiving.html
  - https://www.postgresql.org/docs/17/wal-configuration.html
  - https://www.postgresql.org/docs/17/runtime-config-logging.html
  - https://www.postgresql.org/docs/17/runtime-config-resource.html
  - https://www.postgresql.org/docs/17/storage-file-layout.html
---

This article is the start of the "The DB Instance is running out of disk space" track. It is about the **instance**: the disk of one PostgreSQL server, and everything on it. It is about **PostgreSQL 17**.

> **How this was checked:** The facts about the write-ahead log, logging and temporary files come from the PostgreSQL 17 documentation, listed in the sources. The advice on order and the examples are common operating practice. The article has no SQL, and the thresholds are rules of thumb.

## Two levels, two tracks

When a disk fills, it helps to separate two levels:

| Level | Question | Where it is covered |
|---|---|---|
| **The database** | Which database is big, and why is it growing? | The track [My database is large](topic:database-size-problem) |
| **The instance** | What else on this server uses the disk? | This track |

An [instance](topic:instance) holds several databases, and it also holds things that belong to no database: the write-ahead log, the server logs and temporary files. On a system you manage yourself, the same disk may also hold things that have nothing to do with PostgreSQL.

This track stays at the instance level. When a database turns out to be the largest consumer, it hands over to the track about the database.

## Check these two things first

Do not start with the write-ahead log or the logs. In most cases the answer is one of these two:

1. **Which database is the largest?** PostgreSQL can report the size of each database. If one database is clearly the biggest consumer, the problem is inside it. Go to [Why a database suddenly grows](topic:database-growth-causes), and to the rest of the track on large databases.
2. **What changed recently?** Find out when the disk usage started to rise, and what happened then: a deployment, a new job, an import, a stopped replica or backup, a change in a setting. A disk that has been slowly filling for months is a capacity problem. One that jumped yesterday has a cause.

These two checks take a few minutes and usually point to the answer. Only when they do not, look at the instance-level consumers.

The animation shows a disk that is nearly full, the two first checks, and how the second one points to the write-ahead log.

<iframe src="instance-disk-space/demo.html" title="Animation: the disk of an instance with data, the write-ahead log, logs, temporary files and other things. The log grows until the disk is 94 percent full. Check one finds the largest database unchanged. Check two finds that the archive target became unreachable" width="800" height="450"></iframe>

*The animation repeats about every 28 seconds.*

## Common reasons an instance runs out of space

Almost every case is one of these. Each has a short explanation here and a place in the track.

1. **The databases grew.** The data directory is the largest part of most instances. It grows because more rows are inserted, which is healthy, or because space is wasted by dead rows, indexes or large values. This is the first thing to rule in or out, and it is the subject of the track [My database is large](topic:database-size-problem).
2. **The write-ahead log piled up.** The log is normally recycled. It grows when archiving fails or lags, when a replication slot keeps it for a consumer that is gone or slow, or during heavy writes. This is the dangerous one, because a full log disk shuts the server down. See [WAL and checkpoints](topic:wal).
3. **The logs grew.** Verbose logging, an application that repeats the same error in a loop, a slow query threshold set too low, or old files that nothing removes. See [Server logs](topic:server-logs), [the error log](topic:error-log) and [the slow query log](topic:slow-query-log).
4. **Temporary files.** A large sort or hash that does not fit in memory is written to disk until the query ends. A heavy report, or several at once, can use a lot for a short time.
5. **Something outside PostgreSQL.** On a system you run, backups stored on the same disk, other software, snapshots and a poor disk layout use space whatever PostgreSQL does. On a managed service this is mostly not your concern. See [Managed or self-managed](topic:disk-outside-postgres).
6. **Capacity was never planned.** The disk was sized for last year. Steady, healthy growth with no one watching the trend ends the same way.

The two checks above find reason 1 and 6 quickly. The rest need a look at the parts of the instance.

## What lives on the disk of an instance

| What | Where | Grows when | Covered in |
|---|---|---|---|
| **The data** | The data directory, one folder per database | Rows are added, or space is wasted | [My database is large](topic:database-size-problem) |
| **The write-ahead log** | The `pg_wal` directory | Archiving fails or lags, a replication slot holds the log, or writes are heavy | [WAL and checkpoints](topic:wal) |
| **The server logs** | The log directory | Logging is verbose, an error repeats, or logs are never removed | [Server logs](topic:server-logs), [the error log](topic:error-log), [the slow query log](topic:slow-query-log) |
| **Temporary files** | A temporary area inside the data directory | Big sorts or hashes do not fit in memory | Below |
| **Everything else on the disk** | The rest of the volume | Backups, other software, bad disk layout | [Managed or self-managed](topic:disk-outside-postgres) |

**Temporary files** are the quiet one. A large sort or hash that does not fit in the memory allowed for it is written to disk, and removed when the query ends. A heavy report, or many at once, can use many gigabytes for a short time. By default there is no limit on this, and a setting (`temp_file_limit`) can cap it per process, so the query is cancelled instead of filling the disk.

## Which one is it?

| What you see | Look at |
|---|---|
| The data directory is the part that grows | The largest database, then [My database is large](topic:database-size-problem) |
| `pg_wal` is large | [WAL and checkpoints](topic:wal) |
| The log directory is large | [Server logs](topic:server-logs), then [the error log](topic:error-log) and [the slow query log](topic:slow-query-log) |
| Disk use rises and falls with heavy queries | Temporary files |
| PostgreSQL's own numbers do not add up to the disk usage | [Something outside PostgreSQL](topic:disk-outside-postgres) |

## Why the write-ahead log is the dangerous one

If the disk that holds the write-ahead log fills, PostgreSQL does a **PANIC shutdown**. The documentation says no committed transactions are lost, but the database stays offline until you free space. A full data disk usually makes writes fail. A full disk under the write-ahead log is more serious, because the server cannot continue. This is why the write-ahead log disk deserves the earliest alert.

Never delete files from `pg_wal` by hand to free space. They may still be needed for recovery, for a replica, or for archiving. Fix the cause that holds them, and let PostgreSQL remove them.

## Why it matters for performance

**What it costs.** A full disk first means errors and then an outage. A nearly full disk also leaves no room for maintenance that needs space, such as rewriting a table.

**When it shows up.** After a change, a stuck consumer, a logging change, or steady growth that nobody tracked.

**How to measure.** The size of each database, the size of the write-ahead log, the size of the logs, and the free space on every volume, recorded over time.

**When to worry.** As a rule of thumb, start worrying when less than a few weeks of growth are left, and act when it is days. Alert on time to full, and alert on the write-ahead log disk earliest.

**What you can change.** Remove what is wasted, fix what holds the write-ahead log, change what is logged, cap temporary files, and add space where growth is healthy.

## Common mistakes

- Deleting write-ahead log files by hand.
- Looking at the write-ahead log first, when one database is the cause.
- Watching only the percentage used, and not the growth rate.
- Forgetting that the logs and temporary files share the disk.
- Not asking what changed.

## Checklist

- Which database is the largest, and did it grow?
- What changed, and when did the disk start filling?
- Is `pg_wal` large? Check archiving and replication slots.
- Is the log directory large? Check what is logged and how it is rotated.
- Do PostgreSQL's numbers add up to the disk usage? If not, look outside PostgreSQL.
- Record sizes over time and alert on time to full.
