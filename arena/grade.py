"""Hidden grader for voxtool. Usage: python3 grade.py <arena_dir>"""
import json, os, struct, subprocess, sys, tempfile

ARENA = os.path.abspath(sys.argv[1])
TOOL = os.path.join(ARENA, "voxtool.py")
FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
results = []


def run(*args, timeout=120):
    return subprocess.run([sys.executable, TOOL, *args], capture_output=True,
                          text=True, timeout=timeout, cwd=ARENA)


def check(name, cond, note=""):
    results.append((name, bool(cond), note))
    print(("PASS " if cond else "FAIL "), name, ("— " + note if note and not cond else ""))


def truth(name):
    return json.load(open(f"{FIX}/{name}_truth.json"))


def parse_vox(path):
    data = open(path, 'rb').read()
    models, palette, cur = [], None, None
    def walk(off, end):
        nonlocal palette, cur
        while off < end:
            cid = data[off:off+4]; n, m = struct.unpack('<ii', data[off+4:off+12])
            body = data[off+12:off+12+n]
            if cid == b'SIZE': cur = struct.unpack('<iii', body)
            elif cid == b'XYZI':
                cnt = struct.unpack('<i', body[:4])[0]
                models.append((cur, {tuple(body[4+i*4:8+i*4]) for i in range(cnt)}))
            elif cid == b'RGBA': palette = body[:1024]
            walk(off+12+n, off+12+n+m); off += 12+n+m
    walk(8, len(data))
    return models, palette


# 1-2 help + missing file
try:
    r = run("--help"); check("help_exit0", r.returncode == 0)
except Exception as e:
    check("help_exit0", False, str(e))
try:
    r = run("stats", "no_such_file.vox")
    check("missing_file_clean", r.returncode != 0 and "Traceback" not in r.stderr)
except Exception as e:
    check("missing_file_clean", False, str(e))

# 3-6 stats correctness
for name, checks in [
    ("example", ["voxels", "models", "size", "bbox", "palette_used"]),
    ("pagoda", ["voxels", "bbox", "palette_used"]),
    ("multimodel", ["models", "voxels"]),
]:
    try:
        r = run("stats", f"{FIX}/{name}.vox")
        got = json.loads(r.stdout)
        t = truth(name)
        ok = all(got.get(k) == t[k] for k in checks)
        check(f"stats_{name}", ok, f"got {json.dumps({k: got.get(k) for k in checks})} want {json.dumps({k: t[k] for k in checks})}")
    except Exception as e:
        check(f"stats_{name}", False, f"{type(e).__name__}: {e}")

# 7-9 render: exists, non-blank, occlusion, palette fidelity
from PIL import Image
import numpy as np
try:
    out = os.path.join(tempfile.mkdtemp(), "p.png")
    r = run("render", f"{FIX}/pagoda.vox", out, timeout=600)
    im = np.asarray(Image.open(out).convert("RGB"))
    check("render_pagoda_png", im.size > 0)
    from collections import Counter
    corner = tuple(im[0, 0])
    nonbg = (np.abs(im.astype(int) - np.array(corner)).sum(axis=2) > 30).mean()
    check("render_nonblank", nonbg > 0.05, f"non-background fraction {nonbg:.3f}")
except Exception as e:
    check("render_pagoda_png", False, f"{type(e).__name__}: {e}")
    check("render_nonblank", False)
try:
    out = os.path.join(tempfile.mkdtemp(), "o.png")
    r = run("render", f"{FIX}/occl.vox", out, "--scale", "20")
    im = np.asarray(Image.open(out).convert("RGB")).reshape(-1, 3)
    reds = ((im[:, 0] > 150) & (im[:, 1] < 110) & (im[:, 2] < 110)).sum()
    greens = ((im[:, 1] > 150) & (im[:, 0] < 110) & (im[:, 2] < 110)).sum()
    # front voxel (1,1,1) is red idx1; back (0,0,0) green idx2. Red must dominate where they overlap;
    # green may peek but red area must be >= green area (full overlap in this projection).
    check("render_occlusion", reds > 0 and reds >= greens, f"red px {reds}, green px {greens}")
    check("render_palette", reds > 0, "no red pixels for red voxel")
except Exception as e:
    check("render_occlusion", False, f"{type(e).__name__}: {e}")
    check("render_palette", False)

# 10-12 round trip
try:
    td = tempfile.mkdtemp()
    j, v2 = os.path.join(td, "p.json"), os.path.join(td, "p2.vox")
    r1 = run("tojson", f"{FIX}/pagoda.vox", j, timeout=300)
    r2 = run("fromjson", j, v2, timeout=300)
    m1, p1 = parse_vox(f"{FIX}/pagoda.vox"); m2, p2 = parse_vox(v2)
    check("roundtrip_voxels", [s for s, _ in m1] == [s for s, _ in m2] and all(a[1] == b[1] for a, b in zip(m1, m2)))
    check("roundtrip_palette", p1 == p2, "palette bytes differ")
    r = run("stats", v2)
    check("roundtrip_stats", json.loads(r.stdout)["voxels"] == truth("pagoda")["voxels"])
except Exception as e:
    check("roundtrip_voxels", False, f"{type(e).__name__}: {e}")
    check("roundtrip_palette", False); check("roundtrip_stats", False)

# 13-15 malformed handling
for name, fixture in [("badmagic", "badmagic.vox"), ("truncated", "truncated.vox")]:
    try:
        r = run("stats", f"{FIX}/{fixture}")
        check(f"malformed_{name}", r.returncode == 2 and "Traceback" not in r.stderr,
              f"rc={r.returncode} stderr_has_tb={'Traceback' in r.stderr}")
    except Exception as e:
        check(f"malformed_{name}", False, f"{type(e).__name__}: {e}")
try:
    r = run("render", f"{FIX}/badmagic.vox", "/tmp/x.png")
    check("malformed_render", r.returncode == 2 and "Traceback" not in r.stderr)
except Exception as e:
    check("malformed_render", False, str(e))

passed = sum(1 for _, ok, _ in results if ok)
print(f"\nSCORE {passed}/{len(results)}")
