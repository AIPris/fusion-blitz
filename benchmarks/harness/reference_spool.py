"""Independent reference for the `spool` benchmark task: a flanged eccentric elbow spool.

Built with build123d (OpenCascade) from explicit solids and booleans. It uses neither Fusion nor the fusion_fast
helper, so the expected values it yields (volume, centre of mass, bounding box) do not come from the tool under test.

usage: uv run --python 3.12 --with build123d-mcp==0.3.91 python reference_spool.py [--probes] [out.step]
  prints the facts of the finished solid; --probes also checks every grader probe point against it
"""
import json
import math
import sys

from build123d import Axis, CenterOf, Face, GeomType, Location, Plane, Solid, Vector, Vertex, Wire, export_step

import spool_probes

# ---- dimensions, mm ------------------------------------------------------------------------------------------------
OD1, ID1 = 88.9, 78.9            # main pipe
OD2, ID2 = 60.3, 50.3            # reduced pipe
RUN1_END = 160.0                 # straight inlet run ends here (x); the bend starts
R_BEND = 150.0                   # centreline bend radius, 90 degrees, towards +Z
RISER_X = RUN1_END + R_BEND      # x of the vertical run
RUN2_Z0, RUN2_Z1 = R_BEND, 250.0     # vertical run
RED_Z0, RED_Z1, ECC = 250.0, 330.0, 14.3   # eccentric reducer, offset towards +Y
OUT_Z_END = 398.0                # outlet face
OUT_X, OUT_Y = RISER_X, ECC      # outlet axis
F1_OD, F1_T, F1_PCD, F1_HOLES, F1_HOLE_D = 200.0, 20.0, 160.0, 8, 18.0
HUB_D0, HUB_END = 116.0, 60.0    # hub: dia 116 at the flange back (x=20) tapering to the pipe OD at x=60
GROOVE1 = (104.0, 114.0, 3.0)    # inner dia, outer dia, depth (inlet face)
F2_OD, F2_T, F2_PCD, F2_HOLES, F2_HOLE_D = 165.0, 18.0, 125.0, 4, 18.0
GROOVE2 = (66.0, 78.0, 2.5)      # outlet face
CHAMFER = 1.5                    # flange rims and boss end
RIB_T, RIB_R0, RIB_R1, RIB_H = 8.0, 28.0, 60.0, 40.0
BOSS_D, BOSS_LEN, BOSS_HOLE_D, BOSS_HOLE_FROM, BOSS_ANGLE = 30.0, 70.0, 12.0, 30.0, 45.0
LUG_T, LUG_Z0, LUG_Z1, LUG_REACH, LUG_R, LUG_HOLE_D, LUG_FILLET = 10.0, 175.0, 225.0, 70.0, 25.0, 25.0, 4.0


def plane(origin, direction):
    return Plane(origin=origin, z_dir=direction)


def cyl(r, h, origin, direction):
    return Solid.make_cylinder(r, h, plane(origin, direction))


def circle_wire(r, origin, direction):
    return Wire.make_circle(r, plane(origin, direction))


def rim_chamfered_disc(r, h, origin, direction):
    disc = cyl(r, h, origin, direction)
    return disc.chamfer(CHAMFER, None, disc.edges().filter_by(GeomType.CIRCLE))


def ring_tool(groove, origin, direction):
    """Annular groove cutter, started 1 mm outside the face so the cut is clean."""
    d_in, d_out, depth = groove
    start = Vector(*origin) - Vector(*direction)
    at = (start.X, start.Y, start.Z)
    return cyl(d_out / 2, depth + 1, at, direction) - cyl(d_in / 2, depth + 1, at, direction)


def elbow(r):
    """Torus section: circle of radius r revolved 90 degrees about the bend axis (through (160, 0, 150), along -Y)."""
    face = Face(circle_wire(r, (RUN1_END, 0, 0), (1, 0, 0)))
    return Solid.revolve(face, 90, Axis((RUN1_END, 0, R_BEND), (0, -1, 0)))


def reducer(r0, r1):
    """Straight-sided (ruled) transition from the main to the reduced circle, offset by ECC."""
    return Solid.make_loft([circle_wire(r0, (RISER_X, 0, RED_Z0), (0, 0, 1)),
                            circle_wire(r1, (OUT_X, OUT_Y, RED_Z1), (0, 0, 1))], True)


