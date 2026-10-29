import pytest

from core.units import Units, unit_scale


@pytest.mark.parametrize(
    ("insunits", "units", "scale"),
    [
        (4, Units.MILLIMETERS, 1.0),
        (5, Units.CENTIMETERS, 10.0),
        (6, Units.METERS, 1000.0),
        (1, Units.INCHES, 25.4),
        (2, Units.FEET, 304.8),
    ],
)
def test_known_units_convert_to_mm(insunits, units, scale):
    result = unit_scale(insunits)
    assert result.units == units
    assert result.mm_per_unit == pytest.approx(scale)
    assert result.warnings == ()


def test_unitless_assumes_mm_and_warns():
    result = unit_scale(0)
    assert result.units == Units.UNITLESS
    assert result.mm_per_unit == 1.0
    assert result.warnings


def test_unknown_unit_assumes_mm_and_warns():
    result = unit_scale(99)
    assert result.mm_per_unit == 1.0
    assert result.warnings


def test_round_trip_conversion():
    scale = unit_scale(6)
    assert scale.from_mm(scale.to_mm(2.4)) == pytest.approx(2.4)
