#!/usr/bin/env python3
"""Quality judge for talentsearch (Round 4): drives the app in headless Chrome,
captures screenshots (results / breakdown / error states), then scores frontend
+ backend rubrics with claude-opus-4-6 (vision). Run with ~/ml-env/bin/python.

Usage: judge4.py <arena_dir> [port] [--out results.json]
Needs: ANTHROPIC_API_KEY. Chrome is launched fresh on a private debug port and
torn down with verification (headless-Chrome GPU-leak trap, 2026-08-15).
"""
import base64, json, os, signal, socket, subprocess, sys, time
import urllib.request
import websocket  # websocket-client

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ts_oracle as O

ARENA = os.path.abspath(sys.argv[1])
PORT = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 8895
OUT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(ARENA, "judge4_results.json")
DEBUG_PORT = 9333
SHOTS = os.path.join(ARENA, "judge_shots")
os.makedirs(SHOTS, exist_ok=True)


def wait_port(port, timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
            return True
        except OSError:
            time.sleep(0.2)
    return False


def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method,
                               headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=120) as resp:
        return json.loads(resp.read())


class CDP:
    def __init__(self, debug_port):
        v = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json/version", timeout=5).read())
        self.browser = websocket.create_connection(v["webSocketDebuggerUrl"], timeout=30)
        self.mid = 0
        tid = self.cmd("Target.createTarget", url="about:blank")["targetId"]
        self.sid = self.cmd("Target.attachToTarget", targetId=tid, flatten=True)["sessionId"]

    def cmd(self, method, session=True, **params):
        self.mid += 1
        msg = {"id": self.mid, "method": method, "params": params}
        if session and getattr(self, "sid", None):
            msg["sessionId"] = self.sid
        self.browser.send(json.dumps(msg))
        while True:
            r = json.loads(self.browser.recv())
            if r.get("id") == self.mid:
                if "error" in r:
                    raise RuntimeError(f"{method}: {r['error']}")
                return r.get("result", {})

    def js(self, expr):
        r = self.cmd("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value")

    def goto(self, url, timeout=10):
        self.cmd("Page.navigate", url=url)
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.js("document.readyState") == "complete":
                return True
            time.sleep(0.3)
        return False

    def shot(self, path):
        data = self.cmd("Page.captureScreenshot", format="png")["data"]
        open(path, "wb").write(base64.b64decode(data))
        return path


