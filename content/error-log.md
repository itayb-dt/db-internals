---
title: "The error log: what the instance says about itself"
updated: 2026-10-31
sources:
  - https://www.postgresql.org/docs/17/runtime-config-logging.html
  - https://www.postgresql.org/docs/17/continuous-archiving.html
---

This article continues from [Server logs](topic:server-logs). It covers the error log: what it holds, how to read an entry, and what makes it grow. It is about **PostgreSQL 17**. The slow query log is a separate subject: see [The slow query log](topic:slow-query-log).

> **How this was checked:** The settings, defaults and severity levels come from the PostgreSQL 17 documentation, listed in the sources. The article has no SQL. The examples of what to look for are common operating practice.

## What it is

The error log is the part of the [server log](topic:server-logs) where the instance reports **about itself**. It is the first place to look when something is wrong, and often the only place that says why.

Typical contents:

- **Errors and warnings.** A statement that failed, a connection that was refused, a deadlock that was resolved.
- **Startup and shutdown,** including a crash and the recovery after it.
- **Checkpoints.** On by default, with how many buffers were written and how long it took. See [WAL and checkpoints](topic:wal).
- **Long autovacuum runs.** Autovacuum actions that ran for 10 minutes or more are logged by default.
- **Optional events,** if you turn them on: lock waits, temporary files, connections.

## Severity levels

Every message has a severity. The server writes only messages at or above the level in `log_min_messages`, which is **warning** by default.

| Level | Meaning |
|---|---|
| `DEBUG1` to `DEBUG5` | Detail for developers |
| `INFO` | Information the user asked for, such as the output of a verbose vacuum |
| `NOTICE` | Helpful information, such as a truncated long name |
| `WARNING` | A likely problem |
| `ERROR` | An error that aborted the current command |
| `LOG` | Information for administrators, such as checkpoint activity |
| `FATAL` | An error that aborted the current session |
| `PANIC` | An error that aborted all sessions |

`ERROR` is one command that failed, `FATAL` is one session lost, and `PANIC` is the whole instance. A `PANIC` in the log deserves attention at once. A full disk under the write-ahead log, for example, ends in one.

## Reading an entry

Each entry starts with a **prefix** you can configure. The default is a time stamp and the process ID. A richer prefix adds the user, database and application name, which makes entries much easier to trace. After the prefix come the severity and the message. Many errors add more lines: `DETAIL`, `HINT`, `CONTEXT` and `STATEMENT`. How much is written is set by the verbosity setting.

A statement that causes an error is logged **with its text**, because `log_min_error_statement` defaults to error. See the warning about sensitive data in [the slow query log](topic:slow-query-log), which applies here too.

The log can be written as plain text (the default), CSV or JSON. JSON and CSV need the logging collector, and are the easier ones for tools to read.

The animation shows entries with their severity, and then a repeating error that fills the log, and how to find it.

<iframe src="error-log/demo.html" title="Animation: error log entries with severities LOG, WARNING, ERROR and FATAL. Then the same connection error repeats 4,800 times and fills the log, and the most frequent message is the one to fix" width="800" height="450"></iframe>

*The animation repeats about every 26 seconds.*

## What to look for

- **A repeating error.** The same message many times a minute is usually an application stuck in a retry loop. It is a problem by itself, and it makes the log grow.
- **Connection errors.** A refused connection because there are too many clients points to connection handling. See [load balancers and connection pooling](topic:load-balancer).
- **Failed archive commands.** The archiver's failures are reported here, and some are visible nowhere else. See [WAL and checkpoints](topic:wal).
- **Deadlocks.** The log names the sessions and statements involved. See [Deadlock](topic:deadlock).
- **Out of space errors.** A message that a file could not be written for lack of space is the late sign of the problem this track is about.
- **Crashes and restarts.** A process that ended unexpectedly, and the recovery that followed.

## What makes it grow

- **A repeating error,** as above. This is the most common reason.
- **A lower minimum severity.** Debug levels write a great deal.
- **Higher verbosity,** which adds fields to each message.
- **Optional events** turned on and left on, such as every connection.

Rotation and removal work as for the whole log. See [Server logs](topic:server-logs).

## Managed and self-managed

On a managed service, you usually read the error log through the provider's console or an export, and the provider decides how long it keeps it. On a system you run, you read the files, and you own their rotation.

## Why it matters for performance

**What it costs.** Writing the log costs I/O. A storm of repeating errors costs more, and takes disk with it.

**When it shows up.** During incidents and after a change that makes the application fail.

**How to measure.** The rate of errors per minute, the most frequent message, and the size of the log directory.

**When to worry.** As a rule of thumb, when one message repeats continuously, when `FATAL` or `PANIC` entries appear, or when the log grows much faster than usual.

**What you can change.** Fix the cause of the repeating error, keep `log_min_messages` at its default unless you are debugging, and include a useful prefix.

## Common mistakes

- Never reading the log until an outage.
- Ignoring a repeating error because "the application works".
- Turning on debug logging and forgetting it.
- Sharing the log raw with people who should not see the values in it.
- Looking only at the end of the log, and missing the first error of a chain.

## Checklist

- Know where the error log is and how to read it.
- Use a prefix that shows user, database and application.
- Look for the most frequent message.
- Treat `FATAL` and `PANIC` as incidents.
- Fix repeating errors.
- Control who can read the log.
