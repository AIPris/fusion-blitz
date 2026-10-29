"""Aggregates benchmarks/runs/ into results.json, draws time-per-task.svg and prints the README tables.

usage: python report.py      (paths resolve from this file; standard library only)

A run folder holds timing.json, metrics.json and grading.json. A setup folder is either one run (the files directly in
it, iterations 1 and 2) or several (run-1, run-2, ... subfolders); a cell of the tables is the mean time and tokens over its runs and the total number of Fusion calls.
"""
import json
import sys
from pathlib import Path
from statistics import mean

HERE = Path(__file__).resolve().parent
LABELS = {"comb": "Cable comb", "hook": "Wall hook", "box": "Project box", "spool": "Piping spool"}
MEAN_TASKS = ("comb", "hook", "box")   # the three small parts, the ones both experiments share
# experiment -> (tasks, {setup folder: label}); the first setup is the baseline
EXPERIMENTS = {
    "advisor": (("comb", "hook", "box"),
                {"no-skill": "No skill", "skill-v1": "Skill v1", "skill-v2": "Skill v2"}),
    "no-advisor": (("comb", "hook", "box", "spool"),
                   {"no-skill-noadvisor": "No skill", "skill-v2.3-noadvisor": "Skill v2.3"}),
}
CHART = "no-advisor"


# ---- data ------------------------------------------------------------------------------------------------------

def load_cell(task, setup):
    folder = HERE / "runs" / task / setup
    folders = [folder] if (folder / "timing.json").exists() else sorted(folder.glob("run-*"))
    runs = []
    for run in folders:
        timing, metrics, grading = (json.loads((run / f"{name}.json").read_text(encoding="utf-8"))
                                    for name in ("timing", "metrics", "grading"))
        runs.append({"seconds": timing["total_duration_seconds"], "tokens": timing["total_tokens"],
                     "fusion_calls": metrics["fusion_execute_calls"], "fusion_calls_failed": metrics["fusion_execute_failed"],
                     "checks_passed": grading["summary"]["passed"], "checks_total": grading["summary"]["total"]})
    return runs


def cell(runs):
    return {"runs": len(runs), "seconds": mean(r["seconds"] for r in runs),
            "seconds_min": min(r["seconds"] for r in runs), "seconds_max": max(r["seconds"] for r in runs),
            "tokens": mean(r["tokens"] for r in runs), "fusion_calls": sum(r["fusion_calls"] for r in runs),
            "fusion_calls_failed": sum(r["fusion_calls_failed"] for r in runs),
            "checks_passed": sum(r["checks_passed"] for r in runs), "checks_total": sum(r["checks_total"] for r in runs)}


def summarize_experiment(tasks, setups):
    baseline = next(iter(setups))
    cells = {task: {setup: cell(load_cell(task, setup)) for setup in setups} for task in tasks}
    small = [t for t in MEAN_TASKS if t in tasks]
    cells["mean"] = {setup: {
        "runs": sum(cells[t][setup]["runs"] for t in small),
        "seconds": mean(cells[t][setup]["seconds"] for t in small), "tokens": mean(cells[t][setup]["tokens"] for t in small),
        "fusion_calls": sum(cells[t][setup]["fusion_calls"] for t in small),
        "fusion_calls_failed": sum(cells[t][setup]["fusion_calls_failed"] for t in small),
        "checks_passed": sum(cells[t][setup]["checks_passed"] for t in small),
        "checks_total": sum(cells[t][setup]["checks_total"] for t in small)} for setup in setups}
    for row in cells.values():
        for setup, data in row.items():
            data["speedup"] = row[baseline]["seconds"] / data["seconds"]
            data["token_saving"] = 1 - data["tokens"] / row[baseline]["tokens"]
    return cells


def summarize():
    return {name: summarize_experiment(tasks, setups) for name, (tasks, setups) in EXPERIMENTS.items()}


# ---- chart -----------------------------------------------------------------------------------------------------

WIDTH, LEFT, X0, X1, MAX_SECONDS = 760, 24, 176, 640, 1400
BAR_H, BAR_GAP, GROUP_GAP, TOP = 18, 2, 24, 118
STYLE = """
  text { font-family: system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  .bg { fill: #fcfcfb; } .ink { fill: #0b0b0b; } .ink2 { fill: #52514e; } .muted { fill: #898781; }
  .grid { stroke: #e1e0d9; } .axis { stroke: #c3c2b7; }
  .s0 { fill: #898781; } .s1 { fill: #2a78d6; }
  .halo { stroke: #fcfcfb; stroke-width: 4px; stroke-linejoin: round; paint-order: stroke; }
  @media (prefers-color-scheme: dark) {
    .bg { fill: #1a1a19; } .ink { fill: #f0efec; } .ink2 { fill: #c3c2b7; } .halo { stroke: #1a1a19; }
    .grid { stroke: #2c2c2a; } .axis { stroke: #383835; } .s1 { fill: #5598e7; }
  }"""


def bar_path(x, y, width, height, radius=4):
    """Square at the baseline (left), rounded data end (right)."""
    return (f"M{x:.1f},{y} h{width - radius:.1f} a{radius},{radius} 0 0 1 {radius},{radius} v{height - 2 * radius} "
            f"a{radius},{radius} 0 0 1 {-radius},{radius} h{-(width - radius):.1f} z")


def range_note(data):
    return f" ({data['seconds_min']:.0f}-{data['seconds_max']:.0f})" if data["runs"] > 1 and data["seconds_min"] != data["seconds_max"] else ""


