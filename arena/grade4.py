"""Hidden functional+perf grader for talentsearch (Round 4).
Usage: python3 grade4.py <arena_dir> [port]
Compares the candidate app against ts_oracle on small hand-shaped data, then on
a generated 150k pool with hard latency gates.
"""
import json, os, socket, subprocess, sys, time, urllib.request, urllib.error, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ts_oracle as O

ARENA = os.path.abspath(sys.argv[1])
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8891
APP = os.path.join(ARENA, "app.py")
BASE = f"http://127.0.0.1:{PORT}"
results = []


def check(name, cond, note=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL "), name, ("— " + str(note)[:200] if note and not cond else ""), flush=True)


def req(method, path, body=None, timeout=120):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body or b"null")
        except Exception:
            return e.code, ("NONJSON", body[:200].decode("utf-8", "replace"))
    except Exception as e:
        return 0, str(e)


def rows_match(app_res, oracle_res, tol=0.01):
    a = [(r["id"], round(float(r["score"]), 2)) for r in app_res.get("results", [])]
    b = [(r["id"], round(float(r["score"]), 2)) for r in oracle_res["results"]]
    if len(a) != len(b):
        return False, f"len {len(a)} vs {len(b)}"
    for (ia, sa), (ib, sb) in zip(a, b):
        if ia != ib or abs(sa - sb) > tol:
            return False, f"first diff app=({ia},{sa}) oracle=({ib},{sb})"
    return True, ""


# hand-shaped small pool: exercises every scoring tier + tie-breaks
SMALL = [
    {"id": 1, "name": "Ada", "title": "Senior ML Engineer",
     "skills": [{"name": "Python", "years": 6}, {"name": "PyTorch", "years": 4}],
     "location": "Berlin", "remote_ok": True, "salary_expectation": 110000,
     "years_total": 9, "level": "senior", "last_active": "2026-07-20", "tags": ["open-source"]},
    {"id": 2, "name": "Bob", "title": "Python Platform Engineer",
     "skills": [{"name": "go", "years": 3}, {"name": "kubernetes", "years": 2}],
     "location": "London", "remote_ok": False, "salary_expectation": 140000,
     "years_total": 6, "level": "mid", "last_active": "2026-06-01", "tags": ["contractor"]},
    {"id": 3, "name": "Cy", "title": "Machine Learning Researcher",
     "skills": [{"name": "python", "years": 12}, {"name": "machine learning", "years": 8}],
     "location": "Berlin", "remote_ok": True, "salary_expectation": 176000,
     "years_total": 12, "level": "staff", "last_active": "2025-01-01", "tags": ["phd"]},
    {"id": 4, "name": "Dee", "title": "Recruiter",
     "skills": [{"name": "sourcing", "years": 4}, {"name": "ats", "years": 4},
                {"name": "ATS", "years": 7}],
     "location": "New York", "remote_ok": True, "salary_expectation": 88000,
     "years_total": 5, "level": "mid", "last_active": "2026-07-20", "tags": []},
    # 5 and 6: identical scores for "go" → tie-break by last_active desc then id
    {"id": 5, "name": "Eve", "title": "Backend Engineer",
     "skills": [{"name": "go", "years": 5}], "location": "Austin", "remote_ok": False,
     "salary_expectation": 120000, "years_total": 5, "level": "mid",
     "last_active": "2026-05-05", "tags": []},
    {"id": 6, "name": "Fay", "title": "Backend Engineer",
     "skills": [{"name": "go", "years": 5}], "location": "Austin", "remote_ok": False,
     "salary_expectation": 121000, "years_total": 5, "level": "mid",
     "last_active": "2026-05-05", "tags": []},
    {"id": 7, "name": "Gus", "title": "Backend Engineer",
     "skills": [{"name": "go", "years": 5}], "location": "Austin", "remote_ok": False,
     "salary_expectation": 122000, "years_total": 5, "level": "mid",
     "last_active": "2026-05-06", "tags": []},
]
SMALL_NORM = [O.norm_cand(c) for c in SMALL]


def oracle_search(q, page=1, page_size=20, pool=SMALL_NORM):
    return O.search(pool, q, page, page_size)


if not os.path.exists(APP):
    print("FAIL  app_exists")
    print("\nSCORE 0/0")
    sys.exit(0)

