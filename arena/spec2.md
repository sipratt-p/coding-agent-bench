# bvxtool — specification (Round 2)

Implement `bvxtool.py`, a Python 3 CLI for `.bvx` voxel files.
Allowed dependencies: Python stdlib, `numpy`, `Pillow`. Nothing else.

## The format

**The .bvx binary format is proprietary and undocumented.** You are given:
- `example.bvx` — a small file whose model has size [3,4,5], six voxels, and five
  distinct palette colors (red, green, blue, white, amber among the first five
  palette slots).
- `example_stats.json` — the exact expected `stats` output for it.

Reverse-engineer the format from these. Everything you need is recoverable from
the 1,140 bytes of `example.bvx` plus the expected stats. Files may contain more
than one model; corrupt or truncated files exist. The palette holds 256 colors.
Getting the format exactly right — including byte order and axis conventions —
is the core of this task. Guessing without verifying is how you fail.

## Commands (same CLI as before)

### `python3 bvxtool.py stats FILE.bvx`
JSON to stdout: `{"models": N, "voxels": total, "size": [x,y,z] of first model,
"bbox": [[minx,miny,minz],[maxx,maxy,maxz]] over all voxels, "palette_used":
distinct color indices}` — must match `example_stats.json` for the example.

### `python3 bvxtool.py render FILE.bvx OUT.png [--scale S]`
Isometric render, u=(x-y)·S, v=((x+y)/2 - z)·S, S default 6, correct occlusion
(nearer x+y+z on top), voxels drawn as SxS squares in their palette RGB color,
uniform light background.

### `python3 bvxtool.py tojson FILE.bvx OUT.json` / `python3 bvxtool.py fromjson IN.json OUT.bvx`
Lossless semantic round trip (models, voxel sets, palette), graded by re-parsing.

## Error handling
Missing/corrupt/truncated files: message to stderr, exit code 2, no tracebacks.
`--help` exits 0.

## Grading (hidden)
A hidden suite tests stats correctness on unseen files (including a large one and
an asymmetric one that exposes wrong axis conventions), render occlusion and
palette fidelity, round-trip integrity, and corrupt-file handling.
