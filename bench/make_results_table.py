#!/usr/bin/env python3
"""Generate results/RESULTS.md from the JSON files under results/.

Handles the three result schemas found in the archive:
  * runner schema  : {display, total, possible, results:[{name, score, max_score, status,...}], harness?, ...}
  * April-2026     : {display, total_score, max_score, results:[...]}
  * dict-of-lists  : {"<display>": [ {name, score, max_score, ...}, ... ], ...}
Dates come from results/MANIFEST.json (the original files' modification dates,
recorded when the archive was curated) and fall back to the file mtime.
Repeated runs of one configuration (files differing only by _r<N>/_rep<N>) are
collapsed into one row that reports the mean and every individual run.
"""
import collections
import glob
import json
import os
import re
import statistics
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(REPO, "results")
OUT = os.path.join(RES, "RESULTS.md")

V2 = {"LRU Cache Implementation", "Async Rate Limiter", "Recursive Descent Parser",
      "Trie with Autocomplete", "Event Emitter with Typed Events"}
V3X = {"POSIX Regex Engine (leftmost-longest)", "Convergent Replicated Text (CRDT)"}
V4X = {"Async DAG Orchestrator (cancellation semantics)", "Chunk-Split Streaming JSON Parser"}
STACKS = [("vllm", "vLLM"), ("sglang", "SGLang"), ("llama.cpp", "llama.cpp"), ("llama-server", "llama.cpp"),
          ("omlx", "oMLX"), ("mtplx", "MTPLX"), ("mlx", "MLX"), ("exl3", "EXL3"), ("tr3", "EXL3"),
          ("dspark", "DSpark"), ("(api)", "hosted API")]

manifest = {}
if os.path.exists(os.path.join(RES, "MANIFEST.json")):
    manifest = json.load(open(os.path.join(RES, "MANIFEST.json")))


def date_of(rel, path):
    d = manifest.get(rel, {}).get("date")
    return d or time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(path)))


def suite_label(names):
    s = set(names)
    if s == V2:
        return "v2 core (tasks 1-5, /500)"
    if s == V3X | V4X:
        return "tiebreakers (tasks 6-9, /400)"
    if s == V3X:
        return "v3 extras (tasks 6-7, /200)"
    if s == V4X:
        return "v4 extras (tasks 8-9, /200)"
    if len(s) == 1:
        return "single task: " + next(iter(s))
    return f"custom ({len(s)} tasks)"


def stack_of(display):
    d = display.lower()
    found = []
    for key, label in STACKS:
        if key in d and label not in found:
            found.append(label)
    if "MLX" in found and ("MTPLX" in found or "oMLX" in found):
        found.remove("MLX")
    return " + ".join(found) if found else "n/a (not recorded)"


def norm(d, rel, path):
    rs = [r for r in d.get("results", []) if isinstance(r, dict)]
    names = [r.get("name", "?") for r in rs]
    total, possible = d.get("total", d.get("total_score")), d.get("possible", d.get("max_score"))
    computed = False
    if total is None or possible is None:
        total = sum(r.get("score") or 0 for r in rs)
        possible = sum(r.get("max_score") or 0 for r in rs)
        computed = True
    inconc = [r["name"] for r in rs if str(r.get("status", "")).startswith("INCONCLUSIVE") or r.get("score") is None]
    nosol = [r["name"] for r in rs if r.get("wrote_solution_py") is False and not (r.get("code_len") or 0)]
    errs = [r["name"] for r in rs if r.get("status") == "API_ERROR"]
    harness = d.get("harness")
    return dict(rel=rel, display=d.get("display") or os.path.basename(rel), total=total, possible=possible,
                n=len(rs), names=names, inconc=inconc, nosol=nosol, errs=errs, harness=harness,
                mode="harness-assisted" if harness else "direct API", computed=computed,
                date=date_of(rel, path), stack=stack_of(d.get("display") or ""),
                max_tokens=d.get("max_tokens"), suite=suite_label(names))


