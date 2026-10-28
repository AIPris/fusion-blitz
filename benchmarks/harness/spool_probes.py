"""Point-in-solid probes for the `spool` benchmark task: where the finished part must be solid and where it must be empty.

Volume and centre of mass cannot see a hole, rib or lug that sits in the wrong place or has the wrong size; these points
can. Most come in pairs a fraction of a millimetre either side of a feature edge, so each dimension is pinned to well
under a millimetre. Pure Python, derived from the dimensions in the task text (mm). Every point is checked against both
kernels (reference_spool.py and the Fusion golden build) and lies at least 0.2 mm from any surface, so the
classification is not a tolerance call.
"""
import math

RUN1_END, BEND_R, RISER_X, ECC = 160.0, 150.0, 310.0, 14.3
EDGE = 0.7          # how far either side of a surface the paired probes sit
BOSS_ANGLE = 45.0


def elbow_point(angle_deg, offset):
    """Point in the bend plane at `angle_deg` round the bend, `offset` mm from the centreline (positive = away from the bend centre)."""
    a = math.radians(angle_deg)
    return (RUN1_END + (BEND_R + offset) * math.sin(a), 0.0, BEND_R - (BEND_R + offset) * math.cos(a))


def boss_point(along, aside=0.0):
    """Point on the sensor boss: `along` mm from the centreline point along its axis, `aside` mm sideways in the bend plane."""
    a = math.radians(BOSS_ANGLE)
    x, _, z = elbow_point(BOSS_ANGLE, 0)
    return (x + along * math.sin(a) + aside * math.cos(a), 0.0, z - along * math.cos(a) + aside * math.sin(a))


def around_wall(wall_in, wall_out):
    """Radii that straddle a pipe wall: empty in the bore, solid just inside the wall, solid just inside the outer skin, empty outside."""
    return wall_in - EDGE, wall_in + EDGE, wall_out - EDGE, wall_out + EDGE