def main():
    app_proc = subprocess.Popen([sys.executable, os.path.join(ARENA, "app.py"), "--port", str(PORT)],
                                cwd=ARENA, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome = None
    shots, ui_notes = {}, []
    try:
        assert wait_port(PORT), "app did not start"
        api("POST", "/api/candidates/bulk", O.gen_pool(500, seed=99))

        chrome = subprocess.Popen(
            ["google-chrome", "--headless=new", "--remote-allow-origins=*",
             f"--remote-debugging-port={DEBUG_PORT}",
             f"--user-data-dir={SHOTS}/.chrome-profile", "--no-sandbox",
             "--disable-dev-shm-usage", "--enable-unsafe-swiftshader",
             "--window-size=1500,950", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        assert wait_port(DEBUG_PORT), "chrome debug port never opened"
        c = CDP(DEBUG_PORT)

        loaded = c.goto(f"http://127.0.0.1:{PORT}/", timeout=6)
        ui_notes.append(f"load_event_within_6s={loaded}")
        time.sleep(1.5)

        # results state
        c.js("document.getElementById('search-input').value='skill:python>=3 location:berlin'")
        c.js("document.getElementById('search-button').click()")
        time.sleep(2.5)
        rows = c.js("document.querySelectorAll('#results-table tr').length")
        ui_notes.append(f"result_rows_rendered={rows}")
        shots["results"] = c.shot(f"{SHOTS}/results.png")

        # breakdown state (click first row)
        c.js("(document.querySelector('#results-table tbody tr')||{click(){}}).click()")
        time.sleep(1.0)
        shots["breakdown"] = c.shot(f"{SHOTS}/breakdown.png")

        # error state
        c.js("document.getElementById('search-input').value='((skill:python'")
        c.js("document.getElementById('search-button').click()")
        time.sleep(1.5)
        err_vis = c.js("(e=>e && getComputedStyle(e).display!=='none')(document.getElementById('error-state'))")
        ui_notes.append(f"error_state_visible={err_vis}")
        shots["error"] = c.shot(f"{SHOTS}/error.png")
    finally:
        if chrome:
            try:
                os.killpg(os.getpgid(chrome.pid), signal.SIGKILL)
            except Exception:
                chrome.kill()
        app_proc.kill()
    # verify chrome really died (GPU-leak trap)
    time.sleep(1)
    leftover = subprocess.run(["pgrep", "-f", f"remote-debugging-port={DEBUG_PORT}"],
                              capture_output=True, text=True).stdout.strip()
    if leftover:
        subprocess.run(["kill", "-9", *leftover.split()])

    code = open(os.path.join(ARENA, "app.py")).read()[:120_000]

    import anthropic
    client = anthropic.Anthropic()
    content = [{"type": "text", "text": RUBRIC}]
    for label in ("results", "breakdown", "error"):
        if label in shots:
            content.append({"type": "text", "text": f"Screenshot: {label} state"})
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png",
                            "data": base64.b64encode(open(shots[label], "rb").read()).decode()}})
    content.append({"type": "text", "text": "UI probe notes: " + "; ".join(ui_notes)
                    + "\n\n=== app.py ===\n" + code})
    resp = client.messages.create(model="claude-opus-4-6", max_tokens=3000,
                                  messages=[{"role": "user", "content": content}])
    txt = "".join(b.text for b in resp.content if b.type == "text")
    start, end = txt.find("{"), txt.rfind("}")
    verdict = json.loads(txt[start:end + 1])
    verdict["ui_probe_notes"] = ui_notes
    verdict["screenshots"] = shots
    json.dump(verdict, open(OUT, "w"), indent=1)
    fe = sum(verdict["frontend"].values())
    be = sum(verdict["backend"].values())
    print(f"FRONTEND {fe}/50  BACKEND {be}/50  TOTAL {fe+be}/100 -> {OUT}")
    for side in ("frontend", "backend"):
        for k, v in verdict[side].items():
            print(f"  {side}.{k}: {v}/10")


RUBRIC = """You are judging a candidate-search web app built to a fixed spec, as a harsh
staff-level reviewer. Score TEN dimensions 0-10 each (10 = exceptional,
production-grade; 5 = competent but unremarkable; 2 = careless). Judge the
FRONTEND from the screenshots (plus the UI probe notes), and the BACKEND from
the code. Do not reward mere correctness — that is graded elsewhere; you are
judging craft.

frontend dimensions:
- hierarchy: visual hierarchy and layout clarity (search vs results vs facets)
- typography: type scale, spacing, alignment, density
- polish: color system, affordances, microdetails (chips, hover, states)
- states: quality of empty/error/breakdown states as DESIGNED moments
- product_feel: would a recruiter trust and enjoy this screen?

backend dimensions:
- structure: separation of parsing / indexing / scoring / HTTP; naming
- indexing: real index design vs per-query rescans; appropriate structures
- efficiency: algorithmic choices at 150k scale (sort, sets, caching)
- robustness: input validation, error paths, edge handling
- readability: could a new engineer extend this safely?

Return ONLY a JSON object:
{"frontend": {"hierarchy": n, "typography": n, "polish": n, "states": n,
"product_feel": n}, "backend": {"structure": n, "indexing": n, "efficiency": n,
"robustness": n, "readability": n}, "notes": "<3-6 sentences, most important
strengths and flaws>"}"""


if __name__ == "__main__":
    main()
