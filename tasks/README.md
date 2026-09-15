# Tasks

The task suite is **code**, not data files: each task is a dict with `name`,
`prompt`, `test_code` (the hidden test program) and `scoring` (points per
criterion), defined in

| Module | Tasks | Added |
|---|---|---|
| `bench/coding_benchmark_v2.py` | 1 LRU cache, 2 async token-bucket rate limiter, 3 recursive-descent expression parser, 4 trie with autocomplete, 5 typed event emitter | April 2026 |
| `bench/coding_benchmark_v3.py` | 6 POSIX leftmost-longest regex engine (with a catastrophic-pattern perf gate), 7 RGA text CRDT (out-of-order + duplicate delivery) | 2026-08-16, because every keeper model saturated v2 at 478-485/500 |
| `bench/coding_benchmark_v4.py` | 8 async DAG orchestrator (real concurrency, cancellation semantics), 9 chunk-split streaming JSON parser (must survive a split at every byte) | 2026-08-19 |

`bench/coding_benchmark_v4.py` imports v3, which imports v2, so its `BENCHMARKS`
list is the full ordered nine-task suite. **v4 is the canonical task set**; the
runners select slices of it by name (`--suite v2|v3|v4|v3extras|v4extras|tb`,
see `bench/suites.py`). Tasks 6-9 are the "tiebreakers" (/400) used for every
head-to-head in `results/h2h/`.

`TASKS.md` is a rendered, read-only view of every prompt, rubric and hidden
test program (`python3 tasks/render_tasks.py` regenerates it).

## Scoring

Each task is worth 100 points. The hidden test program prints `<group>: ok`
after each group of assertions and `ALL_TESTS_PASSED` at the end; the functional
criteria are awarded when the whole program passes, or partially by matching
passed group names to criterion names. `code_quality` (15-25 points depending
on the task) is a text heuristic — functions, type hints, docstrings, size, no
TODOs — and is the only criterion that does not require running the code.
That is why "every functional criterion 0 but partial code_quality" is the
signature of a harness extraction bug rather than a model failure.

## Reference solutions (`refs/`)

| File | Task | Purpose |
|---|---|---|
| `ref_regex.py` | 6 | Thompson-NFA POSIX matcher |
| `ref_crdt.py` | 7 | RGA with tombstones, buffering, idempotence |
| `ref_orchestrator.py` | 8 | event-driven DAG runner with `wait_for` cancellation |
| `ref_streamparser.py` | 9 | incremental JSON value parser |

`python3 tasks/validate_refs.py` runs each one through its grader; all four
must print `ALL_TESTS_PASSED` before any model score is trusted. **No reference
solutions were kept for tasks 1-5**; their graders are validated empirically by
the many 96-100/100 scores in `results/` (tasks 1, 2 and 5 have each been
scored 100/100 by a harness-assisted run; 3 and 4 top out at 98 and 97 because
their `code_quality` heuristic rarely awards full marks).
