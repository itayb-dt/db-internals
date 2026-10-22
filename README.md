# Database Internals

An interactive map of how databases work, built around PostgreSQL. Explore the concepts, see how they connect, and follow a learning track to build your understanding step by step.

**Live site:** https://itayb-dt.github.io/db-internals/

## What this project is

Databases are full of ideas that are hard to see from the outside: why a table grows when you delete rows, why a query that was fast yesterday is slow today, why a lock wait turns into a deadlock. Understanding these things is what separates guessing from solving a problem.

This project explains those ideas in plain language, with real examples, SQL you can run, measurements from a real PostgreSQL, and short animations. It is written for people who work with databases but are not expected to be database internals experts.

## Topics: everything is connected

The unit of the map is the **topic**. A topic is one idea, such as a page, an index, MVCC, vacuum or a deadlock. It has a short explanation, and many topics have a full article that answers four questions: what it is, why it matters for performance, how to measure it, and what to change.

Topics are not separate pages. Each one shows what you need to understand first and what it unlocks next, and every one of those links has a reason. A topic like *dead rows* builds on *MVCC*, which builds on how a row is stored. Open any dot on the map and you can follow the links up to the basics or forward to the practical consequences. Colors group the topics into subjects: storage, indexing, query planning, partitions, concurrency and architecture.

## Learning tracks: a path to a clear target

A map is great for exploring, but sometimes you have a goal. A **learning track** is an ordered path through the topics, from basic to advanced, built around one target. Each step says why it is there.

For example, *PostgreSQL Storage* starts with how PostgreSQL stores data and ends with partitioning and how to watch it. *Anatomy of PostgreSQL* walks through the parts of a server and how they fit together. Follow a track and each topic builds on the one before it. You can step through a track with Previous and Next, and dive into any related topic along the way.

## Why we built it

1. **Help our Solution Architects explain deep database internals to customers.** The content is relevant to the Dynatrace Database app, and most Solution Architects are not expected to master it. This gives them the depth in a form they can learn from and share.
2. **Help our customers.** When a customer understands why something happens, and why a suggested fix should work, they can solve problems faster and with more confidence.
3. **Show Dynatrace as an innovative company** that goes the extra mile to help customers understand the technology underneath their problems.

## How it is built

Everything is plain files in this repository: topics, articles, tracks and the animations. Anyone can suggest a fix or a new article with a pull request. The claims in the articles come from the official documentation, and the SQL in them is run against a real PostgreSQL. Anything that could not be run is clearly marked.

- To contribute, read [CONTRIBUTING.md](CONTRIBUTING.md).
- To work on the project or run it locally, read [DEVELOPING.md](DEVELOPING.md).
- To see what changed recently, read [CHANGELOG.md](CHANGELOG.md).

## Where it stands

This is an early, experimental project.

## License

_Choose a licence before publishing._ A common split is MIT for the code (`docs/index.html`, `scripts/`) and CC BY-SA 4.0 for the content (`data/`). Add the files `LICENSE` and `LICENSE-CONTENT` and update this section.

## Credits

The topic model (topics with evidence, and prerequisite links that carry a reason and a strength) is inspired by Marble's open [Skill Taxonomy](https://github.com/withmarbleapp/os-taxonomy). This project does not use Marble's data or code.
