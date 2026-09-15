"""Task-suite selection shared by every runner.

The task definitions live in coding_benchmark_v2.py (tasks 1-5), v3 (6-7) and
v4 (8-9); coding_benchmark_v4.BENCHMARKS is the full ordered 9-task list.
Suite totals are NOT comparable with each other (a /500 v2 run and a /400
tiebreaker run measure different things) -- per-task scores are.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from coding_benchmark_v4 import BENCHMARKS as ALL_TASKS  # noqa: E402

SUITES = {
    "v2": (0, 5),        # tasks 1-5, /500 -- the original 5-task suite
    "v3": (0, 7),        # tasks 1-7, /700
    "v4": (0, 9),        # tasks 1-9, /900 (everything)
    "v3extras": (5, 7),  # tasks 6-7, /200 (POSIX regex + CRDT)
    "v4extras": (7, 9),  # tasks 8-9, /200 (DAG orchestrator + streaming parser)
    "tb": (5, 9),        # tasks 6-9, /400 -- the four "tiebreakers"
}


def select_tasks(suite="v2", pick=""):
    """Return the task dicts for `suite`, optionally filtered by comma-separated
    case-insensitive name substrings in `pick` (e.g. "regex,crdt")."""
    lo, hi = SUITES[suite]
    tasks = ALL_TASKS[lo:hi]
    keys = [k.strip().lower() for k in pick.split(",") if k.strip()]
    if keys:
        tasks = [t for t in tasks if any(k in t["name"].lower() for k in keys)]
    return tasks


def describe():
    lines = []
    for i, t in enumerate(ALL_TASKS, 1):
        lines.append(f"{i}. {t['name']}  (/{sum(t['scoring'].values())})")
    lines.append("suites: " + ", ".join(f"{k}=tasks {lo + 1}-{hi}" for k, (lo, hi) in SUITES.items()))
    return "\n".join(lines)
