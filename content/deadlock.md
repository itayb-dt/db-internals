---
title: "Deadlock: when transactions wait for each other"
updated: 2026-10-18
sources:
  - https://www.postgresql.org/docs/17/explicit-locking.html
  - https://www.postgresql.org/docs/17/runtime-config-locks.html
  - https://www.postgresql.org/docs/17/runtime-config-logging.html
  - https://www.postgresql.org/docs/17/runtime-config-client.html
  - https://www.postgresql.org/docs/17/view-pg-locks.html
  - https://www.postgresql.org/docs/17/monitoring-stats.html
  - https://www.postgresql.org/docs/17/functions-info.html
  - https://www.postgresql.org/docs/17/errcodes-appendix.html
---

This article is about PostgreSQL. Every database with locks can deadlock. SQL Server picks a "deadlock victim" and rolls it back with error 1205, Oracle raises ORA-00060, and MySQL/InnoDB returns error 1213. PostgreSQL's behaviour and tools are described below.

## What a deadlock is

A deadlock is a circle of waiting. Transaction A holds a lock that B wants, and B holds a lock that A wants. Both wait, and neither can ever continue, because each is waiting for the other to finish.

You do not need explicit `LOCK` commands for this. Ordinary row updates are enough. Take two accounts and two sessions that move money in opposite directions:

```sql
-- not run as one script: two sessions, checked by scripts/verify_sql.py
-- step 1, session 1
BEGIN;
UPDATE accounts SET balance = balance - 10 WHERE id = 1;   -- locks row 1

-- step 2, session 2
BEGIN;
UPDATE accounts SET balance = balance - 10 WHERE id = 2;   -- locks row 2

-- step 3, session 1
UPDATE accounts SET balance = balance + 10 WHERE id = 2;   -- waits for session 2

-- step 4, session 2
UPDATE accounts SET balance = balance + 10 WHERE id = 1;   -- waits for session 1: deadlock
```

PostgreSQL does not let this wait forever. It checks for a cycle and **aborts one of the transactions**, so the others can complete. Which one is aborted is hard to predict and you must not rely on it. The aborted session gets an error with SQLSTATE `40P01` (`deadlock_detected`) and its transaction is rolled back.

Error text from a real run on PostgreSQL 16.2 (process and transaction numbers differ each time):

```
ERROR:  deadlock detected
DETAIL:  Process 54714 waits for ShareLock on transaction 848; blocked by process 54715.
Process 54715 waits for ShareLock on transaction 849; blocked by process 54714.
HINT:  See server log for query details.
CONTEXT:  while updating tuple (0,1) in relation "accounts"
```

<iframe src="deadlock/demo.html" title="Animation: two sessions each lock a row, then wait for the other; PostgreSQL detects the deadlock and aborts one" width="800" height="450"></iframe>

*The animation repeats about every 10 seconds.*

Note the difference from plain blocking. If A waits for B and B is just slow, A waits indefinitely, and there is no error. A deadlock is the special case where the wait can never end.

## Why it is a problem

- **Work is lost.** The victim is rolled back, including everything it did before. The application must notice the error and run the whole transaction again. Code that does not retry turns a deadlock into a user-visible failure.
- **It costs time before it is detected.** PostgreSQL does not check for a cycle at once, because the check is relatively expensive. A session first waits `deadlock_timeout` (one second by default) on the lock. During that time both sessions are stuck and hold their other locks, which may block further sessions behind them.
- **It spreads.** Other transactions that need the locked rows queue up behind the deadlocked pair. Connections are held, and the latency of unrelated requests grows.
- **It hints at a design problem.** The usual cause is two code paths that lock the same objects in different orders, or long transactions that hold locks while doing other work. The documentation specifically warns against holding transactions open for long periods, for example while waiting for user input.
- **Retries can pile up.** Under high concurrency, retrying the same conflicting transactions at once can produce more deadlocks.

