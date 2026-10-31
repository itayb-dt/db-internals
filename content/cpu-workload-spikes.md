---
title: "High CPU cause: more requests and overlapping jobs"
updated: 2026-11-01
sources:
  - https://www.postgresql.org/docs/17/monitoring-stats.html
  - https://www.postgresql.org/docs/17/pgstatstatements.html
---

This article covers two of the root causes listed in [Common root causes of high CPU](topic:high-cpu-causes). Both are about the workload jumping. It is about **PostgreSQL 17**.

> **How this was checked:** The names of the statistics views come from the PostgreSQL 17 documentation, listed in the sources. The causes and the advice are common operating practice. The article has no SQL.

## More requests than usual

**What it is.** More statements arrive than on a normal day, so the CPU rises with them.

**Common reasons:**

- **A campaign or a busy hour.** The real traffic grew.
- **A retry storm.** After a failure, clients retry at once, and the retries add load to a system that was already struggling.
- **A change that makes more calls.** A new release that runs one query for each row (the "N plus one" pattern).
- **A cache that empties.** When a cache expires or restarts, every request goes to the database at the same moment.

**How to recognise it.** Statements per second, or transactions per second, are well above a normal day, and the same kinds of statements dominate. The statistics views show the rate: the number of calls of the top statements, and the transactions of the database. The CPU follows the rate.

**What to do:**

- Reduce the calls: cache results, fetch in one query instead of one per row, batch writes.
- Make retries wait longer each time, and limit how many run at once.
- Protect the database with a limit on concurrent requests.
- If the traffic is real and permanent, it is a [capacity problem](topic:cpu-capacity).

## Jobs overlap

**What it is.** Reports, imports, exports and scheduled jobs start at the same time, and compete with the normal load and with each other.

**How to recognise it.** The CPU jumps at the **same clock time** every day or week, and the busy sessions belong to the users or applications that run the jobs.

**What to do:**

- **Stagger** the jobs, so they do not start together.
- **Limit how many run at once.**
- **Run reports on a replica,** so they do not compete with the main workload.
- **Move heavy jobs to quiet hours,** and give them their own, limited connections.

## Telling them apart

| What you see | Likely cause |
|---|---|
| The CPU follows the request rate through the day | More requests, or capacity |
| A sudden rise right after a failure | A retry storm |
| A step after a release | A change that makes more calls |
| A jump at the same time every day | Jobs overlap |

## Common mistakes

- Adding capacity for a jump at 02:00 that a schedule change would remove.
- Letting retries fire at once, which makes the outage worse.
- Looking only at the average CPU, and missing the peak.

## Checklist

- Is the number of statements per second above a normal day?
- Does the CPU jump at a fixed time?
- Who are the busy sessions: users, or job accounts?
- Reduce calls, stagger jobs, or add capacity if the load is real.