def bolt_circle(count, pcd, first_deg, hole_d, origin, direction, length, start_offset):
    """Cylinders on a bolt circle. The sets used are symmetric, so the sense of the angle does not matter."""
    ox, oy, oz = origin
    tools = []
    for k in range(count):
        a = math.radians(first_deg + 360.0 / count * k)
        if direction == (1, 0, 0):      # inlet: angle from +Z towards +Y in the YZ plane
            c = (ox + start_offset, oy + pcd / 2 * math.sin(a), oz + pcd / 2 * math.cos(a))
        else:                           # outlet: angle from +X towards +Y in the XY plane
            c = (ox + pcd / 2 * math.cos(a), oy + pcd / 2 * math.sin(a), oz + start_offset)
        tools.append(cyl(hole_d / 2, length, c, direction))
    return tools


def rib(index):
    y0 = OUT_Y - RIB_T / 2
    z_top = OUT_Z_END - F2_T
    pts = [Vector(OUT_X + RIB_R0, y0, z_top), Vector(OUT_X + RIB_R1, y0, z_top), Vector(OUT_X + RIB_R0, y0, z_top - RIB_H)]
    solid = Solid.extrude(Face(Wire.make_polygon(pts, close=True)), Vector(0, RIB_T, 0))
    return solid.rotate(Axis((OUT_X, OUT_Y, 0), (0, 0, 1)), 90 * index)


def boss_axis():
    a = math.radians(BOSS_ANGLE)
    p = (RUN1_END + R_BEND * math.sin(a), 0.0, R_BEND - R_BEND * math.cos(a))   # centreline point
    d = (math.sin(a), 0.0, -math.cos(a))                                           # outward, away from the bend centre
    return p, d


def along(p, d, s):
    return (p[0] + d[0] * s, p[1] + d[1] * s, p[2] + d[2] * s)


def riser_with_lugs():
    """Vertical run plus both lifting lugs, with the lug-to-pipe fillets."""
    riser = cyl(OD1 / 2, RUN2_Z1 - RUN2_Z0, (RISER_X, 0, RUN2_Z0), (0, 0, 1))
    zc, h = (LUG_Z0 + LUG_Z1) / 2, LUG_Z1 - LUG_Z0
    box = Solid.make_box(LUG_REACH, LUG_T, h).moved(Location((RISER_X, -LUG_T / 2, LUG_Z0)))
    end = cyl(LUG_R, LUG_T, (RISER_X + LUG_REACH, -LUG_T / 2, zc), (0, 1, 0))
    lug_a = box.fuse(end)
    lug_b = lug_a.mirror(plane((RISER_X, 0, 0), (1, 0, 0)))
    body = riser.fuse(lug_a, lug_b)

    def on_junction(edge):
        pts = [edge @ t for t in (0.0, 0.5, 1.0)]
        on_pipe = all(abs(math.hypot(p.X - RISER_X, p.Y) - OD1 / 2) < 1e-4 for p in pts)
        in_lug = all(LUG_Z0 - 1e-4 <= p.Z <= LUG_Z1 + 1e-4 for p in pts)
        return on_pipe and in_lug and abs(pts[0].Y - pts[2].Y) + abs(pts[0].Z - pts[2].Z) > 1e-3

    return body.fillet(LUG_FILLET, [e for e in body.edges() if on_junction(e)])


