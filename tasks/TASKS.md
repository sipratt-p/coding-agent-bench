# Task suite

Rendered by `tasks/render_tasks.py` from `bench/coding_benchmark_v4.py` (which chains v3 and v2). Each task is worth 100 points: the functional criteria are awarded from the hidden test program's `<group>: ok` lines (all of them when it prints `ALL_TESTS_PASSED`), and `code_quality` is a text heuristic (see `score_result` in `bench/coding_benchmark_v2.py`). The model only ever sees the prompt.

Suites: `v2` = tasks 1-5, `v3` = tasks 1-7, `v4` = tasks 1-9, `v3extras` = tasks 6-7, `v4extras` = tasks 8-9, `tb` = tasks 6-9

## 1. LRU Cache Implementation

| Criterion | Points |
|---|---|
| basic_correctness | 30 |
| edge_capacity_1 | 10 |
| edge_update_lru | 15 |
| edge_overwrite | 10 |
| performance | 15 |
| code_quality | 20 |
| **total** | **100** |

### Prompt

```text
Implement an LRU (Least Recently Used) cache in Python with O(1) get and put operations.

Requirements:
- `LRUCache(capacity: int)` — initialize with positive capacity
- `get(key: int) -> int` — return value if key exists, otherwise -1
- `put(key: int, value: int) -> None` — update or insert. Evict LRU when at capacity.

Output only the Python code, no explanation.
```

### Hidden test program

```python
# Basic tests
cache = LRUCache(2)
cache.put(1, 1)
cache.put(2, 2)
assert cache.get(1) == 1, f"Expected 1, got {cache.get(1)}"
cache.put(3, 3)  # evicts key 2
assert cache.get(2) == -1, f"Expected -1, got {cache.get(2)}"
cache.put(4, 4)  # evicts key 1
assert cache.get(1) == -1, f"Expected -1 for evicted key 1"
assert cache.get(3) == 3
assert cache.get(4) == 4

# Edge: capacity 1
c2 = LRUCache(1)
c2.put(1, 10)
assert c2.get(1) == 10
c2.put(2, 20)
assert c2.get(1) == -1
assert c2.get(2) == 20

# Edge: update existing key
c3 = LRUCache(2)
c3.put(1, 1)
c3.put(2, 2)
c3.get(1)  # makes 1 recently used
c3.put(3, 3)  # should evict 2, not 1
assert c3.get(2) == -1, "Should have evicted 2"
assert c3.get(1) == 1, "1 should still be present"

# Edge: overwrite value
c4 = LRUCache(2)
c4.put(1, 1)
c4.put(1, 10)
assert c4.get(1) == 10, f"Expected updated value 10, got {c4.get(1)}"

# Performance: should not degrade with many operations
import time
c5 = LRUCache(1000)
start = time.time()
for i in range(10000):
    c5.put(i, i)
for i in range(10000):
    c5.get(i)
elapsed = time.time() - start
assert elapsed < 1.0, f"Too slow: {elapsed:.2f}s for 20k ops"

print("ALL_TESTS_PASSED")
```

## 2. Async Rate Limiter

| Criterion | Points |
|---|---|
| basic_try_acquire | 25 |
| token_refill | 20 |
| async_acquire | 20 |
| multi_token | 10 |
| code_quality | 25 |
| **total** | **100** |

### Prompt

```text
Implement a token bucket rate limiter in Python using asyncio.

Requirements:
- The class must be named exactly `RateLimiter`
- `RateLimiter(rate: float, burst: int)` — rate is tokens per second, burst is max tokens
- `async acquire(tokens: int = 1) -> None` — async; wait until tokens are available, then consume them
- `try_acquire(tokens: int = 1) -> bool` — **synchronous** (non-async); return True if acquired, False otherwise. Do NOT declare this as `async def` — callers invoke it without `await`.
- Must handle concurrent callers correctly

Output only the Python code, no explanation.
```

### Hidden test program

