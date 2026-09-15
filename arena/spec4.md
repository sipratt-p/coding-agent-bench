# talentsearch — specification (Round 4: agentic candidate search)

Implement `app.py`, a single-file recruiting **search engine** ("TalentSearch") in
Python 3. Allowed dependencies: Python stdlib + Flask. All HTML/CSS/JS served
inline from `app.py` — no separate files, no CDN, fully offline.

Run contract: `python3 app.py --port N` serves on 127.0.0.1:N within 10 seconds.
In-memory state only. `--help` exits 0.

**This round is graded on three axes: exact functional correctness (hidden
suite), performance at scale (hard latency gates on a 150k-candidate pool), and
engineering/UI quality (code + screenshots judged against a rubric). A naive
linear rescan per query WILL fail the performance gates — index your data.**

## Data model

Candidate (as ingested; server assigns nothing, ids come with the data):

```json
{"id": 17, "name": "Ada Chen", "title": "Senior ML Engineer",
 "skills": [{"name": "Python", "years": 6}, {"name": "PyTorch", "years": 4}],
 "location": "Berlin", "remote_ok": true, "salary_expectation": 140000,
 "years_total": 9, "level": "senior", "last_active": "2026-07-14",
 "tags": ["ml", "open-source"]}
```

`level` ∈ {junior, mid, senior, staff}. `last_active` is an ISO date string.
Skill names are compared case-insensitively everywhere (normalize with
`strip().lower()`); duplicate skill entries within one candidate keep the max years.

## Endpoints

### `POST /api/candidates/bulk`
Body: JSON array of candidates (up to 200,000). Replaces the entire pool.
Returns `200` `{"ingested": N}`. Must ingest 150k in ≤ 20 s. Candidates missing
`id` or `name` → reject the whole batch with `400` and an `error` key.

### `GET /api/candidates/<id>` → `200` candidate or `404` `{"error": ...}`.

### `POST /api/search`
Body: `{"q": "<query>", "page": 1, "page_size": 20}` (`page` default 1,
`page_size` default 20, max 100 → larger values clamp to 100).

Response `200`:
```json
{"total": 1234, "page": 1, "page_size": 20, "has_next": true,
 "results": [{"id": ..., "name": ..., "title": ..., "score": ...,
              "breakdown": {"skills": ..., "title": ..., "recency": ...,
                             "salary_fit": ..., "remote": ...}}, ...]}
```
Page past the end → `200` with empty `results` (not an error). Unparseable
query → `400` with `{"error": "<message>", "position": <int char offset>}`.

### `GET /api/facets?q=<query>`
`200` `{"skills": [["python", 812], ...], "locations": [["berlin", 211], ...]}`
— top 10 each **among candidates matching q**, sorted count desc then name asc.
Empty q = whole pool.

## Query language

```
query   := or_expr
or_expr := and_expr ( OR and_expr )*
and_expr:= unary ( AND? unary )*          # juxtaposition means AND
unary   := NOT unary | '(' or_expr ')' | pred
```
`AND` / `OR` / `NOT` are case-insensitive keywords.

Predicates (`pred`):
- `python` or `"machine learning"` — **term**. Matches if any skill name equals
  the term (case-insens) OR the title contains it as a case-insensitive substring.
- `skill:python` — has the skill. `skill:python>=3` — has it with years ≥ 3.
- `location:berlin` — exact case-insensitive match.
- `remote:true` / `remote:false`
- `level:senior`
- `tag:contractor` — has the tag (case-insens).
- `salary<=140000` / `salary>=90000` — against salary_expectation.
- `years>=5` / `years<=10` — against years_total.

A candidate is in the result set iff the boolean expression is satisfied.

## Scoring (exact)

Collect the query's **positive** predicates (every term / `skill:` pred anywhere
in the query, including inside OR branches, but NOT those under a `NOT`).
Dedupe by normalized value — a bare term and a `skill:` pred with the same
value count once (as the skill match). For each candidate in the result set:

- **skills**: for each positive skill-pred or term that matches one of the
  candidate's skills: `10 + min(years_on_that_skill, 10)` points.
- **title**: for each positive term that did NOT match a skill but appears in
  the title: `5` points.
- **recency** (reference date fixed at `2026-08-01`): last_active within 30
  days → `15`; within 90 → `10`; within 365 → `5`; else `0`.
- **salary_fit**: if the query contains `salary<=N` and the candidate's
  expectation ≤ 0.8·N → `5`; else if ≤ N → `2`; else `0`.
- **remote**: query contains `remote:true` and candidate remote_ok → `3`.

`score` = sum, rounded to 2 decimals. `breakdown` carries the five components.
Ordering: score desc, then `last_active` desc, then `id` asc. Pagination slices
this exact ordering, stably.

## Performance gates (hidden, hard)

On a generated 150,000-candidate pool: bulk ingest ≤ 20 s; then a fixed batch
of 25 mixed queries (each `page_size` 20) must complete in ≤ 5 s **total**, and
one facets call over a broad query ≤ 2 s. Design for indexed lookup (skill →
ids, sorted numeric arrays, etc.). Correctness is verified on the big pool too
— indexes must not change results.

## UI (served at `GET /`)

Single self-contained page, judged BOTH functionally and aesthetically
(screenshots go to a design rubric — treat this as a product, not a demo):

Required element ids: `#search-input`, `#search-button`, `#results-table`,
`#pagination`, `#facet-panel`, `#empty-state`, `#error-state`,
`#score-breakdown`. Behavior: typing a query and clicking search renders result
rows (name, title, score) without page reload; clicking a row shows its score
breakdown in `#score-breakdown`; facets update with each search; pagination
works; empty results show `#empty-state`; a 400 from the API shows the error
message (with position) in `#error-state`. The page must reach the `load`
event within 5 s and never hang the browser.

Aesthetic rubric (LLM-judged from screenshots + code): visual hierarchy,
typography/spacing, information density, empty/error-state design, overall
polish. Backend rubric (from code): structure/separation, indexing strategy,
algorithmic efficiency, error-handling robustness, readability.

## Error handling
Malformed JSON → `400` JSON error. No tracebacks ever reach the client.
