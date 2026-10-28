"""Golden Fusion build of the `spool` benchmark task.

Made with fusion_fast for the features it wraps and raw Fusion API calls for what it does not (revolve, loft, construction
axes, a skew work plane, circular pattern). It proves the task can be built in Fusion and gives the Fusion-side facts;
the agents under test never see it. The independent reference is reference_spool.py (build123d).
"""
import json
import math

import adsk.core
import adsk.fusion

import fusion_fast as ff

NAME = "ZZ_golden_spool"
CM, NUDGE, P = ff.CM, ff.NUDGE, ff.P

PARAMS = dict(
    pipe_od=88.9, wall=5, pipe_id="pipe_od - 2 * wall", red_od=60.3, red_id="red_od - 2 * wall",
    run1_end=160, bend_r=150, riser_x="run1_end + bend_r", riser_top=250, red_end=330, ecc=14.3, out_end=398,
    f1_od=200, f1_t=20, f1_pcd=160, f1_hole=18, hub_d0=116, hub_end=60,
    groove1_id=104, groove1_od=114, groove1_depth=3,
    f2_od=165, f2_t=18, f2_pcd=125, f2_hole=18, groove2_id=66, groove2_od=78, groove2_depth=2.5,
    chamfer_d=1.5, rib_t=8, rib_r0=28, rib_r1=60, rib_h=40,
    boss_d=30, boss_len=70, boss_hole=12, boss_hole_from=30,
    lug_t=10, lug_z0=175, lug_z1=225, lug_reach=70, lug_r=25, lug_hole=25, lug_fillet=4, boss_angle="45 deg",
)


# ---- raw-API helpers -----------------------------------------------------------------------------------------------

def plane_at(m, key, at):
    """Offset construction plane parallel to xy / xz / yz (sign of the offset follows the plane's normal)."""
    base = {"xy": m.root.xYConstructionPlane, "xz": m.root.xZConstructionPlane, "yz": m.root.yZConstructionPlane}[key]
    direction = base.geometry.normal.asArray()[ff.PLANE_NORMAL[key]]
    plane_input = m.root.constructionPlanes.createInput()
    plane_input.setByOffset(base, ff.vi(at if direction > 0 else f"-({ff.expr(at)})"))
    return m.root.constructionPlanes.add(plane_input)


def axis_from_planes(m, plane_a, plane_b):
    axes = m.root.constructionAxes
    axis_input = axes.createInput()
    axis_input.setByTwoPlanes(plane_a, plane_b)
    return axes.add(axis_input)


def loft(m, sketch_a, sketch_b, op, name):
    features = m.root.features.loftFeatures
    loft_input = features.createInput(ff.OPERATIONS[op])
    loft_input.loftSections.add(sketch_a.s.profiles.item(0))
    loft_input.loftSections.add(sketch_b.s.profiles.item(0))
    loft_input.isSolid = True
    feature = features.add(loft_input)
    feature.name = name
    sketch_a.s.isLightBulbOn = sketch_b.s.isLightBulbOn = False
    return feature


def revolve(m, sketch, axis, angle, op, name):
    features = m.root.features.revolveFeatures
    revolve_input = features.createInput(sketch.s.profiles.item(0), axis, ff.OPERATIONS[op])
    revolve_input.setAngleExtent(False, ff.vi(angle))
    feature = features.add(revolve_input)
    feature.name = name
    sketch.s.isLightBulbOn = False
    return feature


def ring_profile_index(sketch, inner_d, outer_d):
    """Index of the annulus between two concentric circles (the profile whose area matches)."""
    target = math.pi * ((outer_d / 2) ** 2 - (inner_d / 2) ** 2) * CM ** 2
    for i in range(sketch.s.profiles.count):
        if abs(sketch.s.profiles.item(i).areaProperties().area - target) < 1e-6:
            return i
    raise RuntimeError("ring profile not found")


