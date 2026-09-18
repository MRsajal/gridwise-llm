from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.directives import canonical_to_internal, validate_llm_directives
from app.models import OptimizationRequest
from app.optimizer import optimize_schedule
from app.validator import validate_plan


FIXTURE = ROOT / "tests" / "fixtures" / "public_sample_cases.json"


def main() -> None:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    passed = 0
    for case in cases:
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
        expected = float(case["expected_output"]["total_cost_bdt"])
        if abs(total_cost - expected) > 0.01:
            raise AssertionError(
                f"{case['id']}: cost {total_cost} does not match reference {expected}"
            )
        passed += 1
        print(f"PASS {case['id']}: {total_cost:.2f} BDT")
    print(f"\n{passed}/{len(cases)} public optimizer cases passed")


if __name__ == "__main__":
    main()
