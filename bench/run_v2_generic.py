#!/usr/bin/env python3
"""LEGACY direct-API runner (fence-only extractor). Kept to reproduce Finding 1.

This is the adapter that produced most of the pre-2026-08-26 "direct API" rows in
results/. It has two known defects, both fixed in run_direct.py:

  1. Code extraction is fence-only and falls back to `reasoning + "\\n" + content`,
     so a reasoning model that obeys "output only the code" with an UNFENCED answer
     scores near zero (a correct LRU-cache answer scored 17/100; re-scored 97/100 by
     run_direct.py's extractor). Tell-tale: every functional criterion 0 while
     code_quality gets partial credit.
  2. It sends temperature 0.0 unconditionally (model cards for the models tested
     say 1.0), and API errors / truncation are scored as 0 instead of INCONCLUSIVE.

Usage: run_v2_generic.py [display] [results_json] [base_url] [model]
"""
import json
import os
import re
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coding_benchmark_v2 as cbv2  # noqa: E402

DISPLAY = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BENCH_MODEL", "model")
RESULTS_JSON = sys.argv[2] if len(sys.argv) > 2 else "results_v2_generic.json"
SERVER = (sys.argv[3] if len(sys.argv) > 3 else os.environ.get("BENCH_BASE_URL", "http://127.0.0.1:8000")).rstrip("/") + "/v1/chat/completions"
MODEL = sys.argv[4] if len(sys.argv) > 4 else os.environ.get("BENCH_MODEL", "model")
MAX_TOKENS = None  # no token cap
REQUEST_TIMEOUT = int(os.environ.get("REQ_TIMEOUT", "3600"))


def api_call(server, model, prompt, max_tokens=MAX_TOKENS):
    data = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
    }).encode()
    headers = {"Content-Type": "application/json"}
    if os.environ.get("BENCH_API_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["BENCH_API_KEY"]
    req = urllib.request.Request(server, data=data, headers=headers)
    t0 = time.perf_counter()
    resp = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)
    body = resp.read()
    elapsed = time.perf_counter() - t0
    result = json.loads(body)

    msg = result["choices"][0]["message"]
    response = msg.get("content") or ""
    if not response.strip():
        response = msg.get("reasoning_content") or msg.get("reasoning") or ""
    reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
    if reasoning and msg.get("content"):
        response = reasoning + "\n" + msg["content"]  # <-- defect 1 (see docstring)

    usage = result.get("usage", {}) or {}
    tokens = usage.get("completion_tokens", 0)
    tps = tokens / elapsed if elapsed > 0 else 0.0
    return response, tokens, tps


def extract_python_code(response):
    matches = re.findall(r"```python\n(.*?)```", response, re.DOTALL)
    if matches:
        return matches[-1].strip()
    matches = re.findall(r"```\n(.*?)```", response, re.DOTALL)
    if matches:
        return matches[-1].strip()
    return cbv2.extract_python_code(response)


def run_one(bench, idx, total):
    print(f"\n[{idx}/{total}] {bench['name']}...", flush=True)
    t0 = time.perf_counter()
    try:
        response, tokens, tps = api_call(SERVER, MODEL, bench["prompt"])
    except Exception as e:
        print(f"  API ERROR: {e}", flush=True)
        return {
            "name": bench["name"], "status": "API_ERROR", "score": 0,
            "max_score": sum(bench["scoring"].values()), "pct": 0.0,
            "scores": {k: 0 for k in bench["scoring"]},
            "time": round(time.perf_counter() - t0, 1),
            "tokens": 0, "tps": 0.0, "error": str(e)[:500],
        }
    elapsed = time.perf_counter() - t0
    code = extract_python_code(response)
    success, output, error = cbv2.run_python(code, bench["test_code"])
    scores, total_pts, possible = cbv2.score_result(bench, code, output, response)
    status = ("PASS" if "ALL_TESTS_PASSED" in output
              else "PARTIAL" if output else "FAIL")
    print(f"  Status: {status} | {total_pts}/{possible} pts | "
          f"{elapsed:.1f}s | {tokens} tok | {tps:.1f} tok/s", flush=True)
    for criterion, points in scores.items():
        max_pts = bench["scoring"][criterion]
        icon = "+" if points == max_pts else "-" if points == 0 else "~"
        print(f"    {icon} {criterion}: {points}/{max_pts}", flush=True)
    return {
        "name": bench["name"], "status": status, "score": total_pts,
        "max_score": possible, "pct": round(total_pts / possible * 100, 1),
        "scores": scores, "time": round(elapsed, 1), "tokens": tokens,
        "tps": round(tps, 2), "error": error[:500] if error else None,
        "response_len": len(response), "code_len": len(code),
    }


def main():
    benches = cbv2.BENCHMARKS
    print(f"=== {DISPLAY} ===\n{len(benches)} tasks, max_tokens={MAX_TOKENS}", flush=True)
    results = [run_one(b, i + 1, len(benches)) for i, b in enumerate(benches)]
    total = sum(r["score"] for r in results)
    possible = sum(r["max_score"] for r in results)
    summary = {
        "display": DISPLAY, "server": SERVER, "max_tokens": MAX_TOKENS,
        "runner": "run_v2_generic.py (legacy)", "mode": "direct-api",
        "total": total, "possible": possible,
        "pct": round(total / possible * 100, 1),
        "results": results,
    }
    json.dump(summary, open(RESULTS_JSON, "w"), indent=1)
    print(f"\n=== TOTAL: {total}/{possible} ({summary['pct']}%) -> {RESULTS_JSON}", flush=True)


if __name__ == "__main__":
    main()
