# Prompt: how to write a learning track

Use this when an AI (or a person) writes a track in `data/tracks/<name>.yaml`. Files starting with `_` are ignored by the build. For articles, read `content/_prompt.md` too.

## Two kinds of track

| Kind | `kind:` | For | Looks like |
|---|---|---|---|
| **General** | `general` (the default) | Teaching a subject from basic to advanced: "PostgreSQL Storage", "Anatomy of PostgreSQL" | A route icon, a gold name, only "Step N of M" |
| **Problem** | `problem` | Something that goes wrong: "High CPU", "Low free disk space", "Slow query", "Large database" | A warning icon, an orange name, shown as **Problem: High CPU**, with the phase of each step |

Name a problem track with the symptom alone ("High CPU", "Low free disk space"). The viewer adds the word "Problem". Put the problem tracks after the general ones.

## The flow of a problem track

A problem track always has the same three parts, in this order:

1. **The problem** (`phase: problem`). One or two articles about the problem itself. The first article opens with one sentence that says what is in it, in this order:
   - **What the problem is.**
   - **The impact.** Why the reader should care, and what bad things can happen when the problem happens.
   - **How to get the data.** Last. The data that shows the problem. Say where each signal comes from: the **operating system or the cloud monitoring** (for example CPU use, free space, the CPU split), or a **PostgreSQL system view or function** (for example `pg_stat_activity`, `pg_stat_statements`, `pg_database_size`). On a managed service, say what you can and cannot see.
2. **The potential root causes** (`phase: causes`). Exactly one article, a **quick overview** of every potential root cause, one or two sentences each, with a link to the article that discusses it. Add the tell-tale sign of each cause when it is short. Do not discuss the fixes here.
3. **Each root cause in detail** (`phase: cause`). The rest of the track: one article for each cause, or for two causes that go together. Each answers: what it is, **what more data is needed to tell whether this is really the cause** (the data from the first article is not enough to be sure), what to do, with the cost and the downside of each fix, and the common mistakes.

The `problem` field of the track is **one sentence that says what the problem is**, in the reader's words and without advice or jargon, for example "The CPU of the database instance has been close to 100% for too long." The viewer shows it under the header of every step as: **The problem:** that sentence, followed by the fixed sentence "In this track we will review the impact, the potential root causes and how to analyze them." Do not repeat the impact in the field. The impact is the second part of the first article.

## Rules

- The build checks the phases: every step has one, the first step is `problem`, the order is problem, then causes, then cause, and there is a `causes` step. A general track must not have phases.
- 3 to 10 steps. Reuse topics from other tracks as root-cause articles when one exists (for example the article on connection pooling is the root-cause article for "too many active sessions"). A topic may be in several tracks.
- A cause that has no article yet can be a topic with no article. It shows as "coming soon". Plan the article before you list it.
- When one track hands over to another (for example from disk space to a large database), make the hand-over the last step and say so in its `why`.
- The `why` line of a step says why it is in the track, in one sentence.
- **Do not name a PostgreSQL version** in a track or in its articles unless a feature really differs between versions. See "Versions" in `content/_prompt.md`.
- Keep vendor material short. A product appears as one step at most, and only if it helps with the problem.
- A list of causes is not a tree. Do not call it a tree, a branch or a hypothesis. Say "potential root causes".

## The header the reader sees

The name with its icon, then the phase and the step ("The problem, Step 1 of 10"), a ring with the percentage, Previous and Next, one segment for each step, and the problem statement. It does not show how many prerequisites a topic has.

## Checklist

- Is the track named with the symptom, and is `kind: problem` set?
- Is `problem` one short sentence that says what the problem is (the viewer adds the rest)?
- Does the first article say what the problem is, then the impact, and last how to get the data (and from which source)?
- Does every cause article say what more data is needed to confirm it?
- Is there one overview of the potential root causes, and does it link to a detailed article for each?
- Does every cause that is listed have an article, or a plan for one?
