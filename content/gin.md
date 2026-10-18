---
title: "GIN indexes: searching inside values"
updated: 2026-10-18
sources:
  - https://www.postgresql.org/docs/17/indexes-types.html
  - https://www.postgresql.org/docs/17/gin.html
  - https://www.postgresql.org/docs/17/sql-createindex.html
  - https://www.postgresql.org/docs/17/runtime-config-client.html
---

This article is about the **PostgreSQL 17** GIN index (Generalized Inverted Index). Other engines have similar inverted indexes for full-text search (for example MySQL FULLTEXT, SQL Server full-text indexes), but PostgreSQL's GIN is a general building block used for arrays, `jsonb` and text search.

> **Draft status:** the SQL in this article has been written against the documentation but **not yet run**. Treat every snippet as untested until this note is removed.

## The problem a B-tree cannot solve

A [B-tree](topic:btree) indexes one value per row. But some columns hold many values in one cell: an array of tags, a `jsonb` document, a text document with many words. A question such as "which rows have the tag `urgent`?" asks about something inside the value. A B-tree on the whole column cannot answer it, so the query scans the table.

## How GIN works

GIN is an [index](topic:index) of the **inverted** kind. Instead of "row, then values", it stores "value, then rows". For each key extracted from the data (a tag, a word, a JSON key or value) it keeps a **posting list**, which is the list of rows that contain it. The same row appears under many keys. Each key is stored once, so the index is compact when keys repeat a lot. Inside, the keys are kept in a B-tree. If a posting list grows large, it becomes its own tree (a posting tree).

A search looks up the key and reads the list of rows. Searching for two keys combines two lists.

```sql
CREATE TABLE tickets (id bigint PRIMARY KEY, tags text[], payload jsonb);

CREATE INDEX tickets_tags_gin ON tickets USING gin (tags);
CREATE INDEX tickets_payload_gin ON tickets USING gin (payload);

SELECT * FROM tickets WHERE tags @> ARRAY['urgent'];
SELECT * FROM tickets WHERE payload @> '{"status": "open"}';
```

The array operators supported by the built-in class are `<@`, `@>`, `=` and `&&`. For `jsonb` there are two operator classes. `jsonb_ops` is the default and supports more operators. `jsonb_path_ops` supports fewer operators but is faster for them:

```sql
CREATE INDEX tickets_payload_path_gin ON tickets USING gin (payload jsonb_path_ops);
```

Full-text search uses GIN on a `tsvector`:

```sql
CREATE INDEX articles_fts_gin ON articles USING gin (to_tsvector('english', body));
SELECT id FROM articles WHERE to_tsvector('english', body) @@ to_tsquery('english', 'index & scan');
```

The index must be built on the same expression the query uses.

## Why writes are the weak spot

One row can contain many keys, so one insert can mean many index inserts. To soften this, GIN uses a **pending list** (fast update, on by default). New entries first go to an unsorted list and are moved into the main structure in bulk. This happens when the table is vacuumed or analyzed, when the list exceeds `gin_pending_list_limit`, or when you call `gin_clean_pending_list`.

The pending list has two costs. Searches must also read the pending list, so a long list slows reads. And the insert that triggers a cleanup is much slower than the others. Autovacuum keeps this under control.

## Why it matters for performance

**What it costs.** Slow updates, and slow builds. The build time is very sensitive to `maintenance_work_mem`. The index can also be large for high-cardinality data such as full documents. Large value lists in the table are stored out of line by [TOAST](topic:toast), which adds detoasting cost when the heap rows are checked.

**When it shows up.** On tables with frequent inserts or updates of the indexed column, and when autovacuum falls behind and the pending list grows.

**How to measure.**

```sql
SELECT pg_size_pretty(pg_relation_size('tickets_tags_gin')) AS index_size,
       pg_size_pretty(pg_relation_size('tickets')) AS table_size;

-- needs the pgstattuple extension
SELECT * FROM pgstatginindex('tickets_tags_gin');
```

`pgstatginindex` reports `pending_pages` and `pending_tuples`. Also compare insert latency before and after adding the index with `EXPLAIN (ANALYZE, BUFFERS)` on the write and read queries.

**When to worry.** A pending list that keeps growing between vacuums. Occasional insert latency spikes. An index close to or larger than the table (a rough rule of thumb, not a documented limit).

**What you can change.**

- Make autovacuum more aggressive on the table, so the pending list is cleaned in the background.
- Raise `gin_pending_list_limit` (per index, in kB) to reduce foreground cleanups, knowing that a cleanup then takes longer.
- Turn off fast update (`WITH (fastupdate = off)`) if steady response time matters more than insert speed.
- Raise `maintenance_work_mem` before large builds.
- For huge bulk loads, consider dropping and recreating the index.
- Use `jsonb_path_ops` if you only need containment queries.

## Practical checklist

- Use GIN when the question is "does this value contain X".
- Choose the operator class to match your `jsonb` queries.
- Make sure autovacuum runs often on GIN-indexed tables.
- Watch the pending list and index size.
- Do not use GIN on columns that are updated constantly unless reads justify it.
