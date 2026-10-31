---
title: "Transaction ID wraparound: the failure vacuum exists to prevent"
updated: 2026-10-21
sources:
  - https://www.postgresql.org/docs/17/routine-vacuuming.html
  - https://www.postgresql.org/docs/17/runtime-config-autovacuum.html
  - https://www.postgresql.org/docs/17/runtime-config-client.html
  - https://www.postgresql.org/docs/17/ddl-system-columns.html
  - https://www.postgresql.org/docs/17/view-pg-replication-slots.html
  - https://www.postgresql.org/docs/17/view-pg-prepared-xacts.html
---

This article is about PostgreSQL. It is a PostgreSQL-specific problem. SQL Server and MySQL/InnoDB use wider counters and have no equivalent warning. PostgreSQL uses a 32-bit transaction ID, which is small enough to wrap around on a busy server, so it has to defend against that. The defense is [vacuum](topic:vacuum).

## What it is

Every transaction that writes data gets a **transaction ID (XID)**, a number from a counter. Each row version records the XID that created it (`xmin`), and [MVCC](topic:mvcc) uses those numbers to decide what you can see: a row created by an XID that is "in the future" is invisible to you.

The counter has only **32 bits**, so after about four billion transactions it wraps back to zero. To keep comparisons working, PostgreSQL treats the number space as a **circle**. For any XID, the two billion before it count as "older" and the two billion after it count as "newer". A row version stays "in the past" for the next two billion transactions, no matter which XID it has.

Then comes the problem. If a row version is still around after more than two billion transactions, it suddenly switches sides and looks like it is in the **future**. Transactions that committed long ago appear not to have happened, and the rows vanish from every query. The documentation puts it bluntly: "catastrophic data loss". The data is still on disk, but you cannot get at it. This is **transaction ID wraparound**.

## How PostgreSQL prevents it: freezing

Vacuum **freezes** old row versions. A frozen row is marked as created "so long ago that it is visible to everyone, always", and the rule no longer depends on the circle. In current versions this is a flag bit on the row, so the original `xmin` is kept. The documentation's rule is that every table in every database must be vacuumed at least once every two billion transactions.

| Setting | Default | What it does |
|---|---|---|
| `vacuum_freeze_min_age` | 50 million | A row must be this many transactions old before vacuum freezes it |
| `autovacuum_freeze_max_age` | 200 million | When a table reaches this age, autovacuum starts a forced vacuum, **even if autovacuum is turned off** |
| `vacuum_failsafe_age` | 1.6 billion | Vacuum's last resort: it drops cost throttling and skips non-essential work such as index cleanup |

The [visibility map](topic:visibility-map) helps: its all-frozen bit lets vacuum skip pages that are already frozen, even in a forced vacuum.

## See the safeguard work

I created a table with autovacuum **turned off** and a low limit, then used up 130,000 transaction IDs:

```sql
CREATE TABLE frozen_demo (id int PRIMARY KEY, v int)
  WITH (autovacuum_enabled = off, autovacuum_freeze_max_age = 100000, autovacuum_freeze_min_age = 10000);
INSERT INTO frozen_demo SELECT g, 0 FROM generate_series(1, 1000) g;

DO $$ BEGIN FOR i IN 1..130000 LOOP PERFORM pg_current_xact_id(); COMMIT; END LOOP; END $$;

SELECT c.oid::regclass AS table_name, age(c.relfrozenxid) AS xid_age
FROM pg_class c WHERE c.oid = 'frozen_demo'::regclass;
```

The age was 2 at the start and **130,002** after the loop. Within a few seconds, with autovacuum off for this table, the server log printed:

```
automatic vacuum to prevent wraparound of table "exp4.public.frozen_demo": index scans: 0
    new relfrozenxid: 261600, which is 130002 XIDs ahead of previous value
    frozen: 5 pages from table (100.00% of total) had 1000 tuples frozen
```

The age dropped back to 1. This is the safeguard doing its job. On a real server the numbers are a thousand times bigger: forced vacuums start at 200 million, and on a large table they can run for hours.

## Why it is so dangerous

If the safeguard cannot do its job, the server escalates, as the documentation describes:

1. **At `autovacuum_freeze_max_age`** a forced, aggressive autovacuum starts on the table. It cannot be switched off, and it may be slow and heavy on a big table.
2. **At `vacuum_failsafe_age`** vacuum drops its throttling and non-essential work to finish as fast as it can.
3. **Within forty million transactions of the limit** the server begins to log a warning like this:

```
WARNING:  database "mydb" must be vacuumed within 39985967 transactions
HINT:  To avoid XID assignment failures, execute a database-wide VACUUM in that database.
```

4. **With fewer than three million transactions left** the server **refuses to assign new transaction IDs**:

```
ERROR:  database is not accepting commands that assign new transaction IDs to avoid wraparound data loss in database "mydb"
```

In that state, running transactions may continue, but only read-only transactions can start. Every insert, update, delete and DDL statement fails. For most applications this is a full outage of everything that writes, and the fix is a database-wide vacuum that may take hours on a large database.

**How fast can it happen?** Only transactions that write use an XID. The time to reach 200 million and two billion, at a steady rate:

| Write transactions per second | To 200 million | To 2 billion |
|---|---|---|
| 100 | about 23 days | about 231 days |
| 1,000 | about 2.3 days | about 23 days |
| 10,000 | about 5.6 hours | about 2.3 days |

The arithmetic is simple, and the lesson is that a busy server gets there in days, so vacuum must keep up continuously.

**What usually goes wrong.** The documentation lists the causes you must clear to recover, and they are also the usual causes of the problem:

- an old **prepared transaction** that nobody finished
- a **long-running or idle-in-transaction** session that holds back the horizon
- an old **replication slot**, for example for a standby that no longer exists
- autovacuum that is **turned off, blocked or too slow** for a very large table
- a huge **append-only table** nobody noticed, because it never had enough dead rows to be vacuumed (see [Vacuum](topic:vacuum))

## How to monitor it

The age of the oldest unfrozen XID is stored per table (`pg_class.relfrozenxid`) and per database (`pg_database.datfrozenxid`). `age()` turns it into a number of transactions.

**1. Databases, as a share of the limit.**

```sql
SELECT datname, age(datfrozenxid) AS xid_age,
       round(100.0 * age(datfrozenxid) / current_setting('autovacuum_freeze_max_age')::int, 1) AS pct_of_freeze_max_age,
       round(100.0 * age(datfrozenxid) / 2147483648, 1) AS pct_of_wraparound
FROM pg_database
ORDER BY 2 DESC;
```

`pct_of_freeze_max_age` shows how close the forced vacuum is. `pct_of_wraparound` shows how close the real limit is.

**2. Tables.** This is the documentation's query, extended: it takes the older of the table and its TOAST table, which has an age of its own.

```sql
SELECT c.oid::regclass AS table_name,
       greatest(age(c.relfrozenxid), age(t.relfrozenxid)) AS xid_age,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size
FROM pg_class c
LEFT JOIN pg_class t ON c.reltoastrelid = t.oid
WHERE c.relkind IN ('r', 'm')
ORDER BY 2 DESC
LIMIT 10;
```

The oldest tables are the ones the next forced vacuum will work on. Large ones take a long time, so you want to see them early.

**3. How fast IDs are used.** Sample the current XID twice and divide the difference by the seconds between the samples:

```sql
SELECT pg_current_xact_id() AS xid_now, now() AS sampled_at;
```

With the rate you can estimate the time left: `(autovacuum_freeze_max_age - age) / rate`. (This call itself uses one XID, which does not matter.)

**4. What holds it back.** These are the three places the documentation tells you to check:

```sql
SELECT pid, state, age(backend_xid) AS xid_age, age(backend_xmin) AS xmin_age, left(query, 60) AS query
FROM pg_stat_activity
WHERE backend_xid IS NOT NULL OR backend_xmin IS NOT NULL
ORDER BY greatest(age(backend_xid), age(backend_xmin)) DESC NULLS LAST;

SELECT slot_name, active, age(xmin) AS xmin_age, age(catalog_xmin) AS catalog_xmin_age FROM pg_replication_slots;
SELECT gid, prepared, age(transaction) AS xid_age FROM pg_prepared_xacts;
```

**5. The log.** Search it for `to prevent wraparound` (forced vacuums), `must be vacuumed within` (the warning) and `not accepting commands that assign new transaction IDs` (the outage).

**6. Multixact IDs** are a second counter with the same kind of limit. Watch it too:

```sql
SELECT datname, mxid_age(datminmxid) AS multixact_age FROM pg_database ORDER BY 2 DESC;
```

## What to alert on

Rules of thumb, not documented limits: warn when a database passes **about half of `autovacuum_freeze_max_age`** without a recent forced vacuum, page someone when it passes **one billion**, and treat **1.5 billion** as an emergency, because it is close to the failsafe at 1.6 billion. Also alert on any "must be vacuumed within" line in the log.

## What to do about it

- **Keep autovacuum on and fast.** Do not disable it, and raise the cost limit if big tables take too long (see [Vacuum](topic:vacuum)).
- **Find and remove the blockers** from check 4: end old transactions, drop dead replication slots, resolve prepared transactions.
- **Freeze big append-only tables on purpose,** in a quiet period, so the forced vacuum does not surprise you:

```sql
VACUUM (FREEZE) frozen_demo;
```

- **Tune per table.** A lower `autovacuum_freeze_max_age` on a table starts the forced vacuum earlier (it can only be lowered per table).
- **If the server already refuses writes,** follow the documented steps in this order: resolve prepared transactions, end long transactions, drop old replication slots, then run a plain database-wide `VACUUM`. Do **not** use `VACUUM FULL` (it needs an XID and fails) or `VACUUM FREEZE` (it does more work than needed). Single-user mode is no longer necessary.

## Practical checklist

- XIDs are 32-bit and circular. Freezing is what keeps old rows visible.
- A forced vacuum starts at `autovacuum_freeze_max_age` even when autovacuum is off.
- Under three million transactions left, writes stop.
- Alert on `age(datfrozenxid)` for every database and on the oldest tables.
- Check old transactions, replication slots and prepared transactions first.
- Keep autovacuum healthy on the biggest tables.