```python
import asyncio

async def test_basic():
    rl = RateLimiter(rate=10, burst=5)
    # Should succeed immediately (burst allows 5)
    assert rl.try_acquire(1) == True
    assert rl.try_acquire(1) == True
    assert rl.try_acquire(1) == True
    assert rl.try_acquire(1) == True
    assert rl.try_acquire(1) == True
    # Should fail (burst exhausted)
    assert rl.try_acquire(1) == False
    print("basic: ok")

async def test_refill():
    rl = RateLimiter(rate=100, burst=5)
    # Exhaust burst
    for _ in range(5):
        rl.try_acquire(1)
    assert rl.try_acquire(1) == False
    # Wait for refill
    await asyncio.sleep(0.06)  # should refill ~6 tokens at 100/s
    assert rl.try_acquire(1) == True
    print("refill: ok")

async def test_acquire_waits():
    rl = RateLimiter(rate=100, burst=1)
    rl.try_acquire(1)  # exhaust
    start = asyncio.get_event_loop().time()
    await rl.acquire(1)  # should wait ~0.01s
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed >= 0.005, f"Should have waited, only {elapsed:.3f}s"
    assert elapsed < 0.5, f"Waited too long: {elapsed:.3f}s"
    print("acquire_waits: ok")

async def test_multi_token():
    rl = RateLimiter(rate=10, burst=10)
    assert rl.try_acquire(5) == True
    assert rl.try_acquire(5) == True
    assert rl.try_acquire(1) == False
    print("multi_token: ok")

async def main():
    await test_basic()
    await test_refill()
    await test_acquire_waits()
    await test_multi_token()
    print("ALL_TESTS_PASSED")

asyncio.run(main())
```

## 3. Recursive Descent Parser

| Criterion | Points |
|---|---|
| basic_arithmetic | 15 |
| operator_precedence | 20 |
| parentheses | 15 |
| unary_minus | 15 |
| floating_point | 10 |
| error_handling | 10 |
| code_quality | 15 |
| **total** | **100** |

### Prompt

```text
Write a Python function that parses and evaluates simple mathematical expressions.

Support: +, -, *, /, parentheses, unary minus, floating point numbers.
Respect operator precedence (* and / before + and -).
Raise ValueError on invalid expressions.

`def evaluate(expr: str) -> float`

Output only the Python code, no explanation.
```

### Hidden test program

```python
# Basic arithmetic
assert evaluate("2 + 3") == 5.0
assert evaluate("10 - 4") == 6.0
assert evaluate("3 * 4") == 12.0
assert evaluate("15 / 3") == 5.0
print("basic: ok")

# Precedence
assert evaluate("2 + 3 * 4") == 14.0
assert evaluate("2 * 3 + 4") == 10.0
assert evaluate("10 - 2 * 3") == 4.0
print("precedence: ok")

# Parentheses
assert evaluate("(2 + 3) * 4") == 20.0
assert evaluate("2 * (3 + 4)") == 14.0
assert evaluate("((2 + 3))") == 5.0
print("parens: ok")

# Unary minus
assert evaluate("-5") == -5.0
assert evaluate("-5 + 3") == -2.0
assert evaluate("-(2 + 3)") == -5.0
print("unary: ok")

# Floating point
assert abs(evaluate("3.14 * 2") - 6.28) < 0.001
assert abs(evaluate("1 / 3") - 0.333333) < 0.001
print("float: ok")

# Complex
assert evaluate("(2 + 3) * (4 - 1) / 3") == 5.0
assert abs(evaluate("2.5 * (3 + -1.5)") - 3.75) < 0.001
print("complex: ok")

# Error handling
try:
    evaluate("")
    assert False, "Should raise on empty"
except (ValueError, Exception):
    pass

try:
    evaluate("2 +")
    assert False, "Should raise on incomplete"
except (ValueError, Exception):
    pass

try:
    evaluate("2 + + 3")
    # This could be valid if interpreted as "2 + (+3)" = 5
    # or invalid. Either interpretation is acceptable.
    pass
except (ValueError, Exception):
    pass

print("errors: ok")
print("ALL_TESTS_PASSED")
```

## 4. Trie with Autocomplete

| Criterion | Points |
|---|---|
| insert_search | 20 |
| starts_with | 10 |
| autocomplete_basic | 15 |
| autocomplete_limit | 10 |
| delete_basic | 15 |
| delete_preserves_prefix | 10 |
| code_quality | 20 |
| **total** | **100** |