def build():
    inlet = rim_chamfered_disc(F1_OD / 2, F1_T, (0, 0, 0), (1, 0, 0))
    hub = Solid.make_cone(HUB_D0 / 2, OD1 / 2, HUB_END - F1_T, plane((F1_T, 0, 0), (1, 0, 0)))
    run1 = cyl(OD1 / 2, RUN1_END - HUB_END, (HUB_END, 0, 0), (1, 0, 0))
    run3 = cyl(OD2 / 2, OUT_Z_END - RED_Z1, (OUT_X, OUT_Y, RED_Z1), (0, 0, 1))
    outlet = rim_chamfered_disc(F2_OD / 2, F2_T, (OUT_X, OUT_Y, OUT_Z_END - F2_T), (0, 0, 1))
    p, d = boss_axis()
    boss = cyl(BOSS_D / 2, BOSS_LEN, p, d)
    boss_end = Vector(*along(p, d, BOSS_LEN))
    boss = boss.chamfer(CHAMFER, None, [e for e in boss.edges().filter_by(GeomType.CIRCLE) if (e.arc_center - boss_end).length < 1e-6])
    parts = [inlet, hub, run1, elbow(OD1 / 2), riser_with_lugs(), reducer(OD1 / 2, OD2 / 2), run3, outlet,
             *[rib(i) for i in range(4)], boss]
    body = parts[0].fuse(*parts[1:])

    cuts = [ring_tool(GROOVE1, (0, 0, 0), (1, 0, 0)),
            ring_tool(GROOVE2, (OUT_X, OUT_Y, OUT_Z_END), (0, 0, -1)),
            *bolt_circle(F1_HOLES, F1_PCD, 22.5, F1_HOLE_D, (0, 0, 0), (1, 0, 0), F1_T + 2, -1),
            *bolt_circle(F2_HOLES, F2_PCD, 45.0, F2_HOLE_D, (OUT_X, OUT_Y, OUT_Z_END - F2_T), (0, 0, 1), F2_T + 2, -1),
            cyl(BOSS_HOLE_D / 2, BOSS_LEN - BOSS_HOLE_FROM + 1, along(p, d, BOSS_HOLE_FROM), d)]
    for sign in (1, -1):    # lug holes, through the plate thickness
        cuts.append(cyl(LUG_HOLE_D / 2, LUG_T + 2, (RISER_X + sign * LUG_REACH, -LUG_T / 2 - 1, (LUG_Z0 + LUG_Z1) / 2), (0, 1, 0)))
    # The bore tools abut each other, so fuse them into one tool first: cutting them as separate tools in a single
    # boolean loses about 100 mm3. OpenCascade flags the finished solid invalid at the dia 12 hole / bore intersection
    # until ShapeFix has run; fix() does not change the volume (1719781.86 mm3 before and after in a variant without
    # the boss chamfer).
    bore = cyl(ID1 / 2, RUN1_END + 1, (-1, 0, 0), (1, 0, 0)).fuse(
        elbow(ID1 / 2), cyl(ID1 / 2, RUN2_Z1 - RUN2_Z0, (RISER_X, 0, RUN2_Z0), (0, 0, 1)), reducer(ID1 / 2, ID2 / 2),
        cyl(ID2 / 2, OUT_Z_END - RED_Z1 + 1, (OUT_X, OUT_Y, RED_Z1), (0, 0, 1)))
    return body.cut(*cuts).cut(bore).fix()


def facts(shape):
    box = shape.bounding_box()
    com = shape.center(CenterOf.MASS)
    radii = sorted({round(f.radius, 3) for f in shape.faces() if f.geom_type == GeomType.CYLINDER})
    return {"solids": len(shape.solids()), "valid": shape.is_valid, "volume": round(shape.volume, 3), "area": round(shape.area, 3),
            "com": [round(com.X, 3), round(com.Y, 3), round(com.Z, 3)],
            "min": [round(box.min.X, 3), round(box.min.Y, 3), round(box.min.Z, 3)],
            "size": [round(box.size.X, 3), round(box.size.Y, 3), round(box.size.Z, 3)],
            "faces": len(shape.faces()), "cylinder_radii": radii}


def check_probes(shape):
    """Every grader probe must be classified as expected and sit at least 0.2 mm from any surface."""
    wrong, close = [], []
    for state, points in spool_probes.probes().items():
        for point in points:
            if shape.is_inside(Vector(*point)) != (state == "inside"):
                wrong.append([state, point])
            if min(Vertex(*point).distance_to(face) for face in shape.faces()) < 0.2:
                close.append([state, point])
    return {"probes": sum(len(v) for v in spool_probes.probes().values()), "misclassified": wrong, "closer_than_0.2mm": close}


if __name__ == "__main__":
    result = build()
    print(json.dumps(facts(result)))
    if "--probes" in sys.argv:
        print(json.dumps(check_probes(result)))
    step = [a for a in sys.argv[1:] if not a.startswith("--")]
    if step:
        export_step(result, step[0])