proc = subprocess.Popen([sys.executable, APP, "--port", str(PORT)], cwd=ARENA,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
up = False
t0 = time.time()
while time.time() - t0 < 12:
    try:
        socket.create_connection(("127.0.0.1", PORT), timeout=0.5).close()
        up = True
        break
    except OSError:
        time.sleep(0.2)
check("server_starts_10s", up)
if not up:
    proc.kill(); print("\nSCORE 0/28"); sys.exit(0)

try:
    h = subprocess.run([sys.executable, APP, "--help"], capture_output=True, timeout=15, cwd=ARENA)
    check("help_exit0", h.returncode == 0)

    s, r = req("POST", "/api/candidates/bulk", SMALL)
    check("bulk_small", s == 200 and r.get("ingested") == len(SMALL), (s, r))
    s, r = req("POST", "/api/candidates/bulk", [{"name": "NoId"}])
    check("bulk_reject_missing_id", s == 400 and isinstance(r, dict) and "error" in r, (s, r))
    # reingest after the rejected batch
    s, r = req("POST", "/api/candidates/bulk", SMALL)
    s, r = req("GET", "/api/candidates/3")
    check("get_candidate", s == 200 and r.get("name") == "Cy", (s, r))
    s, r = req("GET", "/api/candidates/999")
    check("get_404", s == 404 and "error" in (r or {}), (s, r))

    CASES = [
        ("term_basic", "python"),
        ("quoted_phrase", '"machine learning"'),
        ("skill_years", "skill:python>=7"),
        ("numeric_preds", "salary<=140000 years>=5"),
        ("bool_nesting", "(python OR go) AND NOT tag:contractor"),
        ("implicit_and", "location:berlin python"),
        ("case_insensitive", "LOCATION:Berlin PYTHON or GO"),
        ("dedupe_term_skill", "python skill:python python"),
        ("not_no_score", "go AND NOT python"),
        ("tie_break", "go"),
        ("salary_fit_tiers", "go salary<=150000"),
        ("remote_bonus", "python remote:true"),
    ]
    for name, q in CASES:
        s, r = req("POST", "/api/search", {"q": q})
        if s != 200:
            check(name, False, (s, r)); continue
        ok, why = rows_match(r, oracle_search(q))
        check(name, ok, f"q={q!r} {why}")

    # breakdown components
    s, r = req("POST", "/api/search", {"q": "python remote:true salary<=140000"})
    o = oracle_search("python remote:true salary<=140000")
    ok = s == 200 and r.get("results") and all(
        abs(float(r["results"][i]["breakdown"][k]) - o["results"][i]["breakdown"][k]) < 0.01
        for i in range(len(o["results"])) for k in ("skills", "title", "recency", "salary_fit", "remote"))
    check("breakdown_components", ok, (s, r.get("results", [])[:1], o["results"][:1]))

    # pagination
    s, r = req("POST", "/api/search", {"q": "go OR python", "page": 2, "page_size": 3})
    o = oracle_search("go OR python", 2, 3)
    ok, why = rows_match(r, o)
    check("pagination_slice", s == 200 and ok and r.get("total") == o["total"]
          and r.get("has_next") == o["has_next"], why)
    s, r = req("POST", "/api/search", {"q": "go", "page": 1, "page_size": 500})
    check("page_size_clamp", s == 200 and r.get("page_size") == 100, (s, r.get("page_size")))
    s, r = req("POST", "/api/search", {"q": "go", "page": 99})
    check("page_past_end", s == 200 and r.get("results") == [], (s, r))

    # parse errors carry position
    s, r = req("POST", "/api/search", {"q": "(python OR"})
    check("parse_error_400", s == 400 and isinstance(r, dict) and "error" in r
          and isinstance(r.get("position"), int), (s, r))
    s, r = req("POST", "/api/search", {"q": "bogusfield:x"})
    check("unknown_field_400", s == 400 and "error" in (r or {}), (s, r))

    # facets
    s, r = req("GET", "/api/facets?q=" + urllib.parse.quote("location:berlin"))
    o = O.facets(SMALL_NORM, "location:berlin")
    check("facets_small", s == 200 and r == o, (s, r, o))

    # malformed body
    rq = urllib.request.Request(BASE + "/api/search", data=b"{nope", method="POST",
                                headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(rq, timeout=10) as resp:
            code, body = resp.status, resp.read()
    except urllib.error.HTTPError as ex:
        code, body = ex.code, ex.read()
    check("malformed_json_400", code == 400 and b"Traceback" not in body, code)

    # ---------- scale ----------
    print("[grader] generating 150k pool...", flush=True)
    big = O.gen_pool(150_000)
    t0 = time.time()
    s, r = req("POST", "/api/candidates/bulk", big, timeout=300)
    ingest_s = time.time() - t0
    check("big_ingest_20s", s == 200 and r.get("ingested") == 150_000 and ingest_s <= 20,
          f"{ingest_s:.1f}s status={s}")

    print("[grader] big-pool correctness (oracle cross-check)...", flush=True)
    big_norm = [O.norm_cand(c) for c in big]
    ok_all = True
    for q in ["skill:python>=3 location:berlin", '(python OR "machine learning") AND salary<=180000',
              "NOT remote:true salary>=100000 skill:java"]:
        s, r = req("POST", "/api/search", {"q": q})
        o = O.search(big_norm, q)
        ok, why = rows_match(r, o)
        if s != 200 or not ok or r.get("total") != o["total"]:
            ok_all = False
            print(f"    big-pool mismatch on {q!r}: {why} total {r.get('total')} vs {o['total']}", flush=True)
    check("big_correctness", ok_all)

    print("[grader] perf batch...", flush=True)
    t0 = time.time()
    slow = []
    for q in O.PERF_QUERIES:
        tq = time.time()
        s, r = req("POST", "/api/search", {"q": q})
        if s != 200:
            slow.append((q, "HTTP " + str(s)))
        elif time.time() - tq > 2:
            slow.append((q, f"{time.time()-tq:.2f}s"))
    batch_s = time.time() - t0
    check("perf_batch_5s", batch_s <= 5 and not slow, f"{batch_s:.2f}s slow={slow[:3]}")
    t0 = time.time()
    s, r = req("GET", "/api/facets?q=" + urllib.parse.quote("remote:true"))
    check("perf_facets_2s", s == 200 and time.time() - t0 <= 2, f"{time.time()-t0:.2f}s")

    # UI static checks (dynamic/E2E + aesthetics live in judge4.py)
    with urllib.request.urlopen(BASE + "/", timeout=10) as resp:
        html = resp.read().decode("utf-8", "replace")
    ids = ["search-input", "search-button", "results-table", "pagination",
           "facet-panel", "empty-state", "error-state", "score-breakdown"]
    missing = [i for i in ids if i not in html]
    check("ui_element_ids", not missing, missing)
    check("ui_selfcontained", "https://" not in html and "fetch(" in html)
finally:
    proc.kill()

score = sum(1 for _, ok in results if ok)
print(f"\nSCORE {score}/{len(results)}")
