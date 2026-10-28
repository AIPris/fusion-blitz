"""Golden reference builds for the benchmark tasks, made with fusion_fast. Used only to get exact expected
volume / bounding box / hole counts for grading - never shown to the agents under test."""
import json

import adsk.core

import fusion_fast as ff


def comb():
    m = ff.new("ZZ_golden_comb", replace=True)
    m.params(bar_l=90, bar_w=28, bar_h=12, slot_w=7, slot_d=8, slot_pitch=16, slots="5", hole_d=4.5, hole_x=4.75,
             corner_r=3)
    s = m.sketch("xy", name="Bar")
    s.rect(0, 0, "bar_l", "bar_w")
    m.extrude(s, "bar_h", body="Comb")
    cut = m.sketch("xy", at="bar_h", name="Slot")
    cut.rect("(bar_l - (slots - 1) * slot_pitch - slot_w) / 2", 0, "slot_w", "bar_w")
    slot = m.extrude(cut, "slot_d", op="cut", toward="-", name="Slot_Cut")
    m.pattern(slot, "x", "slots", "slot_pitch", name="Slot_Pattern")
    m.holes("xy", [("hole_x", "bar_w / 2"), ("bar_l - hole_x", "bar_w / 2")], "hole_d", at="bar_h", toward="-",
            name="Mount_Holes")
    m.fillet("Corner_Round", ("corner_r", m.edges(parallel="z", x=[0, 90], y=[0, 28])))
    m.settle("bar_l")
    return m.report("comb", expect_size=(90, 28, 12), expect_bodies=1)


def hook():
    m = ff.new("ZZ_golden_hook", replace=True)
    m.params(plate_w=50, plate_h=70, plate_t=5, hole_d=5, arm_d=12, arm_l=35, plate_r=4, arm_r=2)
    s = m.sketch("xz", name="Plate")
    s.rect(0, 0, "plate_w", "plate_h")
    m.extrude(s, "plate_t", toward="+", body="Hook")
    m.holes("xz", [("plate_w / 2", 12), ("plate_w / 2", "plate_h - 12")], "hole_d", at="plate_t", toward="-",
            name="Plate_Holes")
    a = m.sketch("xz", at="plate_t", name="Arm")
    a.circle("plate_w / 2", "plate_h / 2", "arm_d")
    m.extrude(a, "arm_l", op="join", toward="+", name="Arm")
    m.fillet("Rounds", ("plate_r", m.edges(parallel="y", x=[0, 50], z=[0, 70])),
             ("arm_r", m.edges(curve="circle", radius=6, y=[5, 40])))
    m.settle("plate_w")
    return m.report("hook", expect_size=(50, 40, 70), expect_bodies=1)


def box():
    m = ff.new("ZZ_golden_box", replace=True)
    m.params(box_x=70, box_y=50, box_z=30, wall=2.5, post_d=8, post_in=7.5, post_top=28, pilot_d=2.8, pilot_depth=12,
             vent_w=2, vent_h=14, vent_z=8, vent_pitch=6, vents="6", corner_r=5)
    s = m.sketch("xy", name="Outer")
    s.rect(0, 0, "box_x", "box_y")
    m.extrude(s, "box_z", body="Box")
    c = m.sketch("xy", at="box_z", name="Cavity")
    c.rect("wall", "wall", "box_x - 2 * wall", "box_y - 2 * wall")
    m.extrude(c, "box_z - wall", op="cut", toward="-", name="Cavity_Cut")
    corners = [("post_in", "post_in"), ("box_x - post_in", "post_in"), ("post_in", "box_y - post_in"),
               ("box_x - post_in", "box_y - post_in")]
    p = m.sketch("xy", at="wall", name="Posts")
    for u, v in corners:
        p.circle(u, v, "post_d")
    m.extrude(p, "post_top - wall", op="join", toward="+", name="Posts")
    m.holes("xy", corners, "pilot_d", depth="pilot_depth", toward="-", at="post_top", name="Pilot_Holes")
    v = m.sketch("xz", name="Vent")
    v.rect("(box_x - (vents - 1) * vent_pitch - vent_w) / 2", "vent_z", "vent_w", "vent_h")
    vent = m.extrude(v, "wall", op="cut", toward="+", name="Vent_Cut")
    m.pattern(vent, "x", "vents", "vent_pitch", name="Vent_Pattern")
    m.fillet("Corner_Round", ("corner_r", m.edges(parallel="z", x=[0, 70], y=[0, 50])))
    m.settle("box_x")
    return m.report("box", expect_size=(70, 50, 30), expect_bodies=1)


def facts(m_name):
    """Volume, bbox and cylinder-face counts by radius, read back from the finished golden document."""
    app = adsk.core.Application.get()
    m = ff.open_model(m_name)
    body = m.root.bRepBodies.item(0)
    radii = {}
    for face in body.faces:
        cyl = adsk.core.Cylinder.cast(face.geometry)
        if cyl:
            key = round(cyl.radius / ff.CM, 3)
            radii[key] = radii.get(key, 0) + 1
    return {"volume_mm3": round(body.volume / ff.CM ** 3, 3), "faces": body.faces.count,
            "cylinder_faces_by_radius_mm": radii}


def run_all():
    out = {}
    for name, build in (("ZZ_golden_comb", comb), ("ZZ_golden_hook", hook), ("ZZ_golden_box", box)):
        build()
        out[name] = facts(name)
        ff.open_model(name).close()
    print(json.dumps(out))