def load_all():
    recs = []
    for path in sorted(glob.glob(os.path.join(RES, "*.json")) + glob.glob(os.path.join(RES, "h2h", "*.json"))):
        rel = os.path.relpath(path, RES)
        if rel == "MANIFEST.json":
            continue
        d = json.load(open(path))
        if isinstance(d, dict) and isinstance(d.get("results"), list):
            recs.append(norm(d, rel, path))
        elif isinstance(d, dict):
            for k, v in d.items():
                if isinstance(v, list):
                    recs.append(norm({"display": k, "results": v}, rel, path))
    return recs


def group_key(rel):
    return re.sub(r"(_rep\d+|_r\d+)(?=\.json$)", "", rel)


def strip_run(display):
    return re.sub(r"\s*\((r|REPEAT)\d+\)\s*$", "", display).replace(" REPEAT2", "")


def pct(t, p):
    return f"{100.0 * t / p:.1f}%" if p else "n/a"


def notes_for(r):
    n = []
    if r["computed"]:
        n.append("total = sum of task rows (file has no total)")
    if r["inconc"]:
        n.append(f"INCONCLUSIVE excluded: {', '.join(r['inconc'])}")
    if r["errs"]:
        n.append(f"API_ERROR scored 0 (legacy runner): {', '.join(r['errs'])}")
    if r["nosol"]:
        n.append(f"no solution.py written ({len(r['nosol'])} task{'s' if len(r['nosol']) > 1 else ''}; scored as empty)")
    if r["max_tokens"]:
        n.append(f"max_tokens cap {r['max_tokens']}")
    if r["n"] == 1:
        n.append("partial run (1 task)")
    return "; ".join(n)


def row(recs):
    """One markdown row for a single record or a group of repeated runs."""
    first = recs[0]
    if len(recs) == 1:
        r = first
        score = f"**{r['total']}/{r['possible']}** ({pct(r['total'], r['possible'])})"
        runs, date, notes = "1", r["date"], notes_for(r)
    else:
        recs = sorted(recs, key=lambda r: r["rel"])
        poss = {r["possible"] for r in recs}
        totals = [r["total"] for r in recs]
        mean = statistics.mean(totals)
        p = recs[0]["possible"] if len(poss) == 1 else None
        score = (f"**mean {mean:.1f}/{p}** ({pct(mean, p)}); runs: " if p else f"**mean {mean:.1f}**; runs: ") + \
                ", ".join(f"{r['total']}/{r['possible']}" for r in recs)
        runs = str(len(recs))
        date = max(r["date"] for r in recs)
        notes = "; ".join(f"r{i + 1}: {notes_for(r)}" for i, r in enumerate(recs) if notes_for(r))
    display = strip_run(first["display"])
    engine = first["harness"] if first["harness"] else first["stack"]
    files = ", ".join(f"`{r['rel']}`" for r in recs)
    return f"| {display} | {score} | {runs} | {date} | {engine} | {notes or '—'} | {files} |"


def section(title, recs, blurb=""):
    out = [f"### {title}", ""]
    if blurb:
        out += [blurb, ""]
    if not recs:
        out += ["_none_", ""]
        return out
    out += ["| Model / configuration | Score | Runs | Date | Engine / harness | Notes | File(s) |",
            "|---|---|---|---|---|---|---|"]
    groups = collections.OrderedDict()
    for r in recs:
        groups.setdefault((group_key(r["rel"]), strip_run(r["display"])), []).append(r)
    rows = []
    for g in groups.values():
        key = statistics.mean(100.0 * r["total"] / r["possible"] if r["possible"] else 0 for r in g)
        rows.append((key, row(g)))
    out += [t for _, t in sorted(rows, key=lambda x: -x[0])]
    return out + [""]


