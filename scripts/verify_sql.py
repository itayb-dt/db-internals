#!/usr/bin/env python3
"""Run the SQL examples from content/*.md against a real PostgreSQL.

Every fenced ```sql block is run, in order, in a fresh throwaway database per article.
Sample tables come from tests/sql_setup/<article>.sql (optional).
A block whose first line starts with "-- not run" is skipped, for SQL that needs a contrib
extension, two sessions, a shell, or anything else this script cannot do. Say why on that line.
The deadlock article is also checked with two real sessions.

Usage:
  PGHOST=127.0.0.1 PGPORT=5432 PGUSER=postgres python3 scripts/verify_sql.py [article ...]

Use a throwaway server: the script creates and drops databases named verify_<article>,
and one example runs ALTER SYSTEM.  Needs psql on the PATH.
"""
import glob, os, re, subprocess, sys, tempfile, threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP = os.path.join(ROOT, "tests", "sql_setup")
FENCE = re.compile(r"```sql\n(.*?)```", re.S)


def psql(db, args, input_text=None):
    cmd = ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", db] + args
    p = subprocess.run(cmd, input=input_text, capture_output=True, text=True, cwd=SETUP)
    return p.returncode, (p.stdout + p.stderr).strip()


def make_db(name):
    psql("postgres", ["-c", f'DROP DATABASE IF EXISTS "{name}"'])
    code, out = psql("postgres", ["-c", f'CREATE DATABASE "{name}"'])
    if code:
        sys.exit(f"cannot create database {name}: {out}")


def verify_article(path):
    name = os.path.splitext(os.path.basename(path))[0]
    blocks = FENCE.findall(open(path, encoding="utf-8").read())
    if not blocks:
        return name, 0, 0, []
    db = "verify_" + name.replace("-", "_")
    make_db(db)
    failures = []
    setup = os.path.join(SETUP, name + ".sql")
    if os.path.isfile(setup):
        code, out = psql(db, ["-f", setup])
        if code:
            return name, 0, 0, [f"setup {os.path.relpath(setup, ROOT)} failed: {out}"]
    ran = skipped = 0
    for i, block in enumerate(blocks, 1):
        if block.lstrip().startswith("-- not run"):
            skipped += 1
            continue
        code, out = psql(db, ["-f", "-"], input_text=block)
        ran += 1
        if code:
            failures.append(f"block {i}: {out}\n    {block.strip().splitlines()[0]}")
    psql("postgres", ["-c", f'DROP DATABASE IF EXISTS "{db}"'])
    return name, ran, skipped, failures


def two_sessions(db, script1, script2):
    out = [None, None]

    def run(i, script):
        out[i] = psql(db, ["-c", script])
    threads = [threading.Thread(target=run, args=(i, s)) for i, s in enumerate((script1, script2))]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return out


def verify_deadlock():
    """The article's two-session example must deadlock, and the ordered version must not."""
    problems = []
    db = "verify_deadlock_sessions"
    make_db(db)
    psql(db, ["-f", os.path.join(SETUP, "deadlock.sql")])
    a = ("BEGIN; UPDATE accounts SET balance = balance - 10 WHERE id = 1; SELECT pg_sleep(1);"
         " UPDATE accounts SET balance = balance + 10 WHERE id = 2; COMMIT;")
    b = ("BEGIN; UPDATE accounts SET balance = balance - 10 WHERE id = 2; SELECT pg_sleep(1);"
         " UPDATE accounts SET balance = balance + 10 WHERE id = 1; COMMIT;")
    r = two_sessions(db, a, b)
    texts = [x[1] for x in r]
    if sum("deadlock detected" in t for t in texts) != 1:
        problems.append("the opposite-order example did not produce exactly one 'deadlock detected': " + repr(texts))
    ordered = ("BEGIN; SELECT id FROM accounts WHERE id IN (1, 2) ORDER BY id FOR UPDATE; SELECT pg_sleep(0.5);"
               " UPDATE accounts SET balance = balance - 10 WHERE id = 1;"
               " UPDATE accounts SET balance = balance + 10 WHERE id = 2; COMMIT;")
    r = two_sessions(db, ordered, ordered)
    if any(x[0] for x in r):
        problems.append("the ordered-locking example failed: " + repr([x[1] for x in r]))
    psql("postgres", ["-c", f'DROP DATABASE IF EXISTS "{db}"'])
    return problems


def main(only):
    paths = sorted(glob.glob(os.path.join(ROOT, "content", "*.md")))
    paths = [p for p in paths if not os.path.basename(p).startswith("_")]
    if only:
        paths = [p for p in paths if os.path.splitext(os.path.basename(p))[0] in only]
    bad = 0
    for p in paths:
        name, ran, skipped, failures = verify_article(p)
        if ran + skipped == 0:
            continue
        status = "FAIL" if failures else "ok"
        print(f"{status:4}  {name:26} {ran} run, {skipped} not run")
        for f in failures:
            print("      - " + f.replace("\n", "\n        "))
        bad += bool(failures)
    if not only or "deadlock" in only:
        problems = verify_deadlock()
        print(f"{'FAIL' if problems else 'ok':4}  {'deadlock (two sessions)':26}")
        for pr in problems:
            print("      - " + pr)
        bad += bool(problems)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
