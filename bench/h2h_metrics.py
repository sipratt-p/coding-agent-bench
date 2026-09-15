#!/usr/bin/env python3
"""Head-to-head metrics: score, time-to-complete, tokens-to-complete, turns -- per model x run x task.

Joins the runner's result JSONs (score + wall time) with prime-agent session logs
($PRIME_SESSIONS, default ~/.prime/agent/sessions/*.jsonl: per-turn usage.output/usage.input,
tool calls) by work-dir + order. The session logs are local to the machine that ran the
agent and are NOT shipped in this repo, so the token/turn columns only fill in there;
the score/time columns come from results/h2h/*.json (or $H2H_DIR).
Usage:  python3 h2h_metrics.py [--md]           # table for all known tags
        python3 h2h_metrics.py --tag qwenfn_uncens_mtp4
Tokens = sum of assistant usage.output over the session (thinking + text + tool args); input = sum of usage.input
(re-read context per turn, i.e. total prompt tokens billed). Operator interventions are not marked here.
"""
import glob, json, os, sys, time

HOME = os.path.expanduser("~")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESS = os.environ.get("PRIME_SESSIONS", f"{HOME}/.prime/agent/sessions")
H2H = os.environ.get("H2H_DIR", f"{REPO}/results/h2h")
RESULTS = f"{REPO}/results"

# tag -> (results glob, workdir substring the agent ran in, driver log with "[h2h] run i/N start/end <local ts>" lines or None)
# The workdir substrings are the scratch-dir names used for the shipped results (see results/RESULTS.md).
TAGS = {
    "qwenfn_uncens_mtp4": (f"{H2H}/qwenfn_uncens_mtp4_tb_r*.json", "prime-tb-work-qwen3-8-flash-next/", f"{H2H}/qwenfn_uncens_mtp4_driver.log"),
    "dsv4_ablit":         (f"{H2H}/dsv4_ablit_tb_r*.json",         "prime-tb-work-deepseek-v4-flash-abliterated/", f"{H2H}/dsv4_ablit_driver.log"),
    "glm53_6bit":         (f"{RESULTS}/glm53mlx6bit_think32k_prime_tb.json", "flash-mlx-6bit/", None),
    "glm53_tr3":          (f"{H2H}/glm53_tr3_tb_r*.json",          "prime-tb-work-glm-5-3-flash-exl3-4bpw/", f"{H2H}/glm53_tr3_driver.log"),
    "flashnext_cosmo":    (f"{H2H}/flashnext_cosmo_tb_r*.json",    "prime-tb-work-qwen3-8-flash-next-oq4e-mtp/", f"{H2H}/flashnext_cosmo_driver.log"),
    "glm53_tr3_t8k":      (f"{H2H}/glm53_tr3_t8k_tb_r*.json",      "prime-tb-work-glm-5-3-flash-exl3-4bpw/", f"{H2H}/glm53_tr3_t8k_driver.log"),
    "flashnext_cosmo_t4k":(f"{H2H}/flashnext_cosmo_t4k_tb_r*.json","prime-tb-work-qwen3-8-flash-next-oq4e-mtp/", f"{H2H}/flashnext_cosmo_t4k_driver.log"),
    "ornith_bf16_cosmo":  (f"{H2H}/ornith_bf16_cosmo_tb_r*.json",  "prime-tb-work-ornith-35b-bf16/", f"{H2H}/ornith_bf16_cosmo_driver.log"),
}


def run_windows(driver_log):
    """[(start_utc, end_utc)] per run from the driver log (local timestamps)."""
    import re, datetime as _dt
    if not driver_log or not os.path.exists(driver_log):
        return []
    starts, ends = {}, {}
    for line in open(driver_log):
        m = re.match(r"\[h2h\] run (\d+)/\d+ (start|end)\s+(\S+ \S+)", line)
        if not m:
            continue
        t = _dt.datetime.strptime(m.group(3), "%Y-%m-%d %H:%M:%S").astimezone()  # local → aware
        (starts if m.group(2) == "start" else ends)[int(m.group(1))] = t.astimezone(_dt.timezone.utc)
    return [(starts[i], ends.get(i)) for i in sorted(starts)]


def assign_by_windows(sessions, windows):
    """Group sessions into runs by driver time windows; within a run, same-task files are merged
    (compaction continuations) unless the earlier one ended in error/abort (false start → superseded)."""
    import datetime as _dt
    runs = []
    for (w0, w1) in windows:
        cur = {}
        for start, task, f in sessions:
            try:
                t = _dt.datetime.fromisoformat(start.replace("Z", "+00:00"))
            except Exception:
                continue
            if t < w0 - _dt.timedelta(seconds=30) or (w1 and t > w1 + _dt.timedelta(seconds=30)):
                continue
            if task in cur:
                end = _ended_clean(cur[task][-1])
                if end and end[0] not in ("error", "aborted"):
                    cur[task].append(f)
                else:
                    cur[task] = [f]
            else:
                cur[task] = [f]
        runs.append(cur)
    return runs


def session_stats(paths):
    """Aggregate over one or more session files (a task compacted mid-way spans several)."""
    if isinstance(paths, str):
        paths = [paths]
    out = inp = turns = tools = 0
    first = last = None
    for path in paths:
      for line in open(path):
        try:
            d = json.loads(line)
        except Exception:
            continue
        m = d.get("message") or {}
        if m.get("role") != "assistant":
            continue
        ts = d.get("timestamp")
        first = first or ts
        last = ts or last
        u = m.get("usage") or {}
        out += int(u.get("output") or 0)
        inp += int(u.get("input") or 0)
        turns += 1
        tools += sum(1 for b in m.get("content", []) if b.get("type") == "toolCall")
    return dict(tokens_out=out, tokens_in=inp, turns=turns, tool_calls=tools, first=first, last=last)


