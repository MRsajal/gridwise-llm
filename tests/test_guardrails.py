import pytest

from app.directives import DirectiveValidationError, validate_llm_directives
from app.models import BatteryInput


BATTERY = BatteryInput(
    capacity_kwh=200,
    initial_energy_kwh=100,
    minimum_energy_kwh=20,
    max_charge_kwh_per_hour=50,
    max_discharge_kwh_per_hour=50,
)


def _entry(**overrides):
    entry = {
        "note_index": 0,
        "applies": True,
        "directive_type": "solar_reduction",
        "hours": [12, 13],
        "factor": 0.25,
        "minimum_energy_kwh": None,
        "max_grid_kwh": None,
        "explanation": "Solar is reduced during cleaning.",
    }
    entry.update(overrides)
    return {"directives": [entry]}


def test_valid_solar_directive_is_converted_to_canonical_shape():
    result = validate_llm_directives(_entry(), ["note"], BATTERY)
    assert result[0].structured_adjustment == {"hours": [12, 13], "factor": 0.25}


@pytest.mark.parametrize(
    "raw",
    [
        _entry(hours=[13, 12]),
        _entry(hours=[12, 12]),
        _entry(hours=[24]),
        _entry(factor=1.1),
        _entry(applies=False),
        _entry(minimum_energy_kwh=20),
    ],
)
def test_invalid_model_output_is_rejected(raw):
    with pytest.raises(DirectiveValidationError):
        validate_llm_directives(raw, ["note"], BATTERY)


def test_no_op_requires_null_adjustments():
    raw = _entry(
        applies=False,
        directive_type="no_op",
        hours=None,
        factor=None,
        minimum_energy_kwh=None,
        max_grid_kwh=None,
    )
    result = validate_llm_directives(raw, ["note"], BATTERY)
    assert result[0].structured_adjustment is None
