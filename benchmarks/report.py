"""Aggregates benchmarks/runs/ into results.json, draws time-per-task.svg and prints the README tables.

usage: python report.py      (paths resolve from this file; standard library only)
"""
import json
import sys
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
TASKS = {"comb": "Cable comb", "hook": "Wall hook", "box": "Project box"}
CONFIGS = {"no-skill": "No skill", "skill-v1": "Skill v1", "skill-v2": "Skill v2"}
BASELINE = "no-skill"


# ---- data ------------------------------------------------------------------------------------------------------

def load_run(task, config):
    run = HERE / "runs" / task / config
    timing, metrics, grading = (json.loads((run / f"{name}.json").read_text(encoding="utf-8"))
                                for name in ("timing", "metrics", "grading"))
    return {"seconds": timing["total_duration_seconds"], "tokens": timing["total_tokens"],
            "fusion_calls": metrics["fusion_execute_calls"], "fusion_calls_failed": metrics["fusion_execute_failed"],
            "checks_passed": grading["summary"]["passed"], "checks_total": grading["summary"]["total"]}


def summarize():
    tasks = {task: {config: load_run(task, config) for config in CONFIGS} for task in TASKS}
    overall = {}
    for config in CONFIGS:
        runs = [tasks[task][config] for task in TASKS]
        overall[config] = {
            "seconds": mean(r["seconds"] for r in runs), "tokens": mean(r["tokens"] for r in runs),
            "fusion_calls": sum(r["fusion_calls"] for r in runs),
            "fusion_calls_failed": sum(r["fusion_calls_failed"] for r in runs),
            "checks_passed": sum(r["checks_passed"] for r in runs), "checks_total": sum(r["checks_total"] for r in runs)}
    for rows in (*tasks.values(), overall):
        for config, row in rows.items():
            row["speedup"] = rows[BASELINE]["seconds"] / row["seconds"]
            row["token_saving"] = 1 - row["tokens"] / rows[BASELINE]["tokens"]
    return {"tasks": tasks, "mean": overall}


# ---- chart -----------------------------------------------------------------------------------------------------

WIDTH, LEFT, X0, X1, MAX_SECONDS = 760, 24, 176, 676, 750
BAR_H, BAR_GAP, GROUP_GAP, TOP = 18, 2, 24, 118
GROUP_H = len(CONFIGS) * BAR_H + (len(CONFIGS) - 1) * BAR_GAP
STYLE = """
  text { font-family: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  .bg { fill: #fcfcfb; } .ink { fill: #0b0b0b; } .ink2 { fill: #52514e; } .muted { fill: #898781; }
  .grid { stroke: #e1e0d9; } .axis { stroke: #c3c2b7; }
  .s0 { fill: #898781; } .s1 { fill: #86b6ef; } .s2 { fill: #2a78d6; }
  .halo { stroke: #fcfcfb; stroke-width: 4px; stroke-linejoin: round; paint-order: stroke; }
  @media (prefers-color-scheme: dark) {
    .bg { fill: #1a1a19; } .ink { fill: #f0efec; } .ink2 { fill: #c3c2b7; } .halo { stroke: #1a1a19; }
    .grid { stroke: #2c2c2a; } .axis { stroke: #383835; } .s1 { fill: #256abf; } .s2 { fill: #5598e7; }
  }"""


def bar_path(x, y, width, height, radius=4):
    """Square at the baseline (left), rounded data end (right)."""
    return (f"M{x:.1f},{y} h{width - radius:.1f} a{radius},{radius} 0 0 1 {radius},{radius} v{height - 2 * radius} "
            f"a{radius},{radius} 0 0 1 {-radius},{radius} h{-(width - radius):.1f} z")


