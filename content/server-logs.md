---
title: "Server logs: what the instance writes, and where it goes"
updated: 2026-10-31
sources:
  - https://www.postgresql.org/docs/17/runtime-config-logging.html
  - https://www.postgresql.org/docs/17/functions-admin.html
---

This article continues from [WAL and checkpoints](topic:wal). It covers the server log in general: where it is written, how it is rotated, and what makes it grow. The two main uses of it have their own articles: [the error log](topic:error-log) and [the slow query log](topic:slow-query-log). It is about **PostgreSQL 17**.

> **How this was checked:** The settings and defaults come from the PostgreSQL 17 documentation, listed in the sources. The article has no SQL. The advice on thresholds is common practice and not from the documentation.

## One log, two uses

PostgreSQL writes **one server log**. It holds:

- **The error log:** what the server reports about itself. See [The error log](topic:error-log).
- **The slow query log:** statements slower than a threshold. PostgreSQL has **no separate slow query log**. Slow statements go to the same log. See [The slow query log](topic:slow-query-log).

Both fill the same files and the same disk, which is why this article treats them together.

## Where it is written

By default the server writes to its standard error stream. A **logging collector** can capture that into files in a log directory (`log`, relative to the data directory, by default), with names based on the time. The log can also be written in other formats, such as CSV or JSON, which tools read more easily, and to the system log.

The collector **rotates** files: it starts a new one after 24 hours or 10 MB by default. It does **not delete old ones**. The documentation says that if you use a file name without time escapes, you should plan to use a log rotation utility to avoid eventually filling the entire disk. A rotation setting that overwrites old files, with a file name that repeats, limits the total.

So the first question is not how much the server logs, but **who removes the old files**.

The animation shows log files appearing every day with nothing to remove them, and then the same with a rotation utility that does.

<iframe src="server-logs/demo.html" title="Animation: a log directory gets a new file every day. Without removal it fills the disk. With a rotation utility that removes files older than five days the disk use stays steady" width="800" height="450"></iframe>

*The animation repeats about every 25 seconds.*

## What makes a log big

The defaults are quiet: warnings and errors, no statements, no connections. The log grows when something makes it noisy:

| Setting | Default | What turning it up does |
|---|---|---|
| `log_min_duration_statement` | -1 (off) | Logs statements slower than the threshold. At 0 it logs **every statement**. |
| `log_statement` | none | `all` logs the text of every statement |
| `log_connections`, `log_disconnections` | off | One line per connection. An application that opens and closes connections constantly can write millions. |
| `log_lock_waits` | off | A line when a session waits too long for a lock |
| `log_temp_files` | -1 (off) | One line per temporary file. At 0 it logs every one. |
| `log_min_messages` | warning | Lower levels write much more |

Two things cause surprises:

- **A repeating error.** An application that retries a failing statement in a loop writes the same error again and again. See [The error log](topic:error-log).
- **Very long statements.** The log holds the text of each statement it records, so a statement with a huge list of values makes a huge line.

## Managed and self-managed

On a **managed service**, the provider usually collects and rotates the log, and may offer a retention period or an export. Check what it keeps, for how long, and how it counts against your storage. On a system you run, **you** configure rotation and removal, and the log directory shares a disk with other things, as [the last article of the track](topic:disk-outside-postgres) explains.

## Why it matters for performance

**What it costs.** Every logged line is an I/O write. Logging every statement on a busy system adds load and fills the disk.

**When it shows up.** After someone turns on verbose logging to debug and forgets to turn it off, and when an application loops on an error.

**How to measure.** The size of the log directory over time, and its growth rate. A function in PostgreSQL lists the log files and their sizes for users with the right role.

**When to worry.** As a rule of thumb, when the logs grow by more than a small share of the disk per day, when nothing removes old files, or when a setting from the table has been changed from its default without a reason.

**What you can change.** Raise the slow-statement threshold, turn off statement and connection logging, rotate and remove old files with a utility or an overwriting file name, ship logs off the host, and fix the error that repeats.

## Common mistakes

- Having no rotation or removal for old files.
- Setting a statement threshold to 0 and leaving it.
- Logging to the same disk as the data and the write-ahead log.
- Reading a log that nobody has changed in months and assuming nothing is wrong.

## Checklist

- Know where the log is written, and which volume it shares.
- Know what rotates it and what removes old files.
- Check which logging settings differ from the defaults.
- Alert on the log directory's size.
