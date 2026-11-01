"""Test setup: fusion_fast imports Fusion's `adsk` modules, which exist only inside Fusion, so a stub stands in.
Run the tests with `python -m pytest tests`. They check the sketch constraint logic against a fake of the sketch API
(fake_fusion.py); they do not replace building and editing a model in Fusion itself."""
import sys
from pathlib import Path
from unittest import mock


class Point3D:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z

    @classmethod
    def create(cls, x, y, z):
        return cls(x, y, z)

    def asArray(self):
        return [self.x, self.y, self.z]


adsk = mock.MagicMock(name="adsk")
adsk.core.Point3D = Point3D
adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation = "horizontal"
adsk.fusion.DimensionOrientations.VerticalDimensionOrientation = "vertical"
sys.modules.update({"adsk": adsk, "adsk.core": adsk.core, "adsk.fusion": adsk.fusion})
sys.path.insert(0, str(Path(__file__).parents[1] / "skills" / "fusion-fast-modeling" / "scripts"))
