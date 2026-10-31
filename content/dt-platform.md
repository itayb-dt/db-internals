---
title: "Dynatrace Observability Platform: the database needs context"
updated: 2026-10-22
sources:
  - https://docs.dynatrace.com/docs/observe/infrastructure-observability/databases
  - https://docs.dynatrace.com/docs/observe/data-observability
  - https://docs.dynatrace.com/docs/dynatrace-intelligence/use-cases/cost-intelligence
---

This article continues from [What a good database observability system gives you](topic:db-observability-expectations). It shows why the database cannot be understood alone, and what the Dynatrace platform brings around it. The next topic zooms in on [the Databases app](topic:dt-databases-app).

## A database is never alone

Take a real complaint: "checkout is slow". Looking only at the database, you may see a busy server and a few heavy queries. That does not tell you whether those queries are the cause, who runs them, or whether anything else is wrong. The answer is usually in the context:

- A **service** started calling the database more often after a deployment.
- The **host** is short of CPU or its disk is slow.
- A **Kubernetes** pod restarted and opened hundreds of new connections.
- A **cloud** resource behind the database hit a limit.
- A downstream **log** shows the application retrying.

A database tool that sees only the database can describe the symptom. To find the cause, you need the surrounding stack.

## The whole stack in one place

The Dynatrace platform collects the layers together:

| Layer | What you see | Why it matters for the database |
|---|---|---|
| Hosts and cloud | CPU, memory, disk, network, cloud service metrics | Rules in or out a resource problem under the database |
| Services | Which services call the database, how often, how slow | Shows who is affected and who creates the load |
| Traces | One request followed across services and database calls | Connects a slow statement to a user action |
| Logs | Application and database logs next to the metrics | Gives the exact error or slow statement |
| Kubernetes | Clusters, workloads and pods | Explains connection surges and restarts |
| Topology | How all of this depends on each other | Tells you the blast radius of a database problem |

The point is that these are **integrated**, not separate tools. You can start from a failing service, follow a trace to a statement, and open the database that ran it. You can also start from a database health alert and see which services depend on it. The platform stores the data in one place, called Grail, and can analyse it together.

## From data to answers

Collecting everything is not enough. The platform also relates the data, so that an anomaly in the database and a deployment ten minutes earlier appear as one problem, not as two alerts. This matters for the [root cause analysis](topic:db-observability-expectations) described earlier: a good explanation often lies outside the database.

## FinOps: databases cost money

Databases are some of the most expensive parts of a cloud bill. The same platform data helps with **FinOps**, the practice of understanding and controlling cloud cost:

- Which hosts and workloads are over-provisioned or idle.
- How consumption develops and what it is likely to cost.
- Where the cost belongs, by team or application.

For a database this means finding oversized instances, unused databases and expensive queries that force you to buy more capacity. Performance work and cost work often meet: one query fixed can mean a smaller instance.

## Data observability

A database can be healthy while the **data** in it is wrong. Dynatrace also has **data observability**, which looks at the data itself and at the pipelines that carry it. Its documentation names five pillars:

- **Freshness:** is the data current?
- **Distribution:** are the values in the usual range?
- **Volume:** did the amount of data suddenly rise or drop?
- **Schema:** did fields appear, vanish or change?
- **Lineage:** where does the data come from and what depends on it?

This is a different question from "is the server healthy". It is the concern of data engineers, who run pipelines and warehouses such as Snowflake. The [Databases app](topic:dt-databases-app) and the Data app serve these two audiences.

## Common mistakes

- Treating a database alert as proof that the database is the cause.
- Running a separate tool per layer and joining the evidence by hand.
- Looking at cost and performance in separate meetings, when one query often explains both.
- Checking server health but never checking whether the data arrived on time.

## Checklist

- Can you go from a failing service to the database statement behind it, and back?
- Do host, cloud, Kubernetes and log data sit next to the database data?
- Do related alerts become one problem?
- Can you attribute database cost to teams or applications?
- Do you watch freshness and volume of the data, not only the server?
