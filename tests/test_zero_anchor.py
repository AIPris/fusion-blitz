"""Issue #1: a sketch coordinate that is 0 now but names a parameter must keep following that parameter."""
import pytest

from fake_fusion import new_sketch

PLANES = ["xy", "xz", "yz"]
PARAMETERS = {"offset": 0, "width": 20, "width0": 20}


def assert_pinned(fake):
    """Solve the sketch against the current parameters; every point pinned, nothing contradictory, no zero length."""
    solved = fake.solve()
    assert solved.healthy, (solved.conflicts, solved.free, solved.zero_dimensions)
    return solved


@pytest.mark.parametrize("plane", PLANES)
@pytest.mark.parametrize("u, v, edit, expected", [
    ("offset", 10, {"offset": 5}, (5, 10)),                  # x only
    (10, "offset", {"offset": 5}, (10, 5)),                  # y only
    ("offset", "offset", {"offset": 5}, (5, 5)),             # both
    ("offset", 10, {"offset": -7}, (-7, 10)),                # to the other side of the origin
    ("width - width0", 10, {"width": 25}, (5, 10)),          # an expression that is 0 only for now
    ("0 mm + offset", 10, {"offset": 5}, (5, 10)),
    (0, "offset", {"offset": 5}, (0, 5)),                    # a constant 0 next to a parametric 0 stays put
    ("offset", 0, {"offset": 5}, (5, 0)),
])
def test_circle_centre_follows_a_parameter_that_starts_at_zero(plane, u, v, edit, expected):
    sketch, fake = new_sketch(plane, **PARAMETERS)
    centre = sketch.circle(u, v, 4).centerSketchPoint
    start = assert_pinned(fake).world(centre)
    fake.design.params.update(edit)
    assert assert_pinned(fake).world(centre) == pytest.approx(expected)
    fake.design.params.update(PARAMETERS)
    assert assert_pinned(fake).world(centre) == pytest.approx(start)


@pytest.mark.parametrize("plane", PLANES)
def test_rectangle_corner_follows_a_parameter_that_starts_at_zero(plane):
    sketch, fake = new_sketch(plane, **PARAMETERS)
    lines = sketch.rect("offset", "offset", 6, 8)
    corners = [lines.item(i).startSketchPoint for i in range(4)]

    def lowest_corner():
        worlds = [assert_pinned(fake).world(p) for p in corners]
        return min(w[0] for w in worlds), min(w[1] for w in worlds)

    assert lowest_corner() == pytest.approx((0, 0))
    fake.design.params["offset"] = 5
    assert lowest_corner() == pytest.approx((5, 5))
    fake.design.params["offset"] = 0
    assert lowest_corner() == pytest.approx((0, 0))


@pytest.mark.parametrize("plane, alignment", [("xy", "addVerticalPoints"), ("xz", "addVerticalPoints"),
                                              ("yz", "addHorizontalPoints")])
def test_a_constant_zero_is_still_an_alignment(plane, alignment):
    """The control: world u = 0 is the sketch's x on xy and xz, its y on yz. No reference point, no dependency."""
    sketch, fake = new_sketch(plane, **PARAMETERS)
    centre = sketch.circle("0 mm", 10, 4).centerSketchPoint
    assert [name for name, *_ in fake.log] == [alignment]
    assert fake.added_points == []
    fake.design.params["offset"] = 5
    assert assert_pinned(fake).world(centre) == pytest.approx((0, 10))


def test_two_constant_zeros_are_still_a_coincidence():
    sketch, fake = new_sketch("xy", **PARAMETERS)
    sketch.circle(0, 0, 4)
    assert [name for name, *_ in fake.log] == ["addCoincident"]
    assert fake.added_points == []


@pytest.mark.parametrize("plane", PLANES)
def test_circles_at_the_same_parametric_zero_share_one_reference_per_axis(plane):
    sketch, fake = new_sketch(plane, **PARAMETERS)
    first = sketch.circle("offset", "offset", 4)
    second = sketch.circle("offset", "offset", 6)
    assert len(fake.added_points) == 2  # one reference point on each sketch axis, however many circles use it
    fake.design.params["offset"] = 5
    solved = assert_pinned(fake)
    assert solved.world(first.centerSketchPoint) == pytest.approx((5, 5))
    assert solved.world(second.centerSketchPoint) == pytest.approx((5, 5))
