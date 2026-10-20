#!/usr/bin/env python3
"""Run the SQL examples from content/*.md against a real PostgreSQL.

Every fenced ```sql block is run, in order, in a fresh throwaway database per article.
Sample tables come from tests/sql_setup/<article>.sql (optional).
A block whose first line starts with "-- not run" is skipped, for SQL that needs a contrib
extension, two sessions, a shell, or anything else this script cannot do. Say why on that line.
The deadlock, MVCC and dead-rows articles are also checked with two real sessions.

Usage:
  PGHOST=127.0.0.1 PGPORT=5432 PGUSER=postgres python3 scripts/verify_sql.py [article ...]

Use a throwaway server: the script creates and drops databases named verify_<article>,
and one example runs ALTER SYSTEM.  Needs psql on the PATH.
"""
import glob, os, re, subprocess, sys, tempfile, threading, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP = os.path.join(ROOT, "tests", "sql_setup")
FENCE = re.compile(r"```sql\n(.*?)```", re.S)


def psql(db, args, input_text=None, tuples_only=False):
    cmd = ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", db] + (["-At"] if tuples_only else []) + args
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


def two_sessions(db, script1, script2, delay2=0.0):
    """Run two scripts at the same time in two real sessions; the second starts delay2 seconds later."""
    out = [None, None]

    def run(i, script, delay):
        if delay:
            time.sleep(delay)
        out[i] = psql(db, ["-f", "-"], input_text=script, tuples_only=True)
    threads = [threading.Thread(target=run, args=(0, script1, 0)), threading.Thread(target=run, args=(1, script2, delay2))]
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


def verify_mvcc():
    """A reader must not wait for an open writer and must see the old value until the commit."""
    problems = []
    db = "verify_mvcc_sessions"
    make_db(db)
    psql(db, ["-c", "CREATE TABLE accounts (id int PRIMARY KEY, balance int); INSERT INTO accounts VALUES (1, 101);"])
    a = "BEGIN;\nUPDATE accounts SET balance = 500 WHERE id = 1;\nSELECT pg_sleep(2);\nCOMMIT;\n"
    b = ("SELECT 'during', balance FROM accounts WHERE id = 1;\nSELECT pg_sleep(2.5);\n"
         "SELECT 'after', balance FROM accounts WHERE id = 1;\n")
    t0 = time.time()
    r = two_sessions(db, a, b, delay2=0.7)
    text = r[1][1]
    if "during|101" not in text or "after|500" not in text:
        problems.append("reader did not see old value during and new value after the commit: " + repr(text))
    psql("postgres", ["-c", f'DROP DATABASE IF EXISTS "{db}"'])
    return problems


def verify_dead_rows():
    """VACUUM must not remove dead rows while an older snapshot is open, and must remove them afterwards."""
    problems = []
    db = "verify_dead_rows_sessions"
    make_db(db)
    psql(db, ["-c", "CREATE TABLE jobs (id int PRIMARY KEY, state text) WITH (autovacuum_enabled = off);"
                    " INSERT INTO jobs SELECT g, 'new' FROM generate_series(1, 20000) g;"])
    a = "BEGIN ISOLATION LEVEL REPEATABLE READ;\nSELECT count(*) FROM jobs;\nSELECT pg_sleep(3);\nCOMMIT;\n"
    b = "UPDATE jobs SET state = 'done';\nVACUUM (VERBOSE) jobs;\n"
    r = two_sessions(db, a, b, delay2=0.7)
    during = r[1][1]
    m = re.search(r"(\d+) are dead but not yet removable", during)
    if not m or int(m.group(1)) < 20000:
        problems.append("vacuum during the old snapshot should leave the dead rows: " + during[-300:])
    time.sleep(0.5)
    code, after = psql(db, ["-c", "VACUUM (VERBOSE) jobs"])
    m = re.search(r"tuples: (\d+) removed, \d+ remain, (\d+) are dead but not yet removable", after)
    if not m or int(m.group(1)) < 20000 or int(m.group(2)) != 0:
        problems.append("vacuum after the snapshot ended should remove the dead rows: " + after[-300:])
    psql("postgres", ["-c", f'DROP DATABASE IF EXISTS "{db}"'])
    return problems


SESSION_CHECKS = [("deadlock", "deadlock (two sessions)", verify_deadlock),
                  ("mvcc", "mvcc (two sessions)", verify_mvcc),
                  ("dead-rows", "dead-rows (two sessions)", verify_dead_rows)]


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
    for key, label, check in SESSION_CHECKS:
        if only and key not in only:
            continue
        problems = check()
        print(f"{'FAIL' if problems else 'ok':4}  {label:26}")
        for pr in problems:
            print("      - " + pr)
        bad += bool(problems)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
