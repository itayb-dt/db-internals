---
title: "Buffer pool settings: sizing the cache and writing dirty pages"
updated: 2026-10-21
sources:
  - https://www.postgresql.org/docs/17/runtime-config-resource.html
  - https://www.postgresql.org/docs/17/runtime-config-query.html
  - https://www.postgresql.org/docs/17/runtime-config-wal.html
  - https://www.postgresql.org/docs/17/wal-configuration.html
  - https://www.postgresql.org/docs/17/monitoring-stats.html
  - https://www.postgresql.org/docs/17/pgbuffercache.html
  - https://www.postgresql.org/docs/17/pgprewarm.html
---

This article continues from [The buffer pool](topic:buffer). It covers the settings that size the pool, the ones that decide how fast dirty pages go to disk, and the ones that people often mistake for buffer settings. Other engines have the same knobs under other names: SQL Server limits memory with `max server memory`, and InnoDB sizes its pool with `innodb_buffer_pool_size`.

## The settings at a glance

```sql
SELECT name, setting, unit, context
FROM pg_settings
WHERE name IN ('shared_buffers', 'huge_pages', 'effective_cache_size',
               'bgwriter_delay', 'bgwriter_lru_maxpages', 'bgwriter_lru_multiplier',
               'checkpoint_timeout', 'max_wal_size', 'min_wal_size', 'checkpoint_completion_target',
               'temp_buffers', 'work_mem', 'maintenance_work_mem')
ORDER BY name;
```

The `context` column tells you how a setting can change: `postmaster` means a restart, `sighup` means a reload of the configuration, and `user` means any session can change it for itself.

| Setting | Default | Context | What it does |
|---|---|---|---|
| `shared_buffers` | 128 MB | restart | Size of the buffer pool |
| `huge_pages` | try | restart | Ask the operating system for huge memory pages for the pool |
| `effective_cache_size` | 4 GB | any session | **Planner hint only.** Not an allocation |
| `bgwriter_delay` | 200 ms | reload | Pause between rounds of the background writer |
| `bgwriter_lru_maxpages` | 100 | reload | Most pages the background writer writes per round |
| `bgwriter_lru_multiplier` | 2.0 | reload | How far ahead of demand it tries to keep clean buffers |
| `checkpoint_timeout` | 5 min | reload | Longest time between checkpoints |
| `max_wal_size` | 1 GB | reload | WAL size that triggers a checkpoint |
| `checkpoint_completion_target` | 0.9 | reload | Spreads a checkpoint's writes over this share of the interval |

## Sizing the pool: `shared_buffers`

The documentation's guidance: on a dedicated database server with 1 GB or more of RAM, **25% of the memory is a reasonable starting value**. Some workloads do better with more, but because PostgreSQL also relies on the operating system's cache, it is unlikely that more than about 40% of RAM works better than a smaller amount. A larger pool usually needs a larger `max_wal_size` too.

```sql
SHOW shared_buffers;
```

Changing it needs a restart, and the pool is empty after it:

```sql
-- not run: changes the server, and takes effect only after a restart
ALTER SYSTEM SET shared_buffers = '8GB';
```

Why not give it nearly all of the memory? The operating system's cache holds a second copy of what PostgreSQL reads, and the server also needs memory for connections, sorts and hashes (`work_mem`) and maintenance. Memory that is too tight leads to swapping, which is far worse than a smaller pool.

`huge_pages` (default `try`) lets the operating system use large memory pages for the pool on Linux. This reduces page table overhead and CPU time. With `on`, the server refuses to start if it cannot get them.

## `effective_cache_size` is not memory

`effective_cache_size` is the planner's **assumption** about how much cache is available to a single query, counting both the pool and the operating system's cache. It allocates nothing. It only changes cost estimates: a higher value makes index scans look cheaper and more likely (see [Cost Based Optimization](topic:cost-based-optimization)). A common mistake is to treat it as a memory setting. Set it to a realistic figure for the memory available for caching, usually the pool plus most of the free operating system cache.

## Writing dirty pages: background writer and checkpoints

Changes happen in the pool, and dirty pages must reach the data files. Two processes do this, besides ordinary queries that must evict a dirty page:

- **The background writer** writes dirty pages in small rounds, so that clean buffers are available when queries need them. `bgwriter_delay`, `bgwriter_lru_maxpages` and `bgwriter_lru_multiplier` control how hard it works. Setting `bgwriter_lru_maxpages` to zero disables it.
- **The checkpointer** flushes *all* dirty pages at each checkpoint, so recovery only replays the log after it. A checkpoint starts every `checkpoint_timeout` or when `max_wal_size` is about to be exceeded. Its writes are spread over `checkpoint_completion_target` of the interval, to avoid a burst of I/O.

