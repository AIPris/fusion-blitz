"""Objective grader, run inside Fusion (read-only) against a finished benchmark document.

Reads a spec JSON (written by the benchmark driver) and writes <run_dir>/grading.json in skill-creator's format.
Nothing here trusts the agent's own report: geometry, constraints, parameters, files and the state of every other
open document are read back from Fusion and the disk.
"""
import json
import re
from pathlib import Path

import adsk.core
import adsk.fusion

CM = 0.1


def snapshot(path):
    app = adsk.core.Application.get()
    rows = [[d.name, d.isSaved, d.isModified] for d in app.documents]
    Path(path).write_text(json.dumps(rows), encoding="utf-8")
    print(f"snapshot of {len(rows)} documents -> {path}")


def close_named(name):
    """Close (without saving) a benchmark document by exact name; refuses anything not called ZZ_bench_*."""
    if not name.startswith("ZZ_bench_"):
        raise RuntimeError("Refusing to close a non-benchmark document")
    app = adsk.core.Application.get()
    for doc in list(app.documents):
        if doc.name == name:
            doc.close(False)
            print("closed", name)
            return
    print("not open:", name)


def cylinder_counts(body):
    counts = {}
    for face in body.faces:
        cylinder = adsk.core.Cylinder.cast(face.geometry)
        if cylinder:
            key = str(round(cylinder.radius / CM, 3))
            counts[key] = counts.get(key, 0) + 1
    return counts


def grade(spec_path):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    app = adsk.core.Application.get()
    checks = []

    def add(text, passed, evidence):
        checks.append({"text": text, "passed": bool(passed), "evidence": evidence})

    doc = next((d for d in app.documents if d.name == spec["doc"]), None)
    add(f"Document {spec['doc']} exists and was left open", doc is not None,
        "found" if doc else "not open: " + str([d.name for d in app.documents if d.name.startswith("ZZ_")]))
    if doc:
        design = adsk.fusion.Design.cast(doc.products.itemByProductType("DesignProductType"))
        root = design.rootComponent
        bodies = list(root.bRepBodies)
        add("Exactly one solid body", len(bodies) == 1 and bodies[0].isSolid,
            f"{len(bodies)} bodies, solid flags {[b.isSolid for b in bodies]}")
        if len(bodies) == 1:
            body = bodies[0]
            box = body.boundingBox
            low = [c / CM for c in box.minPoint.asArray()]
            size = [(h - l) / CM for l, h in zip(box.minPoint.asArray(), box.maxPoint.asArray())]
            add("Bounding box size matches the request (+/-0.05 mm)",
                all(abs(a - b) <= 0.05 for a, b in zip(size, spec["size"])),
                f"size {[round(s, 3) for s in size]} vs {spec['size']}")
            add("Part sits where requested: bounding-box minimum corner (+/-0.05 mm)",
                all(abs(a - b) <= 0.05 for a, b in zip(low, spec["min"])),
                f"min {[round(s, 3) for s in low]} vs {spec['min']}")
            volume = body.volume / CM ** 3
            error = abs(volume - spec["volume"]) / spec["volume"]
            add("Volume matches the reference model within 0.2 % (all features present, right size and place)",
                error <= 0.002, f"{volume:.2f} mm3 vs reference {spec['volume']:.2f} ({error * 100:.3f} % off)")
            counts = cylinder_counts(body)
            add("Cylindrical faces (holes, posts, fillets) match the reference by radius",
                counts == spec["cylinders"], f"{counts} vs reference {spec['cylinders']}")
        timeline = design.timeline
        bad = [timeline.item(i).name for i in range(timeline.count)
               if timeline.item(i).healthState != adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState]
        add("Every timeline feature is healthy", not bad, f"{timeline.count} features, unhealthy: {bad}")
        loose = [s.name for s in root.sketches if not s.isFullyConstrained]
        add("Every sketch is fully constrained", not loose, f"{root.sketches.count} sketches, loose: {loose}")
        names = [p.name for p in design.userParameters]
        add(f"At least {spec['min_params']} named user parameters", len(names) >= spec["min_params"],
            f"{len(names)}: {names}")
        pattern = re.compile(r"\b(" + "|".join(map(re.escape, names)) + r")\b") if names else None
        dims = [d.parameter.expression for s in root.sketches for d in s.sketchDimensions]
        driven = [e for e in dims if pattern and pattern.search(e)]
        share = len(driven) / len(dims) if dims else 0
        add("Most sketch dimensions are driven by named parameters (>= 50 %)", share >= 0.5,
            f"{len(driven)} of {len(dims)} dimensions reference a user parameter")
    out_dir = Path(spec["out_dir"])
    wanted = [f"{spec['stem']}.step", f"{spec['stem']}.stl", f"{spec['stem']}.f3d", f"{spec['stem']}_iso.png"]
    missing = [n for n in wanted if not (out_dir / n).is_file() or (out_dir / n).stat().st_size == 0]
    add("STEP, STL, F3D and iso PNG were delivered, non-empty", not missing, f"missing: {missing}")
    others_now = {tuple(r) for r in ([d.name, d.isSaved, d.isModified] for d in app.documents)
                  if r[0] != spec["doc"]}
    before = {tuple(r) for r in spec["docs_before"]}
    changed = sorted(before ^ others_now)
    add("The user's other documents are untouched (same names, saved and modified flags)", not changed,
        "unchanged" if not changed else f"differences: {changed}")

    passed = sum(c["passed"] for c in checks)
    result = {"expectations": checks, "summary": {"passed": passed, "failed": len(checks) - passed,
                                                  "total": len(checks), "pass_rate": round(passed / len(checks), 3)}}
    Path(spec["run_dir"], "grading.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"]))
    for c in checks:
        print(("PASS " if c["passed"] else "FAIL ") + c["text"] + "  <- " + c["evidence"])
