#!/usr/bin/env python3
"""Harness-assisted runner: Prime Agent (prime-agent CLI).

Each task runs `prime-agent --provider P --model M -p <prompt>` headless in a fresh
scratch directory; the agent can execute and self-test code. The solution.py it
writes is scored with the same hidden tests as the direct-API runner.

Requires a prime-agent install with a provider configured for your endpoint
(see the README). The binary is taken from $PRIME_AGENT_BIN or the PATH.
Sampling: no temperature is sent -- the server default applies.

Example:
  TASK_TIMEOUT=604800 python bench/run_prime_tb.py --display "my-model (r1)" \
      --out results/h2h/my-model_tb_r1.json --provider my-provider --model my-model
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness_common import (TASK_SUFFIX, common_parser, finish, fresh_workdir,  # noqa: E402
                            now, pick_tasks, score_workdir)

PRIME = os.environ.get("PRIME_AGENT_BIN", "prime-agent")


def run_one(args, bench, idx, total):
    print(f"\n[{idx}/{total}] {bench['name']}...", flush=True)
    work = fresh_workdir(args.work_root, "prime-" + args.model, idx)
    prompt = bench["prompt"] + TASK_SUFFIX
    t0 = now()
    timed_out = False
    try:
        r = subprocess.run(
            [PRIME, "--provider", args.provider, "--model", args.model, "-p", prompt],
            cwd=work, capture_output=True, text=True, timeout=args.task_timeout)
        stdout = r.stdout
    except subprocess.TimeoutExpired as e:
        stdout = (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        timed_out = True
        print("  TIMEOUT", flush=True)
    elapsed = now() - t0
    return score_workdir(bench, work, stdout, elapsed, timed_out, args.display, args.task_timeout)


def main():
    p = common_parser(__doc__, default_timeout="3600")
    p.add_argument("--provider", required=True, help="prime-agent provider name")
    p.add_argument("--model", required=True, help="model id under that provider")
    args = p.parse_args()
    benches = pick_tasks(p, args)
    print(f"=== {args.display} ===\n{len(benches)} tasks, provider={args.provider}, "
          f"model={args.model}, timeout {args.task_timeout}s each", flush=True)
    results = [run_one(args, b, i + 1, len(benches)) for i, b in enumerate(benches)]
    finish(args, results, {"harness": "prime-agent", "provider": args.provider, "model": args.model})


if __name__ == "__main__":
    main()