def arena_section():
    out = ["## Agent-harness arena (round 4, `arena/`)", "",
           "Round 4 (TalentSearch: boolean query language + indexes over a 150k-candidate pool + UI) was graded on "
           "three axes: a hidden functional/perf suite (`arena/grade4.py`, /32), and a frontend + backend craft "
           "rubric judged from screenshots and code by an LLM (`arena/judge4.py`, /50 each). All entries drove the "
           "same local DeepSeek V4-Flash except the Qwen row; `ref` is the reference implementation.", "",
           "| Arena dir | Frontend /50 | Backend /50 | Judge total /100 | Functional /32 | File |",
           "|---|---|---|---|---|---|"]
    func = {}
    for p in glob.glob(os.path.join(RES, "arena", "grade4_*.txt")):
        m = re.search(r"SCORE (\d+)/(\d+)", open(p).read())
        if m:
            func[os.path.basename(p).replace("grade4_", "").replace(".txt", "")] = f"{m.group(1)}/{m.group(2)}"
    for p in sorted(glob.glob(os.path.join(RES, "arena", "judge4_*.json"))):
        d = json.load(open(p))
        name = os.path.basename(p).replace("judge4_", "").replace(".json", "")
        fe, be = sum(d["frontend"].values()), sum(d["backend"].values())
        out.append(f"| {name} | {fe} | {be} | **{fe + be}** | {func.get(name, 'not in repo (see README)')} | `arena/{os.path.basename(p)}` |")
    return out + ["", "Screenshots the judge looked at are not included (they live in the arena work dirs, which were excluded).", ""]


def perf_section():
    out = ["## Serving-performance probes (`results/perf/`)", "",
           "Raw throughput/latency probes (decode tok/s, prefill, concurrency sweeps) produced by `bench/perf/`. "
           "They are not scored; listed for completeness.", "", "| File | Model field | Date |", "|---|---|---|"]
    for p in sorted(glob.glob(os.path.join(RES, "perf", "*.json"))):
        rel = os.path.relpath(p, RES)
        d = json.load(open(p))
        out.append(f"| `{rel}` | {d.get('model') or d.get('display') or 'n/a'} | {date_of(rel, p)} |")
    return out + [""]


def main():
    recs = load_all()
    direct = [r for r in recs if r["mode"] == "direct API"]
    harn = [r for r in recs if r["mode"] == "harness-assisted"]
    is_v2 = lambda r: r["suite"].startswith("v2 core")
    lines = ["# Results", "",
             f"Generated by `bench/make_results_table.py` from {len(recs)} result records in `results/`. "
             "Scores are `points/possible` as written by the runner. **Direct-API rows and harness-assisted rows "
             "are separate experiments and must not be compared with each other**, and a /500 v2 total is not "
             "comparable with a /400 tiebreaker total. Every row is a single run unless the Runs column says "
             "otherwise; single runs of the tiebreakers are noisy (see README Findings).", "",
             "Legend: **Date** = modification date of the original result file (from `MANIFEST.json`). "
             "**Engine / harness** = serving stack parsed from the run's display string for direct-API rows "
             "(`n/a` when it was not recorded), or the agent harness for harness-assisted rows. "
             "**INCONCLUSIVE** tasks (timeouts / token caps) are excluded from that row's total by the newer "
             "runners; older files scored API errors as 0 and are flagged. Display strings mention the machine "
             "the server ran on (Beast = 2x RTX PRO 6000 Linux box, Cosmo/Sentry = Mac Studio M3/M4 Ultra) and, "
             "for local models, the quantisation.", ""]
    lines += ["## Direct API (one prompt, one answer, no tools)", ""]
    lines += section("v2 core suite (/500)", [r for r in direct if is_v2(r)])
    lines += section("Tiebreakers and extras (tasks 6-9)", [r for r in direct if not is_v2(r)],
                     "Historical direct-API tiebreaker runs were taken at temperature 0 with the legacy extractor; "
                     "treat them as lower bounds.")
    lines += ["## Harness-assisted (agent can run and test its code)", ""]
    lines += section("v2 core suite (/500)", [r for r in harn if is_v2(r)])
    lines += section("Tiebreakers (/400) and partial runs", [r for r in harn if not is_v2(r)],
                     "Rows with Runs = 3 are the head-to-head repeats (`bench/h2h_repeat.sh`); the mean is the "
                     "number to quote.")
    lines += arena_section()
    lines += perf_section()
    open(OUT, "w").write("\n".join(lines))
    print(f"wrote {OUT}: {len(recs)} records")


if __name__ == "__main__":
    main()
