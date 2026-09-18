import json
from pathlib import Path

import pytest

from app.directives import canonical_to_internal, validate_llm_directives
from app.models import OptimizationRequest
from app.optimizer import optimize_schedule
from app.validator import validate_plan


FIXTURE = Path(__file__).parent / "fixtures" / "public_sample_cases.json"


@pytest.mark.parametrize("case", json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"])
def test_public_case_reaches_reference_optimal_cost(case):
    request = OptimizationRequest.model_validate(case["input"])
    internal = canonical_to_internal(case["expected_output"]["directive_interpretation"])
    directives = validate_llm_directives(internal, request.operator_notes, request.battery)

    plan, total_grid, total_cost, peak_grid = optimize_schedule(request, directives)
    validate_plan(
        request,
        directives,
        plan,
        total_grid,
        total_cost,
        peak_grid,
    )

    assert total_cost == pytest.approx(case["expected_output"]["total_cost_bdt"], abs=0.01)
