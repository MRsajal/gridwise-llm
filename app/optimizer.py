from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog

from .models import DirectiveInterpretation, HourlyPlanEntry, OptimizationRequest


class OptimizationError(RuntimeError):
    """Raised when a scenario cannot be optimized."""


@dataclass(frozen=True)
class AppliedConstraints:
    effective_solar: list[float]
    minimum_energy: list[float]
    charge_allowed: list[bool]
    discharge_allowed: list[bool]
    grid_cap: list[float | None]


def build_constraints(
    request: OptimizationRequest,
    directives: list[DirectiveInterpretation],
) -> AppliedConstraints:
    hours = request.ordered_hours()
    effective_solar = [entry.solar_kwh for entry in hours]
    minimum_energy = [request.battery.minimum_energy_kwh] * 24
    charge_allowed = [True] * 24
    discharge_allowed = [True] * 24
    grid_cap: list[float | None] = [None] * 24

    for directive in directives:
        if not directive.applies:
            continue
        adjustment = directive.structured_adjustment or {}
        affected_hours = adjustment["hours"]
        if directive.directive_type == "solar_reduction":
            factor = float(adjustment["factor"])
            for hour in affected_hours:
                effective_solar[hour] = min(
                    effective_solar[hour], hours[hour].solar_kwh * factor
                )
        elif directive.directive_type == "minimum_battery_reserve":
            reserve = float(adjustment["minimum_energy_kwh"])
            for hour in affected_hours:
                minimum_energy[hour] = max(minimum_energy[hour], reserve)
        elif directive.directive_type == "no_charge_window":
            for hour in affected_hours:
                charge_allowed[hour] = False
        elif directive.directive_type == "no_discharge_window":
            for hour in affected_hours:
                discharge_allowed[hour] = False
        elif directive.directive_type == "max_grid_window":
            cap = float(adjustment["max_grid_kwh"])
            for hour in affected_hours:
                grid_cap[hour] = cap if grid_cap[hour] is None else min(grid_cap[hour], cap)

    return AppliedConstraints(
        effective_solar=effective_solar,
        minimum_energy=minimum_energy,
        charge_allowed=charge_allowed,
        discharge_allowed=discharge_allowed,
        grid_cap=grid_cap,
    )


def optimize_schedule(
    request: OptimizationRequest,
    directives: list[DirectiveInterpretation],
) -> tuple[list[HourlyPlanEntry], float, float, float]:
    data = request.ordered_hours()
    battery = request.battery
    applied = build_constraints(request, directives)

    # Variable blocks: grid, solar used, charge, discharge, energy after.
    grid = range(0, 24)
    solar = range(24, 48)
    charge = range(48, 72)
    discharge = range(72, 96)
    energy = range(96, 120)

    objective = np.zeros(120)
    objective[list(grid)] = [entry.tariff_bdt_per_kwh for entry in data]

    equality_rows: list[np.ndarray] = []
    equality_rhs: list[float] = []

    for hour in range(24):
        balance = np.zeros(120)
        balance[grid[hour]] = 1.0
        balance[solar[hour]] = 1.0
        balance[charge[hour]] = -1.0
        balance[discharge[hour]] = 1.0
        equality_rows.append(balance)
        equality_rhs.append(data[hour].demand_kwh)

        transition = np.zeros(120)
        transition[energy[hour]] = 1.0
        transition[charge[hour]] = -1.0
        transition[discharge[hour]] = 1.0
        if hour == 0:
            equality_rhs.append(battery.initial_energy_kwh)
        else:
            transition[energy[hour - 1]] = -1.0
            equality_rhs.append(0.0)
        equality_rows.append(transition)

    neutrality = np.zeros(120)
    neutrality[energy[23]] = 1.0
    equality_rows.append(neutrality)
    equality_rhs.append(battery.initial_energy_kwh)

    bounds: list[tuple[float, float | None]] = []
    bounds.extend((0.0, applied.grid_cap[h]) for h in range(24))
    bounds.extend((0.0, applied.effective_solar[h]) for h in range(24))
    bounds.extend(
        (
            0.0,
            battery.max_charge_kwh_per_hour if applied.charge_allowed[h] else 0.0,
        )
        for h in range(24)
    )
    bounds.extend(
        (
            0.0,
            battery.max_discharge_kwh_per_hour if applied.discharge_allowed[h] else 0.0,
        )
        for h in range(24)
    )
    bounds.extend((applied.minimum_energy[h], battery.capacity_kwh) for h in range(24))

    result = linprog(
        objective,
        A_eq=np.vstack(equality_rows),
        b_eq=np.asarray(equality_rhs),
        bounds=bounds,
        method="highs",
        options={"presolve": True},
    )
    if not result.success:
        raise OptimizationError("No feasible schedule satisfies the supplied constraints")

    plan: list[HourlyPlanEntry] = []
    running_energy = battery.initial_energy_kwh
    for hour in range(24):
        # A cost-only LP can contain simultaneous charge and discharge. Collapsing
        # both to their net action preserves balance, state, bounds, and cost.
        net_charge = float(result.x[charge[hour]] - result.x[discharge[hour]])
        if abs(net_charge) < 1e-8:
            net_charge = 0.0
            action = "idle"
        elif net_charge > 0:
            action = "charge"
        else:
            action = "discharge"

        solar_used = max(0.0, float(result.x[solar[hour]]))
        grid_used = data[hour].demand_kwh + net_charge - solar_used
        if abs(grid_used) < 1e-8:
            grid_used = 0.0
        running_energy += net_charge

        plan.append(
            HourlyPlanEntry(
                hour=hour,
                grid_kwh=_clean(grid_used),
                solar_used_kwh=_clean(solar_used),
                battery_action=action,
                battery_kwh=_clean(abs(net_charge)),
                battery_energy_after_kwh=_clean(running_energy),
            )
        )

    total_grid = _clean(sum(entry.grid_kwh for entry in plan))
    total_cost = _clean(
        sum(plan[h].grid_kwh * data[h].tariff_bdt_per_kwh for h in range(24))
    )
    peak_grid = _clean(max(entry.grid_kwh for entry in plan))
    return plan, total_grid, total_cost, peak_grid


def _clean(value: float) -> float:
    rounded = round(float(value), 8)
    return 0.0 if abs(rounded) < 1e-8 else rounded
