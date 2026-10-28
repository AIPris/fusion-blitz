"""fusion_fast - tested helpers that keep Fusion MCP modelling scripts short.

Import it inside a script run with fusion_mcp_execute (featureType="script"):

    import sys, importlib
    sys.path.insert(0, r"<skill dir>/scripts") if r"<skill dir>/scripts" not in sys.path else None
    import fusion_fast as ff
    importlib.reload(ff)          # Fusion's Python keeps modules alive between calls

Conventions that remove whole classes of API failures:
  * Every length you pass in is millimetres. A number is mm, a string is a Fusion expression
    ("width / 2", "3 mm") so the model stays parametric. Fusion itself stores cm; this module converts.
  * 2D sketch coordinates are WORLD coordinates of the two axes lying in the sketch plane, in x, y, z order:
    "xy" -> (x, y), "xz" -> (x, z), "yz" -> (y, z). The module maps them onto Fusion's sketch axes, which are
    reversed or swapped on some planes, so you never reason about sketch orientation.
  * Directions are world directions: toward="+" / "-" is along the +/- world axis of the sketch plane's normal.
  * Geometry is picked by position (m.edges, m.face), never by index, so a rebuilt model picks the same things.
  * Only documents made by ff.new() are ever touched; ff.new() refuses a name that is already open.
"""
import builtins
import math
import re
from pathlib import Path

import adsk.core
import adsk.fusion

CM = 0.1  # cm per mm: Fusion stores lengths in cm
TOL = 1e-4  # mm
PROBE_MM = 0.05  # how far beside an edge to test whether the surface turns outward
# Fusion rejects a driving dimension (VCS_SKETCH_OVER_CONSTRAINTS) when its measured value equals an existing one
# measured from the same origin point, e.g. two holes at the same height. Geometry is therefore drawn this far off
# its target; the dimension expressions then pull it exactly into place.
NUDGE = 0.013  # mm
# "Through all" is a long finite cut. A one-sided setAllExtent cut starts failing with "no target body to cut"
# once a join feature has been added to the body, even far from the join; a finite distance does not.
THROUGH_MM = 1000
REGISTRY = "_fusion_fast_documents"
SNAPSHOTS = "_fusion_fast_snapshots"  # per model: the other open documents (name, saved, modified) when it was made
AXIS = {"x": 0, "y": 1, "z": 2}
PLANE_NORMAL = {"xy": 2, "xz": 1, "yz": 0}
OPERATIONS = {"new": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
              "join": adsk.fusion.FeatureOperations.JoinFeatureOperation,
              "cut": adsk.fusion.FeatureOperations.CutFeatureOperation,
              "intersect": adsk.fusion.FeatureOperations.IntersectFeatureOperation}
HORIZONTAL = adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation
VERTICAL = adsk.fusion.DimensionOrientations.VerticalDimensionOrientation


def P(x, y, z=0.0):
    return adsk.core.Point3D.create(x, y, z)


def expr(value):
    """A number is millimetres; a string is already an expression and is passed through."""
    if isinstance(value, str):
        return value
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return ("0" if text in ("", "-0") else text) + " mm"


def count_expr(value):
    return value if isinstance(value, str) else str(int(value))


def vi(value):
    return adsk.core.ValueInput.createByString(expr(value))


def registry():
    """name -> Document of every model ff.new() made. Entries whose document was closed (by us, the user or the
    grader) are dropped here, so a stale name never blocks a rebuild."""
    if not hasattr(builtins, REGISTRY):
        setattr(builtins, REGISTRY, {})
    documents = getattr(builtins, REGISTRY)
    for name in [n for n, d in documents.items() if not d.isValid]:
        documents.pop(name)
    return documents


def snapshots():
    if not hasattr(builtins, SNAPSHOTS):
        setattr(builtins, SNAPSHOTS, {})
    return getattr(builtins, SNAPSHOTS)


def open_documents():
    """[(name, isSaved, isModified)] of every open document - use to prove other documents were untouched."""
    app = adsk.core.Application.get()
    return [(d.name, d.isSaved, d.isModified) for d in app.documents]


