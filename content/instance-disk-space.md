---
title: "Low free disk space: the problem"
updated: 2026-11-01
sources:
  - https://www.postgresql.org/docs/17/continuous-archiving.html
  - https://www.postgresql.org/docs/17/wal-configuration.html
  - https://www.postgresql.org/docs/17/functions-admin.html
  - https://www.postgresql.org/docs/17/storage-file-layout.html
---

This article starts the problem track **Low free disk space**. It explains what the problem is, then the impact and why you should care. Last it explains how to get the data that shows the problem. Later in the track you will see the potential root causes, and what more data is needed to tell whether each one is really the cause. It is about the **instance**: the disk of one PostgreSQL server, and everything on it.

## What it is

The disk that holds a PostgreSQL instance is almost full, or filling quickly. An [instance](topic:instance) holds several databases, and also things that belong to no database: the write-ahead log, the server logs and temporary files. On a system you manage yourself, the same disk may hold other things too.

There are two levels. This track is about the **instance**. When a database turns out to be the largest consumer, it hands over to the problem track [Large database](topic:database-size-problem).

## The impact: why you should care

- **A full disk stops writes.** When the data disk fills, writes fail with errors, and the application fails with them.
- **A full disk under the write-ahead log shuts PostgreSQL down.** The documentation says it does a PANIC shutdown. No committed transaction is lost, but the instance stays offline until you free space.
- **Backups and maintenance fail.** They need free space to work. For example, rewriting a table needs room for a second copy.
- **Recovery is hard on a full disk.** The usual ways to free space need some space to start.
- **It is a deadline.** Unlike a slow query, a disk fills at a rate, and there is a day when it ends.

As a rule of thumb, start worrying when less than a few weeks of growth are left, and act when it is days. The disk under the write-ahead log deserves the earliest alert.

Never delete files from `pg_wal` by hand to free space. They may still be needed for recovery, a replica or archiving.

## How to get the data

The signals come from **the operating system or the cloud monitoring**, and from **PostgreSQL functions**.

| What you look at | Where it comes from | What it tells you |
|---|---|---|
| Free space and used percentage of each volume | Operating system tools, or the cloud provider's monitoring (for example a free storage space metric in CloudWatch on AWS) | How full it is |
| The trend of free space over days | The same, recorded over time | How fast it is filling, and the time left |
| Size of each database | PostgreSQL function `pg_database_size` | Which database is the largest |
| Size of the write-ahead log | PostgreSQL function `pg_ls_waldir`, or the `pg_wal` directory | Whether the log has piled up |
| Size of the log files | PostgreSQL function `pg_ls_logdir`, or the log directory | Whether the logs grew |
| Anything else on the volume | Operating system tools only | Files that PostgreSQL does not know about |

On a **managed service** the volume metric comes from the provider, and the PostgreSQL functions are still yours. The operating system's view of other files is usually not available, and usually not needed.

The most useful number is not the percentage but the **time to full**: free space divided by the rate at which it shrinks. Record sizes over time, because the database does not keep that history.

## The first two checks

Do not start with the write-ahead log or the logs. In most cases the answer is found by these two checks:

1. **Which database is the largest?** If one database is clearly the biggest consumer, the problem is inside it. Go to [Why a database suddenly grows](topic:database-growth-causes) and the rest of the Large database track.
2. **What changed recently?** Find when the disk usage started to rise and what happened then: a deployment, a new job, an import, a stopped replica or backup, a change in a setting. A disk that has been filling slowly for months is a capacity problem. One that jumped yesterday has a cause.

These checks take a few minutes. The animation shows a nearly full disk and the two checks.

<iframe src="instance-disk-space/demo.html" title="Animation: the disk of an instance with data, the write-ahead log, logs, temporary files and other things. The log grows until the disk is 94 percent full. Check one finds the largest database unchanged. Check two finds that the archive target became unreachable" width="800" height="450"></iframe>

*The animation repeats about every 28 seconds.*

## What next

If the two checks do not point to the answer, the next article, [Common root causes of low free disk space](topic:disk-space-causes), lists the usual reasons.

## Checklist

- How full is each volume, and how fast is it filling? How long is left?
- Which database is the largest, and did it grow?
- What changed, and when did the disk start to fill?
- Is `pg_wal` large? Is the disk under it close to full?
- Never remove files from `pg_wal` yourself.