def right_triangle(sketch, corner, du, dv, du_expr, dv_expr):
    """Right triangle with its right angle at world 2D `corner` (expressions), legs du / dv mm (signed numbers) whose
    lengths are the expressions du_expr / dv_expr. Fully constrained."""
    m = sketch.m
    u0, v0 = m.mm(corner[0]) + NUDGE, m.mm(corner[1]) + NUDGE
    lines = sketch.s.sketchCurves.sketchLines
    leg_u = lines.addByTwoPoints(sketch.point(u0, v0), sketch.point(u0 + du, v0))
    leg_v = lines.addByTwoPoints(leg_u.startSketchPoint, sketch.point(u0, v0 + dv))
    lines.addByTwoPoints(leg_u.endSketchPoint, leg_v.endSketchPoint)
    for leg, expression in ((leg_u, du_expr), (leg_v, dv_expr)):
        a, b = leg.startSketchPoint.geometry, leg.endSketchPoint.geometry
        horizontal = abs(a.y - b.y) < 1e-9
        (sketch.s.geometricConstraints.addHorizontal if horizontal else sketch.s.geometricConstraints.addVertical)(leg)
        orientation = ff.HORIZONTAL if horizontal else ff.VERTICAL
        sketch._dimension(leg.startSketchPoint, leg.endSketchPoint, orientation, expression, (b.x - a.x) if horizontal else (b.y - a.y), "leg")
    sketch._anchor(leg_u.startSketchPoint, sketch._coords(ff.expr(corner[0]), ff.expr(corner[1])))


def skew_plane(m):
    """Plane perpendicular to the boss axis through the centreline point at boss_angle. setByPlane only works in direct
    modelling, so the plane is made parametrically: the line through that point along y, rotated out of the xy plane."""
    plane_x = plane_at(m, "yz", "run1_end + bend_r * sin(boss_angle)")
    plane_z = plane_at(m, "xy", "bend_r - bend_r * cos(boss_angle)")
    line = axis_from_planes(m, plane_x, plane_z)
    plane_input = m.root.constructionPlanes.createInput()
    plane_input.setByAngle(line, ff.vi("boss_angle"), plane_z)
    return m.root.constructionPlanes.add(plane_input)


def offset_along_normal(m, plane, distance, target_mm):
    """Plane `distance` (expression) away from `plane`, on the side that contains target_mm."""
    for sign in ("", "-"):
        plane_input = m.root.constructionPlanes.createInput()
        plane_input.setByOffset(plane, ff.vi(f"{sign}({distance})"))
        candidate = m.root.constructionPlanes.add(plane_input)
        if plane_gap(candidate, target_mm) < 1e-3:
            return candidate
        candidate.deleteMe()
    raise RuntimeError("offset plane does not reach the target point")


def plane_gap(construction_plane, point_mm):
    """Distance (mm) of a point from a construction plane."""
    g = construction_plane.geometry
    v = [c * CM - o for c, o in zip(point_mm, g.origin.asArray())]
    return abs(sum(a * b for a, b in zip(v, g.normal.asArray()))) / CM


def skew_sketch(m, plane, name):
    sketch = m.root.sketches.add(plane)
    sketch.name = name
    for curve in [c for c in sketch.sketchCurves if c.isReference]:
        curve.deleteMe()
    return sketch


def skew_circle(m, sketch, centre_mm, diameter, role):
    """Circle on a skew sketch: diameter is an expression, the centre is placed from the sketch origin."""
    centre = sketch.modelToSketchSpace(P(*[c * CM for c in centre_mm]))
    d0 = m.mm(diameter)
    circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(P(centre.x + NUDGE * CM, centre.y + NUDGE * CM, 0), d0 / 2 * CM)
    dimension = sketch.sketchDimensions.addDiameterDimension(circle, P(centre.x + d0 * CM, centre.y + d0 * CM, 0))
    dimension.parameter.expression = diameter
    m.name_param(dimension.parameter, f"{role}_dia")
    origin, constraints = sketch.originPoint, sketch.geometricConstraints
    cx, cy = centre.x / CM, centre.y / CM
    if abs(cx) < 1e-6 and abs(cy) < 1e-6:
        constraints.addCoincident(circle.centerSketchPoint, origin)
        return circle
    for value, orientation, align in ((cx, ff.HORIZONTAL, constraints.addVerticalPoints), (cy, ff.VERTICAL, constraints.addHorizontalPoints)):
        if abs(value) < 1e-6:
            align(origin, circle.centerSketchPoint)
        else:
            text_point = P((origin.geometry.x + circle.centerSketchPoint.geometry.x) / 2 + 0.5, (origin.geometry.y + circle.centerSketchPoint.geometry.y) / 2 + 0.5, 0)
            dim = sketch.sketchDimensions.addDistanceDimension(origin, circle.centerSketchPoint, orientation, text_point)
            dim.parameter.expression = f"{value:.6f} mm"
            m.name_param(dim.parameter, f"{role}_pos")
    return circle