### Prompt

```text
Implement a Trie (prefix tree) in Python with autocomplete functionality.

Requirements:
- `insert(word: str) -> None` — insert a word
- `search(word: str) -> bool` — return True if exact word exists
- `starts_with(prefix: str) -> bool` — return True if any word starts with prefix
- `autocomplete(prefix: str, limit: int = 5) -> list[str]` — return up to `limit` words starting with prefix, sorted alphabetically
- `delete(word: str) -> bool` — remove a word, return True if it existed

Output only the Python code, no explanation.
```

### Hidden test program

```python
t = Trie()
words = ["apple", "app", "application", "apply", "banana", "band", "bandana"]
for w in words:
    t.insert(w)

# Search
assert t.search("apple") == True
assert t.search("app") == True
assert t.search("ap") == False
assert t.search("banana") == True
assert t.search("ban") == False
print("search: ok")

# Starts with
assert t.starts_with("app") == True
assert t.starts_with("ban") == True
assert t.starts_with("xyz") == False
assert t.starts_with("") == True
print("starts_with: ok")

# Autocomplete
result = t.autocomplete("app")
assert result == ["app", "apple", "application", "apply"], f"Got {result}"
result = t.autocomplete("ban")
assert result == ["banana", "band", "bandana"], f"Got {result}"
result = t.autocomplete("app", limit=2)
assert result == ["app", "apple"], f"Got {result}"
result = t.autocomplete("xyz")
assert result == [], f"Got {result}"
print("autocomplete: ok")

# Delete
assert t.delete("app") == True
assert t.search("app") == False
assert t.search("apple") == True  # should NOT delete prefix
assert t.starts_with("app") == True
result = t.autocomplete("app")
assert "app" not in result
assert "apple" in result
print("delete: ok")

# Delete non-existent
assert t.delete("nothere") == False
print("delete_nonexist: ok")

# Edge: empty string
t2 = Trie()
t2.insert("")
assert t2.search("") == True
assert t2.starts_with("") == True
print("edge_empty: ok")

print("ALL_TESTS_PASSED")
```

## 5. Event Emitter with Typed Events

| Criterion | Points |
|---|---|
| basic_on_emit | 15 |
| multiple_listeners | 10 |
| unsubscribe_return | 15 |
| once | 15 |
| off | 10 |
| remove_all | 10 |
| kwargs | 5 |
| code_quality | 20 |
| **total** | **100** |

### Prompt

```text
Implement a typed event emitter in Python.

Requirements:
- The class must be named exactly `EventEmitter` (not `TypedEventEmitter` or anything else)
- `on(event: str, callback: Callable) -> Callable` — register listener, return unsubscribe function
- `once(event: str, callback: Callable) -> Callable` — register one-time listener
- `emit(event: str, *args, **kwargs) -> None` — call all listeners for event
- `off(event: str, callback: Callable) -> None` — remove specific listener
- `listeners(event: str) -> list[Callable]` — return list of listeners
- `remove_all_listeners(event: str = None) -> None` — remove all listeners for event, or all events if None

Output only the Python code, no explanation.
```

### Hidden test program

```python
ee = EventEmitter()

# Basic on/emit
results = []
def on_data(x): results.append(x)
ee.on("data", on_data)
ee.emit("data", 42)
assert results == [42], f"Got {results}"
print("basic: ok")

# Multiple listeners
results2 = []
def on_data2(x): results2.append(x * 2)
ee.on("data", on_data2)
ee.emit("data", 5)
assert results == [42, 5], f"Got {results}"
assert results2 == [10], f"Got {results2}"
print("multi: ok")

# Unsubscribe via return value
unsub = ee.on("test", lambda x: None)
assert len(ee.listeners("test")) == 1
unsub()
assert len(ee.listeners("test")) == 0
print("unsub: ok")

# Once
once_results = []
ee.once("ping", lambda: once_results.append("pong"))
ee.emit("ping")
ee.emit("ping")
assert once_results == ["pong"], f"Got {once_results}"
print("once: ok")

# Off
ee2 = EventEmitter()
handler = lambda x: None
ee2.on("ev", handler)
assert len(ee2.listeners("ev")) == 1
ee2.off("ev", handler)
assert len(ee2.listeners("ev")) == 0
print("off: ok")

# remove_all_listeners specific event
ee3 = EventEmitter()
ee3.on("a", lambda: None)
ee3.on("a", lambda: None)
ee3.on("b", lambda: None)
ee3.remove_all_listeners("a")
assert len(ee3.listeners("a")) == 0
assert len(ee3.listeners("b")) == 1
print("remove_all_specific: ok")

# remove_all_listeners all events
ee3.remove_all_listeners()
assert len(ee3.listeners("b")) == 0
print("remove_all_global: ok")

# kwargs support
kw_results = []
ee4 = EventEmitter()
ee4.on("kw", lambda name="": kw_results.append(name))
ee4.emit("kw", name="test")
assert kw_results == ["test"], f"Got {kw_results}"
print("kwargs: ok")

print("ALL_TESTS_PASSED")
```

