"""Shared pieces for the harness-assisted runners (run_prime_tb.py, run_cc_tb.py).

A harness-assisted run hands the task prompt to a coding agent that can execute and
self-test code in a scratch directory, then scores the solution.py it leaves behind
with the same hidden tests as the direct-API runner. These scores are NOT comparable
with direct-API scores.
"""
import argparse
import json
import os
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench_alert  # noqa: E402
import coding_benchmark_v2 as cbv2  # noqa: E402
from suites import SUITES, select_tasks  # noqa: E402

TASK_SUFFIX = ("\n\nWrite your final, complete solution to a file named solution.py in the "
               "current directory. Test it yourself before finishing. solution.py must "
               "contain ONLY the solution code.")


def common_parser(doc, default_timeout):
    p = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--display", required=True, help="label stored in the results JSON")
    p.add_argument("--out", required=True, help="results JSON path")
    p.add_argument("--suite", choices=sorted(SUITES), default="tb",
                   help="which tasks (default tb = the four tiebreakers, /400)")
    p.add_argument("--tasks", default=os.environ.get("TB_PICK", ""),
                   help="comma-separated name substrings to keep (env TB_PICK)")
    p.add_argument("--task-timeout", type=int, default=int(os.environ.get("TASK_TIMEOUT", default_timeout)),
                   help="wall-clock seconds per task before it is marked INCONCLUSIVE (env TASK_TIMEOUT)")
    p.add_argument("--work-root", default=os.environ.get("BENCH_WORK_ROOT", "work"),
                   help="scratch directory root; each task gets <work-root>/<slug>/task<i> (env BENCH_WORK_ROOT)")
    return p


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def fresh_workdir(work_root, model, idx):
    work = os.path.join(work_root, slug(model), f"task{idx}")
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    return work


def score_workdir(bench, work, stdout, elapsed, timed_out, display, task_timeout):
    """Score solution.py from `work` (fallback: a fenced block in the agent's stdout)."""
    code = ""
    sol = os.path.join(work, "solution.py")
    if os.path.exists(sol):
        code = open(sol).read()
    if not code.strip():
        m = re.findall(r"```python\n(.*?)```", stdout, re.DOTALL)
        code = m[-1].strip() if m else cbv2.extract_python_code(stdout)

    success, output, error = cbv2.run_python(code, bench["test_code"])
    scores, total_pts, possible = cbv2.score_result(bench, code, output, stdout)
    status = ("PASS" if "ALL_TESTS_PASSED" in output
              else "PARTIAL" if output else "FAIL")
    if timed_out and status != "PASS":
        status = "INCONCLUSIVE"
        bench_alert.alert("timeout", display, bench["name"],
                          f"hit the {task_timeout}s task timeout; scored {total_pts}/{possible} "
                          f"but the run was cut short -- do NOT treat as a model failure")
    print(f"  Status: {status} | {total_pts}/{possible} pts | {elapsed:.1f}s | "
          f"solution.py={'yes' if os.path.exists(sol) else 'NO'}", flush=True)
    for criterion, points in scores.items():
        max_pts = bench["scoring"][criterion]
        icon = "+" if points == max_pts else "-" if points == 0 else "~"
        print(f"    {icon} {criterion}: {points}/{max_pts}", flush=True)
    return {
        "name": bench["name"], "status": status, "score": total_pts,
        "max_score": possible, "scores": scores, "time": round(elapsed, 1),
        "error": error[:500] if error else None, "code_len": len(code),
        "wrote_solution_py": os.path.exists(sol),
    }


def finish(args, results, extra):
    scored = [r for r in results if r["status"] != "INCONCLUSIVE"]
    total = sum(r["score"] for r in scored)
    possible = sum(r["max_score"] for r in scored)
    summary = {"display": args.display, "mode": "harness-assisted", "suite": args.suite,
               "total": total, "possible": possible,
               "pct": round(total / possible * 100, 1) if possible else None,
               "inconclusive": [r["name"] for r in results if r["status"] == "INCONCLUSIVE"],
               "results": results}
    summary.update(extra)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    json.dump(summary, open(args.out, "w"), indent=1)
    print(f"\n=== TOTAL: {total}/{possible} ({summary['pct']}%) -> {args.out}", flush=True)
    return summary


def pick_tasks(p, args):
    benches = select_tasks(args.suite, args.tasks)
    if not benches:
        p.error(f"no tasks matched --suite {args.suite} --tasks {args.tasks!r}")
    return benches


def now():
    return time.perf_counter()
