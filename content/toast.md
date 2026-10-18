---
title: "TOAST: how PostgreSQL stores large values"
updated: 2026-10-17
sources:
  - https://www.postgresql.org/docs/17/storage-toast.html
  - https://www.postgresql.org/docs/17/sql-createtable.html
  - https://www.postgresql.org/docs/17/sql-altertable.html
  - https://www.postgresql.org/docs/17/runtime-config-client.html
  - https://www.postgresql.org/docs/17/largeobjects.html
  - https://www.postgresql.org/docs/17/lo-intro.html
  - https://www.postgresql.org/docs/17/lo-implementation.html
  - https://www.postgresql.org/docs/17/lo-interfaces.html
  - https://www.postgresql.org/docs/17/lo.html
  - https://www.postgresql.org/docs/17/vacuumlo.html
  - https://www.postgresql.org/docs/17/app-pgdump.html
  - https://www.postgresql.org/docs/17/functions-admin.html
  - https://www.postgresql.org/docs/17/monitoring-stats.html
  - https://www.postgresql.org/docs/17/pgstatstatements.html
  - https://www.postgresql.org/docs/17/runtime-config-autovacuum.html
---

This article is about **PostgreSQL**, and the details were checked against the PostgreSQL 17 documentation. Other engines solve the same problem differently. MySQL/InnoDB keeps long values on separate overflow pages, SQL Server moves them to row-overflow or LOB pages, and Oracle stores LOBs in a separate LOB segment. The names and thresholds differ, but the idea is the same: a page is small, so big values live somewhere else.

> **Draft status:** the SQL in this article has been written against the documentation but **not yet run**. Treat every snippet as untested until this note is removed.

## What TOAST is and when it kicks in

PostgreSQL [pages](topic:page) are 8 kB by default, and a row ([tuple](topic:tuple)) cannot span pages. A single value, such as a 1 MB JSON document, therefore cannot sit inside the row. TOAST (The Oversized-Attribute Storage Technique) is the mechanism that solves this, transparently to your queries.

It only starts when a row is wider than about 2 kB (the `TOAST_TUPLE_THRESHOLD`). Once it does, PostgreSQL compresses and/or moves column values out of the row until the row is below the target length (`toast_tuple_target`, also about 2 kB by default, 2040 bytes with 8 kB pages) or nothing more can be gained. You can change the target per table, between 128 bytes and the page size minus the header, and it only affects newly written rows:

```sql
ALTER TABLE documents SET (toast_tuple_target = 4096);
```

Values moved out of line go into a hidden **TOAST table** that belongs to the parent table (its OID is in `pg_class.reltoastrelid`). After compression, the value is cut into chunks of roughly 2 kB. Each chunk is one row in the TOAST table, with the columns `chunk_id`, `chunk_seq` and `chunk_data`, and a unique index on `(chunk_id, chunk_seq)`. The main row keeps only an 18-byte pointer, whatever the size of the value. A single value can be at most 1 GB.

Each column has one of four **storage strategies**:

| Strategy | Compression | Out of line | Typical use |
|---|---|---|---|
| `PLAIN` | no | no | Fixed-width types. The only option for them. |
| `EXTENDED` | yes | yes | Default for most TOAST-able types (`text`, `jsonb`, `bytea`). |
| `EXTERNAL` | no | yes | Data that is already compressed, or heavy substring access. |
| `MAIN` | yes | only as a last resort | Keep values in the row if at all possible. |

Change a strategy with `ALTER TABLE ... ALTER COLUMN ... SET STORAGE`. This changes nothing in existing rows; it only sets what happens on future writes.

For compression, PostgreSQL offers `pglz` (the default) and `lz4` (only if the server was built with it). The server-wide default is `default_toast_compression`, and you can override it per column:

```sql
ALTER TABLE documents ALTER COLUMN body SET COMPRESSION lz4;
ALTER TABLE documents ALTER COLUMN pdf SET STORAGE EXTERNAL;
```

Again, only values written afterwards are affected.

## What goes through TOAST

Only types with a variable-length representation (the [GIN](topic:gin) index builds on this for large key lists): `text`, `varchar`, `bytea`, `json`, `jsonb`, `xml`, arrays and similar. Fixed-width types such as `integer`, `bigint`, `timestamp` or `uuid` never use it.

