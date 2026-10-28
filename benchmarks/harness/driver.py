"""Creates a benchmark workspace: evals.json, eval_metadata.json, run folders, agent prompts and grading specs.

usage: python driver.py <iteration> <bench_dir> <docs_before.json>

<docs_before.json> is a snapshot of the documents open in Fusion before the benchmark, written by
grade.snapshot(path) (run it inside Fusion). The grader uses it to prove the user's other documents stayed untouched.
"""
import json
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "skills" / "fusion-fast-modeling"

EVALS = [
    {"id": 1, "name": "comb", "stem": "comb", "size": [90, 28, 12], "min": [0, 0, 0], "volume": 21925.588,
     "cylinders": {"3.0": 4, "2.25": 2}, "min_params": 6,
     "task": ("Model a desk cable comb: a bar 90 mm long (x), 28 mm deep (y) and 12 mm tall (z) with one corner at the "
              "origin. Cut five slots from the top, each 7 mm wide (x), running through the full depth (y) and 8 mm "
              "deep (z), pitch 16 mm, the set of slots centred along the length. Two 4.5 mm mounting holes straight "
              "down through the whole bar at x = 4.75 mm and x = 85.25 mm, y = 14 mm. Round the four vertical corner "
              "edges of the bar with R3."),
     "expected_output": "One solid 90x28x12 comb with 5 slots, 2 through holes and 4 R3 corners, parametric, exported."},
    {"id": 2, "name": "hook", "stem": "hook", "size": [50, 40, 70], "min": [0, 0, 0], "volume": 21198.204,
     "cylinders": {"6.0": 1, "4.0": 4, "2.5": 2}, "min_params": 6,
     "task": ("Model a wall hook: a mounting plate 50 mm wide (x), 70 mm tall (z) and 5 mm thick (y), with its back "
              "face on y = 0, its bottom edge on z = 0 and x running from 0 to 50. Two 5 mm holes through the plate "
              "along y, at x = 25, z = 12 and at x = 25, z = 58. A round hook arm, 12 mm diameter and 35 mm long, "
              "sticking out of the front face (y = 5, toward +y), centred at x = 25, z = 35. Round the four plate "
              "corners (the edges parallel to y) with R4, the free end of the arm with R2, and the joint between "
              "arm and plate with R2."),
     "expected_output": "One solid hook 50x40x70 with holes along y, an arm along +y, R4 corners and R2 arm roundings."},
    {"id": 3, "name": "box", "stem": "box", "size": [70, 50, 30], "min": [0, 0, 0], "volume": 28330.213,
     "cylinders": {"5.0": 4, "1.4": 4, "4.0": 4}, "min_params": 8,
     "task": ("Model a small project box with an open top. Outside size 70 mm (x) by 50 mm (y) by 30 mm (z), one "
              "corner at the origin, 2.5 mm walls and a 2.5 mm floor. Four round screw posts, 8 mm diameter, rising "
              "from the floor to z = 28 mm, centred 7.5 mm in from the outside faces in both x and y at each corner, "
              "i.e. at (7.5, 7.5), (62.5, 7.5), (7.5, 42.5) and (62.5, 42.5); each post has a 2.8 mm pilot hole, "
              "12 mm deep from the post top. Six ventilation slots, 2 mm wide (x) and 14 mm tall (z), cut through the "
              "front wall only (the wall at y = 0), the bottom of the slots at z = 8 mm, pitch 6 mm, the set centred "
              "along x. Round the four vertical outside corner edges of the box with R5."),
     "expected_output": "One solid open box 70x50x30 with 4 posts + pilot holes, 6 front vent slots and R5 corners."},
]

COMMON = """You are modelling a part in Autodesk Fusion 360 on the user's PC through the MCP tools named mcp__fusion-local__* (they are deferred tools: load them first with ToolSearch, for example query "select:mcp__fusion-local__fusion_mcp_execute,mcp__fusion-local__fusion_mcp_read"; mcp__fusion-local__fusion_mcp_execute with featureType "script" runs Fusion Python scripts).

Ground rules
- Fusion holds many open, unsaved documents that belong to the user. Never modify, save or close any document you did not create, and never use the MCP document close/save actions. Create exactly one NEW document named {doc} and leave it open and unsaved when you finish.
- Millimetres. Z is up. Every key dimension is a named user parameter and the sketch dimensions and features use those parameters. Sketches fully constrained, all features healthy, one solid body.
- Deliver into {out} (create the folder): {stem}.step, {stem}.stl, {stem}.f3d (native Fusion archive) and {stem}_iso.png (an isometric preview with Z up).
- You cannot ask questions. Decide sensible details yourself and say what you decided.
- Besides the MCP tools you may read and write files. {extra_access}

The part
{task}

When finished reply with a SHORT summary: what you built, the checks you actually ran and their results, and your best count of how many Fusion MCP calls you made. Do not claim a check you did not run."""

SKILL_LINE = (f"First read and follow the skill at {SKILL / 'SKILL.md'} "
              "(its helper module is in the scripts folder next to it).\n\n")


def prompt(ev, config, out):
    suffix = "skill" if config == "with_skill" else "base"
    text = COMMON.format(doc=f"ZZ_bench_{ev['name']}_{suffix}", out=out, stem=ev["stem"], task=ev["task"],
                         extra_access=("Do not browse anywhere else on disk." if config == "without_skill"
                                       else "Do not browse anywhere else on disk except the skill folder."))
    return (SKILL_LINE if config == "with_skill" else "") + text


def main(iteration, bench, docs_before):
    bench.mkdir(parents=True, exist_ok=True)
    skill_evals = {"skill_name": "fusion-fast-modeling", "evals": [
        {"id": e["id"], "prompt": e["task"], "expected_output": e["expected_output"], "files": []} for e in EVALS]}
    (bench / "evals.json").write_text(json.dumps(skill_evals, indent=2), encoding="utf-8")
    for ev in EVALS:
        base = bench / f"iteration-{iteration}" / f"eval-{ev['name']}"
        base.mkdir(parents=True, exist_ok=True)
        (base / "eval_metadata.json").write_text(json.dumps(
            {"eval_id": ev["id"], "eval_name": ev["name"], "prompt": ev["task"], "assertions": []}, indent=2), encoding="utf-8")
        for config in ("with_skill", "without_skill"):
            run = base / config / "run-1"
            out = run / "outputs"
            out.mkdir(parents=True, exist_ok=True)
            suffix = "skill" if config == "with_skill" else "base"
            spec = {"doc": f"ZZ_bench_{ev['name']}_{suffix}", "stem": ev["stem"], "out_dir": str(out), "run_dir": str(run),
                    "size": ev["size"], "min": ev["min"], "volume": ev["volume"], "cylinders": ev["cylinders"],
                    "min_params": ev["min_params"], "docs_before": docs_before}
            (run / "spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
            (run / "prompt.txt").write_text(prompt(ev, config, str(out)), encoding="utf-8")
    print("workspace ready:", bench / f"iteration-{iteration}")


if __name__ == "__main__":
    main(int(sys.argv[1]), Path(sys.argv[2]), json.loads(Path(sys.argv[3]).read_text(encoding="utf-8")))
