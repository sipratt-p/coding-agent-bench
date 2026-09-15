#!/usr/bin/env python3
"""
Coding benchmark v2: the five core tasks (/500) plus the scoring primitives every
runner shares (extract_python_code, run_python, score_result).

Each task is scored 0-100: functional criteria are awarded from the hidden test
program's "<group>: ok" lines (all of them if it prints ALL_TESTS_PASSED), plus a
code_quality heuristic scored by inspecting the code text (never by running it).
v3 (tasks 6-7) and v4 (tasks 8-9) import this module and extend BENCHMARKS.

The api_call()/main() here are the original April 2026 one-shot driver, kept for
provenance; use run_direct.py for new runs.
"""

import argparse
import json
import urllib.request
import time
import subprocess
import re
import sys
import tempfile
import os

def api_call(server, model, prompt, max_tokens=None, temperature=None):
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    if max_tokens:
        payload["max_tokens"] = max_tokens
    if temperature is not None:
        payload["temperature"] = temperature
    data = json.dumps(payload).encode()
    req = urllib.request.Request(server, data=data, headers={"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=300)
    result = json.loads(resp.read())
    msg = result["choices"][0]["message"]
    response = msg.get("content") or msg.get("reasoning_content") or msg.get("reasoning") or ""
    tokens = result.get("usage", {}).get("completion_tokens", 0)
    timings = result.get("timings", {})
    tps = timings.get("predicted_per_second", 0)
    return response, tokens, tps

def extract_python_code(response):
    """Extract Python code from markdown code blocks or raw response."""
    # Try ```python blocks first
    matches = re.findall(r'```python\n(.*?)```', response, re.DOTALL)
    if matches:
        return matches[0].strip()
    # Try generic ``` blocks
    matches = re.findall(r'```\n(.*?)```', response, re.DOTALL)
    if matches:
        return matches[0].strip()
    # Try to find code by looking for def/class/import
    lines = response.split('\n')
    code_lines = []
    in_code = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(('def ', 'class ', 'import ', 'from ', 'async ')):
            in_code = True
        if in_code:
            if stripped == '' and code_lines and code_lines[-1].strip() == '':
                # Double blank line might mean end of code
                continue
            code_lines.append(line)
    return '\n'.join(code_lines).strip() if code_lines else response

def run_python(code, test_code, timeout=10):
    """Run Python code with test cases, return (success, output, error)."""
    full_code = code + "\n\n" + test_code
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(full_code)
        f.flush()
        try:
            result = subprocess.run(
                [sys.executable, f.name],
                capture_output=True, text=True, timeout=timeout
            )
            return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            return False, "", "TIMEOUT"
        finally:
            os.unlink(f.name)

BENCHMARKS = [
    {
        "name": "LRU Cache Implementation",
        "prompt": """Implement an LRU (Least Recently Used) cache in Python with O(1) get and put operations.

Requirements:
- `LRUCache(capacity: int)` — initialize with positive capacity
- `get(key: int) -> int` — return value if key exists, otherwise -1
- `put(key: int, value: int) -> None` — update or insert. Evict LRU when at capacity.

Output only the Python code, no explanation.""",
        "test_code": """
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
""",
        "scoring": {
            "basic_correctness": 30,      # basic get/put/evict
            "edge_capacity_1": 10,        # handles capacity=1
            "edge_update_lru": 15,        # get() updates recency
            "edge_overwrite": 10,         # overwriting existing key
            "performance": 15,            # O(1) operations
            "code_quality": 20,           # clean code, type hints, etc.
        },
    },
    {
        "name": "Async Rate Limiter",
        "prompt": """Implement a token bucket rate limiter in Python using asyncio.

Requirements:
- The class must be named exactly `RateLimiter`
- `RateLimiter(rate: float, burst: int)` — rate is tokens per second, burst is max tokens
- `async acquire(tokens: int = 1) -> None` — async; wait until tokens are available, then consume them
- `try_acquire(tokens: int = 1) -> bool` — **synchronous** (non-async); return True if acquired, False otherwise. Do NOT declare this as `async def` — callers invoke it without `await`.
- Must handle concurrent callers correctly

Output only the Python code, no explanation.""",
        "test_code": """
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
""",
        "scoring": {
            "basic_try_acquire": 25,
            "token_refill": 20,
            "async_acquire": 20,
            "multi_token": 10,
            "code_quality": 25,
        },
    },
    {
        "name": "Recursive Descent Parser",
        "prompt": """Write a Python function that parses and evaluates simple mathematical expressions.

Support: +, -, *, /, parentheses, unary minus, floating point numbers.
Respect operator precedence (* and / before + and -).
Raise ValueError on invalid expressions.

`def evaluate(expr: str) -> float`

Output only the Python code, no explanation.""",
        "test_code": """
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
""",
        "scoring": {
            "basic_arithmetic": 15,
            "operator_precedence": 20,
            "parentheses": 15,
            "unary_minus": 15,
            "floating_point": 10,
            "error_handling": 10,
            "code_quality": 15,
        },
    },
    {
        "name": "Trie with Autocomplete",
        "prompt": """Implement a Trie (prefix tree) in Python with autocomplete functionality.

Requirements:
- `insert(word: str) -> None` — insert a word
- `search(word: str) -> bool` — return True if exact word exists
- `starts_with(prefix: str) -> bool` — return True if any word starts with prefix
- `autocomplete(prefix: str, limit: int = 5) -> list[str]` — return up to `limit` words starting with prefix, sorted alphabetically
- `delete(word: str) -> bool` — remove a word, return True if it existed

Output only the Python code, no explanation.""",
        "test_code": """
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
""",
        "scoring": {
            "insert_search": 20,
            "starts_with": 10,
            "autocomplete_basic": 15,
            "autocomplete_limit": 10,
            "delete_basic": 15,
            "delete_preserves_prefix": 10,
            "code_quality": 20,
        },
    },
    {
        "name": "Event Emitter with Typed Events",
        "prompt": """Implement a typed event emitter in Python.

Requirements:
- The class must be named exactly `EventEmitter` (not `TypedEventEmitter` or anything else)
- `on(event: str, callback: Callable) -> Callable` — register listener, return unsubscribe function
- `once(event: str, callback: Callable) -> Callable` — register one-time listener
- `emit(event: str, *args, **kwargs) -> None` — call all listeners for event
- `off(event: str, callback: Callable) -> None` — remove specific listener
- `listeners(event: str) -> list[Callable]` — return list of listeners
- `remove_all_listeners(event: str = None) -> None` — remove all listeners for event, or all events if None

Output only the Python code, no explanation.""",
        "test_code": """
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
""",
        "scoring": {
            "basic_on_emit": 15,
            "multiple_listeners": 10,
            "unsubscribe_return": 15,
            "once": 15,
            "off": 10,
            "remove_all": 10,
            "kwargs": 5,
            "code_quality": 20,
        },
    },
]


def score_result(bench, code, test_output, response):
    """Score a benchmark result with granular criteria."""
    scores = {}
    total_possible = sum(bench["scoring"].values())

    # Run the tests and see which pass
    success = "ALL_TESTS_PASSED" in test_output

    # Parse which test groups passed
    test_groups_passed = set()
    for line in test_output.split('\n'):
        if ': ok' in line:
            group = line.split(':')[0].strip()
            test_groups_passed.add(group)

    # Map test groups to scoring criteria
    scoring = bench["scoring"]
    for criterion, points in scoring.items():
        if criterion == "code_quality":
            # Score code quality heuristically
            quality = 0
            if 'def ' in code: quality += 3
            if ': ' in code and '->' in code: quality += 3  # type hints
            if '"""' in code or "'''" in code: quality += 2  # docstrings
            if len(code.split('\n')) < 100: quality += 2  # not bloated
            if not re.search(r'#.*TODO|#.*HACK|#.*FIXME', code): quality += 2
            if 'class ' in code: quality += 2  # OOP when appropriate
            # Normalize to points
            scores[criterion] = min(points, round(quality / 14 * points))
        else:
            # Map criterion name to test group names
            # If all tests pass, give full points
            if success:
                scores[criterion] = points
            else:
                # Partial credit based on which groups passed
                criterion_lower = criterion.lower()
                matched = False
                for group in test_groups_passed:
                    if group.lower() in criterion_lower or criterion_lower in group.lower():
                        scores[criterion] = points
                        matched = True
                        break
                    # Fuzzy match
                    if any(w in criterion_lower for w in group.lower().split('_')):
                        scores[criterion] = points
                        matched = True
                        break
                if not matched:
                    # Check if this is a basic test that likely maps to "basic"
                    if 'basic' in criterion_lower and 'basic' in ' '.join(test_groups_passed).lower():
                        scores[criterion] = points
                    else:
                        scores[criterion] = 0

    total = sum(scores.values())
    return scores, total, total_possible


def run_benchmark_suite(server, model, display_name):
    print(f"\n{'='*70}")
    print(f"CODING BENCHMARK v2: {display_name}")
    print(f"{'='*70}")

    results = []
    for i, bench in enumerate(BENCHMARKS):
        print(f"\n[{i+1}/{len(BENCHMARKS)}] {bench['name']}...")

        start = time.perf_counter()
        response, tokens, tps = api_call(server, model, bench["prompt"])
        elapsed = time.perf_counter() - start

        code = extract_python_code(response)
        success, output, error = run_python(code, bench["test_code"])

        scores, total, possible = score_result(bench, code, output, response)

        status = "PASS" if "ALL_TESTS_PASSED" in output else "PARTIAL" if output else "FAIL"

        print(f"  Status: {status} | {total}/{possible} pts | {elapsed:.1f}s")
        if not success and error:
            print(f"  Error: {error[:200]}")

        # Show individual scores
        for criterion, points in scores.items():
            max_pts = bench["scoring"][criterion]
            icon = "✓" if points == max_pts else "✗" if points == 0 else "~"
            print(f"    {icon} {criterion}: {points}/{max_pts}")

        results.append({
            "name": bench["name"],
            "status": status,
            "score": total,
            "max_score": possible,
            "pct": round(total / possible * 100, 1),
            "scores": scores,
            "time": round(elapsed, 1),
            "tokens": tokens,
            "error": error[:200] if error else None,
        })

    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY: {display_name}")
    print(f"{'='*70}")
    total_score = sum(r["score"] for r in results)
    total_possible = sum(r["max_score"] for r in results)
    print(f"\n{'Test':<30} {'Score':>8} {'Status':>8} {'Time':>7}")
    print("-" * 58)
    for r in results:
        print(f"{r['name']:<30} {r['score']}/{r['max_score']:>3} ({r['pct']:>5.1f}%) {r['status']:>7} {r['time']:>6.1f}s")
    print("-" * 58)
    print(f"{'TOTAL':<30} {total_score}/{total_possible} ({total_score/total_possible*100:.1f}%)")

    return results


def main():
    p = argparse.ArgumentParser(description="One-shot v2 suite driver (legacy). Prefer run_direct.py.")
    p.add_argument("--base-url", default=os.environ.get("BENCH_BASE_URL", "http://127.0.0.1:8000"))
    p.add_argument("--model", default=os.environ.get("BENCH_MODEL", ""), help="model id (env BENCH_MODEL)")
    p.add_argument("--display", default=None)
    p.add_argument("--out", default="coding_benchmark_v2_results.json")
    args = p.parse_args()
    if not args.model:
        p.error("--model is required (or set BENCH_MODEL)")
    url = args.base_url.rstrip("/") + "/v1/chat/completions"
    display = args.display or args.model
    print("=" * 70)
    print("CODING BENCHMARK v2 — Granular Scoring with Code Execution")
    print("=" * 70)
    results = run_benchmark_suite(url, args.model, display)
    with open(args.out, "w") as f:
        json.dump({display: results}, f, indent=2)
    print(f"\nResults saved to {args.out}")


if __name__ == "__main__":
    main()
