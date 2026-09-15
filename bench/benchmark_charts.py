#!/usr/bin/env python3
"""Comparison charts for the April 2026 Mac Studio comparison (Qwen 3.6-35B-A3B vs MiniMax M2.7 vs Opus 4.6).

The numbers are EMBEDDED below (they are not read from results/); this script is kept as
the record of how those charts were produced. Writes four PNGs to the directory given as
the first argument (default: ./charts, or $CHARTS_DIR).
"""
import os
import sys

OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CHARTS_DIR", "charts")
os.makedirs(OUT_DIR, exist_ok=True)

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Color palette
QWEN_COLOR = '#7c3aed'     # purple
MINIMAX_COLOR = '#f59e0b'   # amber
OPUS_COLOR = '#06b6d4'      # cyan
BG_COLOR = '#0f172a'        # dark slate
TEXT_COLOR = '#e2e8f0'
GRID_COLOR = '#334155'

plt.rcParams.update({
    'figure.facecolor': BG_COLOR,
    'axes.facecolor': BG_COLOR,
    'text.color': TEXT_COLOR,
    'axes.labelcolor': TEXT_COLOR,
    'xtick.color': TEXT_COLOR,
    'ytick.color': TEXT_COLOR,
    'font.family': 'sans-serif',
    'font.size': 13,
})

# ===== CHART 1: Raw Inference Quality =====
fig, ax = plt.subplots(figsize=(12, 7))

categories = ['Code Gen\n(Python)', 'Code Gen\n(SQL)', 'Code\nDebugging', 'Security\nReview',
              'Math\nReasoning', 'Logical\nReasoning', 'System\nDesign', 'Structured\nOutput',
              'Summar-\nization', 'Long-form\nWriting']

qwen_quality = [100, 100, 60, 50, 100, 80, 100, 100, 100, 100]
minimax_quality = [100, 100, 100, 100, 60, 80, 100, 100, 100, 100]

x = np.arange(len(categories))
width = 0.35

bars1 = ax.bar(x - width/2, qwen_quality, width, label='Qwen 3.6-35B-A3B', color=QWEN_COLOR, edgecolor='none', alpha=0.9)
bars2 = ax.bar(x + width/2, minimax_quality, width, label='MiniMax M2.7', color=MINIMAX_COLOR, edgecolor='none', alpha=0.9)

ax.set_ylabel('Quality Score (%)', fontsize=14, fontweight='bold')
ax.set_title('Raw Inference Quality — Keyword Hit Rate', fontsize=16, fontweight='bold', pad=15)
ax.set_xticks(x)
ax.set_xticklabels(categories, fontsize=10)
ax.set_ylim(0, 115)
ax.legend(loc='upper right', fontsize=12, framealpha=0.3)
ax.grid(axis='y', color=GRID_COLOR, alpha=0.5)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color(GRID_COLOR)
ax.spines['bottom'].set_color(GRID_COLOR)

# Add value labels
for bar in bars1:
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 2, f'{int(height)}%', ha='center', va='bottom', fontsize=9, color=QWEN_COLOR)
for bar in bars2:
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 2, f'{int(height)}%', ha='center', va='bottom', fontsize=9, color=MINIMAX_COLOR)

plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, 'chart_quality.png'), dpi=200, bbox_inches='tight')
print("Saved chart_quality.png")

# ===== CHART 2: Speed Comparison =====
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

# Single request speed
models = ['Qwen 3.6\n35B-A3B', 'MiniMax M2.7\n229B (Q8)', 'Claude\nOpus 4.6']
speeds = [89.8, 40.6, 90]  # approximate Opus API speed
colors = [QWEN_COLOR, MINIMAX_COLOR, OPUS_COLOR]

bars = ax1.bar(models, speeds, color=colors, edgecolor='none', alpha=0.9, width=0.6)
ax1.set_ylabel('Tokens/sec', fontsize=14, fontweight='bold')
ax1.set_title('Single Request Speed', fontsize=14, fontweight='bold', pad=10)
ax1.set_ylim(0, 120)
ax1.grid(axis='y', color=GRID_COLOR, alpha=0.5)
ax1.spines['top'].set_visible(False)
ax1.spines['right'].set_visible(False)
ax1.spines['left'].set_color(GRID_COLOR)
ax1.spines['bottom'].set_color(GRID_COLOR)

for bar, speed in zip(bars, speeds):
    ax1.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 2, f'{speed}', ha='center', va='bottom', fontsize=12, fontweight='bold')

# Concurrent throughput
concurrency = [1, 2, 4, 8]
qwen_agg = [78.6, 83.5, 84.4, 87.4]
minimax_agg = [39.6, 53.0, 63.8, 63.9]

