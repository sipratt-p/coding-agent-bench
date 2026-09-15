"""Coding benchmark v3 = v2's five tasks + two extra-extra-hard tiebreakers.

Added 2026-08-16 because every keeper model saturated v2 (478-485/500):
  6. POSIX leftmost-longest regex engine — punishes the memorized PCRE
     backtracker on BOTH semantics and a catastrophic-pattern perf gate.
  7. Convergent replicated text (CRDT) — out-of-order + duplicate delivery,
     tombstones, exact concurrent-ordering rule. No canonical solution to recall.

Total /700. v2 rows remain comparable per-task; never mix suite totals.
Reference solutions in tasks/refs/ validate both graders.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coding_benchmark_v2 import (  # noqa: F401  (re-export harness pieces)
    api_call, extract_python_code, run_python, score_result,
    BENCHMARKS as BENCHMARKS_V2,
)

REGEX_TASK = {
    "name": "POSIX Regex Engine (leftmost-longest)",
    "prompt": """Implement a regular-expression engine in Python with POSIX leftmost-longest semantics. No imports of `re` or any regex/parsing library (pure stdlib data structures only).

API:
- `regex_match(pattern: str, text: str) -> tuple[int, int] | None`
  Return `(start, end)` of the match, or `None` if no match anywhere in text.

Pattern syntax to support:
- literal characters; `.` (any single char)
- quantifiers on the previous atom: `*` (0+), `+` (1+), `?` (0/1)
- character classes: `[abc]`, ranges `[a-z0-9]`, negation `[^abc]`
- alternation `|` (lowest precedence), grouping `(...)` (affects precedence only, no capture semantics needed)
- anchors: `^` (only valid at pattern start) and `$` (only at pattern end)

SEMANTICS — this is the core of the task and it is NOT Perl/PCRE:
- LEFTMOST-LONGEST (POSIX): the match is the one starting at the smallest possible index; among matches at that start, the one with the greatest end. This applies through alternation and quantifiers: `regex_match("a|ab", "xab")` must return `(1, 3)` — the LONGER alternative wins, unlike PCRE.
- A pattern that can match the empty string matches at the leftmost position: `regex_match("x*", "abc")` returns `(0, 0)`.

PERFORMANCE — also graded: patterns like `(a|aa)*c` against long runs of `a` with no `c` must complete in well under a second. Exponential backtracking will fail the test suite's time budget. Build a proper NFA/DFA simulation, not a recursive backtracker.

Invalid patterns (unbalanced parens, dangling quantifier like `*a`, unterminated class) must raise `ValueError`. ^ or $ appearing anywhere other than the very start/end of the whole pattern may also raise ValueError.

Output only the Python code, no explanation.""",
    "test_code": r"""
import sys, time

def ok(group):
    print(f"{group}: ok"); sys.stdout.flush()

# basic literals, dot, quantifiers
assert regex_match("abc", "xxabcxx") == (2, 5)
assert regex_match("a.c", "azc") == (0, 3)
assert regex_match("ab*c", "ac") == (0, 2)
assert regex_match("ab*c", "abbbc") == (0, 5)
assert regex_match("ab+c", "ac") is None
assert regex_match("ab?c", "abc") == (0, 3)
assert regex_match("q", "abc") is None
ok("basic")

# leftmost-longest through alternation and quantifiers (POSIX, not PCRE)
assert regex_match("a|ab", "xab") == (1, 3), "alternation must take the LONGER match"
assert regex_match("ab|a", "xab") == (1, 3)
assert regex_match("(a|ab)(c|bcd)", "abcd") == (0, 4), "classic POSIX composite"
assert regex_match("x*", "abc") == (0, 0), "empty match at leftmost position"
assert regex_match("a*", "aaab") == (0, 3), "longest at leftmost start"
assert regex_match("(a|b)*abb", "cabbb") == (1, 4)
assert regex_match("a+|a+b", "xaab") == (1, 4), "longest across alternatives"
ok("leftmost_longest")

