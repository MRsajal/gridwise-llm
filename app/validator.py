from __future__ import annotations

import math

from .models import DirectiveInterpretation, HourlyPlanEntry, OptimizationRequest
from .optimizer import build_constraints


class PlanValidationError(RuntimeError):
    """Raised when the replay validator finds an invalid returned schedule."""


def validate_plan(
    request: OptimizationRequest,
    directives: list[DirectiveInterpretation],
    plan: list[HourlyPlanEntry],
    total_grid_kwh: float,
    total_cost_bdt: float,
    peak_grid_kwh: float,
    tolerance: float = 1e-5,
) -> None:
    if len(plan) != 24 or [entry.hour for entry in plan] != list(range(24)):
        raise PlanValidationError("hourly_plan must contain ordered hours 0 through 23")

    data = request.ordered_hours()
    battery = request.battery
    applied = build_constraints(request, directives)
    energy = battery.initial_energy_kwh

    for hour, entry in enumerate(plan):
        values = (
            entry.grid_kwh,
            entry.solar_used_kwh,
            entry.battery_kwh,
            entry.battery_energy_after_kwh,
        )
        if any(not math.isfinite(value) or value < -tolerance for value in values):
            raise PlanValidationError(f"hour {hour} contains an invalid numeric value")
        if entry.solar_used_kwh > applied.effective_solar[hour] + tolerance:
            raise PlanValidationError(f"hour {hour} exceeds effective solar")
        cap = applied.grid_cap[hour]
        if cap is not None and entry.grid_kwh > cap + tolerance:
            raise PlanValidationError(f"hour {hour} exceeds the grid cap")

        if entry.battery_action == "charge":
            if not applied.charge_allowed[hour]:
                raise PlanValidationError(f"hour {hour} charges in a no-charge window")
            if entry.battery_kwh > battery.max_charge_kwh_per_hour + tolerance:
                raise PlanValidationError(f"hour {hour} exceeds the charge rate")
            charge = entry.battery_kwh
            discharge = 0.0
        elif entry.battery_action == "discharge":
            if not applied.discharge_allowed[hour]:
                raise PlanValidationError(f"hour {hour} discharges in a no-discharge window")
            if entry.battery_kwh > battery.max_discharge_kwh_per_hour + tolerance:
                raise PlanValidationError(f"hour {hour} exceeds the discharge rate")
            charge = 0.0
            discharge = entry.battery_kwh
        else:
            if abs(entry.battery_kwh) > tolerance:
                raise PlanValidationError(f"hour {hour} idle action must have zero battery_kwh")
            charge = discharge = 0.0

        expected_balance = data[hour].demand_kwh + charge
        supplied = entry.grid_kwh + entry.solar_used_kwh + discharge
        if abs(supplied - expected_balance) > tolerance:
            raise PlanValidationError(f"hour {hour} violates energy balance")

        energy += charge - discharge
        if abs(entry.battery_energy_after_kwh - energy) > tolerance:
            raise PlanValidationError(f"hour {hour} has an invalid battery transition")
        if energy < applied.minimum_energy[hour] - tolerance:
            raise PlanValidationError(f"hour {hour} violates the active reserve")
        if energy > battery.capacity_kwh + tolerance:
            raise PlanValidationError(f"hour {hour} exceeds battery capacity")

    if abs(energy - battery.initial_energy_kwh) > tolerance:
        raise PlanValidationError("final battery energy must equal initial battery energy")

    replay_grid = sum(entry.grid_kwh for entry in plan)
    replay_cost = sum(plan[h].grid_kwh * data[h].tariff_bdt_per_kwh for h in range(24))
    replay_peak = max(entry.grid_kwh for entry in plan)
    if abs(total_grid_kwh - replay_grid) > tolerance:
        raise PlanValidationError("total_grid_kwh does not match hourly_plan")
    if abs(total_cost_bdt - replay_cost) > tolerance:
        raise PlanValidationError("total_cost_bdt does not match hourly_plan")
    if abs(peak_grid_kwh - replay_peak) > tolerance:
        raise PlanValidationError("peak_grid_kwh does not match hourly_plan")
