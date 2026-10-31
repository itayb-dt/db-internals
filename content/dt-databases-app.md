---
title: "The Dynatrace Databases app"
updated: 2026-10-22
sources:
  - https://docs.dynatrace.com/docs/observe/infrastructure-observability/databases
  - https://docs.dynatrace.com/docs/observe/infrastructure-observability/databases/concepts
  - https://docs.dynatrace.com/docs/observe/data-observability
---

This article continues from [the Dynatrace Observability Platform](topic:dt-platform). There the database sat in the context of the whole stack. Here we zoom in on the view built for the database itself, and check it against the [expectations](topic:db-observability-expectations) of a good observability system.

## What the app is

The Databases app is where you monitor, analyse and optimise your databases: their performance, health and configuration. According to its documentation it supports engines including PostgreSQL, MySQL, Microsoft SQL Server, Oracle, MariaDB and SAP HANA.

It gets its data from **database extensions**. The extensions run on **ActiveGate**, a Dynatrace component that connects remotely to the database servers. They use a monitoring account that can read the system views and performance metrics. Host metrics from OneAgent complement this, when the host is monitored too.

## What you can do in it

| Need | In the app |
|---|---|
| Is everything healthy? | An **overview** of the whole fleet, and a **health score** for each instance based on availability, performance and configuration checks |
| Which database needs me? | An **explorer** table of instances with health alerts and utilisation such as CPU, memory and active sessions |
| What is in the database? | Views of **databases, tables and indexes**, including indexes that are unused or problematic |
| Which query hurts? | **Statement analysis**: filter the expensive statements by time, CPU, disk or waits, and request their **execution plans** |
| Who blocks whom? | Detection of **blocking queries and deadlocks** |
| What should I check? | **Recommendations** for monitoring gaps, and AI-assisted analysis with anomaly detection and root-cause hints |
| Tell me before users do | Ready-made **alert templates** per engine |

## How it meets the expectations

Compare with the list of what a good system gives you:

- **Built by database experts.** The concepts are those of a DBA: normalised statements, execution plans, blocking and deadlocks, health scores per engine.
- **Statements and plans.** The app collects both, so you can explain a regression.
- **Root cause and recommendations.** It provides AI-assisted analysis and recommendations. As with any such tool, read the evidence before acting. See [the checklist](topic:db-observability-expectations).
- **Context.** The app is part of the platform. The same data is available next to services, traces, logs and host metrics, and Smartscape shows the dependencies. This is the point of the previous topic: you can follow a slow database to the service that feels it, and the other way round.

For PostgreSQL, the things you can look at here are the ones this site explains: [statistics](topic:statistics), [execution plans](topic:execution-plan), [vacuum health](topic:vacuum-monitoring) and [deadlocks](topic:deadlock). Knowing them helps you judge what the app shows.

## Instance or host

Monitoring can target the database **instance** (through the extension) or the **host** it runs on. They are two views of the same thing: the instance shows what the database does, the host shows the resources it uses. Cover both when you can.

## The Data app is a different tool

Do not confuse the Databases app with the **Data app**. The Data app is for **data engineers**. It focuses on Snowflake and on data pipelines: freshness, volume and cost of data, not the internals of a database server. If your question is "why is this PostgreSQL query slow", use the Databases app. If it is "did last night's pipeline load the data on time", look at the Data app and [data observability](topic:dt-platform).

## What it costs

- **Collection load.** The extension queries the system views through a monitoring account, so keep it least-privilege and the interval reasonable.
- **Data volume.** Statements, plans and logs add up. Extension data goes to a dedicated Grail bucket, and access to it can be limited with a policy.
- **Setup.** An ActiveGate with network access to the database, and the extension configured for each one. Where drivers are needed, they must be installed on the ActiveGate.

## Common mistakes

- Reading a health score as the whole truth, without opening the alerts behind it.
- Monitoring the instance but not the host, or the reverse.
- Collecting statements but not enabling execution plans.
- Using the Data app to debug a database server, or the Databases app to check data freshness.

## Checklist

- Is every important database in the explorer, and does the recommendations view show no monitoring gaps?
- Is the monitoring account least-privilege?
- Are statements and execution plans collected?
- Do you know which services depend on each database?
- Do alerts use the engine templates, and do you act on health alerts, not only the score?