def new(name, replace=False):
    """Create a new, empty parametric mm design called `name` and return its Model.

    replace=True first closes (without saving) an earlier model of that name that ff.new() made, so a build
    script can simply be edited and re-run from scratch. A document ff.new() did not make is never replaced."""
    app = adsk.core.Application.get()
    if replace and name in registry():
        open_model(name).close()
    if any(d.name == name for d in app.documents):
        raise RuntimeError(f"A document called {name!r} is already open; choose a new name or pass replace=True "
                           "(only works for models made by ff.new)")
    snapshot = open_documents()
    doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    doc.name = name
    registry()[name] = doc
    snapshots()[name] = snapshot
    model = Model(doc)
    model.design.designType = adsk.fusion.DesignTypes.ParametricDesignType
    model.design.fusionUnitsManager.distanceDisplayUnits = adsk.fusion.DistanceUnits.MillimeterDistanceUnits
    return model


def open_model(name):
    """Re-attach to a model made by ff.new() in an earlier call and make it the active document."""
    doc = registry().get(name)
    if doc is None or not doc.isValid:
        raise RuntimeError(f"No model {name!r} was made by ff.new() in this Fusion session")
    doc.activate()
    return Model(doc)


class Model:
    def __init__(self, doc):
        self.doc = doc
        self.app = adsk.core.Application.get()
        self.design = adsk.fusion.Design.cast(doc.products.itemByProductType("DesignProductType"))
        self.root = self.design.rootComponent

    # ---- basics -------------------------------------------------------------------------------------------
    def mm(self, value):
        """Numeric millimetres of a number or an expression."""
        if not isinstance(value, str):
            return float(value)
        return self.design.unitsManager.evaluateExpression(value, "mm") / CM

    def unit_of(self, text):
        for token in re.findall(r"[A-Za-z_]\w*", text):
            if token in ("mm", "deg"):
                return token
            known = self.design.userParameters.itemByName(token)
            if known:
                return known.unit
        return ""

    def params(self, **values):
        """Create or update user parameters: params(width=40, thickness="3 mm", cols="4", half="width / 2").
        Numbers are mm; a string's unit is read from it (mm, deg) or from the parameters it names."""
        for name, value in values.items():
            text = expr(value)
            existing = self.design.userParameters.itemByName(name)
            if existing:
                existing.expression = text
            else:
                self.design.userParameters.add(name, adsk.core.ValueInput.createByString(text), self.unit_of(text), "")
        return self

    def name_param(self, parameter, base):
        name, n = base, 1
        while self.design.allParameters.itemByName(name):
            n += 1
            name = f"{base}_{n}"
        parameter.name = name

    def body(self, name=None):
        if name:
            found = self.root.bRepBodies.itemByName(name)
            if not found:
                raise RuntimeError(f"No body called {name!r}")
            return found
        if self.root.bRepBodies.count != 1:
            raise RuntimeError(f"{self.root.bRepBodies.count} bodies exist; pass body=<name>")
        return self.root.bRepBodies.item(0)

    def _resolve_body(self, body):
        """None -> the only body; a string -> that body by name; a BRepBody -> itself."""
        return self.body(body) if body is None or isinstance(body, str) else body

    # ---- sketches -----------------------------------------------------------------------------------------
    def sketch(self, plane, at=0, name=None):
        """Sketch on "xy" / "xz" / "yz" (optionally offset along its normal by `at`, number or expression),
        or on a planar axis-aligned BRepFace."""
        if isinstance(plane, str):
            key = plane.lower()
            axis = PLANE_NORMAL[key]
            base = {"xy": self.root.xYConstructionPlane, "xz": self.root.xZConstructionPlane,
                    "yz": self.root.yZConstructionPlane}[key]
            level = self.mm(at)
            if abs(level) > TOL:
                direction = base.geometry.normal.asArray()[axis]
                plane_input = self.root.constructionPlanes.createInput()
                plane_input.setByOffset(base, vi(at if direction > 0 else f"-({expr(at)})"))
                base = self.root.constructionPlanes.add(plane_input)
                if abs(base.geometry.origin.asArray()[axis] / CM - level) > 1e-3:
                    raise RuntimeError("Offset plane landed on the wrong side of the origin")
            target = base
        else:
            face_plane = adsk.core.Plane.cast(plane.geometry)
            if not face_plane:
                raise RuntimeError("Sketch faces must be planar")
            normal = face_plane.normal.asArray()
            axis = max(range(3), key=lambda i: abs(normal[i]))
            if abs(abs(normal[axis]) - 1) > 1e-6:
                raise RuntimeError("Sketch faces must be axis aligned")
            level = face_plane.origin.asArray()[axis] / CM
            target = plane
        raw = self.root.sketches.add(target)
        if name:
            raw.name = name
        # A sketch made on a face arrives with the face outline projected into it (Fusion preference "Automatically
        # project edges on sketch create"). It would become an extra profile that extrudes the whole face.
        for curve in [c for c in raw.sketchCurves if c.isReference]:
            curve.deleteMe()
        return Sketch(self, raw, axis, level)

    # ---- features -----------------------------------------------------------------------------------------
    def set_extent(self, feature_input, distance, toward, sketch):
        sign = sketch.normal_sign()
        if toward == "sym":
            direction = adsk.fusion.ExtentDirections.SymmetricExtentDirection
        else:
            positive = (toward == "+") == (sign > 0)
            direction = (adsk.fusion.ExtentDirections.PositiveExtentDirection if positive
                         else adsk.fusion.ExtentDirections.NegativeExtentDirection)
        if distance == "all":
            distance = THROUGH_MM  # not setAllExtent: see THROUGH_MM
        if toward == "sym":
            feature_input.setSymmetricExtent(vi(distance), True)
        else:
            feature_input.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(vi(distance)), direction)

    def extrude(self, sketch, distance, op="new", toward="+", name=None, body=None, profiles="all"):
        """Extrude every profile of `sketch` (or the listed profile indexes) by `distance` mm / expression, or
        distance="all" to run through everything. op: new | join | cut | intersect. toward: "+" | "-" | "sym"."""
        chosen = adsk.core.ObjectCollection.create()
        for i in (range(sketch.s.profiles.count) if profiles == "all" else profiles):
            chosen.add(sketch.s.profiles.item(i))
        if chosen.count == 0:
            raise RuntimeError("The sketch has no closed profile to extrude")
        feature_input = self.root.features.extrudeFeatures.createInput(chosen, OPERATIONS[op])
        self.set_extent(feature_input, distance, toward, sketch)
        feature = self.root.features.extrudeFeatures.add(feature_input)
        if name:
            feature.name = name
        if body and op == "new":
            feature.bodies.item(0).name = body
        sketch.s.isLightBulbOn = False
        return feature

    def holes(self, plane, points, diameter, depth="all", toward="-", at=0, name="Holes"):
        """Round through (or blind) holes at world 2D `points` [(u, v), ...] drilled from the sketch plane toward
        the material. One sketch, one cut feature, every circle fully dimensioned."""
        sketch = self.sketch(plane, at=at, name=name + "_sketch")
        for u, v in points:
            sketch.circle(u, v, diameter)
        return self.extrude(sketch, depth, op="cut", toward=toward, name=name)

    def axis(self, key):
        return {"x": self.root.xConstructionAxis, "y": self.root.yConstructionAxis,
                "z": self.root.zConstructionAxis}[key]

    def pattern(self, features, axis, count, spacing, axis2=None, count2=None, spacing2=None, name=None):
        """Rectangular pattern of one feature or a list, along a world axis ("x", "y", "z"), optionally two ways."""
        entities = adsk.core.ObjectCollection.create()
        for feature in (features if isinstance(features, (list, tuple)) else [features]):
            entities.add(feature)
        patterns = self.root.features.rectangularPatternFeatures
        pattern_input = patterns.createInput(entities, self.axis(axis), adsk.core.ValueInput.createByString(count_expr(count)),
                                             vi(spacing), adsk.fusion.PatternDistanceType.SpacingPatternDistanceType)
        if axis2:
            pattern_input.setDirectionTwo(self.axis(axis2), adsk.core.ValueInput.createByString(count_expr(count2)), vi(spacing2))
        feature = patterns.add(pattern_input)
        if name:
            feature.name = name
        return feature

    def mirror(self, features, plane, name=None):
        entities = adsk.core.ObjectCollection.create()
        for feature in (features if isinstance(features, (list, tuple)) else [features]):
            entities.add(feature)
        plane_object = {"xy": self.root.xYConstructionPlane, "xz": self.root.xZConstructionPlane,
                        "yz": self.root.yZConstructionPlane}[plane.lower()]
        feature = self.root.features.mirrorFeatures.add(self.root.features.mirrorFeatures.createInput(entities, plane_object))
        if name:
            feature.name = name
        return feature

    def fillet(self, name, *sets):
        """One fillet feature from (radius, edges) pairs: rounds that meet are blended together in one go."""
        fillet_input = self.root.features.filletFeatures.createInput()
        for radius, edges in sets:
            if edges.count == 0:
                raise RuntimeError(f"No edges picked for {name} ({radius})")
            fillet_input.addConstantRadiusEdgeSet(edges, vi(radius), True)
        feature = self.root.features.filletFeatures.add(fillet_input)
        feature.name = name
        return feature

    def chamfer(self, name, distance, edges):
        if edges.count == 0:
            raise RuntimeError(f"No edges picked for {name}")
        chamfer_input = self.root.features.chamferFeatures.createInput2()
        chamfer_input.chamferEdgeSets.addEqualDistanceChamferEdgeSet(edges, vi(distance), True)
        feature = self.root.features.chamferFeatures.add(chamfer_input)
        feature.name = name
        return feature

    # ---- picking geometry by position --------------------------------------------------------------------
    def edges(self, body=None, parallel=None, curve=None, radius=None, convex=None, min_len=None, **ranges):
        """Edges of a body as an ObjectCollection, filtered by world position (mm) - never by index.

        parallel: "x" | "y" | "z" keeps straight edges along that axis.   curve: "line" | "circle" (circles and arcs).
        radius: keeps circles/arcs of that radius in mm.
        x= / y= / z=: edge midpoint is a number (within tolerance), a (low, high) range with None as an open end,
            or a list of those meaning any of them: x=[0, 90], y=[0, 28] picks all four corner edges of a bar.
        convex: minimum turn in degrees; keeps only outside corners (60 = anything sharper than a gentle blend).
        min_len: drops edges shorter than this many mm."""
        body = self._resolve_body(body)
        found = adsk.core.ObjectCollection.create()
        for edge in body.edges:
            geometry = edge.geometry
            line = adsk.core.Line3D.cast(geometry)
            round_curve = adsk.core.Circle3D.cast(geometry) or adsk.core.Arc3D.cast(geometry)
            if curve == "line" and not line or curve == "circle" and not round_curve:
                continue
            if radius is not None and (not round_curve or abs(round_curve.radius / CM - radius) > 1e-3):
                continue
            if parallel:
                if not line:
                    continue
                direction = line.startPoint.vectorTo(line.endPoint)
                direction.normalize()
                if abs(abs(direction.asArray()[AXIS[parallel]]) - 1) > 1e-6:
                    continue
            if min_len is not None and edge.length / CM < min_len:
                continue
            middle = self._midpoint(edge)
            if not all(self._within(middle.asArray()[AXIS[key]] / CM, limit) for key, limit in ranges.items()):
                continue
            if convex is not None and not self._turns_outward(body, edge, middle, convex):
                continue
            found.add(edge)
        return found

    def face(self, body=None, normal="+z", at=None):
        """The planar face whose outward normal is `normal` ("+z", "-x", ...), at coordinate `at` mm along that
        axis, or the outermost one when `at` is None."""
        body = self._resolve_body(body)
        axis, sign = AXIS[normal[1]], (1 if normal[0] == "+" else -1)
        best = None
        for face in body.faces:
            plane = adsk.core.Plane.cast(face.geometry)
            if not plane:
                continue
            outward = self._outward_normal(body, face, face.pointOnFace)
            if outward.asArray()[axis] * sign < 1 - 1e-6:
                continue
            level = plane.origin.asArray()[axis] / CM
            if at is not None:
                if abs(level - self.mm(at)) < 1e-3:
                    return face
            elif best is None or level * sign > best[0] * sign:
                best = (level, face)
        if best is None:
            raise RuntimeError(f"No planar face with normal {normal}" + (f" at {at}" if at is not None else ""))
        return best[1]

    @staticmethod
    def _within(value, limit):
        if limit is None:
            return True
        if isinstance(limit, list):
            return any(Model._within(value, item) for item in limit)
        if isinstance(limit, (int, float)):
            return abs(value - limit) < 1e-3
        low, high = limit
        return (low is None or value >= low - 1e-3) and (high is None or value <= high + 1e-3)

    @staticmethod
    def _midpoint(edge):
        _, low, high = edge.evaluator.getParameterExtents()
        return edge.evaluator.getPointAtParameter((low + high) / 2)[1]

    @staticmethod
    def _outward_normal(body, face, point):
        ok, normal = face.evaluator.getNormalAtPoint(point)
        if not ok:
            raise RuntimeError("No normal at this point")
        normal.normalize()
        probe = P(*[c + n * PROBE_MM * CM for c, n in zip(point.asArray(), normal.asArray())])
        if body.pointContainment(probe) != adsk.fusion.PointContainment.PointOutsidePointContainment:
            normal.scaleBy(-1)
        return normal

    def _turns_outward(self, body, edge, middle, min_turn):
        if edge.faces.count != 2:
            return False
        n0, n1 = (self._outward_normal(body, edge.faces.item(i), middle) for i in range(2))
        turn = math.degrees(math.acos(max(-1.0, min(1.0, n0.dotProduct(n1)))))
        if turn < min_turn:
            return False
        beside = adsk.core.Vector3D.create(n0.x - n1.x, n0.y - n1.y, n0.z - n1.z)
        beside.scaleBy(PROBE_MM * CM)
        outside = adsk.fusion.PointContainment.PointOutsidePointContainment
        return all(body.pointContainment(P(middle.x + s * beside.x, middle.y + s * beside.y, middle.z + s * beside.z)) == outside
                   for s in (1, -1))

    # ---- checks and output --------------------------------------------------------------------------------
    def settle(self, parameter, rounds=2):
        """Regenerate the history through parameter round trips. A fresh build whose last step is a fillet or
        chamfer after patterns can report lost edge references until it has been regenerated from a changed state."""
        target = self.design.userParameters.itemByName(parameter)
        original = target.expression
        for _ in range(rounds):
            try:
                target.expression = f"({original}) + 1 mm"
                self.design.computeAll()
            finally:
                target.expression = original
                self.design.computeAll()

    def probe(self, inside=(), outside=(), label="probe"):
        """Point-in-solid test in world mm: every `inside` point must be material, every `outside` point empty
        (a point exactly on a surface counts as neither). Raises listing the wrong points. Use it where a
        volume cannot tell two layouts apart (which side a slot is on, hole depth, wall beside a post)."""
        def state(point):
            location = P(*[c * CM for c in point])
            states = [body.pointContainment(location) for body in self.root.bRepBodies]
            if adsk.fusion.PointContainment.PointInsidePointContainment in states:
                return "inside"
            return "outside" if all(s == adsk.fusion.PointContainment.PointOutsidePointContainment for s in states) else "on surface"
        wrong = [f"{p} is {state(p)}, expected {want}" for want, points in (("inside", inside), ("outside", outside))
                 for p in points if state(p) != want]
        print(f"{label}: {len(list(inside)) + len(list(outside)) - len(wrong)} of {len(list(inside)) + len(list(outside))} points as expected")
        if wrong:
            raise RuntimeError(f"[{label}] " + "; ".join(wrong))

    def what_if(self, changes, stage="what_if", **expect):
        """Parametric proof: set parameters (e.g. {"box_x": 80, "slot_count": "4"}), regenerate, run report(**expect),
        then restore the originals. Proves the model follows its parameters instead of holding frozen numbers."""
        parameters = {name: self.design.userParameters.itemByName(name) for name in changes}
        originals = {name: parameter.expression for name, parameter in parameters.items()}
        try:
            for name, value in changes.items():
                parameters[name].expression = expr(value)
            self.design.computeAll()
            return self.report(stage, **expect)
        finally:
            for name, text in originals.items():
                parameters[name].expression = text
            self.design.computeAll()

    def report(self, stage="", expect_size=None, expect_volume=None, expect_bodies=None, tol=0.01, vol_tol=0.002,
               strict=True):
        """Checkpoint: print one JSON line (bodies, size, volume, cylinder radii, timeline health, unconstrained
        sketches, a warning if the user's other documents changed) and raise if a check fails, naming `stage` so a
        failure says where it happened.
        expect_size = world bounding box (x, y, z) mm of all bodies, within `tol` mm; expect_volume in mm3 within
        `vol_tol` (0.2 % by default: tight enough to see a missing hole or fillet, so compute it by hand)."""
        import json
        bodies = []
        lo, hi = [1e18] * 3, [-1e18] * 3
        for body in self.root.bRepBodies:
            box = body.boundingBox
            low, high = [c / CM for c in box.minPoint.asArray()], [c / CM for c in box.maxPoint.asArray()]
            lo, hi = [min(a, b) for a, b in zip(lo, low)], [max(a, b) for a, b in zip(hi, high)]
            bodies.append({"name": body.name, "solid": body.isSolid, "min": [round(c, 3) for c in low],
                           "size": [round(h - l, 3) for l, h in zip(low, high)],
                           "volume_mm3": round(body.volume / CM ** 3, 2), "faces": body.faces.count})
        timeline = self.design.timeline
        unhealthy = [f"{timeline.item(i).name}: {timeline.item(i).errorOrWarningMessage}" for i in range(timeline.count)
                     if timeline.item(i).healthState != adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState]
        loose = [s.name for s in self.root.sketches if not s.isFullyConstrained]
        problems = [f"unhealthy: {u}" for u in unhealthy] + [f"sketch not fully constrained: {n}" for n in loose]
        problems += [f"body {b['name']} is not a solid" for b in bodies if not b["solid"]]
        size = [h - l for l, h in zip(lo, hi)] if bodies else [0, 0, 0]
        if expect_bodies is not None and len(bodies) != expect_bodies:
            problems.append(f"expected {expect_bodies} bodies, found {len(bodies)}")
        if expect_size is not None and any(abs(a - b) > tol for a, b in zip(size, expect_size)):
            problems.append(f"size {[round(s, 3) for s in size]} != expected {list(expect_size)}")
        if expect_volume is not None:
            total = sum(b["volume_mm3"] for b in bodies)
            if abs(total - expect_volume) > vol_tol * expect_volume:
                problems.append(f"volume {total} mm3 != expected {round(expect_volume, 2)} (off {abs(total - expect_volume):.2f})")
        cylinders = {}
        for body in self.root.bRepBodies:
            for face in body.faces:
                cylinder = adsk.core.Cylinder.cast(face.geometry)
                if cylinder:
                    key = str(round(cylinder.radius / CM, 3))
                    cylinders[key] = cylinders.get(key, 0) + 1
        now = open_documents()
        before = snapshots().get(self.doc.name)
        # A warning, not a problem: the user may legitimately save or close their own documents while this runs.
        changed = [d for d in (before or []) if d not in now]
        warnings = [f"other documents changed or closed since this model was made: {changed}"] if changed else []
        result = {"stage": stage, "document": self.doc.name, "bodies": bodies, "size_mm": [round(s, 3) for s in size],
                  "cylinder_radii_mm": cylinders, "features": timeline.count, "problems": problems,
                  "warnings": warnings}
        print(json.dumps(result))
        if strict and problems:
            raise RuntimeError(f"[{stage or 'report'}] " + "; ".join(problems))
        return result

    def export(self, outdir, stem, kinds=("f3d", "step", "stl")):
        """Write f3d / step / stl for the whole design into `outdir` (created) and verify each file exists."""
        self.doc.activate()
        folder = Path(outdir)
        folder.mkdir(parents=True, exist_ok=True)
        manager = self.design.exportManager
        written = []
        for kind in kinds:
            path = folder / f"{stem}.{kind}"
            if kind == "f3d":
                options = manager.createFusionArchiveExportOptions(str(path), self.root)
            elif kind == "step":
                options = manager.createSTEPExportOptions(str(path), self.root)
            elif kind == "stl":
                options = manager.createSTLExportOptions(self.root, str(path))
                options.isBinaryFormat = True
                options.sendToPrintUtility = False
                options.meshRefinement = adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
            else:
                raise ValueError(f"Unsupported export kind {kind!r}")
            if not manager.execute(options) or not path.is_file() or path.stat().st_size == 0:
                raise RuntimeError(f"Export failed: {path}")
            written.append(f"{path} ({path.stat().st_size} bytes)")
        print("exported: " + "; ".join(written))
        return written

    def views(self, outdir, stem, names=("iso",), size=(1200, 900)):
        """Save PNG views of the model with world Z up: iso, iso_back, iso_left, iso_left_back, top, bottom, front,
        back, right, left. "iso" looks from +x, -y, +z (the -y side is the "front"); pick "iso_back" when the
        interesting side faces +y, e.g. something that sticks out toward +y.

        Explicit world-axis cameras are used on purpose: Fusion's own view-cube names assume its up-axis
        preference (often Y), which shows Z-up models turned on their side."""
        up = (0, 0, 1)
        directions = {"iso": ((1, -1, 1), up), "iso_back": ((1, 1, 1), up), "iso_left": ((-1, -1, 1), up),
                      "iso_left_back": ((-1, 1, 1), up), "top": ((0, 0, 1), (0, 1, 0)),
                      "bottom": ((0, 0, -1), (0, 1, 0)), "front": ((0, -1, 0), up), "back": ((0, 1, 0), up),
                      "right": ((1, 0, 0), up), "left": ((-1, 0, 0), up)}
        self.doc.activate()
        folder = Path(outdir)
        folder.mkdir(parents=True, exist_ok=True)
        viewport = self.app.activeViewport
        box = self.root.boundingBox
        target = P(*[(a + b) / 2 for a, b in zip(box.minPoint.asArray(), box.maxPoint.asArray())])
        reach = max(b - a for a, b in zip(box.minPoint.asArray(), box.maxPoint.asArray())) * 5 + 10
        written = []
        for view in names:
            eye_direction, up = directions[view]
            camera = viewport.camera
            camera.cameraType = adsk.core.CameraTypes.OrthographicCameraType
            camera.target = target
            camera.eye = P(*[t + d * reach for t, d in zip(target.asArray(), eye_direction)])
            camera.upVector = adsk.core.Vector3D.create(*up)
            camera.isSmoothTransition = False
            camera.isFitView = True
            viewport.camera = camera
            viewport.fit()
            viewport.refresh()
            path = folder / f"{stem}_{view}.png"
            if not viewport.saveAsImageFile(str(path), size[0], size[1]):
                raise RuntimeError(f"Could not render {view}")
            written.append(str(path))
        print("views: " + "; ".join(written))
        return written

    def close(self):
        """Close this model without saving. Only documents made by ff.new() can be closed this way."""
        if registry().get(self.doc.name) != self.doc:
            raise RuntimeError("Refusing to close a document that ff.new() did not create")
        name = self.doc.name
        self.doc.close(False)
        registry().pop(name, None)


