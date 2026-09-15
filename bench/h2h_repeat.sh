#!/bin/bash
# Head-to-head repeat runner: N sequential Prime-harness tiebreaker runs for one model.
# Usage: h2h_repeat.sh <tag> <provider> <model-id> <display> [N=3]
# Output: $H2H_DIR/<tag>_tb_r{1..N}.json + .log (default results/h2h next to this repo).
# Runs are sequential (each is 4 agentic tasks, server-default sampling). No per-task
# time limit by default: TASK_TIMEOUT=604800 (7 d) -- it must stay < 2^31 ms.
# Single runs are noisy (identical reruns of one task scored 98 then 13): report the
# mean over the N runs, never one run.
set -u
TAG=$1; PROVIDER=$2; MODEL=$3; DISPLAY=$4; N=${5:-3}
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${H2H_DIR:-$HERE/../results/h2h}"; mkdir -p "$OUT"
cd "$HERE" || exit 1
for i in $(seq 1 "$N"); do
  f="$OUT/${TAG}_tb_r${i}.json"
  if [ -s "$f" ]; then echo "[h2h] $f exists, skipping"; continue; fi
  echo "[h2h] run $i/$N start $(date '+%F %T')"
  TASK_TIMEOUT=${TASK_TIMEOUT:-604800} python3 run_prime_tb.py --display "$DISPLAY (r$i)" --out "$f" \
      --provider "$PROVIDER" --model "$MODEL" --suite tb > "$OUT/${TAG}_tb_r${i}.log" 2>&1
  echo "[h2h] run $i/$N end   $(date '+%F %T') rc=$?"
  grep -E "Status:|TOTAL|/400" "$OUT/${TAG}_tb_r${i}.log" | head -6
done
echo "[h2h] all $N runs done for $TAG"