def probes():
    inside, outside = [], []

    # Inlet flange: bolt holes (centres and both edges), groove walls and depth, hub taper, rim chamfer
    flange_hole = lambda r, k=0: (10.0, r * math.sin(math.radians(22.5 + 45 * k)), r * math.cos(math.radians(22.5 + 45 * k)))
    outside += [flange_hole(80, k) for k in range(8)] + [flange_hole(80 - 8.3), flange_hole(80 + 8.3)]
    inside += [flange_hole(80 - 9.7), flange_hole(80 + 9.7), (10, 0, 80), (10, 80, 0)]
    outside += [(1.5, 0, 52.7), (1.5, 0, 54.5), (1.5, 0, 56.3), (2.7, 0, 54.5)]    # groove, 52 to 57 wide, 3 deep
    inside += [(1.5, 0, 51.3), (1.5, 0, 57.7), (4.5, 0, 54.5), (3.3, 0, 54.5)]
    outside += [(0.3, 0, 99.5), (40, 0, 51.7)]                                        # chamfer removed; just beyond the hub (r 51.2 at x = 40)
    inside += [(1.4, 0, 99.0), (30, 0, 52.5), (40, 0, 50.7)]

    # Pipe walls and clear bore: straight run, the bend on both sides (direction, radius), the riser
    bore, skin_in, skin_out, air = around_wall(39.45, 44.45)
    outside += [(100, 0, bore), (100, 0, air)]
    inside += [(100, 0, skin_in), (100, 0, skin_out)]
    for angle in (20.0, 70.0):
        for sign in (1, -1):
            outside += [elbow_point(angle, sign * bore), elbow_point(angle, sign * air)]
            inside += [elbow_point(angle, sign * skin_in), elbow_point(angle, sign * skin_out)]
    outside += [elbow_point(BOSS_ANGLE, 0), (250, 0, -40), (80, 0, 0), (RISER_X, 0, 200)]   # (250, 0, -40) is inside a bend that turns the wrong way
    inside += [(RISER_X, -42, 200)]

    # Eccentric reducer at mid length (z = 290): the outer surface runs from y = -30.15 to +44.45, the bore from -25.15 to +39.45
    outside += [(RISER_X, 45.0, 290), (RISER_X, -30.7, 290), (RISER_X, 38.9, 290), (RISER_X, -24.6, 290), (RISER_X, 7.15, 290), (RISER_X, ECC, 360)]
    inside += [(RISER_X, 43.9, 290), (RISER_X, -29.6, 290), (RISER_X, 40.0, 290), (RISER_X, -25.7, 290)]

    # Outlet flange: bolt holes, hole edges, groove walls and depth, rim chamfer; reduced pipe walls
    at = lambda r, angle, z: (RISER_X + r * math.cos(angle), ECC + r * math.sin(angle), z)
    bolt = lambda k: math.radians(45 + 90 * k)
    outside += [at(62.5, bolt(k), 389) for k in range(4)] + [at(62.5 - 8.3, bolt(0), 389), at(62.5 + 8.3, bolt(0), 389)]
    inside += [at(62.5 - 9.7, bolt(0), 389), at(62.5 + 9.7, bolt(0), 389), at(62.5, 0, 389), at(62.5, math.pi / 2, 389)]
    outside += [at(33.7, 0, 396.75), at(36, 0, 396.75), at(38.3, 0, 396.75), at(36, 0, 395.8)]   # groove, 33 to 39 wide, 2.5 deep
    inside += [at(32.3, 0, 396.75), at(39.7, 0, 396.75), at(36, 0, 394.5), at(36, 0, 395.2)]
    outside += [at(82.0, 0, 397.8)]                                                 # chamfer removed
    inside += [at(81.2, 0, 397.0)]
    bore, skin_in, skin_out, air = around_wall(25.15, 30.15)
    outside += [at(bore, bolt(0), 360), at(air, bolt(0), 360)]
    inside += [at(skin_in, bolt(0), 360), at(skin_out, bolt(0), 360)]

    # Gusset ribs: one in each of the four, thickness, hypotenuse and outer tip
    rib_r, rib_z = (28 + 60 + 28) / 3, (380 + 380 + 340) / 3
    inside += [at(rib_r, angle, rib_z) for angle in (0, math.pi, math.pi / 2, 3 * math.pi / 2)]
    inside += [(RISER_X + rib_r, ECC + 4 - EDGE, rib_z), (RISER_X + rib_r, ECC - 4 + EDGE, rib_z), (RISER_X + 50, ECC, 368.2), (RISER_X + 58.9, ECC, 379.6)]
    outside += [(RISER_X + rib_r, ECC + 4 + EDGE, rib_z), (RISER_X + rib_r, ECC - 4 - EDGE, rib_z), (RISER_X + 50, ECC, 366.8),
                (RISER_X + 60.7, ECC, 379.6), (RISER_X + 55, ECC, 345)]

    # Sensor boss: diameter, length, hole diameter, hole breaking through the wall (40.2 is where a blind hole would leave a skin), end chamfer, the far wall left intact
    inside += [boss_point(55, 10), boss_point(55, 15 - EDGE), boss_point(55, 6 + EDGE), boss_point(70 - EDGE, 10), boss_point(68, 14.0), boss_point(-42)]
    outside += [boss_point(50), boss_point(42), boss_point(40.2), boss_point(55, 15 + EDGE), boss_point(55, 6 - EDGE), boss_point(70 + EDGE, 10), boss_point(69.8, 14.7)]

    # Lifting lugs: hole edges, thickness, outline edges, bore clear under them, beyond the ends
    for sign in (1, -1):
        centre = RISER_X + sign * 70
        outside += [(centre, 0, 200), (centre + sign * (12.5 - EDGE), 0, 200), (centre + sign * 18, 5.7, 200), (centre + sign * 18, -5.7, 200),
                    (centre + sign * 30, 0, 200), (RISER_X + sign * 20, 0, 200), (RISER_X + sign * 62, 0, 175 - EDGE), (RISER_X + sign * 62, 0, 225 + EDGE)]
        inside += [(centre + sign * (12.5 + EDGE), 0, 200), (centre + sign * 18, 0, 200), (centre + sign * 18, 4.3, 200), (centre + sign * 18, -4.3, 200),
                   (RISER_X + sign * 40, 0, 200), (RISER_X + sign * 62, 0, 175 + EDGE), (RISER_X + sign * 62, 0, 225 - EDGE)]
    return {"inside": [[round(float(c), 3) for c in p] for p in inside], "outside": [[round(float(c), 3) for c in p] for p in outside]}


if __name__ == "__main__":
    found = probes()
    print(len(found["inside"]), "inside,", len(found["outside"]), "outside")
