---
title: "Execution plan: how PostgreSQL decides to run a query"
updated: 2026-10-18
sources:
  - https://www.postgresql.org/docs/17/query-path.html
  - https://www.postgresql.org/docs/17/using-explain.html
  - https://www.postgresql.org/docs/17/sql-explain.html
  - https://www.postgresql.org/docs/17/runtime-config-query.html
  - https://www.postgresql.org/docs/17/rules-privileges.html
  - https://www.postgresql.org/docs/17/ddl-rowsecurity.html
---

This article is about **PostgreSQL 17**. All relational databases have an optimizer and a plan: SQL Server has the estimated and actual execution plan, Oracle has `EXPLAIN PLAN`, MySQL has `EXPLAIN`. The node names differ, the idea is the same. SQL does not say *how* to get the rows. The plan is the "how".

> **Draft status:** the SQL in this article has been written against the documentation but **not yet run**. Treat every snippet as untested until this note is removed.

## The path of a query

A query passes through several stages before any row is read:

1. **Parser.** Checks the syntax and builds a query tree. Names such as tables and columns are resolved against the catalogs.
2. **Rewriter.** Applies rules stored in the catalogs. The main use is views: a query on a view is rewritten into a query on the base tables.
3. **Planner (optimizer).** Builds all the reasonable ways to produce the result (paths), estimates the cost of each, and picks the cheapest. This becomes the plan.
4. **Executor.** Walks the plan and fetches rows, using the storage system for scans, and performs sorts, joins and filters.

**Permissions** run through this pipeline. For a view, the rewriter replaces the view with its definition, and access to the underlying tables is checked against the view owner's privileges, not the caller's (unless the view is a security invoker view). Row-level security policies are added as conditions that are evaluated before your own conditions, except for functions marked leakproof, so they also shape the plan. The user documentation does not say at which exact moment privilege checks run, so this article does not claim it.

## What a plan looks like

A plan is a tree of nodes. Rows flow from the leaves up to the root.

```sql
EXPLAIN
SELECT o.id, c.name
FROM orders o
JOIN customers c ON c.id = o.customer_id
WHERE o.created_at >= now() - interval '1 day';
```

Illustrative output:

```
Hash Join  (cost=35.20..1240.55 rows=4200 width=36)
  Hash Cond: (o.customer_id = c.id)
  ->  Index Scan using orders_created_idx on orders o  (cost=0.43..1100.10 rows=4200 width=12)
        Index Cond: (created_at >= (now() - '1 day'::interval))
  ->  Hash  (cost=22.00..22.00 rows=1000 width=28)
        ->  Seq Scan on customers c  (cost=0.00..22.00 rows=1000 width=28)
```

Read it from the innermost, most indented node outwards. Each node shows the estimated cost (`startup..total`), the estimated number of rows, and the average row width in bytes.

**Cost is not time.** It is a relative number in arbitrary units, built from page reads and a small CPU charge per row. Startup cost is the work before the first row can come out, and total cost is the work to produce them all. Use costs to compare plans, not to predict seconds. The details, with a worked example, are in [Cost Based Optimization](topic:cost-based-optimization).

## Scan nodes: how rows are read

The leaves read tables. The planner chooses a path per table.

- **Seq Scan.** Reads the whole [heap](topic:heap). Best when many rows match, or the table is small.
- **Index Scan.** Walks an [index](topic:index), then fetches each matching row from the table. Best when few rows match.
- **Bitmap Index Scan and Bitmap Heap Scan.** First collects the locations of matching rows from the index, then reads those table pages in physical order. A middle ground when a moderate share of rows match.
- **Index Only Scan.** Answers from the index without visiting the table when it can.

The choice follows from the statistics. With an estimated 1 matching row out of 10 million, an [index scan](topic:index-scan) wins. If 30% of the table matches, a sequential scan is cheaper because index lookups cost random reads. This is why an index sometimes is not used.

## Join nodes: how tables are combined

- **Nested Loop.** For each row of the outer side, look up matches on the inner side. Excellent with a small outer side and an index on the inner side. Terrible when the outer side is huge.
- **Hash Join.** Builds a hash table from one side, probes it with the other. Good for large inputs and equality conditions.
- **Merge Join.** Merges two sorted inputs. Good when both are already sorted, for example from indexes.

## Join order

