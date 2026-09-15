#!/usr/bin/env python3
"""Perf probe vs an OpenAI-compatible server: warm decode, prefill, concurrency.
Usage: omlx_perf_probe.py <base_url> <model> <out_json>
Measures: warm single-stream decode (code+prose), cache-busted ~11.5K-token
prefill TTFT (2 reps), concurrency sweep C=1/2/4/8 (256-tok decodes)."""
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE, MODEL, OUT = sys.argv[1:4]
URL = BASE.rstrip("/") + "/v1/chat/completions"

WORDS = ("lighthouse harbor granite tempest lantern keeper spiral gallery beacon fog "
         "breakwater squall mooring tide crest gull cliff spray horizon shoal").split()


def call(messages, max_tokens):
    p = {"model": MODEL, "messages": messages, "temperature": 0.0, "max_tokens": max_tokens}
    req = urllib.request.Request(URL, data=json.dumps(p).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    r = json.loads(urllib.request.urlopen(req, timeout=1800).read())
    return r["usage"], time.perf_counter() - t0


results = {"model": MODEL, "base": BASE}

# warm-up / load
call([{"role": "user", "content": "say ok"}], 20)

# single-stream decode
for label, prompt in [("code_edit", "Refactor this to a list comprehension and explain: result=[]\nfor i in range(100):\n  if i%3==0: result.append(i*i)"),
                      ("prose", "Write a vivid two-paragraph description of a lighthouse in a storm.")]:
    u, dt = call([{"role": "user", "content": prompt}], 400)
    results[f"decode_{label}_tok_s"] = round(u["completion_tokens"] / dt, 1)
    print(f"decode {label}: {results[f'decode_{label}_tok_s']} tok/s", flush=True)

# cache-busted prefill: ~11.5K tokens, unique prefix each rep
prefills = []
for rep in range(2):
    filler = " ".join(WORDS[(i + rep * 7) % len(WORDS)] + str(i * 13 + rep) for i in range(8500))
    u, dt = call([{"role": "user", "content": f"Document {rep}-{time.time_ns()}: {filler}\n\nReply with just the word done."}], 5)
    tok_s = round(u["prompt_tokens"] / dt, 1)
    prefills.append({"prompt_tokens": u["prompt_tokens"], "ttft_s": round(dt, 1), "prefill_tok_s": tok_s})
    print(f"prefill rep{rep}: {u['prompt_tokens']} tok in {dt:.1f}s = {tok_s} tok/s", flush=True)
results["prefill"] = prefills

# concurrency sweep
topics = ["mergesort", "dijkstra", "bloom filters", "b-trees", "raft consensus",
          "skip lists", "consistent hashing", "LSM trees"]
sweep = []
for n in (1, 2, 4, 8):
    t0 = time.perf_counter()
    with ThreadPoolExecutor(n) as ex:
        toks = sum(u["completion_tokens"] for u, _ in ex.map(
            lambda i: call([{"role": "user", "content": f"Explain {topics[i % len(topics)]} in detail."}], 256),
            range(n)))
    dt = time.perf_counter() - t0
    row = {"c": n, "agg_tok_s": round(toks / dt, 1), "per_stream_tok_s": round(toks / dt / n, 1)}
    sweep.append(row)
    print(row, flush=True)
results["concurrency"] = sweep

json.dump(results, open(OUT, "w"), indent=1)
print(f"saved -> {OUT}", flush=True)
