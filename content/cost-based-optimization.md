---
title: "Cost Based Optimization: how the planner picks a plan"
updated: 2026-10-19
sources:
  - https://www.postgresql.org/docs/17/using-explain.html
  - https://www.postgresql.org/docs/17/runtime-config-query.html
  - https://www.postgresql.org/docs/17/query-path.html
  - https://www.postgresql.org/docs/17/planner-stats.html
---

This article is about **PostgreSQL 17**. Most modern relational databases use the same approach: SQL Server, Oracle and MySQL all have a cost-based optimizer, with their own cost models and units. The parameter names below are PostgreSQL's.

> **Draft status:** the SQL in this article has been written against the documentation but **not yet run**. Treat every snippet as untested until this note is removed.

## The idea

For one query there are many ways to get the same rows: scan the table or use an [index](topic:index), join in one order or another, hash or sort. The planner builds the candidate paths, **gives each a cost, and keeps the cheapest**. That is cost-based optimization. The alternative, fixed rules such as "always use an index when one exists", cannot know that an index is a bad choice when 40% of the table matches.

The cost is a single number per plan node. You see it in [`EXPLAIN`](topic:execution-plan) as `cost=0.29..8.30`. The first number is the **startup cost** and the second is the **total cost**.

## How a cost is built

A cost is a sum of two kinds of work: reading pages and processing rows. Each has a price set by a planner setting. By convention the price of a sequential page read is 1.0 and the others are relative to it.

| Setting | Meaning | Default |
|---|---|---|
| `seq_page_cost` | One page read as part of a sequential series | 1.0 |
| `random_page_cost` | One page read out of order, such as an index lookup | 4.0 |
| `cpu_tuple_cost` | Processing one row | 0.01 |
| `cpu_index_tuple_cost` | Processing one index entry | 0.005 |
| `cpu_operator_cost` | Running one operator or function, such as a filter | 0.0025 |

The documentation gives a worked example. A table has 345 pages and 10,000 rows. A sequential scan costs pages times `seq_page_cost` plus rows times `cpu_tuple_cost`:

```
345 * 1.0 + 10000 * 0.01 = 445
```

Add a `WHERE` filter and the scan still visits every row, so the cost goes up slightly by `10000 * cpu_operator_cost` (25), to 470. The estimated number of output rows drops, but the work does not.

An [index scan](topic:index-scan) is priced mostly in random page reads, which cost 4.0 each by default, plus a small charge per index entry. With a very selective filter, a few random reads cost far less than reading the whole [heap](topic:heap). With a filter that matches a large share of the table, the random reads add up and the sequential scan wins. The planner finds this crossover by arithmetic, using the row estimate.

## Startup cost and total cost

- **Startup cost** is the work before the first row can be returned. A `Sort` cannot return anything until it has read and sorted all its input, so its startup cost is high. A sequential scan has almost none.
- **Total cost** is the work to return all rows, assuming the node runs to completion.

This matters when only some rows are needed. With `LIMIT 10`, a plan with a low startup cost that streams rows can beat a plan with a lower total cost that must finish first. The planner takes the limit into account when it compares paths.

## What the model assumes

The cost model is only as good as its inputs and assumptions:

- **Row counts are estimates.** Selectivity comes from [statistics](topic:statistics). If they are stale or miss a correlation between columns, every cost above that point is wrong, and the planner may choose a plan that is only good for a few rows.
- **The cache is assumed, not observed.** The planner does not know which pages are in memory. `random_page_cost` is 4.0 and not much higher, because, as the documentation explains, most random accesses such as indexed reads are assumed to be cached. `effective_cache_size` tells the planner how much cache to assume, and a larger value makes index scans look cheaper.
- **Units are relative.** Costs are not milliseconds. Scaling all the cost settings by the same factor changes no decision. Costs are comparable between plans for the same query on the same settings, not between different queries or servers.
- **Not everything is modeled equally well.** Complex expressions, functions and skewed or correlated data are where estimates drift most.

## Why it matters for performance

**What it costs.** Planning time, which grows with the number of candidate paths. A wrong choice costs far more: a plan that is cheap on paper and slow in reality, such as a nested loop over millions of rows chosen because the estimate said 10.

**When it shows up.** After data growth, bulk loads, or changes to indexes and settings. On new hardware, where the page cost assumptions no longer match the storage.

**How to measure.** Compare the costed estimate with reality. Run the [actual plan](topic:actual-plan) and look for nodes where estimated rows and actual rows differ most. Check which settings differ from the defaults:

```sql
EXPLAIN (ANALYZE, BUFFERS, SETTINGS)
SELECT * FROM orders WHERE customer_id = 42;
```

To see whether the cost settings cause a choice, try a change in one session only:

```sql
SET random_page_cost = 1.1;
EXPLAIN SELECT * FROM orders WHERE customer_id = 42;
RESET random_page_cost;
```

**When to worry.** Estimated rows that are far from actual rows (a rule of thumb: 10x or more). A plan that changes between runs without a change in the data. A sequential scan on a large table with a selective filter, or an index scan that reads most of the table.

**What you can change.**

- Fix the inputs first: refresh [statistics](topic:statistics), raise the statistics target, add extended statistics.
- Match the settings to the hardware. Lowering `random_page_cost` relative to `seq_page_cost` makes the planner prefer index scans. Many people use a value close to 1 on fast SSDs, which is a common rule of thumb and not an official recommendation. Set `effective_cache_size` to a realistic value for the memory available for caching.
- Use the `enable_*` settings (for example `enable_seqscan`) only to test. They discourage a plan type, they do not forbid it, and they are a poor permanent fix.
- Add or change an index, or rewrite the query, when the cheapest plan is still expensive.

## Practical checklist

- Read cost as a relative number, never as seconds.
- Check estimated against actual rows before touching any setting.
- Know the defaults: sequential page 1.0, random page 4.0.
- Tune `random_page_cost` and `effective_cache_size` for your storage and memory, and test in a single session first.
- Look at startup cost, not only total cost, for queries with `LIMIT`.