def extrude_skew(m, sketch, direction, distance, op, name):
    """Extrude the sketch's first profile `distance` (expression) along world `direction`."""
    a = sketch.sketchToModelSpace(P(0, 0, 0)).asArray()
    b = sketch.sketchToModelSpace(P(0, 0, 1)).asArray()
    along = sum((y - x) * d for x, y, d in zip(a, b, direction)) > 0
    features = m.root.features.extrudeFeatures
    extrude_input = features.createInput(sketch.profiles.item(0), ff.OPERATIONS[op])
    extrude_input.setOneSideExtent(adsk.fusion.DistanceExtentDefinition.create(ff.vi(distance)),
                                   adsk.fusion.ExtentDirections.PositiveExtentDirection if along else adsk.fusion.ExtentDirections.NegativeExtentDirection)
    feature = features.add(extrude_input)
    feature.name = name
    sketch.isLightBulbOn = False
    return feature


def circle_edges(body, centre_mm, radius_mm):
    found = adsk.core.ObjectCollection.create()
    for edge in body.edges:
        circle = adsk.core.Circle3D.cast(edge.geometry)
        if circle and abs(circle.radius / CM - radius_mm) < 1e-3 and all(abs(a / CM - b) < 1e-2 for a, b in zip(circle.center.asArray(), centre_mm)):
            found.add(edge)
    return found


def lug_junction_edges(body, axis_x, radius_mm, z_low, z_high):
    """Edges where a lug's flat faces meet the riser's outer cylinder."""
    found = adsk.core.ObjectCollection.create()
    for edge in body.edges:
        if edge.faces.count != 2:
            continue
        faces = [edge.faces.item(0), edge.faces.item(1)]
        on_pipe = any((c := adsk.core.Cylinder.cast(f.geometry)) and abs(c.radius / CM - radius_mm) < 1e-3
                      and abs(c.origin.x / CM - axis_x) < 1e-3 and abs(c.origin.y / CM) < 1e-3 and abs(abs(c.axis.z) - 1) < 1e-6 for f in faces)
        on_plane = any(adsk.core.Plane.cast(f.geometry) for f in faces)
        box = edge.boundingBox
        if on_pipe and on_plane and box.minPoint.z / CM >= z_low - 1e-3 and box.maxPoint.z / CM <= z_high + 1e-3:
            found.add(edge)
    return found


def facts(m):
    body = m.root.bRepBodies.item(0)
    props = body.getPhysicalProperties(adsk.fusion.CalculationAccuracy.VeryHighCalculationAccuracy)
    com = props.centerOfMass.asArray()
    box = body.boundingBox
    radii = sorted({round(adsk.core.Cylinder.cast(f.geometry).radius / CM, 3) for f in body.faces if adsk.core.Cylinder.cast(f.geometry)})
    return {"solids": m.root.bRepBodies.count, "volume": round(props.volume / CM ** 3, 3), "area": round(props.area / CM ** 2, 3),
            "com": [round(c / CM, 3) for c in com], "min": [round(c / CM, 3) for c in box.minPoint.asArray()],
            "size": [round((h - l) / CM, 3) for l, h in zip(box.minPoint.asArray(), box.maxPoint.asArray())],
            "faces": body.faces.count, "features": m.design.timeline.count, "cylinder_radii": radii}


# ---- the build -----------------------------------------------------------------------------------------------------

