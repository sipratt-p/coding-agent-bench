#!/usr/bin/env python3
"""Run each reference solution in tasks/refs/ through its task's hidden tests.

A grader is only trusted once a known-good implementation prints ALL_TESTS_PASSED;
this is the check the harness authors ran before scoring any model. Exit code 1 if
any reference fails. Tasks 1-5 have no stored reference (see tasks/README.md).
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "bench"))
import coding_benchmark_v2 as cbv2  # noqa: E402
from suites import ALL_TASKS  # noqa: E402

REFS = {  # ref file -> task name
    "ref_regex.py": "POSIX Regex Engine (leftmost-longest)",
    "ref_crdt.py": "Convergent Replicated Text (CRDT)",
    "ref_orchestrator.py": "Async DAG Orchestrator (cancellation semantics)",
    "ref_streamparser.py": "Chunk-Split Streaming JSON Parser",
}


def main():
    by_name = {t["name"]: t for t in ALL_TASKS}
    failed = 0
    for fname, task_name in REFS.items():
        code = open(os.path.join(REPO, "tasks", "refs", fname)).read()
        task = by_name[task_name]
        ok, out, err = cbv2.run_python(code, task["test_code"], timeout=60)
        scores, pts, poss = cbv2.score_result(task, code, out, code)
        passed = "ALL_TESTS_PASSED" in out
        failed += not passed
        print(f"{'PASS' if passed else 'FAIL'}  {fname:22s} {task_name:50s} {pts}/{poss}")
        if not passed:
            print("    ", (err or out)[-400:].replace("\n", "\n     "))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
