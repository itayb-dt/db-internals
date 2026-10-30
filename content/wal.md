---
title: "WAL and checkpoints: the log written before the data"
updated: 2026-10-31
sources:
  - https://www.postgresql.org/docs/17/wal-intro.html
  - https://www.postgresql.org/docs/17/wal-configuration.html
  - https://www.postgresql.org/docs/17/runtime-config-wal.html
  - https://www.postgresql.org/docs/17/continuous-archiving.html
  - https://www.postgresql.org/docs/17/warm-standby.html
  - https://www.postgresql.org/docs/17/runtime-config-replication.html
  - https://www.postgresql.org/docs/17/view-pg-replication-slots.html
  - https://www.postgresql.org/docs/17/monitoring-stats.html
---

This article is about the **write-ahead log (WAL)** of **PostgreSQL 17**: what it is, what a checkpoint does, and why its size can grow until it fills a disk. SQL Server keeps a transaction log for each database, and InnoDB has a redo log, which is the closest match. PostgreSQL has **one WAL for the whole instance**, whatever the number of databases.

> **How this was checked:** The settings, defaults and behaviours of the log, archiving and slots come from the PostgreSQL 17 documentation, listed in the sources. The basic description of the log is from the documentation's introduction, which I did not re-read for this version. The pages for the size function and for the archiver view were partly summarised, so please confirm those two against the live pages. The three queries below were **not run**, because there is no server here.

## What it is

Before PostgreSQL changes a data file, it writes a description of the change to the log. At commit, it makes sure that the log is on disk. The data files are written **later**, in the background. If the server crashes, it replays the log from the last checkpoint and brings the data files up to date.

This is why a commit can return before the data files are written: the log already holds everything needed to redo the change, and writing it is a fast, sequential append. Writing scattered pages to the data files would be slower.

The log is split into **segment files** in the `pg_wal` directory.

The animation follows one change from memory to the log, to the data files, and then shows what happens to the log when archiving fails.

<iframe src="wal/demo.html" title="Animation: an update changes a page in memory and a record in the log. Commit flushes the log. A checkpoint writes the page to the data files and the old log segments are recycled. When the archive command fails the log segments pile up until the disk is full" width="800" height="450"></iframe>

*The animation repeats about every 30 seconds.*

## Checkpoints

A **checkpoint** writes all changed pages that are still only in memory (see the [buffer pool](topic:buffer)) to the data files. After it, the log before that point is not needed for crash recovery, and its segments can be **recycled or removed**.

A checkpoint has a cost: a burst of writes. It is a balance:

- **More frequent checkpoints** shorten recovery after a crash, but write more. They also make the log larger, because after each checkpoint the first change to a page writes the **whole page** to the log.
- **Less frequent checkpoints** write less overall, but recovery takes longer and more log is kept.

A checkpoint starts every 5 minutes by default, or sooner if the log is about to exceed `max_wal_size` (1 GB by default).

## What else uses the log

The log is the base for more than crash recovery:

- **Replication.** A standby receives the log and replays it.
- **Archiving and point-in-time recovery.** Segments are copied to an archive so you can restore to any moment.
- **Logical decoding.** Logical replication reads the log and turns it into row changes. The setting `wal_level` controls how much goes into it, and `logical` writes more than the default.

Each of these can **hold segments back**, which is where the size problem begins.

## How big should it be?

The size of `pg_wal` depends on `min_wal_size` (80 MB by default), `max_wal_size` (1 GB by default), and how much log was written in recent checkpoint cycles. After a checkpoint, segments that are no longer needed are recycled or removed. A log that sits between the two limits is normal.

`max_wal_size` is a **soft limit**. The documentation says it can be exceeded under heavy load, a failing archive command, or a high `wal_keep_size`.

If the disk that holds `pg_wal` fills up, PostgreSQL does a **PANIC shutdown**. No committed transaction is lost, but the instance stays offline until you free space. This is the most serious way an instance can run out of disk. See [The instance is running out of disk space](topic:instance-disk-space).

## Why it grows

PostgreSQL cannot remove a segment while someone may still need it. Three things commonly hold them.

### 1. Archiving fails or falls behind

If archiving is on, a segment cannot be removed until it has been archived. When the archive command fails, PostgreSQL retries it periodically, and **the log keeps filling until the problem is fixed**. The same happens if archiving cannot keep up with the rate at which the log is written. Typical causes are a full or unreachable archive target, a wrong credential, or a command that returns an error.

