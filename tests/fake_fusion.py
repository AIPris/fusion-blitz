"""A stand-in for the part of Fusion's sketch API that fusion_fast.Sketch uses, in plain Python.

It records points, alignments and distance dimensions, and `solve()` replays them the way a sketch solver would:
starting at the origin, every dimension expression is evaluated again against the current parameters and each point
is placed from the points it is tied to. That is enough to ask "where does this circle sit after a parameter
changes, and is every point still pinned?" without Fusion. Assumptions copied from the documented Fusion behaviour
(SKILL.md): a distance dimension keeps the side its geometry was drawn on, and a negative value flips it.
"""
import re
from types import SimpleNamespace

import fusion_fast as ff

CM = ff.CM
# world (x, y, z) -> sketch (x, y), and back. xz and yz have reversed or swapped sketch axes, as in Fusion.
PLANES = {
    "xy": (lambda w: (w[0], w[1]), lambda s: (s[0], s[1], s[2])),
    "xz": (lambda w: (w[0], -w[2]), lambda s: (s[0], s[2], -s[1])),
    "yz": (lambda w: (-w[2], w[1]), lambda s: (s[2], s[1], -s[0])),
}


class FakeDesign:
    """User parameters in mm, plus the names of the dimension parameters the sketch creates."""

    def __init__(self, **params):
        self.params = dict(params)
        self.dimension_names = set()
        self.unitsManager = SimpleNamespace(evaluateExpression=lambda text, unit: self.evaluate(text) * CM)
        self.allParameters = SimpleNamespace(
            itemByName=lambda name: True if name in self.params or name in self.dimension_names else None)

    def evaluate(self, text):
        """Numeric mm of an expression made of numbers, "mm", parameter names and arithmetic."""
        def substitute(match):
            name = match.group(0)
            return "" if name == "mm" else f"({self.params[name]})"
        # eval is safe here: the text is an expression written in these tests, reduced to numbers and operators
        # above, and evaluated with no builtins. Fusion's own expression evaluator has no stand-in in plain Python.
        return eval(re.sub(r"(?<![\w.])[A-Za-z_]\w*", substitute, text), {"__builtins__": {}})


class FakeParameter:
    def __init__(self, design):
        self.expression, self._design = "", design

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value
        self._design.dimension_names.add(value)


