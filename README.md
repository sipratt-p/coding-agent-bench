# coding-agent-bench

A small, self-contained coding benchmark for LLMs and coding agents, plus the
results and the harness lessons from running it against ~40 local and hosted
model/engine/harness configurations between April and September 2026.

It was built to answer one practical question — *which locally served model
should be the daily driver on a two-GPU workstation and a pair of Mac Studios?* —
and it kept finding that the **harness** (extractor, sampling, caps, single
runs) moved scores more than the models did. Those lessons are the most useful
part of this repo; they are in [Findings](#findings).

## What it measures

Nine Python implementation tasks in the style of Terminal-Bench, each worth 100
points ([tasks/TASKS.md](tasks/TASKS.md) has every prompt, rubric and hidden test):

| # | Task | Suite |
|---|---|---|
| 1 | LRU cache with O(1) get/put | v2 |
| 2 | asyncio token-bucket rate limiter | v2 |
| 3 | recursive-descent expression evaluator | v2 |
| 4 | trie with autocomplete and delete | v2 |
| 5 | typed event emitter | v2 |
| 6 | POSIX leftmost-longest regex engine with a catastrophic-pattern perf gate | tiebreaker |
| 7 | RGA text CRDT under out-of-order and duplicate delivery | tiebreaker |
| 8 | async DAG orchestrator with real concurrency and cancellation semantics | tiebreaker |
| 9 | streaming JSON parser that survives a chunk split at every byte | tiebreaker |

Tasks 1-5 (`--suite v2`, /500) saturate for good models (478-495); tasks 6-9
(`--suite tb`, /400) were added to separate them and rarely pass in one shot.

**Scoring.** The model's answer is extracted, the task's hidden test program is
appended and executed in a subprocess, and each functional criterion is awarded
from the test groups that passed. A `code_quality` heuristic (15-25 points,
inspected from the text — functions, type hints, docstrings, size, no TODOs) is
scored separately and never requires running the code. Timeouts and token-cap
truncations are marked `INCONCLUSIVE` and excluded, not scored 0.

**Two modes, not comparable with each other.**

* **Direct API** (`bench/run_direct.py`): one prompt, one answer, no tools. The
  model never sees the tests.
* **Harness-assisted** (`bench/run_prime_tb.py`, `bench/run_cc_tb.py`): a coding
  agent (Prime Agent, Claude Code, …) gets the same prompt in a scratch
  directory, can write and run its own tests, and its `solution.py` is scored
  with the same hidden tests.

Every results table labels which mode a row came from. Direct-API rows also
used temperature 0 historically while agent harnesses sampled at the server
default, so the two differ in sampling as well as tooling.

There is also an **agent-harness arena** ([arena/](arena/README.md)): four
larger spec-driven rounds (voxel file tools, a Flask app, a search engine with
hard latency gates and an LLM-judged UI rubric) where the *same model* is driven
by different harnesses.

## Running it

Requirements: Python 3.10+ and an OpenAI-compatible `/v1/chat/completions`
endpoint. The benchmark itself is standard library only (`requirements.txt`
lists the optional extras for charts and the arena).

```bash
git clone https://github.com/sipratt-p/coding-agent-bench && cd coding-agent-bench
python3 tasks/validate_refs.py                 # graders pass on the reference solutions
python3 bench/run_direct.py --list-tasks

# direct API, the five core tasks, three runs, mean printed at the end
python3 bench/run_direct.py --base-url http://127.0.0.1:8000 --model my-model \
    --suite v2 --runs 3 --out results/local/my-model_v2.json

# hosted endpoint, the four tiebreakers, explicit temperature
python3 bench/run_direct.py --base-url https://api.example.com --api-key "$KEY" \
    --model some-model --suite tb --temperature 1.0 --out results/local/some-model_tb.json

python3 bench/make_results_table.py            # regenerate results/RESULTS.md
```

`run_direct.py` sends no `temperature` and no `max_tokens` unless you pass
them, so the server's model defaults apply and nothing is truncated. Set
`REQ_TIMEOUT` (seconds, default 2400) for slow models. `--tasks regex,crdt`
filters by name; `--suite v4` runs all nine.

Harness-assisted runs need the agent installed and pointed at your endpoint:

```bash
# Prime Agent: a provider configured for your server in prime-agent's models file
TASK_TIMEOUT=604800 python3 bench/run_prime_tb.py --display "my-model via Prime (r1)" \
    --out results/local/my-model_tb_r1.json --provider my-provider --model my-model
bench/h2h_repeat.sh my-model my-provider my-model "my-model via Prime" 3   # three sequential runs

# Claude Code against a local model needs an Anthropic->OpenAI bridge (e.g. a LiteLLM proxy
# with a route named <model>) at $BRIDGE (default http://127.0.0.1:4001)
python3 bench/run_cc_tb.py --display "my-model via Claude Code" --out results/local/my-model_cc.json --model my-model
```

`bench/bench_alert.py` writes `ALERTS.md` / `ALERTS_LATEST.json` in the working
directory whenever a task hits a timeout or a token cap; read them before
quoting a score. `bench/h2h_metrics.py` joins the run JSONs with Prime Agent
session logs (tokens, turns, tool calls per task) when those logs are present.

## Findings

All numbers below are in [results/RESULTS.md](results/RESULTS.md) (generated from
the JSON files in `results/`) unless marked *from run notes*, which means they
were recorded in the operator's notes but the underlying files were not kept.
Dates are the original result files' modification dates. Every row is a single
run unless stated; see lesson 3 before reading a single run as a ranking.

### Measured results (headline)

**Direct API, five core tasks (/500).** The good local models tie within noise
of a frontier hosted model: Ornith-1.5-35B-A3B 489 (vLLM bf16 and oMLX bf16,
identical), Qwen3.8-27B (MTPLX, Mac Studio) 483, Claude Opus 4.6 483,
Qwen3.8-Flash-Next-Uncensored FP8 475-482 (three runs, MTP on/off), Qwen3.8-27B
NVFP4 / heretic-ara on vLLM 478, DeepSeek V4-Flash 453-459 uncapped. The same
DeepSeek V4-Flash scored 376 when the request carried `max_tokens=32000`
(lesson 4). The April 2026 Mac Studio rows (MiniMax M2.7 4-bit 161, Qwen
3.6-35B-A3B 4-bit 135) were taken with the original driver's 1,500-token cap
and are not comparable with later rows; the later low end is Qwen3.6-27B FP8 on
SGLang at 293 (20k cap).

**Harness-assisted, five core tasks (/500), all DeepSeek V4-Flash builds:**
Prime Agent 495 (clean weights) / 484 (community "drowzeys" build) / 394 (one
task where the agent wrote no file), Claude Code 485, OpenClaw 483-485, the
official `dsh` 481. Against the same model's 453-459 direct-API scores that is a
+25-40 point harness effect on a suite that is already near its ceiling.

**Harness-assisted tiebreakers (/400, Prime Agent), three-run means:**

| Model (serving config) | Mean | Runs |
|---|---|---|
| Qwen3.8-Flash-Next-Uncensored FP8 + MTP (vLLM, 2 GPUs) | **380.0** | 392, 359, 389 |
| GLM-5.3-Flash EXL3 4bpw, 8k thinking budget | **372.3** | 389, 359, 369 |
| Qwen3.8-Flash-Next abliterated NVFP4 (1 GPU) | **300.3** | 274, 359, 268 |
| DeepSeek V4-Flash-Abliterated (vLLM + DSpark) | **288.7** | 287, 197, 382 |

Single-run tiebreaker rows (GLM-5.3-Flash MLX 6-bit 389, Ornith-35B bf16 297,
DeepSeek V4-Flash-Abliterated 304, Qwen3.8-27B-ablit 295, …) are in the full
table; the GLM 6-bit run also needed several operator interruptions of runaway
self-written fuzz loops (*from run notes*), so read it as capability rather than
throughput. Direct-API attempts at the same four tasks score far lower
(DeepSeek V4-Flash-Abliterated 114/400 direct vs 304 via Prime; Ornith-35B
97+79/400 direct vs 297): these tasks need iteration and self-testing.

**Quantisation and engine effects are large.** Ornith-35B at 8-bit MLX scored
211/400 on the tiebreakers where bf16 scored 297 (vLLM) and 161/200 on the two
hardest tasks (oMLX); the regex task alone went 5 → 68 with precision as the
only variable (*from run notes*). On the core suite, Qwen3.8-27B served by
llama.cpp CUDA scored 62-63/500 and by vLLM FP8 with MTP speculative decoding
193/500, while the same weights on vLLM FP8 eager-mode scored 387 and NVFP4+MTP
478 — the run notes attribute both collapses to engine bugs on that hybrid-SSM
architecture (spurious EOS on the CUDA path; FP8 draft/verify numerics with
MTP), not to the model. **Abliteration** cost nothing on one-shot coding (Qwen3.8
MTPLX abliterated 483 = control 483; Ornith "abliterated-ours v3" 489 = base
489), but the two harness-assisted DeepSeek pairs favoured the clean weights by
10-11 points (495 vs 484, 485 vs 483; single runs, suggestive only).

**Arena (agent harnesses on one model, DeepSeek V4-Flash).** Round 1 tied
15/15; round 2 (undocumented binary format with an axis trap) Prime Agent 16/16
beat opencode 14/16, which shipped a renderer with inverted occlusion it never
looked at; round 3 saturated (five perfect 22/22) and was retired (*rounds 1-3
from run notes*). Round 4 judge scores from the files: Qwen3.8 MTPLX 75/100
(best design, 18/32 functional — wrong scoring math at scale), Claude Code 71,
reference 70, OpenClaw 67, `dsh` 58 (its UI never rendered results; the
screenshot judge caught what the static checks passed). The functional scores
for the non-Qwen entries (Claude Code 32/32, OpenClaw 32/32, dsh 31/32, reference
32/32, Prime Agent did not finish twice because of a harness wedge) are *from run
notes*. Verification behaviour — did the harness test its own output — was the
separator every time the task had a testable surface.

### Harness lessons

1. **A fence-only extractor scored a correct answer 17/100.** The prompts end
   with "Output only the Python code, no explanation"; a reasoning model that
   obeys literally returns *unfenced* code. The v2 extractor found no fence,
   fell back to `reasoning + content`, and executed a half-finished draft from
   the thinking trace: a textbook LRU cache scored 17/100 and re-scored 97/100
   through a fixed extractor on the identical bytes. Because functional tests
   are scored separately from the text-only `code_quality` heuristic, the bug
   has a signature — every functional criterion 0, `code_quality` partial — and
   that is how it was found. Fix in `run_direct.py`: extract from `content`
   only (never mine the reasoning field unless content is empty), accept
   unfenced answers when they compile, and keep the functional/heuristic
   split. `run_v2_generic.py` is kept as the reproducer. Three rows in the
   table (Ornith abliterated 293 and 105, Qwen3.8-27B-ablit 295) are additionally
   understated by an agent-side variant of the same bug (no `solution.py`
   written, empty input scored as 4/100); they are flagged in the Notes column.
2. **Temperature 0 was hard-coded; the model cards said 1.0.** Every direct-API
   runner sent `temperature: 0.0` while the generation configs of every model
   tested (DeepSeek V4-Flash, Ornith-1.5, Qwen3.8-Flash-Next) specify 1.0 with
   top-p/top-k, and the agent harnesses sent no temperature at all — so the two
   modes differed in sampling by accident. At temperature 0, Qwen3.8-Flash-Next
   never terminated on 2 of the 5 core tasks (the parser task spiralled to 130k
   and then 153k tokens on separate attempts; the event emitter timed out) and
   scored 290/300 on the three that finished; the same model completed all four
   tiebreakers at the server default. `run_direct.py` now omits temperature by
   default and records what was used in the JSON. Historical direct rows are at
   0.0. Check the *server's* default too: one MLX server silently defaulted to
   0 because it read `config.json` rather than `generation_config.json`.
3. **Identical reruns scored 98 and 13.** The POSIX regex task, same model,
   same prompt, same temperature 1.0, back-to-back: 98/100 then 13/100 with
   different failure modes. Whole-suite repeats spread the same way (392/359/389;
   287/197/382). Every leaderboard row was originally one run. Report means over
   three runs (`--runs 3`, `bench/h2h_repeat.sh`) and show the individual runs.
4. **Timeouts and max-token stops are inconclusive, not failures.** An agent
   that generated exactly 65,536 tokens and stopped with `finish_reason=length`
   was recorded as 8/100 on the regex task; a Claude Code run with no output cap
   configured bailed on three of four tasks (126/400); DeepSeek V4-Flash went
   376 → 459 just by removing a 32k cap. None of that is model capability.
   `bench_alert.py` marks such tasks `INCONCLUSIVE`, excludes them from the
   total, appends to `ALERTS.md` and prints a banner; the runners omit
   `max_tokens` by default. Corollary for agent harnesses: their `maxTokens`
   plus a long tool-loop prompt must fit the server's context window, or the
   server returns HTTP 400 and the task looks like an instant failure.

Smaller lessons: a thinking budget of 4-8k tokens *improved* agentic scores for
the two reasoning models tried, because unbounded reasoning stalled turns or
overflowed context (*from run notes*); and oMLX beat vLLM on the streaming-parser
task with identical weights (93 vs 8, *from run notes*), so "which engine" is a
per-task question.

## Repository layout

```
bench/       harness code
  coding_benchmark_v2.py / v3 / v4   task definitions + scoring primitives (v4 = all nine)
  suites.py                          suite slices used by every runner
  run_direct.py                      direct-API runner (the one to use)
  run_v2_generic.py                  legacy direct runner, kept to reproduce lesson 1
  run_prime_tb.py, run_cc_tb.py      harness-assisted runners (+ harness_common.py)
  h2h_repeat.sh, h2h_metrics.py      three-run repeats and per-task token/turn metrics
  bench_alert.py                     INCONCLUSIVE alerting
  make_results_table.py              results/RESULTS.md generator
  benchmark_charts.py                April 2026 comparison charts (embedded numbers)
  perf/                              decode/prefill/concurrency probes for the perf JSONs
tasks/       TASKS.md (rendered prompts, rubrics, hidden tests), refs/ (reference solutions
             for tasks 6-9), validate_refs.py, render_tasks.py
arena/       agent-harness arena: specs, prompts, graders, LLM judge, fixtures
results/     every result JSON kept (top level = coding suite, h2h/ = three-run repeats,
             arena/ = round-4 judge verdicts, perf/ = throughput probes), MANIFEST.json
             (original dates), RESULTS.md (generated)
```

Not included: agent work directories and transcripts, server and bridge logs,
judge screenshots, the OpenClaw and `dsh` runners (they depended on a
machine-specific SSH target and a locally patched CLI profile) and the LiteLLM
bridge config (LAN addresses; any Anthropic-to-OpenAI proxy with a route named
after the model works), and one run explicitly recorded as invalid (its bridge
was down). Result files are byte-identical to the originals except that private
hostnames, IPs and home-directory paths were redacted; see
[SECRETS-CHECK.md](SECRETS-CHECK.md).

## License

MIT — see [LICENSE](LICENSE).
