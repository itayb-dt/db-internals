---
title: "Statistics: what the planner knows about your data"
updated: 2026-10-18
sources:
  - https://www.postgresql.org/docs/17/planner-stats.html
  - https://www.postgresql.org/docs/17/sql-analyze.html
  - https://www.postgresql.org/docs/17/sql-createstatistics.html
  - https://www.postgresql.org/docs/17/view-pg-stats.html
  - https://www.postgresql.org/docs/17/runtime-config-query.html
  - https://www.postgresql.org/docs/17/runtime-config-autovacuum.html
  - https://www.postgresql.org/docs/17/monitoring-stats.html
---

This article is about **PostgreSQL 17**. Every cost-based database keeps statistics for its optimizer. SQL Server calls them statistics, Oracle calls them optimizer statistics, and MySQL has index statistics and optional histograms. The idea is the same. The catalogs and commands below are PostgreSQL's.

> **Draft status:** the SQL in this article has been written against the documentation but **not yet run**. Treat every snippet as untested until this note is removed.

## Why the planner needs them

Before running a query, the planner must guess how many rows each step will return. That guess decides everything: [index](topic:index) or sequential scan, which join method, which table to join first. The planner cannot look at the data while planning, so it relies on a small summary kept in advance. Those summaries are the **statistics**.

A real example: an `orders` table has 50 million rows and the query asks for `status = 'cancelled'`. If the planner believes 1% of orders are cancelled, it expects 500,000 rows. If it believes 0.001%, it expects 500 rows and may choose a plan that is only good for a few rows. The plan is as good as the estimate. See [Execution plan](topic:execution-plan) for how the estimate is used.

## What is stored

**Per table.** `pg_class.reltuples` is the estimated number of rows and `relpages` the number of pages. These are not updated on every change. `VACUUM`, `ANALYZE` and some DDL commands such as `CREATE INDEX` update them, and a partial scan gives an approximate value. The planner scales the stored values to the current table size.

**Per column.** `ANALYZE` stores, for every column, a summary in `pg_statistic`. Read it through the view `pg_stats`, which anyone can query but which shows only tables the current user can read:

```sql
SELECT attname, null_frac, avg_width, n_distinct,
       most_common_vals, most_common_freqs, histogram_bounds, correlation
FROM pg_stats
WHERE schemaname = 'public' AND tablename = 'orders' AND attname = 'status';
```

| Column | Meaning |
|---|---|
| `null_frac` | Fraction of rows where the column is null |
| `avg_width` | Average size of the values in bytes |
| `n_distinct` | Number of distinct values (a negative number means a fraction of the row count) |
| `most_common_vals`, `most_common_freqs` | The most frequent values and how often each occurs |
| `histogram_bounds` | Boundaries that split the remaining values into groups with about the same number of rows |
| `correlation` | How well the physical row order matches the value order (-1 to +1) |

For `status = 'cancelled'` the planner looks in the most common values first. For a range such as `created_at > '2026-01-01'` it uses the histogram. The `correlation` value tells it whether an index scan reads the table in order or jumps around, which is the same value that decides whether [BRIN](topic:brin) is useful.

## How statistics are collected

`ANALYZE` reads a random sample of the table, not every row. The statistics are therefore always approximate and can change a little between runs. The sample size depends on the largest statistics target among the analyzed columns. The default target is 100 (`default_statistics_target`), which also limits the number of entries in the most-common-values list and the histogram. You can raise it for one column:

```sql
ALTER TABLE orders ALTER COLUMN status SET STATISTICS 500;
ANALYZE orders;
```

A higher target can give better estimates for columns with irregular data, and makes `ANALYZE` slower.

Autovacuum runs `ANALYZE` when enough rows have changed. The trigger is `autovacuum_analyze_threshold` (50 rows by default) plus `autovacuum_analyze_scale_factor` (0.1, or 10% of the table) times the table size. Both can be set per table.

## When one column is not enough

The planner normally assumes that conditions on different columns are independent. If `city = 'Berlin'` matches 1% of rows and `zip = '10115'` matches 0.5%, it multiplies and expects 0.005%. But the zip code determines the city, so the real answer is 0.5%. Per-column statistics cannot capture this. **Extended statistics** can:

```sql
CREATE STATISTICS addr_stats (dependencies) ON city, zip FROM addresses;
ANALYZE addresses;
```

Creating the object only registers interest. `ANALYZE` collects the data. Create them only for column groups that are strongly related, because they add work to `ANALYZE` and to planning.

## Why it matters for performance

**What it costs.** Collecting statistics costs I/O and CPU during `ANALYZE`, more with a higher target. Bad statistics cost far more: a wrong estimate gives a wrong plan, and a wrong plan can be thousands of times slower.

**When it shows up.** After a bulk load or a big delete, before autovacuum has re-analyzed. On skewed columns where one value dominates. On filters over correlated columns. On new tables that were never analyzed.

**How to measure.** Find stale statistics:

```sql
SELECT relname, n_live_tup, n_mod_since_analyze, last_analyze, last_autoanalyze
FROM pg_stat_user_tables
ORDER BY n_mod_since_analyze DESC
LIMIT 20;
```

Then compare estimates to reality in the [actual plan](topic:actual-plan): for each node, `rows=` (estimate) against `actual ... rows=`.

**When to worry.** A large `n_mod_since_analyze` compared to the table size, with an old `last_autoanalyze`. In a plan, estimates that are off by 10x or more (a rule of thumb, not a documented limit), especially near the bottom of the tree.

**What you can change.**

- Run `ANALYZE` after bulk loads and big changes.
- Make autovacuum analyze more often on large, fast-changing tables (per-table scale factor).
- Raise the statistics target on columns with skewed data.
- Add extended statistics for correlated columns.
- Do not fix a wrong estimate by turning off plan types. Fix the statistics first.

## Practical checklist

- Estimate wrong? Check statistics before changing queries or indexes.
- Run `ANALYZE` after bulk loads.
- Watch `n_mod_since_analyze` and `last_autoanalyze`.
- Read `pg_stats` for the columns in your slow filters.
- Use a higher target for skewed columns, and extended statistics for correlated ones.