The documentation notes the trade-off. Checkpoints that happen **more often** mean faster recovery after a crash, but more dirty-page writing and more WAL, because the first change to each page after a checkpoint writes a full copy of it (see [the buffer pool](topic:buffer)). Checkpoints that happen **less often** are cheaper while running, but recovery takes longer.

With `log_checkpoints` on (the default), each checkpoint appears in the server log. A real entry from my test server:

```
checkpoint complete: wrote 2915 buffers (17.8%); 0 WAL file(s) added, 1 removed, 1 recycled;
write=0.060 s, sync=0.022 s, total=0.089 s; sync files=307
```

## What is *not* a buffer pool setting

These are often confused with `shared_buffers`, but they are separate memory:

| Setting | Default | What it really is |
|---|---|---|
| `work_mem` | 4 MB | Memory for **one** sort or hash operation in a query, private to it. One query can use several, and many sessions run at once |
| `maintenance_work_mem` | 64 MB | Memory for `VACUUM`, `CREATE INDEX` and similar jobs |
| `temp_buffers` | 8 MB | Per-session buffers for **temporary tables** only |
| `effective_io_concurrency` | | How many read-ahead requests a session may issue. In 17 it only affects bitmap heap scans |

Raising `work_mem` does not make the cache bigger. It can make sorts and hashes avoid temporary files, which is a different gain.

## How to check what you have

**Is the pool large enough?** Look at the hit ratio and `shared read` values from [the buffer pool](topic:buffer) article. A low ratio on a busy database, with a working set that would fit in more memory, is the signal.

**Is the background writer keeping up?**

```sql
SELECT buffers_clean, maxwritten_clean, buffers_alloc FROM pg_stat_bgwriter;
```

`buffers_clean` is how many pages it wrote. A high `maxwritten_clean` means it stopped because it reached `bgwriter_lru_maxpages` in a round, so it may be limited too low.

**Are checkpoints too frequent?** In 17 the checkpoint counters are in their own view. Compare timed checkpoints with requested ones, which were forced by WAL size:

```sql
-- not run: this view exists from PostgreSQL 17; in 16 and earlier these counters are in pg_stat_bgwriter
SELECT num_timed, num_requested, buffers_written FROM pg_stat_checkpointer;
```

Many requested checkpoints mean `max_wal_size` is too small for the write load.

**What is in the pool now?** The `pg_buffercache` extension, as in the first article, or its summary:

```sql
-- not run: needs the pg_buffercache extension
SELECT * FROM pg_buffercache_summary();
SELECT * FROM pg_buffercache_usage_counts();
```

**Cold start.** After a restart the pool is empty. The `pg_prewarm` extension can load a table back in, and can also do it automatically at startup:

```sql
-- not run: needs the pg_prewarm extension
SELECT pg_prewarm('buf_demo');
```

## Why it matters for performance

**What it costs.** Pool memory is memory the operating system cannot use for its own cache. Frequent checkpoints cost I/O and WAL. Infrequent ones cost recovery time and WAL disk space.

**When it shows up.** A pool that is too small for the working set: constant misses, higher I/O. A pool that is too large: swapping, or no benefit because the operating system cache already did the work. Checkpoints too close together: periodic latency spikes and more WAL.

**When to worry** (rules of thumb, not documented limits): a hit ratio well below about 99% on an OLTP database, `num_requested` checkpoints close to or above `num_timed`, or latency spikes that line up with checkpoint log entries.

**What you can change.**

- Start `shared_buffers` at 25% of RAM, then measure. Change it only with evidence.
- Raise `max_wal_size` if checkpoints are forced by WAL volume, and accept the longer recovery.
- Keep `checkpoint_completion_target` at the default 0.9 unless you have a reason.
- Fix the queries that read too much before you enlarge the cache: [indexes](topic:index) and [partitions](topic:partitioning) reduce the pages touched.
- Prewarm after restarts if cold starts hurt.

## Practical checklist

- `shared_buffers` sizes the pool and needs a restart. 25% of RAM is the starting point.
- `effective_cache_size` is a planner hint, not memory.
- `work_mem`, `maintenance_work_mem` and `temp_buffers` are separate memory.
- Checkpoint frequency trades recovery time against I/O and WAL.
- Watch the hit ratio, `pg_stat_bgwriter` and the checkpoint counters.
- Measure before and after every change.
