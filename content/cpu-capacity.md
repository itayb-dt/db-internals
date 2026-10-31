---
title: "High CPU cause: not enough resources for the workload"
updated: 2026-11-01
sources:
  - https://www.postgresql.org/docs/17/pgstatstatements.html
  - https://www.postgresql.org/docs/17/monitoring-stats.html
---

This is one of the root causes listed in [Common root causes of high CPU](topic:high-cpu-causes).

## What it is

Nothing is wrong with any single statement. The workload simply needs more CPU than the instance has. The instance was sized for last year, or the business grew, or a new feature added load.

## What more data to look at

The first article gave the data that shows the problem. To confirm this cause, look at:

- **The CPU is high during the busy hours, in proportion to the load.** It follows the daily pattern and the traffic, not a single event.
- **Many sessions each use a little.** No process stands out.
- **The trend rises over weeks or months,** with the business.
- **The CPU needed for each request has not changed.** This is what separates it from costly statements. If the same statements now cost more each, look at [why statements are slow](topic:slow-query-causes). If there are simply more of them, or the same cost at a larger scale, it is capacity.
- **There is no headroom.** The peak is close to the limit, so any spike causes trouble.

The statistics views show it: statements per second and the total time of the top statements both grow, while the time per call stays about the same ([Query metrics](topic:query-metrics)).

## What to do

First make sure the work is not wasted. A few costly statements, a missing index or a retry storm can look like a capacity problem, and fixing them is cheaper than adding cores. Then add capacity:

| Option | What it gives | The catch |
|---|---|---|
| **More cores, or a larger instance** | The simplest way to get more CPU | Costs more every month. On a managed service it may need a restart, so check your provider |
| **Read replicas** | Moves reads and reports off the primary | Does nothing for writes. Replicas can lag |
| **Caching and fewer calls** | Less work for the same result | Needs changes in the application, and cached data can be stale |
| **Spreading the load in time** | Lowers the peak | Needs the work to be movable |

## How much headroom

Plan so that the busy hour sits well below the limit. As a rule of thumb, keep the peak under about 60% to 70% of the CPU, so a spike, a failover (where one node must carry everything) or a maintenance job fits. Track the trend, and add capacity before the peak reaches the limit, not after.

## Common mistakes

- Adding cores for a problem that is a runaway or costly statement.
- Sizing for the average, not for the peak.
- Adding capacity with no headroom plan, so the next spike hits the same wall.
- Forgetting that a failover moves all the load to one node.

## Checklist

- Is the CPU per request unchanged, and the number of requests up?
- Is the peak close to the limit?
- Is the work wasted? Rule out costly statements and retries first.
- Choose the option and keep 30% to 40% free at the peak.
