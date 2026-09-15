"""Coding benchmark v4 = v3's seven tasks + two more separators (added 2026-08-19
because the field was bunching up at the top of v3).

  8. Async DAG Orchestrator — cancellation/timeout semantics, failure->skip
     propagation, REAL concurrency (wall-clock gated). Punishes models that
     write sequential await loops or get cancellation edge-semantics wrong.
  9. Chunk-Split Streaming JSON Parser — must survive a feed() split at EVERY
     byte boundary (exhaustive sweep in the tests). No buffering-the-whole-
     input shortcut: memory of past chunks must be O(current record).

Total /900. v2/v3 rows remain comparable per-task; never mix suite totals.
Reference solutions in tasks/refs/ validate the graders (tasks/validate_refs.py).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coding_benchmark_v3 import BENCHMARKS as BENCHMARKS_V3  # noqa: F401

ORCH_TASK = {
    "name": "Async DAG Orchestrator (cancellation semantics)",
    "prompt": """Implement an async task orchestrator in Python (pure stdlib, asyncio only).

API:
- `class Orchestrator:`
  - `add_task(name: str, fn, deps: list[str] = []) -> None`
    `fn` is an async callable invoked as `await fn(results)` where `results` is a
    dict {dep_name: dep_result} containing ONLY that task's declared deps.
    Re-adding an existing name raises `ValueError`. A dep that was never added
    by the time `run()` is called raises `ValueError` from `run()`.
  - `async def run(self, task_timeout: float | None = None) -> dict`
    Executes the whole DAG and returns {name: outcome} for EVERY task, where
    outcome is one of:
      {"status": "ok", "result": <return value>}
      {"status": "failed", "error": <the exception instance>}
      {"status": "cancelled"}            # exceeded task_timeout
      {"status": "skipped"}              # any transitive dep not "ok"

RULES — read carefully, they are exactly graded:
1. CONCURRENCY IS REAL: tasks whose deps are satisfied run concurrently
   (the tests wall-clock this). A task starts as soon as ALL its deps are "ok"
   — not in topological "levels"/batches: if A takes 0.3s and B takes 0.1s and
   C depends only on B, C must start ~0.1s in, while A is still running.
2. A task failure (exception) marks it "failed"; every transitive dependent
   becomes "skipped" (never started). Unrelated tasks keep running to completion.
3. `task_timeout` applies per task: a task exceeding it is cancelled
   (asyncio-cancelled, not left running) and reported "cancelled"; its
   dependents are "skipped".
4. Cycles: `run()` raises `ValueError` BEFORE starting any task.
5. `run()` never raises for task failures/timeouts — they are reported in the
   returned dict.

Output only the Python code, no explanation.""",
    "test_code": r"""
import asyncio, sys, time

def ok(group):
    print(f"{group}: ok"); sys.stdout.flush()

async def sleepy(t, ret=None, log=None, name=None):
    if log is not None: log.append((name, "start", time.monotonic()))
    await asyncio.sleep(t)
    if log is not None: log.append((name, "end", time.monotonic()))
    return ret

# --- basic DAG order + results routing
async def t_basic():
    o = Orchestrator()
    o.add_task("a", lambda res: sleepy(0.01, ret=2))
    o.add_task("b", lambda res: sleepy(0.01, ret=3))
    async def mul(res): return res["a"] * res["b"]
    o.add_task("c", mul, deps=["a", "b"])
    r = await o.run()
    assert r["a"] == {"status": "ok", "result": 2}
    assert r["c"]["status"] == "ok" and r["c"]["result"] == 6
    # results dict contains ONLY declared deps
    async def keys(res): return sorted(res.keys())
    o2 = Orchestrator()
    o2.add_task("x", lambda res: sleepy(0, ret=1))
    o2.add_task("y", lambda res: sleepy(0, ret=1))
    o2.add_task("z", keys, deps=["y"])
    r2 = await o2.run()
    assert r2["z"]["result"] == ["y"], f"results must contain only declared deps, got {r2['z']['result']}"
    return True
assert asyncio.run(t_basic())
ok("basic_dag")

