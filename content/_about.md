---
title: About Database Internals
---

Database Internals is an open, interactive map of how databases work, built around PostgreSQL. You can explore the concepts, see how they connect, and follow a learning track to build your understanding step by step.

## Why it exists

Databases are full of ideas that are hard to see from the outside: why a table grows when you delete rows, why a query that was fast yesterday is slow today, why a lock wait turns into a deadlock. Understanding these things is what separates guessing from solving a problem.

The project exists to:

- **Help Solution Architects** explain deep database internals to customers.
- **Help customers** solve problems faster, because they understand why something happens and why a fix should work.
- **Show Dynatrace** as a company that helps customers understand the technology underneath their problems.

## How it is organised

- **Topics.** One topic is one idea, such as a page, an index, MVCC or a deadlock. Many topics have a full article.
- **Prerequisites.** Every topic shows what to understand first and what it unlocks next, with a reason for each link.
- **Subjects.** Colours group topics into subjects such as Storage, Indexing and Concurrency.
- **Learning tracks.** An ordered path through topics, from basic to advanced, built around one goal.

## What an article gives you

Each article answers four questions: what it is, why it matters for performance, how to measure it, and what to change. The articles use real examples, SQL you can run, and short animations. Every claim comes from the official documentation, and any SQL that was not run is marked.

## Who it is for

Backend engineers, DBAs and Solution Architects who know SQL but are not expected to be database internals experts.

## How it is built

Everything is plain files in a Git repository: the topics, the articles, the tracks and the animations. Anyone can suggest a fix or a new article with a pull request.

## Where it stands

This is an early, experimental project. Topics and articles are added often, and some topics are still marked "coming soon".