JSON deserves a warning. A `jsonb` document is one value. If it is large, it is compressed and stored as a single opaque blob. Reading one key means fetching and decompressing the whole document, and changing one key writes a new copy of the whole document. The documentation makes the same point about TOASTed fields in general: most operations read or write the value as a unit.

## Images and video: technically yes, practically no

A `bytea` column is TOASTed, so a 5 MB image fits, up to the 1 GB limit. The problems are practical:

- The whole value is handled in memory, in the server and in your client. There is no streaming of a `bytea`.
- Every change to the value, and the initial insert, goes into the WAL, which grows replication traffic and backup size.
- Large values can push useful pages out of the buffer cache.
- Backups, dumps and restores become slow and large.

The usual recommendation is to keep large binaries in object storage (S3 and similar) and store the key or URL plus metadata (size, type, checksum) in the database. `bytea` is still reasonable for small thumbnails and small attachments, or when the file must be part of the same transaction as the row that owns it.

## Large Objects, the other mechanism

PostgreSQL has a second facility: **Large Objects**. They live in the system table `pg_largeobject`, with one entry per object in `pg_largeobject_metadata`. You create them with `lo_*` functions and refer to them from your tables by `oid`.

The documentation says TOAST makes this facility partially obsolete, but two advantages remain. An object can be up to 4 TB, and you can read or write a part of it, with seek, instead of the whole value. Objects are split into chunks stored as rows, and unwritten ranges take no space. They have an owner and permissions managed with `GRANT` and `REVOKE`. All `lo_*` file-descriptor operations must run inside a transaction block.

The main pitfall is cleanup. A large object is independent of the row that references it, so deleting the row leaves the object behind:

```sql
-- Orphan protection with the lo module (contrib)
CREATE EXTENSION lo;
CREATE TABLE image (title text, raster lo);
CREATE TRIGGER t_raster BEFORE UPDATE OR DELETE ON image
    FOR EACH ROW EXECUTE FUNCTION lo_manage(raster);

-- Remove objects already orphaned (shell command)
-- vacuumlo -n mydb     (dry run)
-- vacuumlo mydb
```

`lo_manage` assumes only one row references each object. It does not fire on `DROP TABLE` or `TRUNCATE`, so use `vacuumlo` as a back-stop. Also check your dump setup: `pg_dump` includes large objects by default, except when you select specific schemas or tables, where you must add `--large-objects`. Finally, the system table `pg_largeobject` has no TOAST table of its own, so PostgreSQL does not compress large objects for you. Compress in the client if you need it.

| | TOAST / `bytea` | Large Objects | Object storage + key |
|---|---|---|---|
| Size limit | 1 GB per value | 4 TB per object | Practically none |
| Streaming / partial access | No (whole value) | Yes, with seek | Yes (range requests) |
| Transactional | Yes | Yes | No, you coordinate it |
| Backup | In the table backup | In the dump, if included | Separate backup |
| Cleanup | Automatic with the row | Manual (`lo_unlink`, `vacuumlo`, `lo_manage`) | Your own lifecycle rules |
| Typical use | Small files, JSON, text | Rare: huge objects needing partial access in the DB | Images, video, documents |

## Why it matters for performance

The upside of TOAST is that the main table stays small. Queries that filter on small columns work on narrow rows, more of them fit in the buffer cache, and sorts stay in memory. Big values are fetched only when you select them, so `SELECT id, title` is cheap and `SELECT *` is not.

Watch for these costs:

- **Detoasting.** Reading a toasted column means fetching its chunks and decompressing them. A filter on the content (`WHERE body LIKE '%x%'`, `length(body) > 100000`) detoasts every candidate row. An index scan finds rows quickly, but still has to fetch the toasted columns you select.
- **Compression CPU.** Compression and decompression cost CPU. For data that is already compressed (JPEG, PDF), `EXTERNAL` avoids wasted work. It also makes substring operations on large `text` and `bytea` faster, because PostgreSQL can fetch only the needed chunks of an uncompressed value.
- **Hidden size.** A table with 100,000 rows can hold tens of gigabytes. Row counts and the main table size tell you little about it.
- **Updates.** An `UPDATE` that does not touch the toasted column keeps the same pointer, so it costs no TOAST work. Changing the toasted value writes a new copy to the TOAST table. The old chunks stay as dead rows until vacuum removes them.
- **WAL and replication.** New copies of big values are written to the WAL, so frequent updates of large values mean high WAL volume and more replication lag.

## Why it matters for database health, and what to monitor