# --- real concurrency: independent tasks overlap; C starts when B done (not when A done)
async def t_conc():
    log = []
    o = Orchestrator()
    o.add_task("A", lambda res: sleepy(0.5, log=log, name="A"))
    o.add_task("B", lambda res: sleepy(0.1, log=log, name="B"))
    o.add_task("C", (lambda res: sleepy(0.1, log=log, name="C")), deps=["B"])
    t0 = time.monotonic()
    await o.run()
    total = time.monotonic() - t0
    assert total < 0.75, f"A(0.5s) and B(0.1s)+C(0.1s) must overlap; took {total:.2f}s"
    ev = {(n, k): t for n, k, t in log}
    assert ev[("C", "start")] < ev[("A", "end")] - 0.15, "C must start while A still running (no level-sync)"
    return True
assert asyncio.run(t_conc())
ok("true_concurrency")

# --- failure propagation: transitive skip, unrelated tasks unaffected
async def t_fail():
    async def boom(res): raise RuntimeError("nope")
    o = Orchestrator()
    o.add_task("a", boom)
    o.add_task("b", lambda res: sleepy(0.05, ret="b"), deps=["a"])
    o.add_task("c", lambda res: sleepy(0.05, ret="c"), deps=["b"])
    o.add_task("free", lambda res: sleepy(0.05, ret="free"))
    r = await o.run()
    assert r["a"]["status"] == "failed" and isinstance(r["a"]["error"], RuntimeError)
    assert r["b"]["status"] == "skipped" and r["c"]["status"] == "skipped"
    assert r["free"] == {"status": "ok", "result": "free"}
    return True
assert asyncio.run(t_fail())
ok("failure_skip")

# --- timeout cancellation: task truly cancelled, dependents skipped
async def t_cancel():
    flag = {"leaked": False}
    async def slow(res):
        try:
            await asyncio.sleep(5)
            flag["leaked"] = True
        except asyncio.CancelledError:
            raise
    o = Orchestrator()
    o.add_task("slow", slow)
    o.add_task("dep", lambda res: sleepy(0.01, ret=1), deps=["slow"])
    o.add_task("quick", lambda res: sleepy(0.05, ret="q"))
    t0 = time.monotonic()
    r = await o.run(task_timeout=0.2)
    took = time.monotonic() - t0
    assert r["slow"]["status"] == "cancelled"
    assert r["dep"]["status"] == "skipped"
    assert r["quick"]["status"] == "ok"
    assert took < 1.5, f"run must not wait out the 5s sleep (took {took:.2f}s)"
    await asyncio.sleep(0.05)
    assert not flag["leaked"], "cancelled task kept running"
    return True
assert asyncio.run(t_cancel())
ok("timeout_cancel")

# --- validation: cycles + unknown deps + duplicate names
async def t_valid():
    o = Orchestrator()
    o.add_task("a", lambda res: sleepy(0), deps=["b"])
    o.add_task("b", lambda res: sleepy(0), deps=["a"])
    try:
        await o.run()
        raise AssertionError("cycle must raise ValueError")
    except ValueError:
        pass
    o2 = Orchestrator()
    o2.add_task("a", lambda res: sleepy(0), deps=["ghost"])
    try:
        await o2.run()
        raise AssertionError("unknown dep must raise ValueError")
    except ValueError:
        pass
    o3 = Orchestrator()
    o3.add_task("a", lambda res: sleepy(0))
    try:
        o3.add_task("a", lambda res: sleepy(0))
        raise AssertionError("duplicate name must raise ValueError")
    except ValueError:
        pass
    return True
assert asyncio.run(t_valid())
ok("validation")

print("ALL_TESTS_PASSED")
""",
    "scoring": {
        "basic_dag": 15,
        "true_concurrency": 20,
        "failure_skip": 20,
        "timeout_cancel": 20,
        "validation": 10,
        "code_quality": 15,
    },
}

STREAM_TASK = {
    "name": "Chunk-Split Streaming JSON Parser",
    "prompt": """Implement an incremental (streaming) JSON value parser in Python — pure stdlib, and you may NOT import `json` or any parsing library. It must produce complete top-level JSON values as they finish arriving, no matter how the input is split into chunks.

API:
- `class StreamParser:`
  - `feed(chunk: str) -> list`
    Consume the next chunk of the stream and return a list of the top-level
    JSON values COMPLETED by this chunk (usually empty or one; may be several
    if one chunk contains several values). Top-level values are separated by
    arbitrary whitespace (spaces, tabs, newlines) in the stream.
  - `close() -> None`
    Signal end of stream. Raises `ValueError` if a value is incomplete
    (mid-string, unbalanced brackets, dangling literal, etc.). Trailing
    whitespace is fine.

