# talentmatch — specification (Round 3: web app)

Implement `app.py`, a single-file recruiting web app ("TalentMatch") in Python 3.
Allowed dependencies: Python stdlib + Flask. Nothing else. All HTML/CSS/JS must be
served inline from `app.py` (no separate files, no CDN — the UI must work offline).

Run contract: `python3 app.py --port N` serves on 127.0.0.1:N. State is in-memory
only (no files, no database). The process must start serving within 10 seconds.

## Data model

**Job**: `{"id": int, "title": str, "required_skills": [str], "nice_to_have": [str]}`
**Candidate**: `{"id": int, "name": str, "skills": [str], "years": float}`

IDs are integers assigned by the server starting at 1, incrementing per collection.
All skill matching is case-insensitive; skills are compared after `strip().lower()`.
Duplicate skills within one list count once.

## JSON API

### `POST /api/jobs`
Body: `{"title": ..., "required_skills": [...], "nice_to_have": [...]}`
(`nice_to_have` optional, default `[]`). Returns `201` and the created Job.
Missing/empty `title` or missing/empty `required_skills` → `400` with
`{"error": "<message>"}`.

### `GET /api/jobs` → `200`, list of all Jobs (creation order).

### `POST /api/candidates`
Body: `{"name": ..., "skills": [...], "years": ...}` (`years` optional, default 0).
Returns `201` and the created Candidate. Missing/empty `name` or missing/empty
`skills` → `400` with an `error` key. Negative `years` → `400`.

### `GET /api/candidates` → `200`, list of all Candidates (creation order).

### `GET /api/match/<job_id>`
Returns `200` and a JSON list of ALL candidates ranked for this job, best first:
`[{"candidate_id": ..., "name": ..., "score": ..., "matched_required": [...],
"matched_nice": [...]}, ...]`

**Scoring (exact):**
```
score = 10 * |matched required skills|
      + 3 * |matched nice-to-have skills|
      + min(years, 10) * 0.5
```
Rounded to 2 decimals. `matched_required` / `matched_nice` list the matched skill
names lowercased, sorted alphabetically. A skill in both required and nice-to-have
counts only as required. Ties broken by candidate id ascending.
Unknown `job_id` → `404` with an `error` key. No candidates → `200` and `[]`.

### `POST /api/parse_resume`
Body: `{"text": "<free text resume>"}`. Extracts skills by scanning the text
(case-insensitive, word-boundary matches) against the union of every skill
mentioned in any existing Job (required + nice_to_have). Returns `200` and
`{"skills": [...]}` — lowercased, sorted, deduplicated. Empty/missing text → `400`.

## UI (served at `GET /`)

Single page, self-contained. Must contain these element ids and work end-to-end
against the API above using fetch():
- `#job-form` (create job), `#candidate-form` (create candidate)
- `#job-list` (all jobs), `#candidate-list` (all candidates)
- `#match-select` (choose a job) and `#match-table` (ranked results with scores)
Rows appear without a page reload after each create.

## Error handling
Malformed JSON bodies → `400` JSON error, never a traceback page. `--help` exits 0.

## Grading (hidden)
A hidden suite exercises every endpoint above on unseen data, including the exact
scoring formula, tie-breaks, case-insensitivity, dedup, both-lists overlap, years
capping, resume parsing against the live job-skill taxonomy, 400/404 paths, and
checks the UI page for the required element ids. Correct scoring is worth the most.
