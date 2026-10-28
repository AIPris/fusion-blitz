"""Independent check of an exported STEP: re-import it with build123d and compare to the reference.

usage: uv run --python 3.12 --with build123d-mcp==0.3.91 python step_check.py <run_dir>
Appends one expectation to <run_dir>/grading.json (reads <run_dir>/spec.json).
"""
import json
import sys
from pathlib import Path

from build123d import import_step


def main(run_dir):
    run = Path(run_dir)
    spec = json.loads((run / "spec.json").read_text(encoding="utf-8"))
    step = Path(spec["out_dir"]) / f"{spec['stem']}.step"
    if not step.is_file():
        passed, evidence = False, f"{step} missing"
    else:
        shape = import_step(str(step))
        box = shape.bounding_box()
        size = [box.size.X, box.size.Y, box.size.Z]
        low = [box.min.X, box.min.Y, box.min.Z]
        volume = shape.volume
        error = abs(volume - spec["volume"]) / spec["volume"]
        solids = len(shape.solids())
        ok_size = all(abs(a - b) <= 0.05 for a, b in zip(size, spec["size"]))
        ok_min = all(abs(a - b) <= 0.05 for a, b in zip(low, spec["min"]))
        passed = solids == 1 and shape.is_valid and ok_size and ok_min and error <= 0.002
        evidence = (f"STEP re-imported: {solids} solid(s), valid={shape.is_valid}, size {[round(s, 3) for s in size]}, "
                    f"min {[round(s, 3) for s in low]}, volume {volume:.2f} vs {spec['volume']:.2f} ({error * 100:.3f} % off)")
    text = "Delivered STEP re-imports as one valid solid with the reference size, position and volume"
    path = run / "grading.json"
    grading = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"expectations": []}
    grading["expectations"] = [e for e in grading["expectations"] if e["text"] != text]
    grading["expectations"].append({"text": text, "passed": bool(passed), "evidence": evidence})
    total = len(grading["expectations"])
    done = sum(e["passed"] for e in grading["expectations"])
    grading["summary"] = {"passed": done, "failed": total - done, "total": total, "pass_rate": round(done / total, 3)}
    path.write_text(json.dumps(grading, indent=2), encoding="utf-8")
    print(("PASS " if passed else "FAIL ") + evidence)


if __name__ == "__main__":
    main(sys.argv[1])