ax2.plot(concurrency, qwen_agg, 'o-', color=QWEN_COLOR, linewidth=2.5, markersize=8, label='Qwen 3.6')
ax2.plot(concurrency, minimax_agg, 's-', color=MINIMAX_COLOR, linewidth=2.5, markersize=8, label='MiniMax M2.7')
ax2.set_xlabel('Concurrent Requests', fontsize=12, fontweight='bold')
ax2.set_ylabel('Aggregate tok/s', fontsize=14, fontweight='bold')
ax2.set_title('Concurrent Throughput Scaling', fontsize=14, fontweight='bold', pad=10)
ax2.set_xticks(concurrency)
ax2.legend(fontsize=12, framealpha=0.3)
ax2.grid(color=GRID_COLOR, alpha=0.5)
ax2.spines['top'].set_visible(False)
ax2.spines['right'].set_visible(False)
ax2.spines['left'].set_color(GRID_COLOR)
ax2.spines['bottom'].set_color(GRID_COLOR)
ax2.set_ylim(0, 110)

plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, 'chart_speed.png'), dpi=200, bbox_inches='tight')
print("Saved chart_speed.png")

# ===== CHART 3: Agentic Test Results =====
fig, ax = plt.subplots(figsize=(12, 6))

tests = ['File\nAnalysis', 'Hydration\nDiagnosis', 'System\nAnalysis', 'GH Actions\nWorkflow']

# Scores: quality (0-100), use 0 for timeout
qwen_agentic = [85, 100, 0, 0]    # 0 = timeout
minimax_agentic = [100, 100, 100, 100]

x = np.arange(len(tests))
width = 0.35

bars1 = ax.bar(x - width/2, qwen_agentic, width, label='Qwen 3.6-35B-A3B', color=QWEN_COLOR, edgecolor='none', alpha=0.9)
bars2 = ax.bar(x + width/2, minimax_agentic, width, label='MiniMax M2.7', color=MINIMAX_COLOR, edgecolor='none', alpha=0.9)

ax.set_ylabel('Score', fontsize=14, fontweight='bold')
ax.set_title('Agentic Benchmark — Tool Use & Multi-Step Tasks', fontsize=16, fontweight='bold', pad=15)
ax.set_xticks(x)
ax.set_xticklabels(tests, fontsize=12)
ax.set_ylim(0, 125)
ax.legend(loc='upper right', fontsize=12, framealpha=0.3)
ax.grid(axis='y', color=GRID_COLOR, alpha=0.5)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.spines['left'].set_color(GRID_COLOR)
ax.spines['bottom'].set_color(GRID_COLOR)

# Annotate timeouts
for i, val in enumerate(qwen_agentic):
    if val == 0:
        ax.text(x[i] - width/2, 5, 'TIMEOUT', ha='center', va='bottom', fontsize=10, color='#ef4444', fontweight='bold')

# Time labels
qwen_times = ['27s', '25s', '120s\n(fail)', '120s\n(fail)']
minimax_times = ['26s', '25s', '29s', '33s']

for i in range(len(tests)):
    if qwen_agentic[i] > 0:
        ax.text(x[i] - width/2, qwen_agentic[i] + 2, qwen_times[i], ha='center', va='bottom', fontsize=9, color=QWEN_COLOR)
    ax.text(x[i] + width/2, minimax_agentic[i] + 2, minimax_times[i], ha='center', va='bottom', fontsize=9, color=MINIMAX_COLOR)

plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, 'chart_agentic.png'), dpi=200, bbox_inches='tight')
print("Saved chart_agentic.png")

# ===== CHART 4: Overall Summary Radar =====
fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

dims = ['Coding\nQuality', 'Reasoning', 'Speed\n(tok/s)', 'Tool\nUse', 'Concurrency\nScaling', 'Complex\nTasks']
N = len(dims)

# Normalize to 0-100
qwen_scores = [77.5, 93.3, 90, 33, 10, 25]     # tool use: partial, complex: timeouts
minimax_scores = [100, 80, 41, 100, 62, 100]     # speed normalized to 100
opus_scores = [100, 100, 90, 100, 100, 100]       # baseline

angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
angles += angles[:1]

for scores, color, label in [
    (qwen_scores, QWEN_COLOR, 'Qwen 3.6'),
    (minimax_scores, MINIMAX_COLOR, 'MiniMax M2.7'),
    (opus_scores, OPUS_COLOR, 'Opus 4.6 (API)'),
]:
    values = scores + scores[:1]
    ax.plot(angles, values, 'o-', linewidth=2, color=color, label=label, markersize=6)
    ax.fill(angles, values, alpha=0.1, color=color)

ax.set_xticks(angles[:-1])
ax.set_xticklabels(dims, fontsize=11)
ax.set_ylim(0, 110)
ax.set_yticks([25, 50, 75, 100])
ax.set_yticklabels(['25', '50', '75', '100'], fontsize=9)
ax.grid(color=GRID_COLOR, alpha=0.5)
ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=11, framealpha=0.3)
ax.set_title('Overall Model Comparison\nMac Studio M3 Ultra — 512GB', fontsize=14, fontweight='bold', pad=20, y=1.08)

plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, 'chart_radar.png'), dpi=200, bbox_inches='tight')
print("Saved chart_radar.png")

print(f"\nAll charts saved to {OUT_DIR}/")