The TOAST table is vacuumed together with its parent, but it is a table like any other and can bloat. Autovacuum decides about the TOAST table on its own statistics. You can tune it with the `toast.`-prefixed storage parameters, for example `toast.autovacuum_vacuum_scale_factor`. The values below are rules of thumb, not documented limits.

**1. Heap, TOAST and index size.** `pg_relation_size` on the table returns only the main data. The TOAST table is separate.

```sql
SELECT c.oid::regclass AS table_name,
       pg_size_pretty(pg_relation_size(c.oid)) AS heap,
       pg_size_pretty(coalesce(pg_total_relation_size(nullif(c.reltoastrelid, 0)), 0)) AS toast,
       pg_size_pretty(pg_indexes_size(c.oid)) AS indexes,
       pg_size_pretty(pg_total_relation_size(c.oid)) AS total
FROM pg_class c
WHERE c.oid = 'documents'::regclass;
```

`pg_table_size` is heap plus TOAST (plus free space and visibility maps), and `pg_total_relation_size` adds the indexes. Worry when TOAST is many times larger than the heap and you did not expect it.

**2. TOAST dead tuples and vacuum.** TOAST tables appear in `pg_stat_all_tables` in the schema `pg_toast`.

```sql
SELECT s.schemaname, s.relname, s.n_live_tup, s.n_dead_tup,
       s.last_autovacuum, s.autovacuum_count
FROM pg_class c
JOIN pg_stat_all_tables s ON s.relid = c.reltoastrelid
WHERE c.oid = 'documents'::regclass;
```

Worry when `n_dead_tup` stays high relative to `n_live_tup` and `last_autovacuum` is old or null.

**3. Compression effectiveness.** `pg_column_size` returns the stored size, `octet_length` the raw size.

```sql
SELECT avg(pg_column_size(body)) AS stored_bytes,
       avg(octet_length(body))   AS raw_bytes
FROM documents TABLESAMPLE SYSTEM (1);
```

A stored size close to the raw size means compression is not helping. Consider `EXTERNAL` for that column.

**4. Tables with the biggest TOAST share.**

```sql
SELECT c.oid::regclass AS table_name,
       pg_size_pretty(pg_total_relation_size(c.reltoastrelid)) AS toast,
       round(100.0 * pg_total_relation_size(c.reltoastrelid)
             / pg_total_relation_size(c.oid), 1) AS toast_pct
FROM pg_class c
WHERE c.relkind = 'r' AND c.reltoastrelid <> 0
ORDER BY pg_total_relation_size(c.reltoastrelid) DESC
LIMIT 20;
```

**5. WAL rate and replication lag.** Sample the WAL position twice and compare:

```sql
SELECT pg_current_wal_lsn();            -- note the value, wait a minute, run again
SELECT pg_wal_lsn_diff('0/5000000', '0/3000000');  -- replace with your two values

SELECT application_name, write_lag, flush_lag, replay_lag
FROM pg_stat_replication;
```

Worry when WAL bursts line up with updates to large columns, and lag grows with them.

**6. Cache hit ratio on TOAST blocks.**

```sql
SELECT relname, toast_blks_read, toast_blks_hit,
       round(100.0 * toast_blks_hit / nullif(toast_blks_hit + toast_blks_read, 0), 1) AS hit_pct
FROM pg_statio_all_tables
WHERE relid = 'documents'::regclass;
```

A low percentage means large values are mostly read from outside shared buffers (possibly from the OS cache). A cold, big working set is common here, so compare against the heap numbers in the same view.

**7. Slow queries that read large columns.** This needs the `pg_stat_statements` extension to be loaded.

```sql
SELECT left(query, 80) AS query, calls, mean_exec_time, shared_blks_read, wal_bytes
FROM pg_stat_statements
ORDER BY shared_blks_read DESC
LIMIT 10;
```

Look for `SELECT *` queries on tables with wide columns, and for updates with large `wal_bytes`.

## Practical guidance

- Select only the columns you need. Avoid `SELECT *` on tables with large values.
- Move rarely-read large columns into a side table keyed by the main id.
- Avoid frequent updates of big `jsonb` documents. Split hot keys into their own columns.
- Use `EXTERNAL` for data that is already compressed, such as JPEG or PDF.
- Consider `lz4` for faster compression, if your build has it.
- Tune autovacuum for TOAST-heavy tables with the `toast.` storage parameters.
- Keep big binaries out of the database. Store a key and metadata instead.