def draw(results):
    tasks, setups = EXPERIMENTS[CHART]
    cells = results[CHART]
    baseline, skill = list(setups)
    scale = (X1 - X0) / MAX_SECONDS
    rows = [("Mean of 3 small parts", cells["mean"])] + [(LABELS[t] + (" (2 runs)" if cells[t][skill]["runs"] > 1 else ""), cells[t])
                                                         for t in tasks]
    group_h = len(setups) * BAR_H + (len(setups) - 1) * BAR_GAP
    height = TOP + len(rows) * (group_h + GROUP_GAP) + 70
    axis_bottom = TOP + len(rows) * (group_h + GROUP_GAP) - GROUP_GAP + 6
    small = cells["mean"]
    spool = cells["spool"]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" width="{WIDTH}" height="{height}" '
        f'role="img" aria-labelledby="t d">',
        "<title id=\"t\">Time to build the same Fusion 360 part, with and without the fusion-fast-modeling skill</title>",
        f"<desc id=\"d\">Without the advisor tool: the mean of the three small parts drops from {small[baseline]['seconds']:.0f} to "
        f"{small[skill]['seconds']:.0f} seconds ({small[skill]['speedup']:.1f} times faster); the piping spool from "
        f"{spool[baseline]['seconds']:.0f} to {spool[skill]['seconds']:.0f} seconds ({spool[skill]['speedup']:.1f} times faster).</desc>",
        f"<style>{STYLE}\n</style>",
        f'<rect class="bg" width="{WIDTH}" height="{height}" rx="10"/>',
        f'<text class="ink" x="{LEFT}" y="38" font-size="18" font-weight="600">Time to build the same part in Fusion 360</text>',
        f'<text class="ink2" x="{LEFT}" y="60" font-size="13">Same prompts, same model, same grader, no advisor tool. Small parts: '
        f'{small[baseline]["seconds"]:.0f} s to {small[skill]["seconds"]:.0f} s.</text>',
        f'<text class="ink2" x="{LEFT}" y="78" font-size="13">Piping spool: {spool[baseline]["seconds"]:,.0f} s to '
        f'{spool[skill]["seconds"]:.0f} s.</text>',
    ]
    for i, label in enumerate(setups.values()):
        x = X0 + i * 104
        parts.append(f'<rect class="s{i}" x="{x}" y="92" width="12" height="12" rx="3"/>')
        parts.append(f'<text class="ink2" x="{x + 18}" y="102" font-size="12">{label}</text>')
    for seconds in range(0, MAX_SECONDS, 200):
        x = X0 + seconds * scale
        parts.append(f'<line class="{"axis" if seconds == 0 else "grid"}" x1="{x:.1f}" x2="{x:.1f}" y1="{TOP - 10}" y2="{axis_bottom}"/>')
        parts.append(f'<text class="muted" x="{x:.1f}" y="{axis_bottom + 18}" font-size="11" text-anchor="middle">{seconds} s</text>')
    parts.append(f'<text class="muted" x="{X0}" y="{axis_bottom + 44}" font-size="11">seconds from prompt to a finished, exported model (lower is better)</text>')
    for g, (label, data) in enumerate(rows):
        top = TOP + g * (group_h + GROUP_GAP)
        weight = "600" if g == 0 else "400"
        parts.append(f'<text class="ink" x="{LEFT}" y="{top + group_h / 2 + 4}" font-size="13" font-weight="{weight}">{label}</text>')
        if g == 1:
            y = top - GROUP_GAP / 2
            parts.append(f'<line class="grid" x1="{LEFT}" x2="{WIDTH - LEFT}" y1="{y}" y2="{y}"/>')
        for i, setup in enumerate(setups):
            y = top + i * (BAR_H + BAR_GAP)
            width = data[setup]["seconds"] * scale
            note = "" if setup == baseline else f'<tspan class="ink2" font-weight="400"> · {data[setup]["speedup"]:.1f}× faster</tspan>'
            parts.append(f'<path class="s{i}" d="{bar_path(X0, y, width, BAR_H)}"/>')
            parts.append(f'<text class="ink halo" x="{X0 + width + 8:.1f}" y="{y + 13}" font-size="12" font-weight="600">'
                         f'{data[setup]["seconds"]:.0f} s{note}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


# ---- README tables ---------------------------------------------------------------------------------------------

def tables(results, name):
    tasks, setups = EXPERIMENTS[name]
    cells, baseline = results[name], next(iter(setups))
    out = ["| Setup | Mean time, 3 small parts | vs no skill | Mean tokens | Fusion script calls (failed) | Checks passed |",
           "|---|---:|---:|---:|---:|---:|"]
    for setup, label in setups.items():
        r = cells["mean"][setup]
        speed = "–" if setup == baseline else f"{r['speedup']:.1f}× faster"
        out.append(f"| {label} | {r['seconds']:.0f} s | {speed} | {r['tokens']:,.0f} | "
                   f"{r['fusion_calls']} ({r['fusion_calls_failed']}) | {r['checks_passed']}/{r['checks_total']} |")
    out += ["", "| Task | " + " | ".join(setups.values()) + " |", "|---|" + "---:|" * len(setups)]
    for task in tasks:
        row = []
        for setup in setups:
            r = cells[task][setup]
            calls = f"{r['fusion_calls']} call" + ("" if r["fusion_calls"] == 1 else "s") + (f" in {r['runs']} runs" if r["runs"] > 1 else "")
            row.append(f"{r['seconds']:,.0f} s{range_note(r)}, {calls} ({r['fusion_calls_failed']} failed), "
                       f"{r['tokens'] / 1000:.0f}k tokens")
        out.append(f"| {LABELS[task]} | " + " | ".join(row) + " |")
    return "\n".join(out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    summary = summarize()
    (HERE / "results.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (HERE / "time-per-task.svg").write_text(draw(summary), encoding="utf-8")
    for experiment in EXPERIMENTS:
        print(f"## {experiment}\n\n{tables(summary, experiment)}\n")
