"""Open-top project box: 70 x 50 x 30 mm, 2.5 mm walls/floor, four screw posts with pilot holes, six front slots,
R5 outside vertical corners. Built with fusion_fast; every key dimension is a user parameter."""
import math

import fusion_fast as ff

NAME = "ZZ_bench_box_skill"

# --- hand-computed reference values (mm / mm^3), mirrored from the parameters below ----------------------------
BX, BY, BZ, WALL, FLOOR = 70, 50, 30, 2.5, 2.5
POST_D, POST_TOP, PILOT_D, PILOT_DEPTH = 8, 28, 2.8, 12
SLOT_W, SLOT_H, SLOT_Z0, SLOT_PITCH, SLOT_COUNT, CORNER_R = 2, 14, 8, 6, 6, 5


def expected_volume(bx=BX, wall=WALL, slots=SLOT_COUNT):
    block = bx * BY * BZ - 4 * (1 - math.pi / 4) * CORNER_R ** 2 * BZ
    cavity = (bx - 2 * wall) * (BY - 2 * wall) * (BZ - FLOOR)
    posts = 4 * math.pi * (POST_D / 2) ** 2 * (POST_TOP - FLOOR)
    pilots = 4 * math.pi * (PILOT_D / 2) ** 2 * PILOT_DEPTH
    slot_cut = slots * SLOT_W * SLOT_H * wall
    return block, block - cavity, block - cavity + posts, block - cavity + posts - pilots - slot_cut


def build(out_dir=None):
    m = ff.new(NAME, replace=True)
    m.params(box_x=BX, box_y=BY, box_z=BZ, wall=WALL, floor_t=FLOOR, corner_r=CORNER_R,
             post_d=POST_D, post_top=POST_TOP, post_inset=7.5, pilot_d=PILOT_D, pilot_depth=PILOT_DEPTH,
             slot_w=SLOT_W, slot_h=SLOT_H, slot_z0=SLOT_Z0, slot_pitch=SLOT_PITCH, slot_count=str(SLOT_COUNT),
             cavity_depth="box_z - floor_t", post_h="post_top - floor_t")

    # 1. Solid block with the four vertical outside corners rounded.
    outline = m.sketch("xy", name="Outline")
    outline.rect(0, 0, "box_x", "box_y")
    m.extrude(outline, "box_z", body="Box", name="Block")
    corners = m.edges(parallel="z", x=[0, BX], y=[0, BY])
    m.fillet("Corner_Fillet", ("corner_r", corners))
    block_vol, shell_vol, post_vol, final_vol = expected_volume()
    m.report("block+fillet", expect_size=(BX, BY, BZ), expect_volume=block_vol, expect_bodies=1)

    # 2. Open-top cavity: walls on all four sides, floor stays.
    cavity = m.sketch("xy", at="box_z", name="Cavity")
    cavity.rect("wall", "wall", "box_x - 2 * wall", "box_y - 2 * wall")
    m.extrude(cavity, "cavity_depth", op="cut", toward="-", name="Cavity")
    m.report("cavity", expect_size=(BX, BY, BZ), expect_volume=shell_vol, expect_bodies=1)

    # 3. Screw posts standing on the floor.
    posts = m.sketch("xy", at="floor_t", name="Posts")
    for u, v in (("post_inset", "post_inset"), ("box_x - post_inset", "post_inset"),
                 ("post_inset", "box_y - post_inset"), ("box_x - post_inset", "box_y - post_inset")):
        posts.circle(u, v, "post_d")
    m.extrude(posts, "post_h", op="join", toward="+", name="Posts")
    m.report("posts", expect_size=(BX, BY, BZ), expect_volume=post_vol, expect_bodies=1)

    # 4. Pilot holes, blind, drilled down from the post tops.
    m.holes("xy", [("post_inset", "post_inset"), ("box_x - post_inset", "post_inset"),
                   ("post_inset", "box_y - post_inset"), ("box_x - post_inset", "box_y - post_inset")],
            "pilot_d", depth="pilot_depth", toward="-", at="post_top", name="Pilot_Holes")

    # 5. Ventilation slots through the front wall (y = 0): one slot, patterned along x, set centred on the box.
    slot = m.sketch("xz", at=0, name="Slot")
    slot.rect("box_x / 2 - ((slot_count - 1) * slot_pitch + slot_w) / 2", "slot_z0", "slot_w", "slot_h")
    cut = m.extrude(slot, "wall", op="cut", toward="+", name="Slot_Cut")
    m.pattern(cut, "x", "slot_count", "slot_pitch", name="Slot_Pattern")
    m.report("holes+slots", expect_size=(BX, BY, BZ), expect_volume=final_vol, expect_bodies=1)

    # Volume cannot tell WHICH wall the slots are in, or the hole depth: probe points.
    xs = [BX / 2 - (SLOT_COUNT - 1) * SLOT_PITCH / 2 + i * SLOT_PITCH for i in range(SLOT_COUNT)]
    m.probe(
        outside=[(x, WALL / 2, SLOT_Z0 + SLOT_H / 2) for x in xs]                      # slot centres, front wall
        + [(xs[0], WALL / 2, SLOT_Z0 + 0.5), (xs[-1], WALL / 2, SLOT_Z0 + SLOT_H - 0.5)]  # slot ends
        + [(px, py, 20) for px in (7.5, 62.5) for py in (7.5, 42.5)]                  # pilot hole axes
        + [(7.5, 7.5, 16.5), (35, 25, 10), (1.0, 1.0, 15)],                           # in hole, in cavity, rounded corner
        inside=[(x, BY - WALL / 2, SLOT_Z0 + SLOT_H / 2) for x in xs]                 # back wall untouched
        + [(xs[0] + 3, WALL / 2, SLOT_Z0 + SLOT_H / 2), (xs[0], WALL / 2, SLOT_Z0 - 1),
           (xs[0], WALL / 2, SLOT_Z0 + SLOT_H + 1)]                                    # web between / below / above slots
        + [(7.5, 7.5, 15.5), (10, 7.5, 20), (7.5 + 3, 7.5, 27.5), (35, 25, 1), (1, 25, 15), (2, 2, 15)],
        label="slots/holes/posts")

    # Parametric proof: wider box, fewer slots, thicker wall.
    wide = expected_volume(bx=80, wall=3, slots=4)[3]
    m.what_if({"box_x": 80, "slot_count": "4", "wall": "3 mm"}, "what_if wide", expect_size=(80, BY, BZ),
              expect_volume=wide, expect_bodies=1)
    m.report("restored", expect_size=(BX, BY, BZ), expect_volume=final_vol, expect_bodies=1)

    if out_dir:
        m.export(out_dir, "box")
        m.views(out_dir, "box", names=("iso",))
    return m