class FakeSketch:
    def __init__(self, design, plane):
        self.design, self.plane, self.name = design, plane, "Position"
        self.originPoint = SimpleNamespace(geometry=ff.P(0, 0, 0))
        self.points = [self.originPoint]
        self.added_points = []  # points made with sketchPoints.add, i.e. not part of a curve
        self.log = []  # (constraint name, point, point) for the alignments the sketch was given
        self.same = []  # (axis, a, b): a and b share this sketch coordinate
        self.dimensions = []  # (a, b, axis, sign, parameter)
        self.sketchPoints = SimpleNamespace(add=self._add_sketch_point)
        self.geometricConstraints = SimpleNamespace(
            addCoincident=lambda a, b: self._align("addCoincident", (0, 1), a, b),
            addVerticalPoints=lambda a, b: self._align("addVerticalPoints", (0,), a, b),
            addHorizontalPoints=lambda a, b: self._align("addHorizontalPoints", (1,), a, b),
            addVertical=lambda line: self._align("addVertical", (0,), line.startSketchPoint, line.endSketchPoint),
            addHorizontal=lambda line: self._align("addHorizontal", (1,), line.startSketchPoint, line.endSketchPoint))
        self.sketchDimensions = SimpleNamespace(
            addDistanceDimension=self._distance,
            addDiameterDimension=lambda circle, text_point: SimpleNamespace(parameter=FakeParameter(design)))
        self.sketchCurves = SimpleNamespace(
            sketchCircles=SimpleNamespace(addByCenterRadius=self._circle),
            sketchLines=SimpleNamespace(addTwoPointRectangle=self._rectangle))

    # ---- the Fusion calls fusion_fast makes ---------------------------------------------------------------
    def modelToSketchSpace(self, point):
        x, y = PLANES[self.plane][0](point.asArray())
        return ff.P(x, y, 0)

    def sketchToModelSpace(self, point):
        return ff.P(*PLANES[self.plane][1](point.asArray()))

    def _new_point(self, geometry):
        point = SimpleNamespace(geometry=ff.P(geometry.x, geometry.y, 0))
        self.points.append(point)
        return point

    def _add_sketch_point(self, geometry):
        point = self._new_point(geometry)
        self.added_points.append(point)
        return point

    def _align(self, name, axes, a, b):
        self.log.append((name, a, b))
        self.same += [(axis, a, b) for axis in axes]

    def _distance(self, a, b, orientation, text_point):
        axis = 0 if orientation == "horizontal" else 1
        side = 1 if getattr(b.geometry, "xy"[axis]) - getattr(a.geometry, "xy"[axis]) >= 0 else -1
        parameter = FakeParameter(self.design)
        self.dimensions.append((a, b, axis, side, parameter))
        return SimpleNamespace(parameter=parameter)

    def _circle(self, centre, radius):
        point = self._new_point(centre)
        return SimpleNamespace(centerSketchPoint=point, geometry=SimpleNamespace(center=point.geometry))

    def _rectangle(self, first, second):
        corners = [self._new_point(ff.P(x, y, 0)) for x, y in
                   ((first.x, first.y), (second.x, first.y), (second.x, second.y), (first.x, second.y))]
        lines = [SimpleNamespace(startSketchPoint=corners[i], endSketchPoint=corners[(i + 1) % 4]) for i in range(4)]
        return SimpleNamespace(count=4, item=lambda i: lines[i])

    # ---- the solver ---------------------------------------------------------------------------------------
    def solve(self):
        """Place every point from the origin with the current parameter values. Returns a Solution."""
        position = {id(p): [None, None] for p in self.points}
        position[id(self.originPoint)] = [0.0, 0.0]
        values = [(a, b, axis, side, self.design.evaluate(parameter.expression) * CM)
                  for a, b, axis, side, parameter in self.dimensions]
        changed = True
        while changed:
            changed = False
            ties = [(axis, a, b, 0.0) for axis, a, b in self.same] + [(axis, a, b, side * v) for a, b, axis, side, v in values]
            for axis, a, b, gap in ties:  # b = a + gap along `axis`
                pa, pb = position[id(a)], position[id(b)]
                if pa[axis] is not None and pb[axis] is None:
                    pb[axis], changed = pa[axis] + gap, True
                elif pb[axis] is not None and pa[axis] is None:
                    pa[axis], changed = pb[axis] - gap, True
        conflicts = [(axis, a, b) for axis, a, b, gap in ties
                     if None not in (position[id(a)][axis], position[id(b)][axis])
                     and abs(position[id(b)][axis] - position[id(a)][axis] - gap) > 1e-9]
        free = [p for p in self.points if None in position[id(p)]]
        zero_dimensions = [v for *_, v in values if abs(v) < 1e-9]
        return Solution(self, position, conflicts, free, zero_dimensions)


class Solution:
    def __init__(self, sketch, position, conflicts, free, zero_dimensions):
        self._sketch, self._position = sketch, position
        self.conflicts, self.free, self.zero_dimensions = conflicts, free, zero_dimensions

    @property
    def healthy(self):
        """Every point pinned, nothing contradicting itself, and no dimension asking for a length of 0."""
        return not (self.conflicts or self.free or self.zero_dimensions)

    def world(self, point):
        """World (u, v) in mm of a sketch point, in the sketch plane's two world axes in x, y, z order."""
        x, y = self._position[id(point)]
        world = PLANES[self._sketch.plane][1]((x, y, 0))
        return tuple(round(c / CM, 6) for i, c in enumerate(world) if i != ff.PLANE_NORMAL[self._sketch.plane])


def new_sketch(plane, **params):
    """(Sketch, FakeSketch) on a world plane, with user parameters given in mm."""
    design = FakeDesign(**params)
    model = object.__new__(ff.Model)  # Model.mm, name_param and the parameter lookup only need `design`
    model.design = design
    fake = FakeSketch(design, plane)
    return ff.Sketch(model, fake, ff.PLANE_NORMAL[plane], 0), fake