## 6. POSIX Regex Engine (leftmost-longest)

| Criterion | Points |
|---|---|
| basic | 15 |
| leftmost_longest | 25 |
| classes_anchors | 15 |
| invalid_patterns | 10 |
| performance | 20 |
| code_quality | 15 |
| **total** | **100** |

### Prompt

```text
Implement a regular-expression engine in Python with POSIX leftmost-longest semantics. No imports of `re` or any regex/parsing library (pure stdlib data structures only).

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

Output only the Python code, no explanation.
```

### Hidden test program

```python
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
```

## 7. Convergent Replicated Text (CRDT)

| Criterion | Points |
|---|---|
| basic | 10 |
| serializable | 5 |
| concurrent_order | 25 |
| out_of_order | 25 |
| convergence_fuzz | 20 |
| code_quality | 15 |
| **total** | **100** |

### Prompt

```text
Implement a convergent replicated text document (a CRDT) in Python, stdlib only.

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

Output only the Python code, no explanation.
```

### Hidden test program

```python
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
```

## 8. Async DAG Orchestrator (cancellation semantics)

| Criterion | Points |
|---|---|
| basic_dag | 15 |
| true_concurrency | 20 |
| failure_skip | 20 |
| timeout_cancel | 20 |
| validation | 10 |
| code_quality | 15 |
| **total** | **100** |

### Prompt

```text
Implement an async task orchestrator in Python (pure stdlib, asyncio only).

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

Output only the Python code, no explanation.
```

### Hidden test program

```python
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
```

## 9. Chunk-Split Streaming JSON Parser

| Criterion | Points |
|---|---|
| basic | 10 |
| char_at_a_time | 20 |
| every_split_point | 20 |
| random_chunkings | 10 |
| boundaries | 10 |
| malformed | 15 |
| code_quality | 15 |
| **total** | **100** |

### Prompt

```text
Implement an incremental (streaming) JSON value parser in Python — pure stdlib, and you may NOT import `json` or any parsing library. It must produce complete top-level JSON values as they finish arriving, no matter how the input is split into chunks.

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
- strings with escapes: \" \\ \/ \b \f \n \r \t and \uXXXX -> str
- numbers: integers, decimals, exponents, leading minus (e.g. -1.5e-3).
  Integers (no '.', no exponent) -> int, otherwise -> float
- true/false/null -> True/False/None

HARD REQUIREMENTS — exactly graded:
1. Chunks split ANYWHERE: mid-string, mid-escape (even between the backslash
   and the 'u', or between \u digit hex chars), mid-number, mid-literal
   (e.g. 'tr' then 'ue'), mid-key. The tests feed a corpus split at EVERY
   single character boundary, one char at a time, and in random chunkings —
   the outputs must be identical every time.
2. Malformed input raises `ValueError` at the earliest chunk where the text
   cannot be a prefix of any valid stream (e.g. `{"a": tru5}` on the '5';
   `[1,]` on the ']'). You do NOT need mid-number strictness beyond: a number
   must not be immediately followed by an alphanumeric character.
3. A number at top level is only complete once a non-number character or
   close() confirms it (e.g. feed("12") feed("3 ") -> [123]).

Output only the Python code, no explanation.
```

### Hidden test program

```python
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
```
