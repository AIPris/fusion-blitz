"""Wall hook: 50 x 70 x 5 mm plate (back on y = 0, bottom on z = 0), two 5 mm holes, a 12 mm x 35 mm round arm
sticking out of the front face (+y). R4 plate corners, R2 arm tip, R2 arm/plate joint."""
import math
import os

import fusion_fast as ff

NAME = "ZZ_bench_hook_skill"


def ring_fillet_volume(r, big_r, concave):
    """Volume (mm3) a constant-radius fillet r removes from (convex) or adds to (concave) a circular edge of radius
    big_r, by Pappus on the (1 - pi/4) r^2 corner section."""
    quarter = math.pi * r ** 2 / 4
    if concave:
        return 2 * math.pi * (r ** 2 * (big_r + r / 2) - quarter * (big_r + r) + r ** 3 / 3)
    return 2 * math.pi * (r ** 2 * (big_r - r / 2) - quarter * (big_r - r) - r ** 3 / 3)


def build(out_dir=None):
    m = ff.new(NAME, replace=True)
    m.params(plate_w=50, plate_h=70, plate_t=5,
             corner_r=4,
             hole_d=5, hole_x="plate_w / 2", hole_z1=12, hole_z2="plate_h - hole_z1",
             arm_d=12, arm_len=35, arm_x="plate_w / 2", arm_z="plate_h / 2",
             tip_r=2, joint_r=2)

    # Plate: sketch on the XZ plane (coordinates (x, z)) at y = 0, extruded toward +y by the thickness.
    plate = m.sketch("xz", name="Plate")
    plate.rect(0, 0, "plate_w", "plate_h")
    m.extrude(plate, "plate_t", toward="+", body="Hook", name="Plate")
    plate_vol = 50 * 70 * 5
    m.report("plate", expect_size=(50, 5, 70), expect_volume=plate_vol, expect_bodies=1)

    # R4 on the four plate corners (edges parallel to y), done on the bare plate so exactly four edges match.
    m.fillet("Plate_Corners", ("corner_r", m.edges(parallel="y", x=[0, 50], z=[0, 70])))
    corners = 4 * (1 - math.pi / 4) * 4 ** 2 * 5
    m.report("corners", expect_size=(50, 5, 70), expect_volume=plate_vol - corners, expect_bodies=1)

    # Two 5 mm through holes along y, drilled from the back face (y = 0) into the material.
    m.holes("xz", [("hole_x", "hole_z1"), ("hole_x", "hole_z2")], "hole_d", depth="plate_t", toward="+", at=0,
            name="Mount_Holes")
    holes = 2 * math.pi * 2.5 ** 2 * 5
    m.report("holes", expect_size=(50, 5, 70), expect_volume=plate_vol - corners - holes, expect_bodies=1)

    # Arm: circle on the XZ plane offset to the front face (y = plate_t), extruded +y and joined.
    arm = m.sketch("xz", at="plate_t", name="Arm")
    arm.circle("arm_x", "arm_z", "arm_d")
    m.extrude(arm, "arm_len", op="join", toward="+", name="Arm")
    arm_vol = math.pi * 6 ** 2 * 35
    m.report("arm", expect_size=(50, 40, 70), expect_volume=plate_vol - corners - holes + arm_vol, expect_bodies=1)

    # R2 on the free end of the arm (convex circle at y = 40) and R2 on the arm/plate joint (concave circle at y = 5).
    tip_edges = m.edges(curve="circle", radius=6, y=40)
    joint_edges = m.edges(curve="circle", radius=6, y=5)
    if tip_edges.count != 1 or joint_edges.count != 1:
        raise RuntimeError(f"expected one tip and one joint edge, got {tip_edges.count} and {joint_edges.count}")
    m.fillet("Arm_Fillets", ("tip_r", tip_edges), ("joint_r", joint_edges))
    tip = ring_fillet_volume(2, 6, concave=False)
    joint = ring_fillet_volume(2, 6, concave=True)
    final = plate_vol - corners - holes + arm_vol - tip + joint
    m.report("fillets", expect_size=(50, 40, 70), expect_volume=final, expect_bodies=1)

    # Volume cannot tell where the holes and the arm are: probe points (x, y, z).
    m.probe(inside=[(25, 2.5, 35), (25, 20, 35), (30, 20, 35), (25, 2.5, 20), (25, 2.5, 50), (4, 2.5, 4)],
            outside=[(25, 2.5, 12), (25, 2.5, 58), (25, 20, 42), (32, 20, 35), (25, 20, 28), (0.3, 2.5, 0.3)], label="holes and arm")

    # Parametric proof: a taller plate must move hole 2 and the arm centre with it.
    m.what_if({"plate_h": 80}, "taller plate", expect_size=(50, 40, 80),
              expect_volume=(50 * 80 * 5) - (4 * (1 - math.pi / 4) * 4 ** 2 * 5) - holes + arm_vol - tip + joint,
              expect_bodies=1)
    m.report("restored", expect_size=(50, 40, 70), expect_volume=final, expect_bodies=1)

    if out_dir:
        m.export(out_dir, "hook")
        written = m.views(out_dir, "hook", names=("iso_back",))
        os.replace(written[0], os.path.join(out_dir, "hook_iso.png"))
    return m