With three or more tables, the order matters a lot, because it decides how many rows flow through each step. The planner explores orders and picks the cheapest. Exhaustive search gets expensive as tables are added, so settings limit it: `join_collapse_limit` and `from_collapse_limit` control how many items are reordered, and above `geqo_threshold` (12 FROM items by default) the planner switches to a genetic algorithm that does not guarantee the best plan. Setting `join_collapse_limit` to 1 keeps the join order you wrote.

## What an estimated plan cannot tell you

A plain `EXPLAIN` is a prediction made before anything runs. It cannot know:

- **How many rows will really be read.** Row counts are estimates from [statistics](topic:statistics), and they can be far off. A node that says `rows=1` may return a million rows. Every cost number downstream is built on these guesses.
- **How long anything takes.** There is no timing in an estimated plan, only cost units. Two plans with similar costs can differ a lot in real time.
- **What is in memory and what is on disk.** The planner does not look at the buffer cache. It uses fixed assumptions: a cost for sequential and random page reads, and a setting (`effective_cache_size`) for how much cache it may assume. Which pages come from shared buffers and which from disk is known only after the query runs.

To see real rows, time and buffer reads, use the [actual plan](topic:actual-plan).

## EXPLAIN options and output format

Options go in parentheses: `EXPLAIN (VERBOSE, SETTINGS) SELECT ...`. Each takes `true` or `false`, and a bare name means true. These work without running the query:

| Option | What it does | Default |
|---|---|---|
| `COSTS` | Shows estimated cost, rows and width per node. Turn it off for a plan that is easy to diff or to read. | on |
| `VERBOSE` | Adds the output columns of each node, schema-qualified names and the trigger names. Shows the query identifier if one is computed. | off |
| `SETTINGS` | Lists the planner-related settings that differ from the built-in defaults. Useful when two people get different plans. | off |
| `GENERIC_PLAN` | Plans a statement with placeholders such as `$1`, as a prepared statement's generic plan. Cannot be combined with `ANALYZE`. | off |
| `SUMMARY` | Adds the summary lines (such as planning time). | off for plain `EXPLAIN`, on with `ANALYZE` |
| `MEMORY` | Shows how much memory the planning phase used. | off |
| `FORMAT` | Chooses the output format, see below. | `TEXT` |

Some options belong to the [actual plan](topic:actual-plan) and are covered there: `ANALYZE` itself, and `TIMING`, `WAL` and `SERIALIZE`, which can only be used together with `ANALYZE`. `BUFFERS` is also mainly useful there.

`FORMAT` accepts `TEXT`, `XML`, `JSON` and `YAML`. The non-text formats contain the same information as text. Text is compact and made for people. Use `JSON` when a program will read the plan, for example a plan visualiser or your own script, because the nodes become a nested structure and you do not need to parse indentation:

```sql
EXPLAIN (FORMAT JSON) SELECT * FROM customers WHERE id = 42;
```

Illustrative shape of the result (shortened):

```json
[{"Plan": {"Node Type": "Index Scan", "Relation Name": "customers",
           "Startup Cost": 0.29, "Total Cost": 8.30, "Plan Rows": 1, "Plan Width": 244}}]
```

## Why it matters for performance

**What it costs.** Planning itself takes time, which grows with the number of tables, indexes and partitions. A bad plan costs far more: the wrong join method on a big input can turn milliseconds into minutes.

**When it shows up.** When estimates are wrong (see [Statistics](topic:statistics)), when data volume changes, and after upgrades or setting changes.

**How to measure.** `EXPLAIN` shows the plan without running the query, so it is safe for any statement:

```sql
EXPLAIN SELECT ... ;                 -- estimated plan only
EXPLAIN (VERBOSE, SETTINGS) SELECT ... ;
```

It shows estimates only. To see what actually happened, use the [actual plan](topic:actual-plan).

**When to worry.** A sequential scan with a very selective filter on a large table. A nested loop whose outer side has a large estimated row count. Estimates that look suspicious: `rows=1` on a big table.

**What you can change.** In order of preference: fix [statistics](topic:statistics); add or change an index; rewrite the query; adjust cost settings such as `random_page_cost` to match your storage. The `enable_*` settings can force a different plan, but use them only to test, not as a permanent fix.

## Practical checklist

- Read plans from the innermost node outwards.
- Check the estimated rows first. Cost numbers only compare plans, they are not seconds.
- A sequential scan is not automatically bad. It depends on how many rows match.
- Match join choices to row counts: nested loop for few, hash or merge for many.
- Compare with the actual plan before changing anything.