### 2. A replication slot holds the log

A replication slot makes the server keep the log until the slot's consumer has read it. If the consumer is gone, for example a replica that was shut down or a logical subscriber that stopped, the slot keeps the log indefinitely. The documentation warns that slots can retain so many segments that they fill the log directory. The limit on how much a slot may retain, `max_slot_wal_keep_size`, is **unlimited by default**.

### 3. Heavy writing, and a large `wal_keep_size`

A big load, a mass update or a table rewrite writes a lot of log in a short time, and the log can pass its soft limit until the checkpoint catches up. Updating large values writes the new value to the log too. A high `wal_keep_size` keeps a fixed amount of log on purpose, for replicas that fall behind, whether or not it is needed.

## How to see it

**How big is `pg_wal`?** A function lists the log files and their sizes:

```sql
-- not run: needs a live server and the pg_monitor role or a superuser
SELECT pg_size_pretty(sum(size)) AS wal_size, count(*) AS files FROM pg_ls_waldir();
```

**Is archiving failing?** The archiver view counts successes and failures and names the last failure:

```sql
-- not run: needs a live server, and archiving to be on
SELECT archived_count, failed_count, last_failed_wal, last_failed_time FROM pg_stat_archiver;
```

A `failed_count` that keeps rising, or a `last_failed_time` close to now, means archiving is broken. Some archiver failures are not counted there, so also read [the error log](topic:error-log).

**Which slot holds the log?**

```sql
-- not run: needs a live server
SELECT slot_name, active, wal_status,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS retained
FROM pg_replication_slots
ORDER BY pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) DESC NULLS LAST;
```

A slot that is not active and retains a lot is the usual culprit. The status `lost` means the slot fell so far behind that the log it needed is gone.

## What to do

| Cause | Fix | Trade-off |
|---|---|---|
| Archiving fails | Fix the archive command or its target first. The log is removed on its own once archiving catches up. | None. Do this first. |
| A slot with no consumer | Drop the slot, or bring the consumer back. | The consumer of a dropped slot must be rebuilt. |
| A slot that may lag again | Set `max_slot_wal_keep_size`, so a slot that falls too far is invalidated instead of filling the disk. | The consumer may need to be rebuilt. |
| Heavy bursts | Spread the load out, or give the log a bigger disk. | More space, or a slower load. |
| High volume in general | Turn on `wal_compression` (off by default). | Extra CPU. |
| A large `wal_keep_size` | Lower it if replicas do not need it. | A replica that falls behind may fail to catch up. |

**Never delete files from `pg_wal` by hand.** They may still be needed for recovery, a replica or archiving. Removing the wrong one can make recovery impossible. Fix the cause, and PostgreSQL cleans up.

## Why it matters for performance

**What it costs.** Every change is written twice: once to the log, once later to the data files. Checkpoints cost bursts of I/O, and a large log costs disk.

**When it shows up.** Checkpoint cost shows under heavy writes. Log size shows after an archiving failure, a stuck replica or subscriber, or a big load.

**How to measure.** The size of `pg_wal` over time, the archiver counters, and the retained size and status of each slot. The [error log](topic:error-log) reports checkpoints, and `log_checkpoints` is on by default.

**When to worry.** As a rule of thumb, when `pg_wal` is many times `max_wal_size` and still rising, when archiving has failed recently, or when a slot is inactive and retaining a lot. Alert on the log disk earlier than on the data disk.

**What you can change.** The table above, and the checkpoint settings for the balance between write bursts and recovery time.

## Common mistakes

- Deleting log files by hand.
- Leaving a slot behind after removing a replica.
- Fixing the disk size but not the archive command.
- Setting `max_slot_wal_keep_size` without knowing which consumers can be rebuilt.
- Alerting on the data disk and not on the log disk.
- Shortening the checkpoint interval to speed up recovery, and getting more log and more writes.

## Checklist

- Know what a checkpoint is and how often one happens.
- Check the size of `pg_wal`, and compare it with `max_wal_size`.
- Check whether archiving has failed recently.
- List the slots, and look for inactive ones that retain a lot.
- Decide whether a limit on slot retention is acceptable.
- Never remove files from `pg_wal` yourself.