def draw(results):
    scale = (X1 - X0) / MAX_SECONDS
    rows = [("Mean of 3 tasks", results["mean"])] + [(label, results["tasks"][task]) for task, label in TASKS.items()]
    height = TOP + len(rows) * (GROUP_H + GROUP_GAP) + 70
    axis_bottom = TOP + len(rows) * (GROUP_H + GROUP_GAP) - GROUP_GAP + 6
    mean_no, mean_v2 = (results["mean"][c]["seconds"] for c in ("no-skill", "skill-v2"))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" width="{WIDTH}" height="{height}" '
        f'role="img" aria-labelledby="t d">',
        "<title id=\"t\">Time to build the same Fusion 360 part, with and without the fusion-fast-modeling skill</title>",
        f"<desc id=\"d\">Mean {mean_no:.0f} seconds without the skill, {mean_v2:.0f} seconds with skill v2 "
        f"({mean_no / mean_v2:.1f} times faster), over three tasks.</desc>",
        f"<style>{STYLE}\n</style>",
        f'<rect class="bg" width="{WIDTH}" height="{height}" rx="10"/>',
        f'<text class="ink" x="{LEFT}" y="38" font-size="18" font-weight="600">Time to build the same part in Fusion 360</text>',
        f'<text class="ink2" x="{LEFT}" y="60" font-size="13">Same prompts, same model, same grader. With the skill the mean '
        f'drops from {mean_no:.0f} s to {mean_v2:.0f} s ({mean_no / mean_v2:.1f}× faster).</text>',
    ]
    for i, (name, label) in enumerate(CONFIGS.items()):
        x = X0 + i * 104
        parts.append(f'<rect class="s{i}" x="{x}" y="82" width="12" height="12" rx="3"/>')
        parts.append(f'<text class="ink2" x="{x + 18}" y="92" font-size="12">{label}</text>')
    for seconds in range(0, MAX_SECONDS, 200):
        x = X0 + seconds * scale
        parts.append(f'<line class="{"axis" if seconds == 0 else "grid"}" x1="{x:.1f}" x2="{x:.1f}" y1="{TOP - 10}" y2="{axis_bottom}"/>')
        parts.append(f'<text class="muted" x="{x:.1f}" y="{axis_bottom + 18}" font-size="11" text-anchor="middle">{seconds} s</text>')
    parts.append(f'<text class="muted" x="{X0}" y="{axis_bottom + 44}" font-size="11">seconds from prompt to a finished, exported model (lower is better)</text>')
    for g, (label, data) in enumerate(rows):
        top = TOP + g * (GROUP_H + GROUP_GAP)
        weight = "600" if g == 0 else "400"
        parts.append(f'<text class="ink" x="{LEFT}" y="{top + GROUP_H / 2 + 4}" font-size="13" font-weight="{weight}">{label}</text>')
        if g == 1:
            y = top - GROUP_GAP / 2
            parts.append(f'<line class="grid" x1="{LEFT}" x2="{WIDTH - LEFT}" y1="{y}" y2="{y}"/>')
        for i, config in enumerate(CONFIGS):
            y = top + i * (BAR_H + BAR_GAP)
            width = data[config]["seconds"] * scale
            note = "" if config == BASELINE else f'<tspan class="ink2" font-weight="400"> · {data[config]["speedup"]:.1f}× faster</tspan>'
            parts.append(f'<path class="s{i}" d="{bar_path(X0, y, width, BAR_H)}"/>')
            parts.append(f'<text class="ink halo" x="{X0 + width + 8:.1f}" y="{y + 13}" font-size="12" font-weight="600">'
                         f'{data[config]["seconds"]:.0f} s{note}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


# ---- README tables ---------------------------------------------------------------------------------------------

def tables(results):
    out = ["| Setup | Mean time | vs no skill | Mean tokens | Fusion script calls (failed) | Checks passed |",
           "|---|---:|---:|---:|---:|---:|"]
    for config, label in CONFIGS.items():
        r = results["mean"][config]
        speed = "–" if config == BASELINE else f"{r['speedup']:.1f}× faster"
        out.append(f"| {label} | {r['seconds']:.0f} s | {speed} | {r['tokens']:,.0f} | "
                   f"{r['fusion_calls']} ({r['fusion_calls_failed']}) | {r['checks_passed']}/{r['checks_total']} |")
    out += ["", "| Task | " + " | ".join(CONFIGS.values()) + " |", "|---|" + "---:|" * len(CONFIGS)]
    for task, label in TASKS.items():
        cells = []
        for config in CONFIGS:
            r = results["tasks"][task][config]
            calls = f"{r['fusion_calls']} call" + ("" if r["fusion_calls"] == 1 else "s")
            cells.append(f"{r['seconds']:.0f} s, {calls} ({r['fusion_calls_failed']} failed)")
        out.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    summary = summarize()
    (HERE / "results.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (HERE / "time-per-task.svg").write_text(draw(summary), encoding="utf-8")
    print(tables(summary))
