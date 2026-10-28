"""Creates a benchmark workspace: evals.json, eval_metadata.json, run folders, agent prompts and grading specs.

usage: python driver.py <iteration> <bench_dir> <docs_before.json>

<docs_before.json> is a snapshot of the documents open in Fusion before the benchmark, written by
grade.snapshot(path) (run it inside Fusion). The grader uses it to prove the user's other documents stayed untouched.
"""
import json
import sys
from pathlib import Path

import spool_probes

SKILL = Path(__file__).resolve().parents[2] / "skills" / "fusion-fast-modeling"
SPEC_KEYS = ("size", "min", "volume", "volume_tol", "cylinders", "cylinder_radii", "com", "probes", "min_params")   # what the grader reads

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
    {"id": 4, "name": "spool", "stem": "spool", "size": [405, 200, 498], "min": [0, -100, -100],
     "volume": 1719679.341, "volume_tol": [0.001, 0.00005], "com": [179.489, 3.562, 129.911], "min_params": 25,
     "probes": spool_probes.probes(),
     "cylinder_radii": [4.0, 6.0, 9.0, 12.5, 15.0, 25.0, 25.15, 30.15, 33.0, 39.0, 39.45, 44.45, 52.0, 57.0, 82.5, 100.0],
     "task": (
              "Model a flanged eccentric reducing elbow (a piping spool) as one solid body. Millimetres, Z up. The "
              "centreline lies in the XZ plane (y = 0) except for the offset of the outlet. The inlet face is the plane x = "
              "0 and the centreline starts at the origin.\n\nPipe: the main pipe is 88.9 mm outside diameter with a 78.9 mm "
              "bore (5 mm wall); the reduced pipe is 60.3 mm outside diameter with a 50.3 mm bore. The bore runs clear from "
              "the inlet face to the outlet face and nothing (boss, ribs, lugs) intrudes into it.\n\nCentreline, in order: "
              "(1) straight along +X from x = 0 to x = 160; (2) a 90 degree bend of radius 150 turning towards +Z, arc "
              "centre (160, 0, 150), from (160, 0, 0) to (310, 0, 150); (3) straight along +Z at x = 310 from z = 150 to z "
              "= 250; (4) an eccentric reducer from z = 250 to z = 330: a straight-sided (ruled, no guide rails) transition "
              "from the 88.9 mm circle centred on x = 310, y = 0 to the 60.3 mm circle centred on x = 310, y = 14.3, so the "
              "outer surfaces line up along the +Y side; the bore makes the same transition from 78.9 mm to 50.3 mm with "
              "the same two circle centres; (5) straight along +Z at x = 310, y = 14.3 from z = 330 to z = 398, which is "
              "the outlet face.\n\nInlet flange (axis along X): a disc of 200 mm diameter, 20 mm thick (x = 0 to 20), with "
              "8 holes of 18 mm diameter on a 160 mm bolt circle at 22.5 + k * 45 degrees measured from +Z in the YZ plane; "
              "an annular groove in the x = 0 face, 104 mm inner and 114 mm outer diameter, 3 mm deep; a conical weld-neck "
              "hub from 116 mm diameter at x = 20 to the 88.9 mm pipe diameter at x = 60; 1.5 mm x 45 degree chamfers on "
              "both outer edges of the disc.\n\nOutlet flange (axis along Z through x = 310, y = 14.3): a disc of 165 mm "
              "diameter, 18 mm thick (z = 380 to 398), with 4 holes of 18 mm diameter on a 125 mm bolt circle at 45 + k * "
              "90 degrees measured from +X in the XY plane; an annular groove in the z = 398 face, 66 mm inner and 78 mm "
              "outer diameter, 2.5 mm deep; 1.5 mm x 45 degree chamfers on both outer edges of the disc. Four gusset ribs "
              "under the disc, each an 8 mm thick right triangle lying in a plane that contains the outlet axis, at 0, 90, "
              "180 and 270 degrees (parallel to the XZ and YZ planes): the right angle is 28 mm from the outlet axis "
              "(inside the pipe wall, so the rib fuses with it) on the underside of the disc (z = 380), one leg runs 32 mm "
              "outwards along the underside (to 60 mm from the axis), the other runs 40 mm down along the pipe (to z = "
              "340).\n\nSensor boss: a 30 mm diameter cylinder whose axis passes through the centreline point of the bend "
              "at 45 degrees, (266.066, 0, 43.934), and points radially away from the bend centre, direction (0.7071, 0, "
              "-0.7071). It runs from that centreline point out to 70 mm along its axis, with a 1.5 mm x 45 degree chamfer "
              "on the edge of its free end. A 12 mm diameter hole along the axis from the free end down to 30 mm from the "
              "centreline point opens into the bore.\n\nLifting lugs: two 10 mm thick plates (y = -5 to +5) on the vertical "
              "run, in the XZ plane, z = 175 to 225, from x = 240 to x = 380 (they pass through the pipe axis), each end "
              "finished with a semicircle of radius 25 centred at (380, 200) and (240, 200), so the plates reach x = 215 "
              "and x = 405. A 25 mm diameter hole through each plate at those centres. Where the plates meet the outside of "
              "the pipe they are blended with 4 mm fillets along the whole junction (both flat faces and the top and bottom "
              "faces).\n\nAdd nothing else: no other fillets, chamfers, threads or welds."),
     "expected_output": "One solid spool: inlet and outlet flanges with bolt holes, grooves and chamfers, a weld-neck hub, "
                        "a 90 degree bend, an eccentric reducer, a 45 degree sensor boss with a hole, four gusset ribs and "
                        "two filleted lifting lugs, with a clear bore."},
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
                    "docs_before": docs_before, **{key: ev[key] for key in SPEC_KEYS if key in ev}}
            (run / "spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
            (run / "prompt.txt").write_text(prompt(ev, config, str(out)), encoding="utf-8")
    print("workspace ready:", bench / f"iteration-{iteration}")


if __name__ == "__main__":
    main(int(sys.argv[1]), Path(sys.argv[2]), json.loads(Path(sys.argv[3]).read_text(encoding="utf-8")))
