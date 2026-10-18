---
title: Database Internals
---

An open, interactive map of how databases work. Every dot on the left is a concept. Every line says what you need to understand first. The articles use **PostgreSQL** as the reference engine and note how other engines differ.

**How to use it.** Drag to rotate the map, scroll to zoom, and click a dot to read about it. A ring on a dot means there is a full article. Click a subject in the legend to hide or show it. Each article explains what a concept is, why it matters for performance, how to measure it, and what to change.

## Where to start

- **Storage.** Begin with the [page](topic:page), the unit of disk I/O. Then see how rows live in it: [tuple](topic:tuple) and [heap table](topic:heap). Then [TOAST](topic:toast), which stores large values.
- **Indexing.** Start with the [index](topic:index) and why every database needs one. Then the types: [B-Tree](topic:btree), [Hash](topic:hash), [GIN](topic:gin) and [BRIN](topic:brin).
- **Query planning.** Start with [statistics](topic:statistics), the planner's view of your data. Then the [execution plan](topic:execution-plan), how it is chosen by [cost](topic:cost-based-optimization), and the [actual plan](topic:actual-plan) with real measurements.
- **Concurrency.** Start with the [deadlock](topic:deadlock): what it is, why it hurts, and how to detect it.

## About the project

The map and the articles are plain files in a Git repository. To add or fix a topic, see `CONTRIBUTING.md` in the repository.
