"""Hidden grader for talentmatch (Round 3). Usage: python3 grade3.py <arena_dir> [port]"""
import json, os, socket, subprocess, sys, time, urllib.request, urllib.error

ARENA = os.path.abspath(sys.argv[1])
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8871
APP = os.path.join(ARENA, "app.py")
BASE = f"http://127.0.0.1:{PORT}"
results = []


def check(name, cond, note=""):
    results.append((name, bool(cond), note))
    print(("PASS " if cond else "FAIL "), name, ("— " + str(note)[:160] if note and not cond else ""))


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except Exception:
            return e.code, None
    except Exception as e:
        return 0, str(e)


def rawget(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)


if not os.path.exists(APP):
    print("FAIL  app_exists — no app.py")
    print("\nSCORE 0/20")
    sys.exit(0)

proc = subprocess.Popen([sys.executable, APP, "--port", str(PORT)], cwd=ARENA,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
up = False
for _ in range(50):
    try:
        socket.create_connection(("127.0.0.1", PORT), timeout=0.5).close()
        up = True
        break
    except OSError:
        time.sleep(0.2)
check("server_starts", up)
if not up:
    proc.kill()
    print("\nSCORE 0/20")
    sys.exit(0)

try:
    # jobs
    s, j1 = req("POST", "/api/jobs", {"title": "ML Engineer",
        "required_skills": ["Python", "PyTorch", "SQL"], "nice_to_have": ["Docker", "AWS"]})
    check("job_create_201", s == 201 and j1 and j1.get("id") == 1, (s, j1))
    s, j2 = req("POST", "/api/jobs", {"title": "Recruiter",
        "required_skills": ["sourcing", "ATS", "python"]})  # overlap taxonomy + default nice
    check("job_default_nice", s == 201 and j2.get("nice_to_have") == [], (s, j2))
    s, e = req("POST", "/api/jobs", {"title": "", "required_skills": ["x"]})
    check("job_400_empty_title", s == 400 and isinstance(e, dict) and "error" in e, (s, e))
    s, lst = req("GET", "/api/jobs")
    check("jobs_list", s == 200 and isinstance(lst, list) and len(lst) == 2, (s, lst))

    # candidates
    s, c1 = req("POST", "/api/candidates", {"name": "Ada",
        "skills": ["python", "pytorch", "docker", "PYTHON"], "years": 12})
    check("cand_create_dedup", s == 201 and c1.get("id") == 1, (s, c1))
    s, c2 = req("POST", "/api/candidates", {"name": "Bob", "skills": ["SQL", "python", "aws"], "years": 3})
    s, c3 = req("POST", "/api/candidates", {"name": "Cy", "skills": ["sql", "Python", "AWS"], "years": 3})
    check("cand_more", c2.get("id") == 2 and c3.get("id") == 3, (c2, c3))
    s, e = req("POST", "/api/candidates", {"name": "Neg", "skills": ["x"], "years": -1})
    check("cand_400_neg_years", s == 400, (s, e))

    # match: exact scoring
    s, m = req("GET", "/api/match/1")
    ok = s == 200 and isinstance(m, list) and len(m) == 3
    check("match_returns_all", ok, (s, m))
    if ok:
        # Ada: req {python,pytorch}=2*10, nice {docker}=3, years min(12,10)*0.5=5 -> 28.0
        # Bob: req {python,sql}=20, nice {aws}=3, years 1.5 -> 24.5
        # Cy: same as Bob -> 24.5, tie -> Bob (id 2) first
        top = m[0]
        check("match_top_ada", top.get("candidate_id") == 1 and abs(top.get("score", 0) - 28.0) < 0.01, top)
        check("match_matched_lists", top.get("matched_required") == ["python", "pytorch"]
              and top.get("matched_nice") == ["docker"], top)
        check("match_tiebreak", m[1].get("candidate_id") == 2 and m[2].get("candidate_id") == 3
              and abs(m[1].get("score", 0) - 24.5) < 0.01, m[1:])
    else:
        check("match_top_ada", False, "skipped")
        check("match_matched_lists", False, "skipped")
        check("match_tiebreak", False, "skipped")

    # required-vs-nice overlap: skill in both counts as required only
    s, j3 = req("POST", "/api/jobs", {"title": "Both", "required_skills": ["python"],
                                      "nice_to_have": ["python", "sql"]})
    s, m = req("GET", f"/api/match/{j3.get('id', 3)}")
    bob = next((r for r in m if r.get("candidate_id") == 2), {}) if isinstance(m, list) else {}
    # Bob: req {python}=10, nice {sql}=3, years 1.5 -> 14.5
    check("match_overlap_required_only", abs(bob.get("score", 0) - 14.5) < 0.01
          and bob.get("matched_nice") == ["sql"], bob)

    s, m404 = req("GET", "/api/match/999")
    check("match_404", s == 404 and isinstance(m404, dict) and "error" in m404, (s, m404))

    # resume parsing against live taxonomy
    s, p = req("POST", "/api/parse_resume",
               {"text": "Shipped Python services on AWS; ran the ATS. pythonic!= python skills; Sourcing pro."})
    want = ["ats", "aws", "python", "sourcing"]
    check("resume_parse", s == 200 and p.get("skills") == want, (s, p, want))
    s, e = req("POST", "/api/parse_resume", {"text": ""})
    check("resume_400_empty", s == 400, (s, e))

    # malformed body
    r = urllib.request.Request(BASE + "/api/jobs", data=b"{not json", method="POST",
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            code, body = resp.status, resp.read()
    except urllib.error.HTTPError as ex:
        code, body = ex.code, ex.read()
    check("malformed_json_400", code == 400 and b"Traceback" not in body, code)

    # UI
    s, html = rawget("/")
    ids = ["job-form", "candidate-form", "job-list", "candidate-list", "match-select", "match-table"]
    missing = [i for i in ids if i not in html]
    check("ui_page", s == 200 and len(html) > 500, (s, len(html) if isinstance(html, str) else html))
    check("ui_element_ids", not missing, missing)
    check("ui_selfcontained", "http://" not in html.replace(f"http://127.0.0.1", "")
          and "https://" not in html, "external refs found")
    check("ui_uses_fetch", "fetch(" in html, "no fetch() found")

    # --help exits 0
    h = subprocess.run([sys.executable, APP, "--help"], capture_output=True, timeout=15, cwd=ARENA)
    check("help_exit0", h.returncode == 0)
finally:
    proc.kill()

score = sum(1 for _, ok, _ in results if ok)
print(f"\nSCORE {score}/{len(results)}")