# classes and anchors
assert regex_match("[a-c]+", "zzabcaz") == (2, 6)
assert regex_match("[^a-c]+", "abxyzc") == (2, 5)
assert regex_match("[a-]x", "-x") == (0, 2)
assert regex_match("^ab", "xab") is None
assert regex_match("^ab", "abx") == (0, 2)
assert regex_match("bc$", "abcb") is None
assert regex_match("bc$", "abc") == (1, 3)
assert regex_match("^a*$", "aaa") == (0, 3)
assert regex_match("^$", "") == (0, 0)
ok("classes_anchors")

# invalid patterns
for bad in ["(ab", "ab)", "*a", "+", "a[bc", "a**"]:
    try:
        regex_match(bad, "abc")
        raise AssertionError(f"pattern {bad!r} should raise ValueError")
    except ValueError:
        pass
ok("invalid_patterns")

# performance: catastrophic for backtrackers, trivial for NFA simulation
t0 = time.time()
assert regex_match("(a|aa)*c", "a" * 45) is None
assert regex_match("(a|aa)*c", "a" * 45 + "c") == (0, 46)
assert regex_match("(x*)*y", "x" * 40) is None, "epsilon-cycle star must terminate"
assert regex_match("(ab|a)*d", "ab" * 30) is None
elapsed = time.time() - t0
assert elapsed < 2.0, f"pathological patterns took {elapsed:.1f}s — backtracking detected"
ok("performance")

print("ALL_TESTS_PASSED")
""",
    "scoring": {
        "basic": 15,
        "leftmost_longest": 25,
        "classes_anchors": 15,
        "invalid_patterns": 10,
        "performance": 20,
        "code_quality": 15,
    },
}

CRDT_TASK = {
    "name": "Convergent Replicated Text (CRDT)",
    "prompt": """Implement a convergent replicated text document (a CRDT) in Python, stdlib only.

