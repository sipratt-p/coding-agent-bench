"""Hidden grader for bvxtool (Round 2). Usage: python3 grade2.py <arena_dir>"""
import json, os, struct, subprocess, sys, tempfile

ARENA = os.path.abspath(sys.argv[1])
TOOL = os.path.join(ARENA, "bvxtool.py")
FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures2")
results = []


def run(*args, timeout=180):
    return subprocess.run([sys.executable, TOOL, *args], capture_output=True,
                          text=True, timeout=timeout, cwd=ARENA)


def check(name, cond, note=""):
    results.append((name, bool(cond), note))
    print(("PASS " if cond else "FAIL "), name, ("— " + note if note and not cond else ""))


def truth(name):
    return json.load(open(f"{FIX}/{name}_truth.json"))


def parse_bvx(path):
    data = open(path, 'rb').read()
    assert data[:4] == b'BVX1'
    cnt = struct.unpack('<H', data[4:6])[0]
    off = 6
    models = []
    for _ in range(cnt):
        sx, sy, sz, n = struct.unpack('<HHHI', data[off:off+10]); off += 10
        vox = set()
        for i in range(n):
            z, y, x, ci = data[off:off+4]
            vox.add((x, y, z, ci)); off += 4
    # NOTE: bug guard — voxels appended per model
        models.append(((sx, sy, sz), vox))
    assert data[off:off+4] == b'CLRS'
    pal = data[off+4:off+4+768]
    return models, pal


# 1-2
try:
    r = run("--help"); check("help_exit0", r.returncode == 0)
except Exception as e:
    check("help_exit0", False, str(e))
try:
    r = run("stats", "no_such.bvx")
    check("missing_file_clean", r.returncode != 0 and "Traceback" not in r.stderr)
except Exception as e:
    check("missing_file_clean", False, str(e))

# 3-6 stats (example, axis = the separator, pagoda large, multimodel)
for name, checks in [
    ("example", ["voxels", "models", "size", "bbox", "palette_used"]),
    ("axis", ["size", "bbox", "voxels", "palette_used"]),
    ("pagoda", ["voxels", "bbox", "palette_used"]),
    ("multimodel", ["models", "voxels"]),
]:
    try:
        r = run("stats", f"{FIX}/{name}.bvx")
        got = json.loads(r.stdout)
        t = truth(name)
        ok = all(got.get(k) == t[k] for k in checks)
        check(f"stats_{name}", ok, f"got {json.dumps({k: got.get(k) for k in checks})} want {json.dumps({k: t[k] for k in checks})}")
    except Exception as e:
        check(f"stats_{name}", False, f"{type(e).__name__}: {e}")

# 7-10 render
from PIL import Image
import numpy as np
try:
    out = os.path.join(tempfile.mkdtemp(), "p.png")
    r = run("render", f"{FIX}/pagoda.bvx", out, timeout=600)
    im = np.asarray(Image.open(out).convert("RGB"))
    check("render_pagoda_png", im.size > 0)
    corner = tuple(im[0, 0])
    nonbg = (np.abs(im.astype(int) - np.array(corner)).sum(axis=2) > 30).mean()
    check("render_nonblank", nonbg > 0.05, f"non-background fraction {nonbg:.3f}")
except Exception as e:
    check("render_pagoda_png", False, f"{type(e).__name__}: {e}")
    check("render_nonblank", False)
try:
    out = os.path.join(tempfile.mkdtemp(), "o.png")
    r = run("render", f"{FIX}/occl.bvx", out, "--scale", "20")
    im = np.asarray(Image.open(out).convert("RGB")).reshape(-1, 3)
    reds = ((im[:, 0] > 150) & (im[:, 1] < 110) & (im[:, 2] < 110)).sum()
    greens = ((im[:, 1] > 150) & (im[:, 0] < 110) & (im[:, 2] < 110)).sum()
    check("render_occlusion", reds > 0 and reds >= greens, f"red px {reds}, green px {greens}")
    check("render_palette", reds > 0, "no red pixels for red voxel")
except Exception as e:
    check("render_occlusion", False, f"{type(e).__name__}: {e}")
    check("render_palette", False)

# 11-13 round trip
try:
    td = tempfile.mkdtemp()
    j, v2 = os.path.join(td, "p.json"), os.path.join(td, "p2.bvx")
    run("tojson", f"{FIX}/pagoda.bvx", j, timeout=300)
    run("fromjson", j, v2, timeout=300)
    m1, p1 = parse_bvx(f"{FIX}/pagoda.bvx"); m2, p2 = parse_bvx(v2)
    check("roundtrip_voxels", [s for s, _ in m1] == [s for s, _ in m2] and all(a[1] == b[1] for a, b in zip(m1, m2)))
    check("roundtrip_palette", p1 == p2, "palette bytes differ")
    r = run("stats", v2)
    check("roundtrip_stats", json.loads(r.stdout)["voxels"] == truth("pagoda")["voxels"])
except Exception as e:
    check("roundtrip_voxels", False, f"{type(e).__name__}: {e}")
    check("roundtrip_palette", False); check("roundtrip_stats", False)

# 14-16 malformed
for name, fixture in [("badmagic", "badmagic.bvx"), ("truncated", "truncated.bvx")]:
    try:
        r = run("stats", f"{FIX}/{fixture}")
        check(f"malformed_{name}", r.returncode == 2 and "Traceback" not in r.stderr,
              f"rc={r.returncode} stderr_has_tb={'Traceback' in r.stderr}")
    except Exception as e:
        check(f"malformed_{name}", False, f"{type(e).__name__}: {e}")
try:
    r = run("render", f"{FIX}/badmagic.bvx", "/tmp/x2.png")
    check("malformed_render", r.returncode == 2 and "Traceback" not in r.stderr)
except Exception as e:
    check("malformed_render", False, str(e))

passed = sum(1 for _, ok, _ in results if ok)
print(f"\nSCORE {passed}/{len(results)}")
