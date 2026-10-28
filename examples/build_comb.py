"""Desk cable comb: 90 x 28 x 12 bar, five 7 mm slots (8 mm deep, 16 mm pitch, centred), two 4.5 mm holes, R3 corners."""
import math

import fusion_fast as ff

NAME = "ZZ_bench_comb_skill"

# Hand-computed reference values (mm / mm3) for the checkpoints.
L, W, H = 90.0, 28.0, 12.0
SLOT_W, SLOT_D, PITCH, COUNT = 7.0, 8.0, 16.0, 5
HOLE_D, CORNER_R = 4.5, 3.0
BAR = L * W * H
CORNERS = 4 * (1 - math.pi / 4) * CORNER_R ** 2 * H
SLOTS = lambda n: n * SLOT_W * W * SLOT_D
HOLES = 2 * math.pi * (HOLE_D / 2) ** 2 * H


def build(out_dir=None):
    old = ff.registry().get(NAME)
    if old is not None and not old.isValid:      # stale registry entry of a document closed earlier: nothing to replace
        del ff.registry()[NAME]
    m = ff.new(NAME, replace=True)
    m.params(bar_len=L, bar_w=W, bar_h=H,
             slot_w=SLOT_W, slot_d=SLOT_D, slot_pitch=PITCH, slot_count=str(COUNT),
             slot_x0="(bar_len - ((slot_count - 1) * slot_pitch + slot_w)) / 2",   # centres the slot set along x
             hole_d=HOLE_D, hole_x=4.75, hole_x2="bar_len - hole_x", hole_y="bar_w / 2",
             corner_r=CORNER_R)

    # Bar: one corner at the origin, footprint on XY, extruded up.
    base = m.sketch("xy", name="Bar")
    base.rect(0, 0, "bar_len", "bar_w")
    m.extrude(base, "bar_h", body="Comb")
    m.report("bar", expect_size=(L, W, H), expect_volume=BAR, expect_bodies=1)

    # R3 on the four vertical corner edges.
    m.fillet("Corner_Fillet", ("corner_r", m.edges(parallel="z", x=[0, L], y=[0, W])))
    m.report("corners", expect_size=(L, W, H), expect_volume=BAR - CORNERS, expect_bodies=1)

    # First slot on the XZ plane (u = x, v = z), cut along +y through the full depth, then patterned along x.
    slot = m.sketch("xz", name="Slot")
    slot.rect("slot_x0", "bar_h - slot_d", "slot_w", "slot_d")
    cut = m.extrude(slot, "bar_w", op="cut", toward="+", name="Slot_Cut")
    m.pattern(cut, "x", "slot_count", "slot_pitch", name="Slot_Pattern")
    m.report("slots", expect_size=(L, W, H), expect_volume=BAR - CORNERS - SLOTS(COUNT), expect_bodies=1)

    # Two mounting holes straight down through the whole bar, drilled from the top face.
    m.holes("xy", [("hole_x", "hole_y"), ("hole_x2", "hole_y")], "hole_d", depth="bar_h", at="bar_h", toward="-",
            name="Mount_Holes")
    final = BAR - CORNERS - SLOTS(COUNT) - HOLES
    result = m.report("holes", expect_size=(L, W, H), expect_volume=final, expect_bodies=1)
    radii = result["cylinder_radii_mm"]
    if radii != {"2.25": 2, "3.0": 4}:
        raise RuntimeError(f"cylinder radii {radii}: expected 2 hole faces R2.25 and 4 corner faces R3")

    # Volume cannot say where things are: probe slot centres, webs between slots, hole axes, rounded corners.
    c = [13, 29, 45, 61, 77]                                        # slot centres: 9.5 + 3.5 + k * 16
    m.probe(inside=[(21, 14, 10), (9, 14, 10), (81, 14, 10), (13, 14, 2), (c[2], 14, 3.5),
                    (2, 14, 6), (88, 14, 6), (1, 1, 6), (89, 27, 6)],
            outside=[(x, 14, 8) for x in c] + [(c[0], 1, 11.5), (c[4], 27, 11.5), (4.75, 14, 6), (85.25, 14, 6),
                                                (4.75, 14, 11.5), (85.25, 14, 0.5), (0.3, 0.3, 6), (89.7, 27.7, 6)],
            label="slots, holes, corners")

    # Parametric proof: longer bar, four slots (still centred; second hole follows the far end).
    m.what_if({"bar_len": 100, "slot_count": "4"}, "longer, 4 slots", expect_size=(100, W, H),
              expect_volume=100 * W * H - 4 * (1 - math.pi / 4) * CORNER_R ** 2 * H - SLOTS(4) - HOLES,
              expect_bodies=1)
    m.report("restored", expect_size=(L, W, H), expect_volume=final, expect_bodies=1)

    if out_dir:
        m.export(out_dir, "comb")
        m.views(out_dir, "comb", names=("iso",))
    return m