def sessions_for(workdir_sub):
    """All sessions whose cwd contains workdir_sub, ordered by creation time, with task index."""
    found = []
    for f in glob.glob(f"{SESS}/*.jsonl"):
        try:
            head = open(f).read(4000)
        except Exception:
            continue
        if workdir_sub not in head:
            continue
        i = head.find(workdir_sub)
        tail = head[i + len(workdir_sub):i + len(workdir_sub) + 6]
        if not tail.startswith("task"):
            continue
        try:
            task = int(tail[4])
        except ValueError:
            continue
        # order by the session's FIRST event timestamp (mtime collides for adjacent tasks)
        import re
        m = re.search(r'"timestamp":"([^"]+)"', head)
        found.append((m.group(1) if m else time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(os.path.getmtime(f))), task, f))
    found.sort()
    return found


def _ended_clean(path):
    """True if the file's last assistant message ended normally (compaction continuation follows)."""
    last = None
    for line in open(path):
        try:
            d = json.loads(line)
        except Exception:
            continue
        m = d.get("message") or {}
        if m.get("role") == "assistant":
            last = (m.get("stopReason"), d.get("timestamp"))
    return last


def assign(sessions, n_runs):
    """Walk sessions in time order, grouping into runs of tasks 1..4. A repeated task number is a
    compaction continuation (merge) if the previous file ended cleanly and the new one starts within
    ~3 min; otherwise it is a false start/restart and supersedes the earlier file(s)."""
    import datetime as _dt
    def _ts(s):
        try:
            return _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    runs, cur, expected = [], {}, 1
    for start, task, f in sessions:
        if task < expected and cur:  # wrapped to a new run
            runs.append(cur); cur = {}
        if task in cur:
            prev = cur[task][-1]
            end = _ended_clean(prev)
            t0, t1 = (_ts(end[1]) if end else None), _ts(start)
            gap = (t1 - t0).total_seconds() if (t0 and t1) else 1e9
            if end and end[0] not in ("error", "aborted") and gap < 180:
                cur[task].append(f)          # compaction continuation
            else:
                cur[task] = [f]              # false start superseded
        else:
            cur[task] = [f]
        expected = task
    if cur:
        runs.append(cur)
    # false starts / killed runs leave incomplete groups: keep only complete 4-task groups,
    # then align from the START with the result files (r1, r2, ...); an in-flight run is dropped
    complete = [r for r in runs if all(t in r for t in (1, 2, 3, 4))]
    return complete[:n_runs] if n_runs else complete


def main():
    md = "--md" in sys.argv
    only = None
    if "--tag" in sys.argv:
        only = sys.argv[sys.argv.index("--tag") + 1]
    rows = []
    for tag, (rglob, wsub, dlog) in TAGS.items():
        if only and tag != only:
            continue
        results = sorted(glob.glob(rglob))
        if not results:
            continue
        wins = run_windows(dlog)
        runs_sessions = assign_by_windows(sessions_for(wsub), wins) if wins else assign(sessions_for(wsub), len(results))
        for ri, rf in enumerate(results):
            data = json.load(open(rf))
            tasks = data.get("results") or data.get("tasks") or data
            if isinstance(tasks, dict) and "results" in tasks:
                tasks = tasks["results"]
            sess = runs_sessions[ri] if ri < len(runs_sessions) else {}
            for ti, t in enumerate(tasks, 1):
                st = session_stats(sess[ti]) if ti in sess else {}
                rows.append(dict(model=tag, run=os.path.basename(rf).split("_tb_")[-1].replace(".json", ""),
                                 task=t.get("name", "?")[:28], score=t.get("score"), max=t.get("max_score"),
                                 status=t.get("status"), time_s=t.get("time"), **{k: st.get(k) for k in ("tokens_out", "tokens_in", "turns", "tool_calls")}))
    if not rows:
        print("no results found"); return
    hdr = ["model", "run", "task", "score", "status", "time_s", "tokens_out", "tokens_in", "turns", "tool_calls"]
    if md:
        print("| " + " | ".join(hdr) + " |"); print("|" + "---|" * len(hdr))
        for r in rows:
            print("| " + " | ".join(str(r.get(h, "")) for h in hdr) + " |")
    else:
        print("%-20s %-3s %-28s %5s %-8s %8s %10s %10s %5s %5s" % tuple(hdr))
        for r in rows:
            print("%-20s %-3s %-28s %5s %-8s %8s %10s %10s %5s %5s" % (r["model"][:20], r["run"], r["task"], r["score"], str(r["status"])[:8], r["time_s"], r["tokens_out"], r["tokens_in"], r["turns"], r["tool_calls"]))
    # per-run totals
    print()
    from collections import defaultdict
    tot = defaultdict(lambda: dict(score=0, time=0.0, tok=0, turns=0, n=0))
    for r in rows:
        k = (r["model"], r["run"]); a = tot[k]
        a["score"] += r["score"] or 0; a["time"] += r["time_s"] or 0; a["tok"] += r["tokens_out"] or 0; a["turns"] += r["turns"] or 0; a["n"] += 1
    print("%-20s %-3s %9s %10s %12s %6s  %s" % ("model", "run", "score/400", "wall_min", "tokens_out", "turns", "tokens per point"))
    for (m, run), a in tot.items():
        pts = a["score"] or 1
        print("%-20s %-3s %9s %10.1f %12s %6s  %.0f" % (m[:20], run, a["score"], a["time"] / 60, a["tok"], a["turns"], a["tok"] / pts))


if __name__ == "__main__":
    main()
