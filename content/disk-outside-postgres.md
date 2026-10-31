---
title: "Managed or self-managed: what else uses the disk"
updated: 2026-10-31
sources:
  - https://www.postgresql.org/docs/17/storage-file-layout.html
  - https://www.postgresql.org/docs/17/runtime-config-logging.html
  - https://www.postgresql.org/docs/17/continuous-archiving.html
---

This article continues from [The slow query log](topic:slow-query-log). So far the track looked at what PostgreSQL writes. This article is about the disk usage PostgreSQL does not know about, and about who owns what on a managed service and on a system you run.

## Two worlds

| | Managed cloud service | A system you run (VM, bare metal, Kubernetes) |
|---|---|---|
| Who runs the operating system and the volume | The provider | You |
| Who runs backups and snapshots | The provider, with settings you choose | You |
| What fills your storage | Almost only PostgreSQL itself: the data, the write-ahead log, the logs and temporary files | PostgreSQL, and anything else on the same disk |
| What you can see | Storage metrics from the provider, and PostgreSQL's own views | The whole host, and PostgreSQL's views |
| What you can fix | PostgreSQL's settings, and usually the size of the storage | Everything, which also means everything is your job |

### On a managed service

On a managed service such as Amazon RDS, the previous articles are very nearly the whole story. The provider's layer holds the operating system, the volume setup and the backups. What uses **your allocated storage** is mostly the data, the write-ahead log, the logs and temporary files: the things this track covered. Two points to check in your provider's documentation: whether the storage can grow automatically, and whether it can ever shrink. Often it can grow but not shrink, so a one-off bloat can leave you paying for space for good.

Also check how the provider counts logs and backups against the storage you pay for, and how replication slots and other settings are exposed to you.

### On a system you run

When you run the operating system yourself, on a virtual machine or on Kubernetes, more things share the disk, and they use space **regardless of the PostgreSQL instance**.

The animation compares a managed service with a system you run, shows the gap between what PostgreSQL reports and what the volume shows, and the fix.

<iframe src="disk-outside-postgres/demo.html" title="Animation: on a managed service the volume holds only PostgreSQL files. On a system you run, backups, other logs and snapshots add 34 GB that PostgreSQL does not report. Separate volumes keep one from filling another" width="800" height="450"></iframe>

*The animation repeats about every 28 seconds.*

## What else fills the disk

**Backups and dumps on the same volume.** Base backups, dump files and the local copy of the archive directory are easy to leave on the database host. They can be larger than the database, and they grow every day. A backup job that runs out of space also fails to produce a backup.

**Disk layout.** Everything on one volume means the data, the write-ahead log, the logs and the backups compete. A good layout separates them, so a runaway log cannot stop the database from writing. A volume that is too small for growth is the plain version of the same mistake. Filesystems also reserve a share of space and a limited number of file entries, so a disk can report free space and still refuse new files.

**Logs from other software.** The system log, the container runtime and other services on the same host write logs too, and PostgreSQL's own logs may be rotated by an operating-system tool you must configure.

**Snapshots.** Volume snapshots and copy-on-write file systems keep old blocks. A snapshot you forgot about holds space that deleting data does not return.

**Crash files.** Core dumps from a crashed process can be as large as the memory it used.

**Other tenants of the host.** On a shared node, other containers, images and volumes may use the same disk.

### Kubernetes

Kubernetes adds its own limits:

- **The persistent volume** that holds the data has a fixed size. Growing it needs support from the storage class, and it may need steps you must know before you need them.
- **Ephemeral storage**, the space a container uses for itself, and for anything written outside a mounted volume, is limited per pod and per node. A pod can be evicted when it is exceeded.
- **Sidecars and log collectors** write their own files.
- An **operator** that manages PostgreSQL may handle volumes, backups and rotation for you. Find out what it does, and what it leaves to you.

## How to find disk use that PostgreSQL does not know about

The test is to **compare two numbers**:

1. What PostgreSQL reports: the databases, the write-ahead log, the logs and temporary files, added up.
2. What the volume reports as used.

If the second is much larger than the first, the **gap** is outside PostgreSQL. Then use the operating system's own tools to list which directories on the volume are largest, and look for backups, dump files, other logs, snapshots and crash dumps. On Kubernetes, look at the volume from inside the pod, and at the node's storage.

## What to put in place

- **Separate volumes** for the data, the write-ahead log, the logs and the backups, so one cannot fill another.
- **Backups off the host.** Keep only what is needed for the job locally.
- **Rotation and removal** for logs, in PostgreSQL and in the operating system.
- **Alerts for each volume,** on time to full, and on free file entries as well as free space.
- **A written note** of what is yours and what the provider's on each platform.

## Why it matters for performance

**What it costs.** A full volume stops writes, no matter who filled it. Space used by non-PostgreSQL files is invisible to PostgreSQL's own monitoring.

**When it shows up.** On systems you run, after a change that adds files: a backup job, a debug setting, a new sidecar or a crash.

**How to measure.** The two numbers above, per volume, over time.

**When to worry.** As a rule of thumb, when the gap between the volume and PostgreSQL's total is more than a small share of the volume, or when it grows.

**What you can change.** Separate the volumes, move the backups, rotate the logs, remove old snapshots, and size the volume for growth.

## Common mistakes

- Trusting PostgreSQL's numbers alone on a system you run.
- Keeping backups on the database disk.
- Putting the data, the log and the backups on one volume.
- Assuming that managed storage can shrink.
- Not checking how the provider counts logs and backups.

## Checklist

- Is this a managed service or a system you run? Who owns each layer?
- Do PostgreSQL's numbers add up to the volume's usage?
- Are the data, the log and the backups on separate volumes?
- Are backups kept off the host?
- Is anything on the volume rotated and removed?
- If the largest consumer is a database, go to [Large database](topic:database-size-problem).
