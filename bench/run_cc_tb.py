#!/usr/bin/env python3
"""Harness-assisted runner: Claude Code (`claude -p`) pointed at a local model.

Claude Code speaks the Anthropic Messages API, so a local OpenAI-compatible model
needs an Anthropic->OpenAI bridge (LiteLLM proxy works; the bridge URL goes in
$BRIDGE, default http://127.0.0.1:4001, and the bridge must route <model>).
The auth token sent to the bridge is a dummy string -- the bridge is local.

Each task runs headless in a fresh scratch directory with permissions skipped;
the solution.py the agent writes is scored with the same hidden tests as the
direct-API runner. Output caps are raised for local reasoning models via
CC_MAX_OUTPUT_TOKENS / CC_MAX_THINKING_TOKENS.

Example:
  python bench/run_cc_tb.py --display "my-model via Claude Code" \
      --out results/my-model_cc_tb.json --model my-model
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness_common import (TASK_SUFFIX, common_parser, finish, fresh_workdir,  # noqa: E402
                            now, pick_tasks, score_workdir)

BRIDGE = os.environ.get("BRIDGE", "http://127.0.0.1:4001")


def run_one(args, bench, idx, total):
    print(f"\n[{idx}/{total}] {bench['name']}...", flush=True)
    work = fresh_workdir(args.work_root, "cc-" + args.model, idx)
    prompt = bench["prompt"] + TASK_SUFFIX
    env = dict(os.environ,
               ANTHROPIC_BASE_URL=BRIDGE,
               ANTHROPIC_AUTH_TOKEN="bench",   # dummy; the local bridge ignores it
               ANTHROPIC_API_KEY="bench",
               ANTHROPIC_MODEL=args.model,
               ANTHROPIC_SMALL_FAST_MODEL=args.model,
               # local reasoning models overthink -- never let the harness cap them
               CLAUDE_CODE_MAX_OUTPUT_TOKENS=os.environ.get("CC_MAX_OUTPUT_TOKENS", "128000"),
               MAX_THINKING_TOKENS=os.environ.get("CC_MAX_THINKING_TOKENS", "60000"),
               CLAUDE_CODE_USE_BEDROCK="", CLAUDECODE="")
    t0 = now()
    timed_out = False
    stdout = ""
    try:
        r = subprocess.run(
            ["claude", "-p", prompt, "--model", args.model, "--dangerously-skip-permissions"],
            cwd=work, env=env, capture_output=True, text=True, timeout=args.task_timeout)
        stdout = r.stdout + "\n" + r.stderr[-2000:]
    except subprocess.TimeoutExpired as e:
        stdout = str(e.stdout or "")
        timed_out = True
        print("  TIMEOUT", flush=True)
    elapsed = now() - t0
    return score_workdir(bench, work, stdout, elapsed, timed_out, args.display, args.task_timeout)


def main():
    p = common_parser(__doc__, default_timeout="5400")
    p.add_argument("--model", required=True, help="model id routed by the bridge")
    args = p.parse_args()
    benches = pick_tasks(p, args)
    print(f"=== {args.display} ===\n{len(benches)} tasks, model={args.model}, "
          f"bridge={BRIDGE}, timeout {args.task_timeout}s each", flush=True)
    results = [run_one(args, b, i + 1, len(benches)) for i, b in enumerate(benches)]
    finish(args, results, {"harness": "claude-code", "bridge": BRIDGE, "model": args.model})


if __name__ == "__main__":
    main()
