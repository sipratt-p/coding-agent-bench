#!/usr/bin/env python3
"""Direct-API runner: one prompt per task to an OpenAI-compatible endpoint.

Each task prompt is sent as a single user message to POST {base_url}/v1/chat/completions,
the answer's code is extracted, the hidden test program is appended and executed in a
subprocess, and the task is scored (functional test groups + a code_quality heuristic).

This is the merge of the two runners that produced the "direct API" rows in results/:
  * run_v2_reasoning.py -- reasoning-model-safe extraction (fixes the unfenced-answer
    mis-scoring described in the README) and INCONCLUSIVE handling for timeouts,
  * run_tb.py           -- finish_reason == "length" -> INCONCLUSIVE (max-token cap).
Scoring is byte-identical to the original harness (coding_benchmark_v2.score_result).

Direct-API scores are NOT comparable with harness-assisted scores (run_prime_tb.py,
run_cc_tb.py): the agent harnesses can execute and self-test code, and they sample at
the server default temperature while historical direct runs used temperature 0.

Example:
  python bench/run_direct.py --base-url http://127.0.0.1:8000 --model my-model \
      --suite v2 --runs 3 --out results/my-model_v2.json
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bench_alert  # noqa: E402
import coding_benchmark_v2 as cbv2  # noqa: E402
from suites import SUITES, describe, select_tasks  # noqa: E402

CODE_HINT = re.compile(r"^\s*(?:from |import |def |class |@|async def )", re.M)


def api_call(url, model, prompt, temperature=None, max_tokens=None, timeout=2400,
             api_key=None):
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens:  # None/0 -> omit entirely (generate to EOS or context end)
        payload["max_tokens"] = max_tokens
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
    t0 = time.perf_counter()
    body = urllib.request.urlopen(req, timeout=timeout).read()
    elapsed = time.perf_counter() - t0
    result = json.loads(body)
    choice = result["choices"][0]
    msg = choice["message"]
    content = msg.get("content") or ""
    reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
    # Reasoning models: the ANSWER is `content`. Never mine the scratchpad for code
    # unless content is genuinely empty -- concatenating them makes "last fenced
    # block wins" grab a half-finished draft out of the reasoning trace.
    response = content if content.strip() else reasoning
    usage = result.get("usage") or {}
    tokens = usage.get("completion_tokens", 0)
    return {
        "response": response, "content": content, "reasoning": reasoning,
        "finish": choice.get("finish_reason") or "", "tokens": tokens,
        "tps": tokens / elapsed if elapsed > 0 else 0.0, "elapsed": elapsed,
    }


def extract_python_code(response):
    """Fenced block wins (LAST one); otherwise accept a bare-code answer.

    Prompts in this suite say "Output only the Python code, no explanation".
    A model that obeys that literally emits UNFENCED code, which a fence-only
    extractor scores as zero. Fall back to the raw text when it compiles.
    """
    matches = re.findall(r"```python\n(.*?)```", response, re.DOTALL)
    if matches:
        return matches[-1].strip()
    matches = re.findall(r"```\n(.*?)```", response, re.DOTALL)
    if matches:
        return matches[-1].strip()
    stripped = response.strip()
    if stripped and CODE_HINT.search(stripped):
        try:
            compile(stripped, "<answer>", "exec")
            return stripped
        except SyntaxError:
            pass
    return cbv2.extract_python_code(response)


def run_one(args, url, bench, idx, total):
    print(f"\n[{idx}/{total}] {bench['name']}...", flush=True)
    t0 = time.perf_counter()
    possible = sum(bench["scoring"].values())
    try:
        r = api_call(url, args.model, bench["prompt"], args.temperature, args.max_tokens,
                     args.timeout, args.api_key)
    except Exception as e:  # network / HTTP / timeout -> not a model result
        kind = "INCONCLUSIVE_TIMEOUT" if "timed out" in str(e).lower() else "API_ERROR"
        print(f"  {kind}: {e}", flush=True)
        bench_alert.alert("timeout" if kind.startswith("INCONCLUSIVE") else "api_error",
                          args.display, bench["name"], str(e)[:300])
        return {"name": bench["name"], "status": kind, "score": None, "max_score": possible,
                "pct": 0.0, "scores": {k: 0 for k in bench["scoring"]},
                "time": round(time.perf_counter() - t0, 1), "tokens": 0, "tps": 0.0,
                "error": str(e)[:500]}
    elapsed = time.perf_counter() - t0
    code = extract_python_code(r["response"])
    success, output, error = cbv2.run_python(code, bench["test_code"], timeout=args.test_timeout)
    scores, total_pts, possible = cbv2.score_result(bench, code, output, r["response"])
    status = "PASS" if "ALL_TESTS_PASSED" in output else "PARTIAL" if output else "FAIL"
    if r["finish"] == "length" and status != "PASS":
        # ran to the token cap / context ceiling -> we never saw a final answer
        status = "INCONCLUSIVE_LENGTH"
        bench_alert.alert("max_tokens", args.display, bench["name"],
                          f"generation stopped at the token cap ({r['tokens']} tokens, "
                          f"finish_reason=length); scored {total_pts}/{possible} but the answer "
                          f"was truncated -- raise the cap and rerun")
    print(f"  Status: {status} | {total_pts}/{possible} pts | {elapsed:.1f}s | "
          f"{r['tokens']} tok | {r['tps']:.1f} tok/s", flush=True)
    for criterion, points in scores.items():
        max_pts = bench["scoring"][criterion]
        icon = "+" if points == max_pts else "-" if points == 0 else "~"
        print(f"    {icon} {criterion}: {points}/{max_pts}", flush=True)
    return {"name": bench["name"], "status": status, "score": total_pts, "max_score": possible,
            "pct": round(total_pts / possible * 100, 1), "scores": scores,
            "time": round(elapsed, 1), "tokens": r["tokens"], "tps": round(r["tps"], 2),
            "finish_reason": r["finish"], "error": error[:500] if error else None,
            "response_len": len(r["response"]), "code_len": len(code)}


def run_suite(args, url, benches, out_path, run_label):
    print(f"=== {run_label} ===\n{len(benches)} tasks, temperature="
          f"{'server default' if args.temperature is None else args.temperature}, "
          f"max_tokens={args.max_tokens or 'none'}", flush=True)
    results = [run_one(args, url, b, i + 1, len(benches)) for i, b in enumerate(benches)]
    # INCONCLUSIVE / API_ERROR tasks are excluded from the score, NOT counted as zero --
    # a harness limit is not a model failure.
    scored = [r for r in results if r["score"] is not None
              and not str(r["status"]).startswith("INCONCLUSIVE")]
    inconclusive = [r["name"] for r in results if r not in scored]
    total = sum(r["score"] for r in scored)
    possible = sum(r["max_score"] for r in scored)
    summary = {
        "display": run_label, "server": url, "model": args.model, "suite": args.suite,
        "temperature": args.temperature, "max_tokens": args.max_tokens,
        "runner": "run_direct.py", "mode": "direct-api",
        "total": total, "possible": possible,
        "pct": round(total / possible * 100, 1) if possible else None,
        "inconclusive": inconclusive, "scored_tasks": len(scored),
        "total_tasks": len(results), "results": results,
    }
    if inconclusive:
        print(f"\n!! INCONCLUSIVE (excluded, not scored 0): {inconclusive}", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    json.dump(summary, open(out_path, "w"), indent=1)
    print(f"\n=== TOTAL: {total}/{possible} ({summary['pct']}%) over {len(scored)}/"
          f"{len(results)} tasks -> {out_path}", flush=True)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base-url", default=os.environ.get("BENCH_BASE_URL", "http://127.0.0.1:8000"),
                   help="OpenAI-compatible server base URL, without /v1 (env BENCH_BASE_URL)")
    p.add_argument("--model", default=os.environ.get("BENCH_MODEL", ""),
                   help="model id to send in the request (env BENCH_MODEL)")
    p.add_argument("--display", default=None, help="label stored in the results JSON (default: model id)")
    p.add_argument("--out", default="results.json", help="results JSON path (with --runs N: <stem>_r<i>.json)")
    p.add_argument("--suite", choices=sorted(SUITES), default="v2",
                   help="which tasks: v2=1-5 (/500), tb=6-9 (/400), v4=all nine (/900), ...")
    p.add_argument("--tasks", default="", help="comma-separated name substrings to keep, e.g. 'regex,crdt'")
    p.add_argument("--runs", type=int, default=1,
                   help="repeat the suite N times and report the mean (single runs are noisy)")
    p.add_argument("--temperature", type=float, default=None,
                   help="sampling temperature; default omits the field so the server's model "
                        "default applies (historical direct runs used 0.0 -- see README)")
    p.add_argument("--max-tokens", type=int, default=None,
                   help="max_tokens for the request; default omits it (no cap)")
    p.add_argument("--timeout", type=int, default=int(os.environ.get("REQ_TIMEOUT", "2400")),
                   help="HTTP timeout per request, seconds (env REQ_TIMEOUT)")
    p.add_argument("--test-timeout", type=int, default=10, help="seconds allowed for the hidden test run")
    p.add_argument("--api-key", default=os.environ.get("BENCH_API_KEY"),
                   help="bearer token if the server needs one (env BENCH_API_KEY)")
    p.add_argument("--list-tasks", action="store_true", help="print the task list and exit")
    args = p.parse_args()

    if args.list_tasks:
        print(describe())
        return
    if not args.model:
        p.error("--model is required (or set BENCH_MODEL)")
    args.display = args.display or args.model
    url = args.base_url.rstrip("/") + "/v1/chat/completions"
    benches = select_tasks(args.suite, args.tasks)
    if not benches:
        p.error(f"no tasks matched --suite {args.suite} --tasks {args.tasks!r}")

    if args.runs <= 1:
        run_suite(args, url, benches, args.out, args.display)
        return
    stem, ext = os.path.splitext(args.out)
    totals = []
    for i in range(1, args.runs + 1):
        s = run_suite(args, url, benches, f"{stem}_r{i}{ext or '.json'}", f"{args.display} (r{i})")
        totals.append((s["total"], s["possible"]))
    print("\n=== RUNS: " + ", ".join(f"{t}/{q}" for t, q in totals))
    if totals:
        print(f"=== MEAN: {sum(t for t, _ in totals) / len(totals):.1f}/{totals[0][1]} over {len(totals)} runs")


if __name__ == "__main__":
    main()
