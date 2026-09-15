#!/usr/bin/env python3
"""Shared alerting for the bench harnesses.

Rule: a task that dies on a TIMEOUT or a MAX-TOKENS cap is NOT a model
failure -- it is an inconclusive run caused by harness limits. Never score it
as FAIL. Mark it INCONCLUSIVE, raise an alert, and let the operator decide
(raise the cap / rerun / accept).

Alerts are appended to $BENCH_ALERTS_DIR/ALERTS.md and ALERTS_LATEST.json
(default: the current working directory).
"""
import datetime
import json
import os

ALERTS_DIR = os.environ.get("BENCH_ALERTS_DIR", ".")
ALERTS = os.path.join(ALERTS_DIR, "ALERTS.md")
LATEST = os.path.join(ALERTS_DIR, "ALERTS_LATEST.json")


def alert(kind, run, task, detail):
    """kind: 'timeout' | 'max_tokens' | other harness-limit reason."""
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    line = f"- **{ts}** `{kind}` — run *{run}*, task *{task}* — {detail}\n"
    os.makedirs(ALERTS_DIR, exist_ok=True)
    with open(ALERTS, "a") as f:
        f.write(line)
    payload = {"ts": ts, "kind": kind, "run": run, "task": task, "detail": detail}
    prev = []
    if os.path.exists(LATEST):
        try:
            prev = json.load(open(LATEST))
        except Exception:
            prev = []
    prev.append(payload)
    json.dump(prev[-50:], open(LATEST, "w"), indent=1)
    # loud marker so it's unmissable in the log tail
    print("\n" + "!" * 68, flush=True)
    print(f"!! HARNESS-LIMIT ALERT ({kind}) — INCONCLUSIVE, NOT A MODEL FAILURE", flush=True)
    print(f"!! run={run}  task={task}", flush=True)
    print(f"!! {detail}", flush=True)
    print("!" * 68 + "\n", flush=True)
