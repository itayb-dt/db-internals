#!/usr/bin/env python3
"""Validate data/*.yaml and compile docs/graph.json.  Usage: python3 scripts/build.py"""
import glob, json, os, sys
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEVELS = ["Concept", "Core structure", "Mechanism", "Implementation", "Operational"]
REQUIRED = ["id", "name", "domain", "level", "description"]

subjects, topics, edges, errors = [], {}, [], []

for path in sorted(glob.glob(os.path.join(ROOT, "data", "*.yaml"))):
    doc = yaml.safe_load(open(path, encoding="utf-8"))
    subjects.append({"name": doc["subject"], "color": doc["color"]})
    for t in doc["topics"]:
        where = f"{os.path.basename(path)}:{t.get('id', '?')}"
        for k in REQUIRED:
            if k not in t:
                errors.append(f"{where}: missing '{k}'")
        if t["id"] in topics:
            errors.append(f"{where}: duplicate id")
        if not 0 <= t["level"] < len(LEVELS):
            errors.append(f"{where}: level must be 0-{len(LEVELS)-1}")
        topics[t["id"]] = {
            "id": t["id"], "name": t["name"], "subject": doc["subject"], "domain": t["domain"],
            "level": t["level"], "description": t["description"], "evidence": t.get("evidence", []),
        }
        for p in t.get("prerequisites", []):
            edges.append({"topic": t["id"], "prerequisite": p["id"],
                          "strength": p.get("strength", "hard"), "reason": p.get("reason", "")})

for e in edges:
    if e["prerequisite"] not in topics:
        errors.append(f"{e['topic']}: unknown prerequisite '{e['prerequisite']}'")

# cycle check (DFS)
adj = {}
for e in edges:
    adj.setdefault(e["topic"], []).append(e["prerequisite"])
state = {}
def visit(n, trail):
    if state.get(n) == 1:
        errors.append("cycle: " + " -> ".join(trail + [n])); return
    if state.get(n) == 2: return
    state[n] = 1
    for m in adj.get(n, []):
        if m in topics: visit(m, trail + [n])
    state[n] = 2
for n in topics: visit(n, [])

if errors:
    print("\n".join(errors)); sys.exit(1)

out = {"levels": LEVELS, "subjects": subjects, "topics": list(topics.values()), "edges": edges}
os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
with open(os.path.join(ROOT, "docs", "graph.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
print(f"OK: {len(topics)} topics, {len(edges)} links, {len(subjects)} subjects -> docs/graph.json")