Supported JSON subset (returned as native Python values):
- objects {} -> dict, arrays [] -> list, arbitrarily nested
- strings with escapes: \\" \\\\ \\/ \\b \\f \\n \\r \\t and \\uXXXX -> str
- numbers: integers, decimals, exponents, leading minus (e.g. -1.5e-3).
  Integers (no '.', no exponent) -> int, otherwise -> float
- true/false/null -> True/False/None

HARD REQUIREMENTS — exactly graded:
1. Chunks split ANYWHERE: mid-string, mid-escape (even between the backslash
   and the 'u', or between \\u digit hex chars), mid-number, mid-literal
   (e.g. 'tr' then 'ue'), mid-key. The tests feed a corpus split at EVERY
   single character boundary, one char at a time, and in random chunkings —
   the outputs must be identical every time.
2. Malformed input raises `ValueError` at the earliest chunk where the text
   cannot be a prefix of any valid stream (e.g. `{"a": tru5}` on the '5';
   `[1,]` on the ']'). You do NOT need mid-number strictness beyond: a number
   must not be immediately followed by an alphanumeric character.
3. A number at top level is only complete once a non-number character or
   close() confirms it (e.g. feed("12") feed("3 ") -> [123]).

Output only the Python code, no explanation.""",
    "test_code": r"""
import sys, random

def ok(group):
    print(f"{group}: ok"); sys.stdout.flush()

EXPECT = [
    {"name": 'café "quoted"', "n": -1.5e-3,
     "arr": [1, 2.5, {"deep": [True, False, None]}],
     "u": "Aé", "empty": {}, "ea": []},
    [1, "two", 3.0],
    True,
    -42,
    "tail\n",
]
src =' {"name": "caf\\u00e9 \\"quoted\\"", "n": -1.5e-3, "arr": [1, 2.5, {"deep": [true, false, null]}], "u": "\\u0041\\u00e9", "empty": {}, "ea": []}  [1, "two", 3.0]  true  -42  "tail\\n"  '

def run_stream(chunks):
    p = StreamParser()
    out = []
    for c in chunks:
        got = p.feed(c)
        assert isinstance(got, list)
        out.extend(got)
    p.close()
    return out

# --- basic: whole input in one chunk
assert run_stream([src]) == EXPECT
ok("basic")

# --- exhaustive single-char feed
assert run_stream(list(src)) == EXPECT, "one-char-at-a-time must match"
ok("char_at_a_time")

# --- every split point (two chunks, split at every boundary)
for i in range(1, len(src)):
    assert run_stream([src[:i], src[i:]]) == EXPECT, f"split at {i} diverged"
ok("every_split_point")

# --- random chunkings (seeded)
rng = random.Random(1234)
for _ in range(25):
    chunks, s = [], src
    while s:
        k = rng.randint(1, 7)
        chunks.append(s[:k]); s = s[k:]
    assert run_stream(chunks) == EXPECT
ok("random_chunkings")

# --- number completion at close / boundary
p = StreamParser()
assert p.feed("12") == []
assert p.feed("3 ") == [123]
p.close()
p2 = StreamParser()
assert p2.feed('"ab') == []
try:
    p2.close()
    raise AssertionError("mid-string close() must raise ValueError")
except ValueError:
    pass
p3 = StreamParser()
p3.feed('{"a": 1')
try:
    p3.close()
    raise AssertionError("unbalanced close() must raise ValueError")
except ValueError:
    pass
ok("boundaries")

# --- malformed input
for bad in ['{"a": tru5}', '[1,]', '{"a" 1}', '{1: 2}', '01a', '"\\x22"']:
    p = StreamParser()
    try:
        for ch in bad:
            p.feed(ch)
        p.close()
        raise AssertionError(f"{bad!r} must raise ValueError")
    except ValueError:
        pass
ok("malformed")

print("ALL_TESTS_PASSED")
""",
    "scoring": {
        "basic": 10,
        "char_at_a_time": 20,
        "every_split_point": 20,
        "random_chunkings": 10,
        "boundaries": 10,
        "malformed": 15,
        "code_quality": 15,
    },
}

BENCHMARKS = BENCHMARKS_V3 + [ORCH_TASK, STREAM_TASK]
