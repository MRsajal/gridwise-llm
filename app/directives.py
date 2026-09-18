from __future__ import annotations

import math
from typing import Any

from .models import BatteryInput, DirectiveInterpretation


ALLOWED_TYPES = {
    "solar_reduction",
    "minimum_battery_reserve",
    "no_charge_window",
    "no_discharge_window",
    "max_grid_window",
    "no_op",
}


class DirectiveValidationError(ValueError):
    """Raised when language-model output fails deterministic guardrails."""


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DirectiveValidationError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise DirectiveValidationError(f"{name} must be finite")
    return number


def _hours(value: Any) -> list[int]:
    if not isinstance(value, list) or not value:
        raise DirectiveValidationError("hours must be a non-empty array")
    if any(isinstance(hour, bool) or not isinstance(hour, int) for hour in value):
        raise DirectiveValidationError("hours must contain integers")
    if any(hour < 0 or hour > 23 for hour in value):
        raise DirectiveValidationError("hours must be between 0 and 23")
    if value != sorted(set(value)):
        raise DirectiveValidationError("hours must be unique and in ascending order")
    return value


def validate_llm_directives(
    raw: Any,
    notes: list[str],
    battery: BatteryInput,
) -> list[DirectiveInterpretation]:
    if not isinstance(raw, dict) or set(raw) != {"directives"}:
        raise DirectiveValidationError("top-level model output must contain only directives")
    entries = raw["directives"]
    if not isinstance(entries, list) or len(entries) != len(notes):
        raise DirectiveValidationError("model must return exactly one directive per note")

    validated: list[DirectiveInterpretation] = []
    for expected_index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise DirectiveValidationError("each directive must be an object")

        required = {
            "note_index",
            "applies",
            "directive_type",
            "hours",
            "factor",
            "minimum_energy_kwh",
            "max_grid_kwh",
            "explanation",
        }
        if set(entry) != required:
            raise DirectiveValidationError("directive fields do not match the internal schema")
        if entry["note_index"] != expected_index:
            raise DirectiveValidationError("note_index values must be ordered and contiguous")
        if not isinstance(entry["applies"], bool):
            raise DirectiveValidationError("applies must be boolean")
        directive_type = entry["directive_type"]
        if directive_type not in ALLOWED_TYPES:
            raise DirectiveValidationError("unsupported directive type")
        if not isinstance(entry["explanation"], str) or not entry["explanation"].strip():
            raise DirectiveValidationError("explanation must be a non-empty string")

        adjustment: dict[str, Any] | None
        if directive_type == "no_op":
            if entry["applies"] is not False:
                raise DirectiveValidationError("no_op must use applies=false")
            if any(
                entry[name] is not None
                for name in ("hours", "factor", "minimum_energy_kwh", "max_grid_kwh")
            ):
                raise DirectiveValidationError("no_op must not contain adjustment values")
            adjustment = None
        else:
            if entry["applies"] is not True:
                raise DirectiveValidationError("applicable directives must use applies=true")
            hours = _hours(entry["hours"])

            if directive_type == "solar_reduction":
                factor = _number(entry["factor"], "factor")
                if not 0 <= factor <= 1:
                    raise DirectiveValidationError("factor must be between 0 and 1")
                if entry["minimum_energy_kwh"] is not None or entry["max_grid_kwh"] is not None:
                    raise DirectiveValidationError("solar_reduction contains unrelated values")
                adjustment = {"hours": hours, "factor": factor}
            elif directive_type == "minimum_battery_reserve":
                reserve = _number(entry["minimum_energy_kwh"], "minimum_energy_kwh")
                if not 0 <= reserve <= battery.capacity_kwh:
                    raise DirectiveValidationError(
                        "minimum_energy_kwh must be within battery capacity"
                    )
                if entry["factor"] is not None or entry["max_grid_kwh"] is not None:
                    raise DirectiveValidationError(
                        "minimum_battery_reserve contains unrelated values"
                    )
                adjustment = {"hours": hours, "minimum_energy_kwh": reserve}
            elif directive_type == "max_grid_window":
                grid_cap = _number(entry["max_grid_kwh"], "max_grid_kwh")
                if grid_cap < 0:
                    raise DirectiveValidationError("max_grid_kwh must be non-negative")
                if entry["factor"] is not None or entry["minimum_energy_kwh"] is not None:
                    raise DirectiveValidationError("max_grid_window contains unrelated values")
                adjustment = {"hours": hours, "max_grid_kwh": grid_cap}
            else:
                if any(
                    entry[name] is not None
                    for name in ("factor", "minimum_energy_kwh", "max_grid_kwh")
                ):
                    raise DirectiveValidationError(
                        f"{directive_type} must contain only an hours adjustment"
                    )
                adjustment = {"hours": hours}

        validated.append(
            DirectiveInterpretation(
                note_index=expected_index,
                applies=entry["applies"],
                directive_type=directive_type,
                structured_adjustment=adjustment,
                explanation=entry["explanation"].strip()[:500],
            )
        )

    return validated


def canonical_to_internal(
    directives: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Convert public/canonical directive objects to the guarded internal shape."""
    result: list[dict[str, Any]] = []
    for directive in directives:
        adjustment = directive.get("structured_adjustment") or {}
        result.append(
            {
                "note_index": directive["note_index"],
                "applies": directive["applies"],
                "directive_type": directive["directive_type"],
                "hours": adjustment.get("hours"),
                "factor": adjustment.get("factor"),
                "minimum_energy_kwh": adjustment.get("minimum_energy_kwh"),
                "max_grid_kwh": adjustment.get("max_grid_kwh"),
                "explanation": directive.get("explanation", "Validated public directive."),
            }
        )
    return {"directives": result}
