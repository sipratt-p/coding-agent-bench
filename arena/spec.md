# voxtool — specification

Implement `voxtool.py`, a Python 3 command-line tool for MagicaVoxel `.vox` files.
Allowed dependencies: Python stdlib, `numpy`, `Pillow`. Nothing else.

## The .vox format (all you need)

Little-endian binary. Layout:

- Bytes 0-3: magic `VOX ` (with trailing space). Bytes 4-7: version int32.
- Then a tree of chunks. Chunk header: 4-byte ID, int32 `content_bytes`, int32
  `children_bytes`; then the content, then the children chunks.
- Root chunk is `MAIN` (content empty; everything else is its children).
- `SIZE` content: int32 x, y, z — dimensions of one model.
- `XYZI` content: int32 n, then n voxels of 4 bytes each: x, y, z, colorIndex
  (all uint8). A model is a SIZE chunk followed by its XYZI chunk; a file may
  contain multiple SIZE/XYZI pairs (multiple models).
- `RGBA` content: 256 × 4 bytes (r,g,b,a). Voxel colorIndex `i` (1-255) maps to
  palette entry `i-1`. If no RGBA chunk exists, use any reasonable default
  palette (grading only checks palette colors when an RGBA chunk is present).
- Other chunk IDs may appear: skip them using their sizes.

## Commands

### `python3 voxtool.py stats FILE.vox`
Print to stdout a single JSON object:
```json
{
  "models": <int>,                  // number of SIZE/XYZI pairs
  "voxels": <int>,                  // total voxel count across models
  "size": [x, y, z],                // dimensions of the FIRST model
  "bbox": [[minx,miny,minz],[maxx,maxy,maxz]],  // over all voxels, all models
  "palette_used": <int>            // count of DISTINCT colorIndex values used
}
```

### `python3 voxtool.py render FILE.vox OUT.png [--scale S]`
Render all voxels as an isometric projection to a PNG:
- Project each voxel at screen position u = (x - y) and v = (x + y)/2 - z
  (scaled by S, default 6 pixels per voxel; each voxel drawn as an SxS square).
- **Occlusion must be correct**: nearer voxels (greater x + y + z) must be drawn
  over farther ones. A painter's/z-buffer approach both work. No scatter plots.
- Fill each voxel square with its palette RGB color (flat shading is fine;
  optional face shading allowed but the dominant pixel color of a voxel must
  stay recognizably its palette color).
- Background: any uniform light color.

### `python3 voxtool.py tojson FILE.vox OUT.json`
### `python3 voxtool.py fromjson IN.json OUT.vox`
Lossless round trip: `tojson` then `fromjson` must reproduce a .vox file with
identical models, voxel sets, and palette (byte-identical files NOT required —
semantic equality is graded by re-parsing). Choose any sane JSON schema.

## Error handling
For missing files, wrong magic, or truncated/corrupt files: print a clear error
to **stderr** and exit with **code 2**. No tracebacks may reach the user.
`--help` must exit 0.

## Provided
- `example.vox` — 5-voxel test file.
- `example_stats.json` — the exact expected `stats` output for it.

## Grading (hidden)
A hidden test suite runs your tool against files you have not seen — including
large real files, multi-model files, and corrupt files — and checks every
behavior above. Test your implementation thoroughly before finishing; untested
edge cases are where submissions fail.
