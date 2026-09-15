# Agent-harness arena

A second, separate experiment from the coding suite: the **same model** is driven
by different coding-agent harnesses (Prime Agent, opencode, Claude Code, OpenClaw,
the official DeepSeek `dsh`) on one larger spec-driven task per round, and the
resulting artifact is graded by a hidden acceptance suite. It measures the
harness (does it read the spec, test its own output, notice a broken render)
more than the model.

| Round | Spec | Prompt | Grader | Deliverable | Hidden checks |
|---|---|---|---|---|---|
| 1 | `spec.md` | `task_prompt.txt` | `grade.py` (+ `fixtures/`) | `voxtool.py` — MagicaVoxel `.vox` stats / isometric render / JSON round-trip | 15 |
| 2 | `spec2.md` | `task2_prompt.txt` | `grade2.py` (+ `fixtures2/`) | `bvxtool.py` — same CLI for an **undocumented** `.bvx` format with a reversed-axis trap | 16 |
| 3 | `spec3.md` | `task3_prompt.txt` | `grade3.py` | `app.py` — single-file Flask recruiting app with an exact match-scoring formula | 22 |
| 4 | `spec4.md` | `task4_prompt.txt` | `grade4.py` + `ts_oracle.py` (functional + perf gates on a generated 150k-candidate pool), `judge4.py` (LLM-judged UI/code craft rubric from headless-Chrome screenshots) | `app.py` — candidate search engine with a boolean query language, indexes, facets, pagination | 32 + 100 |

Round 3 was retired after five harnesses scored a perfect 22/22; round 4 was
built to discriminate (hard latency gates plus a design rubric) and did — no
ties. Each round's reference implementation was graded first to validate the
suite (the round-1 reference scored 12/15 on its first attempt, which is how the
graders got their teeth).

## Running a round

```bash
mkdir -p /tmp/arena && cp arena/spec4.md /tmp/arena/spec.md      # the agent sees only spec.md
# point your agent at /tmp/arena with the text of arena/task4_prompt.txt as the task
python3 arena/grade4.py /tmp/arena            # functional + perf, prints SCORE n/32
ANTHROPIC_API_KEY=... python3 arena/judge4.py /tmp/arena   # optional craft rubric; needs google-chrome,
                                                            # websocket-client, anthropic
```

Rounds 1-2 graders need `numpy` and `Pillow` (they inspect rendered PNGs);
rounds 3-4 candidate apps need `Flask`. `ts_oracle.py` is the deliberately naive
reference parser/scorer that `grade4.py` cross-checks candidate apps against.

The per-harness work directories (agent transcripts, generated apps, judge
screenshots) are not included; the round-4 judge verdicts and the one saved
`grade4` transcript are in `results/arena/`, and the scores are summarised in
`results/RESULTS.md` and the README.
