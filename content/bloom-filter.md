---
title: "Bloom filters and the bloom index: a cheap way to say no"
updated: 2026-10-31
sources:
  - https://www.postgresql.org/docs/17/bloom.html
  - https://www.postgresql.org/docs/17/contrib.html
  - https://www.postgresql.org/docs/17/indexes-types.html
---

This is an **advanced topic** and is not part of any track. It starts with the general idea of a Bloom filter, then shows how PostgreSQL uses it in the `bloom` index.

## What a Bloom filter is

A Bloom filter answers one question about a set: *is this value in it?* It gives one of two answers:

- **"Definitely not."** This answer is always right.
- **"Maybe."** This answer can be wrong. The value may not be in the set.

In return, it is tiny. It does not store the values at all, only a row of bits, all starting at 0, and a few hash functions.

- **To add a value,** run it through the hash functions. Each one picks a bit. Set those bits to 1.
- **To check a value,** run it through the same hash functions and look at the bits. If any bit is 0, the value was never added. If all are 1, it may have been.

The animation shows both steps on a 16-bit array with three hash functions. It adds two values, checks one that is absent (a certain no), and then checks one that was never added but still gets a "maybe".

<iframe src="bloom-filter/demo.html" title="Animation: a Bloom filter is 16 bits. Adding alice and bob sets three bits each. Checking carol finds a 0 bit, so she is definitely not in the set. Checking dave finds three 1 bits, so he may be in the set, which here is a false positive" width="800" height="450"></iframe>

*The animation repeats about every 20 seconds.*

## Why there are false positives, and never false negatives

Different values share bits. After enough values have been added, the bits that a new value picks may all be 1 already, set by other values. That is a **false positive**: the filter says "maybe" for a value that was never added.

A false negative cannot happen. A value that was added set its bits to 1, and bits are never set back to 0. That is why a "no" is always safe to trust.

Two practical consequences:

- **A "maybe" must be checked** against the real data. The filter only removes the work that is not needed.
- **The bit array fills up.** The more values it holds, the more false positives. A bigger array, or fewer values, lowers the rate. As a rule of thumb, about 10 bits per value with a few hash functions gives roughly 1% false positives.

A plain Bloom filter also cannot remove a value, because clearing a bit could erase another value's mark.

## When it pays off

A Bloom filter helps when two things are true:

1. The real check is **expensive**: a disk read, a network call, or a scan of a big file.
2. **Most checks have the answer "no".** Then the cheap filter saves most of the real checks, and the false positives cost little.

If most values are present, the filter says "maybe" almost every time and saves nothing.

## Real-world scenarios

These are well-known uses, described from general knowledge:

- **Databases built on sorted files** (Cassandra, RocksDB, HBase and similar). A read may have to look in many data files. Each file keeps a Bloom filter of its keys, so the database skips the files that certainly do not contain the key.
- **Joins across servers.** A query engine can send a small Bloom filter of the join keys to the side that holds the large table, so rows with no match are dropped before they cross the network.
- **Caches and CDNs.** A cache can use a filter to remember what was requested once, so it stores an object only on its second request, and avoids filling up with one-off items.
- **"Is it taken?" checks.** A signup page can ask a filter first, and go to the database only when the answer is "maybe".
- **Lists of known bad items,** such as malicious addresses, where a small local filter avoids a lookup for the vast majority of safe ones.

## In PostgreSQL: the bloom index

PostgreSQL ships a contrib module called `bloom`. It gives an index type built on Bloom filters. Each index entry is a small **signature** of the values in one row, and the signatures are used to rule rows out quickly.

**What it is for.** The documentation says it is most useful when **a table has many columns and queries test arbitrary combinations of them**. A B-tree is faster, but supporting every combination of filters would need many B-tree indexes. One bloom index can serve them all.

`bloom` is an extension, so it has to be installed like any other extension before you can use it. After that, you create one bloom index that covers the columns people filter on. A query that tests any of those columns, in any combination, can use it: `c2` and `c5` today, `c1`, `c3` and `c6` tomorrow.

**What it gives up.** It is a trade, and the documentation is open about it:

- **Equality only.** Only the `=` operator is supported. No ranges, no sorting.
- **Limited types.** The module includes operator classes for `int4` and `text` only.
- **No unique indexes, and no search for `NULL`.**
- **It is lossy.** Every match is rechecked in the table, because of false positives. In a plan this shows as `Rows Removed by Index Recheck` under a bitmap heap scan.

**What the documentation measured.** On a table of 10 million rows with six integer columns, a query on two columns took about 357 ms with a sequential scan, about 23 ms with one bloom index (153 MB), and under a millisecond with six separate B-tree indexes (531 MB in total). So the bloom index was much smaller than the six B-trees, and much faster than a scan, but not as fast as the matching B-trees. These are the documentation's numbers for its own test, not a promise for your data.

**Two settings control the error.** The signature length (`length`, 80 bits by default) and the number of bits per column (2 by default). Longer signatures mean fewer false positives and fewer useless table visits, but a bigger index that is slower to scan.

## Check your cloud vendor first

> **Reminder:** every extension must be checked against the cloud provider you use **before you design around it**. Managed PostgreSQL services allow only the extensions on their own approved list, and the list differs between providers and versions. A module that ships with PostgreSQL, like `bloom`, is not automatically available. Look up the provider's supported-extension list for your PostgreSQL version, and check again before a major upgrade or a move to another provider. An index that depends on a missing extension can block both.

## Why it matters for performance

**What it costs.** Disk space for the signatures, work on every insert and update to maintain them, and a table visit for each match, including the false ones.

**When it shows up.** On wide tables with many ad hoc equality filters, which is where it is meant to help. It is a poor fit for one frequent query on one column, where a B-tree is better.

**How to measure.** Compare the index size with the B-trees it would replace, and run `EXPLAIN (ANALYZE, BUFFERS)` on real queries. Look at how many rows the recheck removes compared with how many rows come back.

**When to worry.** As a rule of thumb, when the recheck throws away many more rows than the query returns, the signatures are too short for your data.

**What you can change.** Lengthen the signature or the bits for the most selective columns, replace the bloom index with B-trees on the one or two columns that are queried most, or rethink the design if the queries are not really arbitrary.

## Common mistakes

- Using a bloom index where a B-tree on one column would do.
- Expecting ranges or sorting from it.
- Reading a large "removed by recheck" count as a failure of the plan, when it is the filter working at its limit.
- Designing around the extension without checking the cloud provider.
- Testing on a small table. The benefit only shows at scale.

## Checklist

- Is the table wide, with many equality filters in changing combinations?
- Are the columns `int4` or `text`, and are all conditions equality?
- Did you check the provider's list of allowed extensions?
- Did you compare size and timing with the B-trees it replaces?
- Does the recheck remove far more rows than the query returns? If so, lengthen the signature or choose B-trees.