def build(out_dir=None):
    m = ff.new(NAME, replace=True)
    m.params(**PARAMS)

    # Inlet flange (axis +x), rim chamfered
    s = m.sketch("yz", at=0, name="Inlet_Flange")
    s.circle(0, 0, "f1_od")
    m.extrude(s, "f1_t", toward="+", body="Spool", name="Inlet_Flange")
    m.chamfer("Inlet_Rim_Chamfer", "chamfer_d", m.edges(curve="circle", radius=m.mm("f1_od") / 2, x=[0, m.mm("f1_t")]))
    # Weld-neck hub: loft from dia 116 at x=20 to the pipe OD at x=60
    hub_a, hub_b = m.sketch("yz", at="f1_t", name="Hub_Start"), m.sketch("yz", at="hub_end", name="Hub_End")
    hub_a.circle(0, 0, "hub_d0")
    hub_b.circle(0, 0, "pipe_od")
    loft(m, hub_a, hub_b, "join", "Hub")
    # Straight inlet run
    s = m.sketch("yz", at="hub_end", name="Run1")
    s.circle(0, 0, "pipe_od")
    m.extrude(s, "run1_end - hub_end", op="join", toward="+", name="Run1")
    # Elbow: circle revolved 90 degrees about the bend axis (x = run1_end, z = bend_r, along y)
    bend_axis = axis_from_planes(m, plane_at(m, "yz", "run1_end"), plane_at(m, "xy", "bend_r"))
    s = m.sketch("yz", at="run1_end", name="Elbow_Profile")
    s.circle(0, 0, "pipe_od")
    revolve(m, s, bend_axis, "90 deg", "join", "Elbow")
    # Vertical run
    s = m.sketch("xy", at="bend_r", name="Riser")
    s.circle("riser_x", 0, "pipe_od")
    m.extrude(s, "riser_top - bend_r", op="join", toward="+", name="Riser")
    # Eccentric reducer
    red_a, red_b = m.sketch("xy", at="riser_top", name="Reducer_Start"), m.sketch("xy", at="red_end", name="Reducer_End")
    red_a.circle("riser_x", 0, "pipe_od")
    red_b.circle("riser_x", "ecc", "red_od")
    loft(m, red_a, red_b, "join", "Reducer")
    # Outlet run and outlet flange
    s = m.sketch("xy", at="red_end", name="Outlet_Run")
    s.circle("riser_x", "ecc", "red_od")
    m.extrude(s, "out_end - red_end", op="join", toward="+", name="Outlet_Run")
    s = m.sketch("xy", at="out_end - f2_t", name="Outlet_Flange")
    s.circle("riser_x", "ecc", "f2_od")
    m.extrude(s, "f2_t", op="join", toward="+", name="Outlet_Flange")
    m.chamfer("Outlet_Rim_Chamfer", "chamfer_d", m.edges(curve="circle", radius=m.mm("f2_od") / 2,
                                                         z=[m.mm("out_end - f2_t"), m.mm("out_end")]))
    m.report("body, no details yet", expect_bodies=1)

    # Gusset rib under the outlet flange, patterned 4x about the outlet axis
    s = m.sketch("xz", at="ecc", name="Rib")
    right_triangle(s, ("riser_x + rib_r0", "out_end - f2_t"), m.mm("rib_r1 - rib_r0"), -m.mm("rib_h"), "rib_r1 - rib_r0", "rib_h")
    rib = m.extrude(s, "rib_t", op="join", toward="sym", name="Rib")
    outlet_axis = axis_from_planes(m, plane_at(m, "yz", "riser_x"), plane_at(m, "xz", "ecc"))
    entities = adsk.core.ObjectCollection.create()
    entities.add(rib)
    pattern_input = m.root.features.circularPatternFeatures.createInput(entities, outlet_axis)
    pattern_input.quantity = ff.vi("4")
    pattern_input.totalAngle = ff.vi("360 deg")
    pattern_input.isSymmetric = False
    m.root.features.circularPatternFeatures.add(pattern_input).name = "Rib_Pattern"

    # Boss on the elbow at 45 degrees, axis radially outward through the centreline
    a = m.design.userParameters.itemByName("boss_angle").value      # radians
    run1_end, bend_r = m.mm("run1_end"), m.mm("bend_r")
    centre = (run1_end + bend_r * math.sin(a), 0.0, bend_r - bend_r * math.cos(a))
    direction = (math.sin(a), 0.0, -math.cos(a))
    at = lambda s_mm: tuple(c + d * s_mm for c, d in zip(centre, direction))
    boss_plane = skew_plane(m)
    if plane_gap(boss_plane, centre) > 1e-3 or abs(abs(sum(a * b for a, b in zip(boss_plane.geometry.normal.asArray(), direction))) - 1) > 1e-6:
        raise RuntimeError("boss plane is not perpendicular to the boss axis through the centreline point")
    boss_sketch = skew_sketch(m, boss_plane, "Boss")
    skew_circle(m, boss_sketch, centre, "boss_d", "boss")
    extrude_skew(m, boss_sketch, direction, "boss_len", "join", "Boss")
    m.chamfer("Boss_Chamfer", "chamfer_d", circle_edges(m.body(), at(m.mm("boss_len")), m.mm("boss_d") / 2))

    # Two lifting lugs on the vertical run, then fillets where they meet the pipe
    s = m.sketch("xz", at=0, name="Lugs")
    s.rect("riser_x - lug_reach", "lug_z0", "2 * lug_reach", "lug_z1 - lug_z0")
    for sign in ("+", "-"):
        s.circle(f"riser_x {sign} lug_reach", "(lug_z0 + lug_z1) / 2", "2 * lug_r")
    m.extrude(s, "lug_t", op="join", toward="sym", name="Lugs")
    edges = lug_junction_edges(m.body(), m.mm("riser_x"), m.mm("pipe_od") / 2, m.mm("lug_z0"), m.mm("lug_z1"))
    m.fillet("Lug_Fillets", ("lug_fillet", edges))
    m.report("positive features done", expect_bodies=1)

    # Face grooves
    s = m.sketch("yz", at=0, name="Inlet_Groove")
    s.circle(0, 0, "groove1_od")
    s.circle(0, 0, "groove1_id")
    m.extrude(s, "groove1_depth", op="cut", toward="+", profiles=[ring_profile_index(s, m.mm("groove1_id"), m.mm("groove1_od"))], name="Inlet_Groove")
    s = m.sketch("xy", at="out_end", name="Outlet_Groove")
    s.circle("riser_x", "ecc", "groove2_od")
    s.circle("riser_x", "ecc", "groove2_id")
    m.extrude(s, "groove2_depth", op="cut", toward="-", profiles=[ring_profile_index(s, m.mm("groove2_id"), m.mm("groove2_od"))], name="Outlet_Groove")
    # Bolt holes (angles from +z towards +y on the inlet; from +x towards +y on the outlet; both sets are symmetric)
    inlet_points = [(f"f1_pcd / 2 * sin({22.5 + 45 * k} deg)", f"f1_pcd / 2 * cos({22.5 + 45 * k} deg)") for k in range(8)]
    m.holes("yz", inlet_points, "f1_hole", depth="f1_t", toward="+", at=0, name="Inlet_Bolt_Holes")
    outlet_points = [(f"riser_x + f2_pcd / 2 * cos({45 + 90 * k} deg)", f"ecc + f2_pcd / 2 * sin({45 + 90 * k} deg)") for k in range(4)]
    m.holes("xy", outlet_points, "f2_hole", depth="f2_t", toward="-", at="out_end", name="Outlet_Bolt_Holes")
    # Lug holes through the plate thickness
    m.holes("xz", [("riser_x + lug_reach", "(lug_z0 + lug_z1) / 2"), ("riser_x - lug_reach", "(lug_z0 + lug_z1) / 2")],
            "lug_hole", depth="lug_t + 2 mm", toward="-", at="lug_t / 2 + 1 mm", name="Lug_Holes")

    # Bore: straight inlet, elbow, riser, eccentric reducer, outlet
    s = m.sketch("yz", at=0, name="Bore_Inlet")
    s.circle(0, 0, "pipe_id")
    m.extrude(s, "run1_end", op="cut", toward="+", name="Bore_Inlet")
    s = m.sketch("yz", at="run1_end", name="Bore_Elbow_Profile")
    s.circle(0, 0, "pipe_id")
    revolve(m, s, bend_axis, "90 deg", "cut", "Bore_Elbow")
    s = m.sketch("xy", at="bend_r", name="Bore_Riser")
    s.circle("riser_x", 0, "pipe_id")
    m.extrude(s, "riser_top - bend_r", op="cut", toward="+", name="Bore_Riser")
    bore_a, bore_b = m.sketch("xy", at="riser_top", name="Bore_Reducer_Start"), m.sketch("xy", at="red_end", name="Bore_Reducer_End")
    bore_a.circle("riser_x", 0, "pipe_id")
    bore_b.circle("riser_x", "ecc", "red_id")
    loft(m, bore_a, bore_b, "cut", "Bore_Reducer")
    s = m.sketch("xy", at="red_end", name="Bore_Outlet")
    s.circle("riser_x", "ecc", "red_id")
    m.extrude(s, "out_end - red_end", op="cut", toward="+", name="Bore_Outlet")
    # Boss hole: dia 12, from the end of the boss down to 30 mm from the centreline (breaks into the bore)
    hole_at = at(m.mm("boss_hole_from"))
    hole_sketch = skew_sketch(m, offset_along_normal(m, boss_plane, "boss_hole_from", hole_at), "Boss_Hole")
    skew_circle(m, hole_sketch, hole_at, "boss_hole", "boss_hole")
    extrude_skew(m, hole_sketch, direction, "boss_len - boss_hole_from + 1 mm", "cut", "Boss_Hole")

    m.report("finished", expect_bodies=1)
    print("FACTS " + json.dumps(facts(m)))
    for item in (*m.root.constructionPlanes, *m.root.constructionAxes):      # keep the preview images clean
        item.isLightBulbOn = False
    if out_dir:
        m.export(out_dir, "spool")
        m.views(out_dir, "spool", names=("iso", "iso_back"))
    return m
