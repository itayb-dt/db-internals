# Prompt: how to write a learning track

Use this when an AI (or a person) writes a track in `data/tracks/<name>.yaml`. Files starting with `_` are ignored by the build. For articles, read `content/_prompt.md` too.

## Two kinds of track

- **A problem track** starts from something that went wrong ("My query is slow", "My database is large", "The DB instance is running out of disk space"). Write it with the structure below.
- **A learning track** teaches a subject from basic to advanced ("PostgreSQL Storage", "Anatomy of PostgreSQL"). It has no `problem` and no `phase`. Its header only shows the step.

## The problem statement

A problem track has a `problem` field. It is shown in the header of every step, so the reader always knows why they are here.

- One or two sentences, plain words.
- **What happened,** in the reader's words: "A query that used to be fast now takes seconds."
- **Why they should care,** briefly: what it costs, or what breaks if they ignore it.
- No advice, no jargon, no product names, no numbers you cannot defend.

## The three questions

Every step of a problem track belongs to one phase, and the phases go in this order:

| Phase (`phase:`) | The question | What the steps give the reader |
|---|---|---|
| `now` | **What is happening now?** | The relevant metrics and events, and the recent trends. How to see the size of the problem and when it began. |
| `why` | **Why did it happen?** | The potential root causes. Help the reader weigh the explanations and find the most reasonable one. Explain the cause in plain words before the technical detail. |
| `fix` | **How to fix it?** | The fixes, with their cost and downside, and how to check that the fix worked. |

Rules:

- Order the steps `now`, then `why`, then `fix`. The build fails on a different order, and on a track where only some steps have a phase.
- A phase may have several steps, and a phase may be empty. A track that only points elsewhere for the fix can end with a hand-over step.
- A step that belongs to two phases is two ideas. Split the topic, or choose the phase of its main idea.
- Start with the cheapest checks. The first step should say what to look at first and what to rule out.

## The steps

- 3 to 10 steps. One topic per step. Use topics that already have an article, and add the missing articles in track order.
- The `why` line of a step says why it is in the track, in one sentence. If the sentence needs "and", the step is doing too much.
- Reuse topics from other tracks. A topic can be in several tracks. When one track hands over to another, make the hand-over the last step, and say so in its `why`.
- Keep vendor material short. A product appears as one step at most, and only if it answers one of the three questions.

## The header the reader sees

The header is short on purpose. It shows the name of the track with an icon, the phase and the step ("Why did it happen, step 3 of 9"), a ring with the percentage, Previous and Next, one segment for each step, and then the problem statement. It does not show how many prerequisites a topic has, or the next step twice.

## Checklist

- Is the problem written as what happened and why it matters, in one or two sentences?
- Does every step have a phase, in the order now, why, fix?
- Does the first step tell the reader what to check first?
- Does every step have an article, or a plan for one?
- Does the last step hand over, if the fix belongs to another track?
