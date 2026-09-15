# Secrets and private-data check

What was removed or rewritten while curating this snapshot from the private
working directories, and how the result was verified. No secret values appear
in this file.

## Patterns scrubbed

| Pattern | Where it occurred | Action |
|---|---|---|
| Tailscale addresses (`100.x.x.x`) | one runner (`run_openclaw_bench.py`: an `user@100.x.x.x` SSH target), one queue script, `server`/`base` URL fields in 9 result JSONs | runner and script omitted; URL hosts rewritten to `REDACTED-TAILSCALE-HOST` (port kept) |
| LAN addresses (`192.168.x.x`) | the LiteLLM bridge config, five April-2026 runner scripts, `server`/`base` URL fields in 19 result JSONs | config and scripts omitted; URL hosts rewritten to `REDACTED-LAN-HOST` (port kept) |
| SSH targets (`user@host`, `*.local` hostnames) | `run_openclaw_bench.py`, shell queue scripts | omitted |
| Home-directory paths (Linux `/home/…` and macOS user-home prefixes) | default results/work/alerts paths in every runner, chart output paths, a Prime Agent binary path under `~/.nvm`, a model path and an HF cache path in two result JSONs, judge screenshot paths in five arena JSONs | replaced by CLI flags / env vars with relative defaults (`--out`, `--work-root`, `BENCH_ALERTS_DIR`, `PRIME_AGENT_BIN`, `CHARTS_DIR`); JSON values shortened to the bare model id / `judge_shots/<name>.png` |
| Machine nicknames and the operator's first name in code comments | docstrings and comments in the runners | rewritten neutrally; nicknames remain only inside result `display` strings ("Beast", "Cosmo", "Sentry" = the machines a server ran on) and are explained in RESULTS.md |
| Per-run alert log (`ALERTS.md`, `ALERTS_LATEST.json`) | operator narrative with timestamps | not copied; now git-ignored |
| Logs, agent work directories, transcripts, screenshots, `__pycache__` | `*.log`, `prime-tb-work-*`, `cc-*-work*`, `arena*-*/`, `judge_shots/` | not copied; patterns git-ignored |

## Credentials

* No API keys, tokens, passwords or private keys were found in any copied file.
  The runners read a bearer token only from `BENCH_API_KEY` / `--api-key`.
* `run_cc_tb.py` sets `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_API_KEY` to the
  literal placeholder `bench` for a local bridge; it is not a credential.
* `arena/judge4.py` reads `ANTHROPIC_API_KEY` from the environment only.

## Verification

Run from the repository root after checkout; both should print nothing:

```bash
grep -rnIE '\b(100|192|10)\.[0-9]+\.[0-9]+\.[0-9]+\b|/U[s]ers/|/home/[a-z]|ghp_[A-Za-z0-9]{20,}|xox[bp]-|sk-(ant-|proj-)?[A-Za-z0-9]{10,}|BEGIN (RSA|OPENSSH) PRIVATE|@[a-z0-9.-]+\.local\b|\.ts\.net' --exclude-dir=.git --exclude=SECRETS-CHECK.md .
grep -rnIiE 'api[_-]?key\s*[:=]\s*["'"'"'][^"'"'"']{6,}|password\s*[:=]' --exclude-dir=.git --exclude=SECRETS-CHECK.md .
```

Both were empty at commit time (this file is excluded because it names the patterns). Binary fixtures (`arena/fixtures*/*.vox|*.bvx`)
are synthetic voxel files with no text content.
