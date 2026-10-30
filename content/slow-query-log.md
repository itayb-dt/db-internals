---
title: "The slow query log: the statements that took too long"
updated: 2026-10-31
sources:
  - https://www.postgresql.org/docs/17/runtime-config-logging.html
  - https://www.postgresql.org/docs/17/auto-explain.html
---

This article continues from [The error log](topic:error-log). It covers the slow query log: what it is, what an entry contains, the risk of personal data, and the two ideas that matter most in its configuration, thresholds and sampling. It is about **PostgreSQL 17**.

> **How this was checked:** The settings, defaults and warnings come from the PostgreSQL 17 documentation, listed in the sources. The article has no SQL. Example thresholds are rules of thumb. The mention of a log analysis tool is general knowledge.

## What it is

PostgreSQL has **no separate slow query log**. It is the [server log](topic:server-logs) with extra entries: the statements that ran for at least a time you set. The setting is `log_min_duration_statement`, in milliseconds. It is off by default.

Why use it, when [query metrics](topic:query-metrics) exist? Metrics show **totals**. They tell you which statement costs the most, but not which single run was slow, or with which values. The slow query log shows **single executions**, with their real values, at the moment they happened.

## What an entry contains

Each entry is a line in the log with:

- **A prefix:** the time and process, and, if you configured it, the user, database and application name.
- **The duration** of the statement.
- **The statement text,** with its **literal values**.
- **Bind parameters,** for statements sent with parameters, unless you turn that off.

For clients that send statements in steps (parse, bind, execute), the durations of the steps are logged independently. The log does not contain the **plan**, or the number of rows. For plans, see the end of this article.

## Warning: it can contain personal data

The log holds the **text of statements with their values**. A query such as `WHERE email = '…'` writes that email address to a file. So can names, account numbers, tokens, and the parameters of prepared statements. The documentation warns that logged statements might reveal sensitive data, and even contain plaintext passwords.

Treat the slow query log as sensitive data:

- **Limit who can read it.** Developers and support often get access to logs more freely than to the database. Do not allow that by default.
- **Do not log bind parameters** if you can avoid it. A setting limits the length of each logged parameter, and zero turns parameter logging off for ordinary statement messages. Its default logs them in full.
- **Remember where the log goes.** Log shippers and monitoring tools copy it to other systems, with their own access and retention.
- **Check the rules that apply to you,** such as privacy regulations. A log with personal data may need the same retention limits as the data itself.
- **Redact before sharing.** Never paste log entries into a ticket or chat without removing the values.

The [error log](topic:error-log) has the same issue, because failing statements are written with their text.

## The two settings that matter

You do not need every option. Two ideas cover most uses.

### Threshold

`log_min_duration_statement` decides which statements are written:

| Value | Meaning |
|---|---|
| -1 | Off. This is the default. |
| 0 | Every statement, with its duration. A flood on a busy system. |
| 1000 (1 second) | Statements that took one second or more |

Choose the threshold from what "slow" means for **your** application:

- Start **high**, such as one second, so you see the worst cases and the log stays small.
- Lower it **for a short time** when you investigate a specific problem, and put it back.
- Be careful with a low threshold on a busy system. Every entry is a write, and the volume can fill the disk.

### Sampling

Sampling reduces the volume when you want to see **borderline** statements without logging all of them. Three settings work together:

- **`log_min_duration_statement`:** statements slower than this are **always** logged.
- **`log_min_duration_sample`:** statements slower than this, but under the first threshold, are logged **only for a fraction** of them.
- **`log_statement_sample_rate`:** that fraction, from 0 to 1. At 0.1, about one in ten of the sampled statements is logged.

For example: always log anything over 2 seconds, and log a tenth of the statements between 200 ms and 2 seconds. You see every serious case and a representative slice of the rest.

A third setting, `log_transaction_sample_rate`, logs **all statements of a fraction of the transactions**. It is useful to see what a whole transaction does, and like every statement-logging option it can add significant overhead.

The animation shows eight statements meeting the two thresholds and the sample, then what one logged entry exposes, and what to do about it.

<iframe src="slow-query-log/demo.html" title="Animation: eight statements. Those over 2,000 ms are always logged, those between 200 and 2,000 ms are sampled, and the rest are ignored. A logged entry contains an email address, which is personal data. Three steps to protect the log" width="800" height="450"></iframe>

*The animation repeats about every 30 seconds.*

## Using what you find

1. **Find the slow statement** in the log, with its duration and values.
2. **Check how often it happens,** with [query metrics](topic:query-metrics). A statement slow once is a different problem from one slow every time.
3. **Look at its plan.** Run it with the values from the log through [EXPLAIN](topic:execution-plan), and compare the estimate with [what happened](topic:actual-plan).
4. **Find the cause** among the [common root causes](topic:slow-query-causes).

Many teams use a tool that reads the log and summarises it, for example a log analyser that groups statements and shows the slowest. It is easier than reading the file.

### Plans in the log

If you need the **plan** of slow statements in the log, an extension module called `auto_explain` can write it there, for statements over a threshold. It is a module that must be loaded, and it has costs: the documentation warns that when the option that records real timing is on, per-plan timing is taken for all statements, and that this can have an extremely negative impact on performance. Sampling is available for it too.

**Remember:** every extension must be checked against your cloud provider before you rely on it. A managed service allows only the extensions on its own list, so confirm that `auto_explain` is allowed for your version.

## Managed and self-managed

On a managed service, the settings above are usually changed through the provider's parameter settings, and the log is read through its console or an export. The names are the same. The provider may limit who can read the log and how long it keeps it, and you should check both, because of the personal data in it.

## Why it matters for performance

**What it costs.** Each logged statement is a write, and the log competes for the same disk as everything else. A threshold that is too low on a busy system can slow the instance and fill the disk.

**When it shows up.** After lowering the threshold to debug and forgetting it, or on a system with a very high statement rate.

**How to measure.** The size of the log and its growth rate, and how many statements are logged per minute.

**When to worry.** As a rule of thumb, when the log grows by a large share of the disk per day, or when the slow query log is the main part of it.

**What you can change.** Raise the threshold, use sampling for the borderline range, turn off parameter logging, rotate and remove old files, and ship the log to a controlled place.

## Common mistakes

- Leaving the threshold at 0.
- Logging bind parameters with personal data and giving everyone access.
- Copying log entries into tickets with the values.
- Using the log instead of metrics to find the biggest cost.
- Using an extension without checking that the cloud provider allows it.

## Checklist

- Is the threshold set from what slow means for you?
- Is sampling used for the borderline range?
- Who can read the log, and where is it shipped?
- Are bind parameters logged? Do they have to be?
- Does anything rotate and remove the files?
- Have you checked that any extension you rely on is allowed by the provider?