class Sketch:
    """A sketch with world-coordinate drawing and fully dimensioned, parameter-named geometry."""

    def __init__(self, model, sketch, normal_axis, level_mm):
        self.m, self.s, self.normal_axis, self.level = model, sketch, normal_axis, level_mm
        self.ui, self.vi = [a for a in range(3) if a != normal_axis]
        self.tag = re.sub(r"\W", "_", sketch.name)
        origin = sketch.sketchToModelSpace(P(0, 0, 0)).asArray()
        off_axis = [origin[a] / CM for a in range(3) if a != normal_axis]
        if any(abs(c) > 1e-3 for c in off_axis):
            raise RuntimeError("This sketch's origin is not the world origin's projection; "
                               "sketch on an offset 'xy'/'xz'/'yz' plane (at=...) instead of that face")
        o, pu, pv = self.point(0, 0), self.point(1, 0), self.point(0, 1)
        self.axis_of = {}
        for key, p in (("u", pu), ("v", pv)):
            dx, dy = p.x - o.x, p.y - o.y
            axis = 0 if abs(dx) > abs(dy) else 1
            self.axis_of[key] = (axis, 1 if (dx if axis == 0 else dy) > 0 else -1)

    def point(self, u, v):
        """World 2D coordinates (mm) -> sketch-space Point3D (cm)."""
        world = [0.0, 0.0, 0.0]
        world[self.ui], world[self.vi], world[self.normal_axis] = u * CM, v * CM, self.level * CM
        return self.s.modelToSketchSpace(P(*world))

    def normal_sign(self):
        """+1 if the sketch normal points along the +world axis of the plane normal, else -1."""
        a = self.s.sketchToModelSpace(P(0, 0, 0)).asArray()
        b = self.s.sketchToModelSpace(P(0, 0, 1)).asArray()
        return 1 if b[self.normal_axis] - a[self.normal_axis] > 0 else -1

    def _coords(self, u_expr, v_expr):
        """Per sketch axis: (expression of the sketch coordinate, its value in mm) for a world point."""
        out = [None, None]
        for key, text in (("u", u_expr), ("v", v_expr)):
            axis, sign = self.axis_of[key]
            out[axis] = (text if sign > 0 else f"-({text})", sign * self.m.mm(text))
        return out

    def _dimension(self, a, b, orientation, expression, value, role):
        ga, gb = a.geometry, b.geometry
        text_point = P((ga.x + gb.x) / 2 + 0.5, (ga.y + gb.y) / 2 + 0.5, 0)
        dimension = self.s.sketchDimensions.addDistanceDimension(a, b, orientation, text_point)
        dimension.parameter.expression = expression if value >= 0 else f"-({expression})"
        self.m.name_param(dimension.parameter, f"{self.tag}_{role}")

    def _anchor(self, point, coords):
        """Fix a sketch point relative to the origin: dimension each coordinate, or align it when it is 0."""
        origin, constraints = self.s.originPoint, self.s.geometricConstraints
        (x_expr, x_val), (y_expr, y_val) = coords
        if abs(x_val) < TOL and abs(y_val) < TOL:
            constraints.addCoincident(point, origin)
            return
        if abs(x_val) < TOL:
            constraints.addVerticalPoints(origin, point)
        else:
            self._dimension(origin, point, HORIZONTAL, x_expr, x_val, "x")
        if abs(y_val) < TOL:
            constraints.addHorizontalPoints(origin, point)
        else:
            self._dimension(origin, point, VERTICAL, y_expr, y_val, "y")

    def rect(self, u, v, w, h, center=False):
        """Rectangle with min corner (u, v) - or centre, with center=True - size w x h, fully dimensioned."""
        u_e, v_e, w_e, h_e = (expr(x) for x in (u, v, w, h))
        if center:
            u_e, v_e = f"({u_e}) - ({w_e}) / 2", f"({v_e}) - ({h_e}) / 2"
        u0, v0, du, dv = (self.m.mm(x) for x in (u_e, v_e, w_e, h_e))
        u0, v0 = u0 + NUDGE, v0 + NUDGE  # see NUDGE
        lines = self.s.sketchCurves.sketchLines.addTwoPointRectangle(self.point(u0, v0), self.point(u0 + du, v0 + dv))
        for i in range(lines.count):
            line = lines.item(i)
            if abs(line.startSketchPoint.geometry.y - line.endSketchPoint.geometry.y) < 1e-9:
                self.s.geometricConstraints.addHorizontal(line)
            else:
                self.s.geometricConstraints.addVertical(line)
        corners = {}
        for i in range(lines.count):
            for p in (lines.item(i).startSketchPoint, lines.item(i).endSketchPoint):
                corners[(round(p.geometry.x, 5), round(p.geometry.y, 5))] = p
        keys = list(corners)
        bl = corners[min(keys, key=lambda k: (k[0], k[1]))]
        br = corners[min(keys, key=lambda k: (-k[0], k[1]))]
        tl = corners[min(keys, key=lambda k: (k[0], -k[1]))]
        extent = [None, None]
        for key, size in (("u", w_e), ("v", h_e)):
            extent[self.axis_of[key][0]] = size
        corner_u = u_e if self.axis_of["u"][1] > 0 else f"({u_e}) + ({w_e})"
        corner_v = v_e if self.axis_of["v"][1] > 0 else f"({v_e}) + ({h_e})"
        self._dimension(bl, br, HORIZONTAL, extent[0], 1, "w")
        self._dimension(bl, tl, VERTICAL, extent[1], 1, "h")
        self._anchor(bl, self._coords(corner_u, corner_v))
        return lines

    def circle(self, u, v, diameter):
        """Circle centred at world (u, v) with the given diameter, fully dimensioned."""
        u_e, v_e, d_e = expr(u), expr(v), expr(diameter)
        u0, v0, d0 = self.m.mm(u_e), self.m.mm(v_e), self.m.mm(d_e)
        circle = self.s.sketchCurves.sketchCircles.addByCenterRadius(self.point(u0 + NUDGE, v0 + NUDGE), d0 / 2 * CM)
        centre = circle.geometry.center
        dimension = self.s.sketchDimensions.addDiameterDimension(circle, P(centre.x + d0 * CM, centre.y + d0 * CM, 0))
        dimension.parameter.expression = d_e
        self.m.name_param(dimension.parameter, f"{self.tag}_dia")
        self._anchor(circle.centerSketchPoint, self._coords(u_e, v_e))
        return circle
