# Database Internals Map

An open, interactive 3D map of how databases work. Every dot is a concept, every link says what you need to understand first, and why.

**Live site:** `https://<your-user>.github.io/<your-repo>/`

Click any dot to see its description, everything it builds on, what it unlocks, and how you know you understand it. Drag to spin, scroll to zoom, click a subject in the legend to hide or show it.

## How it works

The content is plain YAML. A small script validates it and compiles one JSON file, and a static page renders that file. There is no backend and no build tooling beyond Python.

```
data/*.yaml  ->  scripts/build.py  ->  docs/graph.json  ->  docs/index.html
 (you edit)       (validate + merge)    (generated)          (viewer)
```

In the viewer, dot colour is the subject and height is the level, from concept at the bottom to operational detail at the top. Dashed links are soft prerequisites. Small dots travel along each link from prerequisite to dependent.

## Repository layout

```
data/               one YAML file per subject; the source of truth
  storage.yaml
  indexing.yaml
scripts/build.py    validates data/ and writes docs/graph.json
docs/               what GitHub Pages serves
  index.html        the viewer (static, no dependencies)
  graph.json        generated; commit it
requirements.txt    pyyaml
```

## Add or edit a topic

1. Open the YAML file for the subject, or create a new file in `data/`.
2. Add a topic:

   ```yaml
   - id: gin                       # unique, lowercase, never changes
     name: GIN
     domain: Specialised indexes   # group inside the subject
     level: 2                      # 0-4, see below
     description: Inverted index. One row can appear under many keys.
     evidence:                     # how you know someone understands it
       - Explain why GIN fits "array contains" queries
     prerequisites:
       - {id: index, reason: A GIN is a kind of index}
       - {id: toast, reason: Large key lists use out-of-line storage, strength: soft}
   ```

3. Rebuild and check:

   ```
   pip install -r requirements.txt
   python3 scripts/build.py
   ```

4. Commit the YAML and the regenerated `docs/graph.json`, then open a pull request.

A new subject file starts with:

```yaml
subject: Transactions
color: "#c78bff"
topics:
  - ...
```

### Fields

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Stable unique identifier. Links refer to it, so don't rename it. |
| `name` | yes | Label shown on the dot. |
| `domain` | yes | Group within the subject, shown in the panel. |
| `level` | yes | 0 Concept, 1 Core structure, 2 Mechanism, 3 Implementation, 4 Operational. Sets the height. |
| `description` | yes | One or two plain sentences. |
| `evidence` | no | Observable statements that show understanding. |
| `prerequisites` | no | List of `{id, reason, strength}`. `strength` is `hard` (default) or `soft`. |

The build fails on missing fields, duplicate ids, unknown prerequisites and cycles.

### Writing good topics

- One teachable idea per topic. If the description needs "and", split it.
- Write prerequisites for understanding, not for chronology. Ask "could someone follow this without knowing that?"
- Give every prerequisite a `reason`. It makes the link reviewable.
- Write `evidence` as something you could check, such as "explain why X", not "know about X".

## Run locally

```
python3 scripts/build.py
python3 -m http.server -d docs
```

Open http://localhost:8000. Opening `docs/index.html` directly from disk won't work, because browsers block loading `graph.json` from a local file.

## Publish on GitHub Pages

Settings, then Pages, then Deploy from a branch, then `main` and `/docs`.

## Contributing

Pull requests that add topics, fix prerequisites or improve descriptions are welcome. Please run `python3 scripts/build.py` before opening one and include `docs/graph.json` in the commit. For a new topic, mention where the information comes from, such as official documentation or a paper.

## License

_Choose a licence before publishing._ A common split is MIT for the code (`docs/index.html`, `scripts/`) and CC BY-SA 4.0 for the content (`data/`). Add the files `LICENSE` and `LICENSE-CONTENT` and update this section.

## Credits

The topic model (topics with evidence, and prerequisite links that carry a reason and a strength) is inspired by Marble's open [Skill Taxonomy](https://github.com/withmarbleapp/os-taxonomy). This project does not use Marble's data or code.