A single deadlock now and then is a normal cost of concurrent writes if your application retries. A steady stream of them is a bug.

## How to detect deadlocks

**1. The server log.** Every detected deadlock is reported as an error, and the log includes the processes and the statements involved. This is the best source for finding which queries collide. Search the log for `deadlock detected`.

**2. The counter.** Each database counts deadlocks. Sample it over time to see the rate:

```sql
SELECT datname, deadlocks, stats_reset
FROM pg_stat_database
WHERE datname = current_database();
```

The value is cumulative since `stats_reset`, so look at the change between two samples, not the absolute number.

**3. Lock waits that did not become deadlocks yet.** With `log_lock_waits` on (off by default), the server logs a message when a session waits longer than `deadlock_timeout` for a lock. This finds slow blocking that is a warning sign for deadlocks:

```sql
ALTER SYSTEM SET log_lock_waits = on;
SELECT pg_reload_conf();
```

**4. Live blocking right now.** See who is waiting and who blocks them:

```sql
SELECT a.pid, a.state, now() - a.query_start AS waiting_for,
       pg_blocking_pids(a.pid) AS blocked_by, left(a.query, 80) AS query
FROM pg_stat_activity a
WHERE cardinality(pg_blocking_pids(a.pid)) > 0;
```

To see the locks themselves, `pg_locks` has one row per lock request. A row with `granted = false` is a session waiting:

```sql
SELECT pid, locktype, mode, granted, waitstart
FROM pg_locks
WHERE NOT granted;
```

**5. In the application.** Count and log errors with SQLSTATE `40P01`, together with the transaction that failed. The retry rate is a direct health metric.

## Why it matters for performance

**What it costs.** Wasted work (rolled-back transactions), lost time (at least `deadlock_timeout` of waiting before detection), and held locks and connections that delay other sessions.

**When it shows up.** On write-heavy tables updated by several code paths, in batch jobs that update many rows in arbitrary order, and when transactions are long. Also when locks are taken one at a time instead of up front.

**When to worry.** A deadlock counter that keeps increasing between samples, or any recurring `40P01` in the application. Waits that regularly exceed `deadlock_timeout` in the log. There is no documented threshold. Rule of thumb: one now and then is acceptable if you retry, a pattern is not.

**What you can change.**

- **Lock in a consistent order.** The documentation calls this the best defence. Make every code path touch rows and tables in the same order, for example by id. For multi-row work, lock the rows first in a fixed order:

```sql
BEGIN;
SELECT id FROM accounts WHERE id IN (1, 2) ORDER BY id FOR UPDATE;
UPDATE accounts SET balance = balance - 10 WHERE id = 1;
UPDATE accounts SET balance = balance + 10 WHERE id = 2;
COMMIT;
```

- **Take the strongest lock you need first.** The first lock on an object should be the most restrictive mode the transaction will need.
- **Keep transactions short.** Do not hold a transaction open while waiting for a user or an external call.
- **Retry on `40P01`.** If you cannot prove an order, handle the error by running the whole transaction again, ideally with a short random delay.
- **Fail fast instead of waiting.** `lock_timeout` limits how long a statement waits for a lock. `NOWAIT` and `SKIP LOCKED` on `SELECT ... FOR UPDATE` avoid waiting at all, which suits work queues. Setting `idle_in_transaction_session_timeout` ends sessions that sit idle inside a transaction.
- **Do not just raise `deadlock_timeout`.** A longer value reduces needless checks, but it delays the report of real deadlocks.

## Practical checklist

- Touch rows and tables in the same order everywhere.
- Keep transactions short and never wait for users inside one.
- Retry the whole transaction on error `40P01`.
- Turn on `log_lock_waits` and watch `pg_stat_database.deadlocks`.
- Use `pg_blocking_pids` to find the blocker during an incident.
- Use `SKIP LOCKED` or `NOWAIT` for queue-like workloads.
