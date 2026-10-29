"""Template build script - an L bracket. Copy it to outputs/<job>/build_<job>.py and edit.

The whole model is one build() that makes a fresh document every run (replace=True), so the loop is:
run -> read the error -> Edit the file -> run again. Each m.report() is a checkpoint; the first wrong one stops the
build and names the stage. A stage whose total volume is a one-line closed form gets expect_volume; any other stage
gets its size, its body count and probe points at its feature edges, but no expected volume: Fusion measures that.
"""
import math

import fusion_fast as ff

NAME = "Bracket_Example"


def build(out_dir=None):
    m = ff.new(NAME, replace=True)
    m.params(base_len=50, width=20, thick=4, leg_h=30, hole_d=4.5, bend_r=3)

    # Base plate on the XY plane (coordinates are (x, y)), then the upright leg at the x = 0 end, drawn on the YZ
    # plane (coordinates are (y, z)) and extruded along +x by the plate thickness.
    base = m.sketch("xy", name="Base")
    base.rect(0, 0, "base_len", "width")
    m.extrude(base, "thick", body="Bracket")
    leg = m.sketch("yz", name="Leg")
    leg.rect(0, "thick", "width", "leg_h - thick")          # starts at z = thick so it stands on the plate
    m.extrude(leg, "thick", op="join", toward="+", name="Leg")
    base_vol, leg_vol = 50 * 20 * 4, 4 * 20 * (30 - 4)
    m.report("body", expect_size=(50, 20, 30), expect_volume=base_vol + leg_vol, expect_bodies=1)   # a closed form: exact

    # Two holes through the base (drilled down from its top face) and one through the leg (from its outer face).
    m.holes("xy", [(25, "width / 2"), (42, "width / 2")], "hole_d", at="thick", toward="-", name="Base_Holes")
    m.holes("yz", [("width / 2", 18)], "hole_d", at=0, toward="+", name="Leg_Hole")
    holes = 3 * math.pi * 2.25 ** 2 * 4
    m.report("holes", expect_size=(50, 20, 30), expect_volume=base_vol + leg_vol - holes, expect_bodies=1)

    # Inside corner: the concave edge along y where the leg meets the base.
    inner = m.edges(parallel="y", x=4, z=4)
    m.fillet("Bend_Fillet", ("bend_r", inner))
    m.report("fillet", expect_size=(50, 20, 30), expect_bodies=1)    # a blend: no expected volume, probe it below

    # Volume cannot say WHERE a hole is, so probe points: empty at the hole axes, solid beside them. The same
    # pair of points, one just inside and one just outside, checks the fillet (radius 3, centre at x = z = 7).
    m.probe(inside=[(30, 10, 2), (2, 10, 25)], outside=[(25, 10, 2), (42, 10, 2), (2, 10, 18)], label="hole positions")
    m.probe(inside=[(4.3, 10, 4.3)], outside=[(6.5, 10, 6.5)], label="fillet")

    # Parametric proof: stretch the leg, check the geometry followed, restore. (Counts are strings: "4", not 4.)
    m.what_if({"leg_h": 40}, "taller leg", expect_size=(50, 20, 40), expect_change=4 * 20 * (40 - 30), expect_bodies=1)

    if out_dir:
        m.export(out_dir, "bracket")
        m.views(out_dir, "bracket", names=("iso", "front"))
    return m
