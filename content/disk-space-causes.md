---
title: "Common root causes of low free disk space"
updated: 2026-11-01
sources:
  - https://www.postgresql.org/docs/17/continuous-archiving.html
  - https://www.postgresql.org/docs/17/wal-configuration.html
  - https://www.postgresql.org/docs/17/runtime-config-logging.html
  - https://www.postgresql.org/docs/17/runtime-config-resource.html
  - https://www.postgresql.org/docs/17/storage-file-layout.html
---

This article continues from [Low free disk space: the problem](topic:instance-disk-space). It is a quick overview of the potential root causes, with a short explanation of each. The rest of the track discusses the causes one by one. It is about **PostgreSQL 17**.

> **How this was checked:** The facts about the write-ahead log, logging and temporary files come from the PostgreSQL 17 documentation, listed in the sources. The remarks about managed services, backups and snapshots are common operating practice. The article has no SQL.

## What lives on the disk of an instance

| What | Where | Grows when |
|---|---|---|
| **The data** | The data directory, one folder per database | Rows are added, or space is wasted |
| **The write-ahead log** | The `pg_wal` directory | Archiving fails or lags, a replication slot holds the log, or writes are heavy |
| **The server logs** | The log directory | Logging is verbose, an error repeats, or logs are never removed |
| **Temporary files** | A temporary area inside the data directory | Big sorts or hashes do not fit in memory |
| **Everything else on the disk** | The rest of the volume | Backups, other software, bad disk layout |

## Potential root causes

1. **The databases grew** ([details](topic:database-growth-causes)). The data directory is the largest part of most instances. It grows because more rows are inserted, which is healthy, or because space is wasted by dead rows, indexes or large values. The problem track [Large database](topic:database-size-problem) covers it.
2. **The write-ahead log piled up** ([details](topic:wal)). The log is normally recycled. It grows when archiving fails or lags, when a replication slot keeps it for a consumer that is gone or slow, or during heavy writes. This is the dangerous one, because a full log disk shuts the server down.
3. **The server logs grew** ([details](topic:server-logs)). Verbose logging, old files that nothing removes, and an application that repeats the same error ([the error log](topic:error-log)), or a slow query threshold that is too low ([the slow query log](topic:slow-query-log)).
4. **Temporary files.** A large sort or hash that does not fit in memory is written to disk until the query ends. A heavy report, or several at once, can use a lot for a short time. By default there is no limit, and a setting (`temp_file_limit`) can cap it for each process so the query is cancelled instead of filling the disk.
5. **Something outside PostgreSQL** ([details](topic:disk-outside-postgres)). On a system you run, backups kept on the same disk, other software, snapshots and a poor disk layout use space whatever PostgreSQL does. On a managed service this is mostly not your concern.
6. **Capacity was never planned.** The disk was sized for last year. Steady, healthy growth with no one watching the trend ends the same way.

## Which one is it?

| What you see | Look at |
|---|---|
| The data directory is the part that grows | The largest database, then [Large database](topic:database-size-problem) |
| `pg_wal` is large | [WAL and checkpoints](topic:wal) |
| The log directory is large | [Server logs](topic:server-logs), then [the error log](topic:error-log) and [the slow query log](topic:slow-query-log) |
| Disk use rises and falls with heavy queries | Temporary files |
| PostgreSQL's own numbers do not add up to the disk usage | [Something outside PostgreSQL](topic:disk-outside-postgres) |

## Checklist

- Which part of the disk grew: data, log, logs, temporary files, or something else?
- Do PostgreSQL's numbers add up to the volume's usage?
- If a database is the largest consumer, hand over to the Large database track.