API:
- `Replica(site_id: str)` — one collaborator's copy. `site_id` is unique per replica.
- `r.local_insert(pos: int, ch: str) -> dict` — insert single char at index `pos` in r's current visible text; apply locally and return the operation as a JSON-serializable dict to broadcast.
- `r.local_delete(pos: int) -> dict` — delete visible char at index `pos`; apply locally, return the op.
- `r.apply(op: dict) -> None` — apply an op received from another replica (or a duplicate of any op, including one's own).
- `r.text() -> str` — current visible text.

Required semantics (exactly these — they are what the tests check):
1. IDENTITY: every inserted character gets the id `(counter, site_id)` where `counter` is a Lamport clock: each replica's counter starts at 0, increments by 1 on each LOCAL insert, and on receiving any op updates to `max(local, op_counter)` before/so that later local ids stay unique and causally greater. Deletes do not create new ids; a delete op names the id of the deleted character.
2. STRUCTURE (RGA / insert-after): an insert op records the id of the character it was inserted AFTER (`origin`), or the sentinel origin `None` for position 0. Deleted characters become invisible TOMBSTONES but keep their place in the sequence (they still serve as origins).
3. CONCURRENT ORDER RULE: characters inserted after the SAME origin appear in DESCENDING order of `(counter, site_id)` — i.e. higher counter first; ties on counter broken by higher site_id first. (This makes a replica's own consecutive typing read left-to-right, and gives one deterministic answer for concurrent inserts.) When walking to place a new node after its origin, it must skip over any nodes (and their descendants) with greater `(counter, site_id)` per this rule — the standard RGA insertion scan.
4. DELIVERY: ops may arrive OUT OF ORDER and DUPLICATED. `apply` must be idempotent (same op twice = once). An insert whose origin hasn't arrived yet, or a delete whose target hasn't arrived yet, must be BUFFERED and applied automatically once its dependency arrives. No exceptions thrown for any of this.
5. CONVERGENCE: any set of replicas that has received the same set of ops (in any order, with any duplication) has identical `text()`.

Output only the Python code, no explanation.""",
    "test_code": r"""
import sys, json, random

def ok(group):
    print(f"{group}: ok"); sys.stdout.flush()

def dup(op):
    return json.loads(json.dumps(op))

# basic single-replica editing
a = Replica("A")
ops = []
for i, ch in enumerate("hello"):
    ops.append(a.local_insert(i, ch))
assert a.text() == "hello"
ops.append(a.local_delete(0))
assert a.text() == "ello"
ops.append(a.local_insert(0, "H"))
assert a.text() == "Hello"
ok("basic")

# ops are JSON-serializable dicts
for op in ops:
    assert isinstance(op, dict)
    json.dumps(op)
ok("serializable")

# two-way convergence with the EXACT concurrent-order rule
a = Replica("A"); b = Replica("B")
oa = a.local_insert(0, "x")          # A: (1,"A")
b.apply(dup(oa))
assert b.text() == "x"
o1 = a.local_insert(1, "a")          # concurrent, same origin (after 'x'): A (2,"A")
o2 = b.local_insert(1, "b")          # B (2,"B")
a.apply(dup(o2)); b.apply(dup(o1))
assert a.text() == b.text(), f"diverged: {a.text()!r} vs {b.text()!r}"
assert a.text() == "xba", f"concurrent order rule: expected 'xba', got {a.text()!r}"
ok("concurrent_order")

# out-of-order + duplicate delivery, buffering
a = Replica("A"); b = Replica("B")
o1 = a.local_insert(0, "1")
o2 = a.local_insert(1, "2")
o3 = a.local_insert(2, "3")
od = a.local_delete(1)              # deletes '2'
assert a.text() == "13"
b.apply(dup(od))                    # delete before its insert arrives
b.apply(dup(o3))                    # insert whose origin hasn't arrived
assert b.text() in ("", "3"), "buffering should hold od/o3 or show only what is placeable"
b.apply(dup(o1))
b.apply(dup(o2))
assert b.text() == "13", f"after full delivery expected '13', got {b.text()!r}"
for op in (o1, o2, o3, od):
    b.apply(dup(op))                # duplicates
assert b.text() == "13", "idempotence violated"
ok("out_of_order")

# three-replica randomized convergence (deterministic seed)
random.seed(20260816)
reps = [Replica(s) for s in ("A", "B", "C")]
log = []
for step in range(120):
    r = random.choice(reps)
    if r.text() and random.random() < 0.3:
        log.append(r.local_delete(random.randrange(len(r.text()))))
    else:
        pos = random.randrange(len(r.text()) + 1)
        log.append(r.local_insert(pos, random.choice("abcdefg")))
    # occasionally deliver a random subset in random order to a random replica
    if random.random() < 0.5:
        tgt = random.choice(reps)
        batch = random.sample(log, min(len(log), random.randrange(1, 12)))
        for op in batch:
            tgt.apply(dup(op))
# full delivery, shuffled differently per replica, with duplicates
for r in reps:
    order = log[:]
    random.shuffle(order)
    for op in order:
        r.apply(dup(op))
        if random.random() < 0.2:
            r.apply(dup(op))
texts = [r.text() for r in reps]
assert texts[0] == texts[1] == texts[2], f"divergence: {[t[:40] for t in texts]}"
assert len(texts[0]) > 10, "fuzz produced implausibly short text"
ok("convergence_fuzz")

print("ALL_TESTS_PASSED")
""",
    "scoring": {
        "basic": 10,
        "serializable": 5,
        "concurrent_order": 25,
        "out_of_order": 25,
        "convergence_fuzz": 20,
        "code_quality": 15,
    },
}

BENCHMARKS = BENCHMARKS_V2 + [REGEX_TASK, CRDT_TASK]
