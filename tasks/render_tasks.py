#!/usr/bin/env python3
"""Render tasks/TASKS.md (prompt, scoring rubric and hidden test program for every task)
from the source of truth in bench/coding_benchmark_v{2,3,4}.py."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "bench"))
from suites import ALL_TASKS, SUITES  # noqa: E402

OUT = os.path.join(REPO, "tasks", "TASKS.md")


def main():
    lines = ["# Task suite", "",
             "Rendered by `tasks/render_tasks.py` from `bench/coding_benchmark_v4.py` (which chains v3 and v2). "
             "Each task is worth 100 points: the functional criteria are awarded from the hidden test program's "
             "`<group>: ok` lines (all of them when it prints `ALL_TESTS_PASSED`), and `code_quality` is a text "
             "heuristic (see `score_result` in `bench/coding_benchmark_v2.py`). The model only ever sees the prompt.", "",
             "Suites: " + ", ".join(f"`{k}` = tasks {lo + 1}-{hi}" for k, (lo, hi) in SUITES.items()), ""]
    for i, t in enumerate(ALL_TASKS, 1):
        lines += [f"## {i}. {t['name']}", "", "| Criterion | Points |", "|---|---|"]
        lines += [f"| {c} | {p} |" for c, p in t["scoring"].items()]
        lines += [f"| **total** | **{sum(t['scoring'].values())}** |", "", "### Prompt", "", "```text",
                  t["prompt"].rstrip(), "```", "", "### Hidden test program", "", "```python",
                  t["test_code"].strip("\n"), "```", ""]
    open(OUT, "w").write("\n".join(lines))
    print(f"wrote {OUT}: {len(ALL_TASKS)} tasks")


if __name__ == "__main__":
    main()
