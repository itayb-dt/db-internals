---
title: "MVCC: how PostgreSQL lets readers and writers work together"
updated: 2026-10-20
sources:
  - https://www.postgresql.org/docs/17/mvcc-intro.html
  - https://www.postgresql.org/docs/17/transaction-iso.html
  - https://www.postgresql.org/docs/17/ddl-system-columns.html
  - https://www.postgresql.org/docs/17/routine-vacuuming.html
  - https://www.postgresql.org/docs/17/storage-hot.html
---

This article is about **PostgreSQL 17**. MVCC stands for multiversion concurrency control. Oracle, MySQL/InnoDB and SQL Server (with snapshot isolation) also keep several versions of data. The difference is where the old versions live. In InnoDB and Oracle, old versions are kept in undo space and rebuilt on demand. In PostgreSQL they stay in the table itself, which is why this article is followed by [Dead rows](topic:dead-rows).

> **How this was checked:** The SQL in this article was run on PostgreSQL 16.2. The two-session example was run with two real sessions.

## The problem MVCC solves

Imagine a shop with one `accounts` table. A report is reading all balances while a payment updates one of them. With plain locking, either the report waits for the payment, or the payment waits for the report. At high concurrency, everything queues behind someone.

MVCC avoids this. PostgreSQL does not overwrite a row when it is changed. It writes a **new version** of the row and keeps the old one. Each statement or transaction sees a **snapshot**, a consistent picture of the data as it was at one moment, and picks the right version for that moment. The documentation states the result: reading never blocks writing, and writing never blocks reading. Two writers on the same row still wait for each other.

## What a row version looks like

Every row version carries two hidden columns: `xmin` is the ID of the transaction that created the version, and `xmax` is the ID of the transaction that deleted it (zero if nobody has). `ctid` is the version's physical location in the table.

```sql
CREATE TABLE accounts (id int PRIMARY KEY, balance int, note text);
INSERT INTO accounts SELECT g, 100, 'x' FROM generate_series(1, 3) g;

SELECT ctid, xmin, xmax, * FROM accounts ORDER BY id;
UPDATE accounts SET balance = balance + 1 WHERE id = 1;
SELECT ctid, xmin, xmax, * FROM accounts ORDER BY id;
```

Output from my run (the transaction numbers differ on your server):

```
 ctid  | xmin | xmax | id | balance
-------+------+------+----+---------
 (0,1) | 1138 |    0 |  1 |     100
 (0,2) | 1138 |    0 |  2 |     100
 (0,3) | 1138 |    0 |  3 |     100

 ctid  | xmin | xmax | id | balance
-------+------+------+----+---------
 (0,4) | 1139 |    0 |  1 |     101
 (0,2) | 1138 |    0 |  2 |     100
 (0,3) | 1138 |    0 |  3 |     100
```

Row 1 moved from `(0,1)` to `(0,4)` and has a new `xmin`. The old version at `(0,1)` is still in the page, now marked as deleted by the transaction that updated the row. Because of this, `ctid` is not a stable row identifier. Use the primary key.

## How a snapshot decides what you see

A snapshot records which transactions had committed when it was taken. A row version is visible to you if the transaction that created it (`xmin`) had committed in your snapshot, and the transaction that deleted it (`xmax`), if any, had not. Everything else is invisible to you, although it may still be visible to someone else.

Two sessions show the effect:

```sql
-- not run as one script: two sessions, checked by scripts/verify_sql.py
-- session A
BEGIN;
UPDATE accounts SET balance = 500 WHERE id = 1;     -- not committed yet

-- session B, while A is still open
SELECT balance FROM accounts WHERE id = 1;          -- returns 101: the old version, no waiting

-- session A
COMMIT;

-- session B, a new statement
SELECT balance FROM accounts WHERE id = 1;          -- returns 500
```

Session B did not wait, and it never saw A's uncommitted change.

## Isolation levels: when the snapshot is taken

The isolation level decides how long a snapshot lasts.

- **Read Committed** (the default). Each statement gets a fresh snapshot, so two `SELECT`s in one transaction can see different data if someone commits in between.
- **Repeatable Read.** One snapshot for the whole transaction, taken at its first statement. Every `SELECT` sees the same data, whatever others commit.

```sql
SHOW default_transaction_isolation;

BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT count(*) FROM accounts;
COMMIT;
```

Serializable adds checks on top for anomalies. The documentation describes all three in detail.

## What MVCC costs

- **Old versions pile up.** Every `UPDATE` and `DELETE` leaves a version behind that nobody may need anymore. These are [dead rows](topic:dead-rows), and [vacuum](topic:vacuum) must find and recycle them.
- **Updates write more.** An update is a new row version, and a new index entry for each index, unless it qualifies as a heap-only tuple (HOT): no indexed column changed and the page has room.
- **Long transactions are expensive.** A snapshot that stays open keeps every version it might need, so vacuum cannot clean them. This is the main way MVCC hurts a busy database.
- **Writers still conflict.** Two transactions updating the same row wait for each other, and can [deadlock](topic:deadlock).

## Why it matters for performance

**What it costs.** Extra space, extra write work, and background vacuum work. Reads do not take locks that block writers, so read-heavy workloads scale well.

**When it shows up.** On tables with frequent updates or deletes, and when long-running or idle-in-transaction sessions exist.

**How to measure.** Look for the oldest snapshots, because they set how far back vacuum may not clean:

```sql
SELECT pid, state, now() - xact_start AS open_for, age(backend_xmin) AS xmin_age,
       left(query, 60) AS query
FROM pg_stat_activity
WHERE backend_xmin IS NOT NULL
ORDER BY age(backend_xmin) DESC;
```

Then check how many dead rows each table has, as described in [Dead rows](topic:dead-rows).

**When to worry.** A session that has been open for minutes or hours, especially in the state `idle in transaction`. A fast-growing `age(backend_xmin)` on one backend. These are rules of thumb, not documented limits.

**What you can change.** Keep transactions short. Set `idle_in_transaction_session_timeout` to end sessions that sit idle inside a transaction. Use Read Committed unless you need one stable snapshot. Run long reports on a replica, or in short batches.

## Practical checklist

- Remember that an `UPDATE` is a new row version, not an overwrite.
- Do not use `ctid` as an identifier.
- Keep transactions short, and never wait for a user inside one.
- Pick the isolation level on purpose: Read Committed for most work, Repeatable Read for consistent reports.
- Watch the oldest `backend_xmin` in `pg_stat_activity`.
- Read [Dead rows](topic:dead-rows) next for the consequences.
