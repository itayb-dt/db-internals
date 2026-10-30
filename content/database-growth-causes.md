---
title: "Why a database suddenly grows"
updated: 2026-10-31
sources:
  - https://www.postgresql.org/docs/17/routine-vacuuming.html
  - https://www.postgresql.org/docs/17/warm-standby.html
  - https://www.postgresql.org/docs/17/storage-toast.html
---

This article continues from [Monitoring table size](topic:table-size), which showed where the space goes. It answers one question: why did the database get bigger? It starts with the healthy answer, and then covers the others. It is about **PostgreSQL 17**. It looks at the data inside the database. A server that is running out of disk for other reasons is a different problem, and is not covered here.

> **How this was checked:** The facts about vacuum and replication slots come from the PostgreSQL 17 documentation, listed in the sources. The rest is common operating practice. The article has no SQL, and the thresholds are rules of thumb.

## First question: is it healthy?

The most common reason for growth is the good one: **more rows are being inserted**. The business grew, a new feature writes more, a customer was onboarded, or a big import ran. This is normal, and the right response is capacity planning, not cleanup.

To tell healthy growth from waste, compare the **size** with the **number of rows**.

| What you see | What it means |
|---|---|
| Size and rows grow together, and the size per row is steady | Healthy growth |
| Size grows faster than rows | Something is adding space beyond the data |
| Size grows while the number of rows stays the same or falls | Waste, almost certainly |
| A sudden step in size | A one-off event: an import, a mass update, a retained log file |

If the answer is "healthy", the questions become how long you keep the data and whether old data can be dropped or [partitioned](topic:partitioning) away.

The animation compares three charts of rows and size: healthy growth, waste, and a sudden step.

<iframe src="database-growth-causes/demo.html" title="Animation: three charts of rows and size over time. In the first the size follows the rows, in the second the size grows while the rows stay flat, in the third the size jumps with no new rows" width="800" height="450"></iframe>

*The animation repeats about every 28 seconds.*

## The healthy and expected causes

- **More traffic or customers.** Rows grow with the business.
- **A new feature that writes a lot,** such as an audit trail, events or logs stored in the database.
- **A backfill, import or migration.** One large load that stays.
- **A longer retention period.** Someone decided to keep two years of history, not one.

## The unwelcome causes

### Dead rows that vacuum cannot reach

When a row is updated or deleted, PostgreSQL keeps the old version for a while. [Dead rows](topic:dead-rows) are cleaned up by [vacuum](topic:vacuum), and the space is reused. If many updates and deletes arrive faster than vacuum cleans, the table grows with dead space. This is the most common waste.

Vacuum only **marks the space as reusable**. It does not return it to the operating system, except for empty pages at the end of a table. So a bloated table does not shrink after vacuum. It stops growing, and new rows fill the gaps. Shrinking it needs a rewrite, which locks the table.

### Something blocks vacuum

Vacuum cannot remove a dead row if some session might still need to see it. The usual culprits are a transaction left open for hours, a session that is "idle in transaction", an old prepared transaction, or a replication slot whose consumer is gone. The documentation says a slot keeps the primary from removing rows that a disconnected standby might still need. The table grows even though vacuum runs. See [Monitoring vacuum](topic:vacuum-monitoring).

### One big update or delete

A single statement that updates every row of a table creates a new version of each row. The table can nearly double until vacuum catches up. A mass delete does not free space for the same reason. Schema changes that rewrite a table also need room for a full second copy while they run.

### Indexes

Every [index](topic:index) is stored separately and grows with the table. Many indexes, duplicate indexes and indexes nobody uses can add up to more than the table itself. Indexes on random values (random identifiers, for example) and indexes on heavily updated columns also bloat faster.

### Large values

Large text, `jsonb` and binary values are stored outside the main table by [TOAST](topic:toast). The table looks small, and the real size is in a separate storage table. Growth of large values hides from a quick look at the table size.

### Data that is never removed

Without a retention rule, old rows stay forever. Dropping a [partition](topic:partitioning) removes old data in one cheap step. Deleting the same rows leaves dead space.

## How to find the cause

Work from the outside in:

1. **Which database, which table?** Find the biggest tables and the ones that grew the most. See [Monitoring table size](topic:table-size).
2. **Where in the table?** Split it into the table, the large values and the indexes.
3. **Rows or waste?** Compare the number of rows with the size, and look at the share of dead rows.
4. **Is vacuum keeping up?** See [Monitoring vacuum](topic:vacuum-monitoring).
5. **What changed?** A deployment, a new job, an import, a stopped consumer.

| Symptom | Likely cause | Next step |
|---|---|---|
| Rows steady, size growing | Dead rows or bloat | Check dead rows and vacuum |
| Vacuum runs but the table keeps growing | Something blocks it | Look for long or idle transactions and slots that do not advance |
| Table small, database large | Large values or indexes | Split the table size into parts |
| One sudden jump | A mass update, an import or a rewrite | Ask what ran |
| Steady growth in line with business | Healthy | Plan capacity and retention |

## Why it matters for performance

**What it costs.** Wasted space makes scans read more, indexes larger and backups longer, as the previous article explained.

**When it shows up.** Under update-heavy or delete-heavy workloads, after a stuck consumer, and after one-off jobs.

**How to measure.** Size per table over time, rows over time, and dead rows.

**When to worry.** As a rule of thumb, when size grows noticeably faster than rows, or when the growth rate suddenly changes.

**What you can change.** Make vacuum start earlier and run faster ([Vacuum configuration](topic:vacuum-configuration)), end long transactions, remove slots that nothing reads, drop unused indexes, set a retention rule, and use partitions for data that expires.

## Common mistakes

- Treating all growth as waste, and cleaning up data the business needs.
- Treating all growth as healthy, without comparing size with rows.
- Expecting vacuum to shrink the files.
- Deleting old rows instead of dropping partitions.

## Checklist

- Compare size with rows, over time.
- Check dead rows, and whether anything blocks vacuum.
- Split big tables into table, large values and indexes.
- Check for long or idle transactions and slots that do not advance.
- Ask what changed.
- If it is healthy, plan capacity and retention.
