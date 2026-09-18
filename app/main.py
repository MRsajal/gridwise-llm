from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import Settings
from .llm import InterpreterError, LLMInterpreter
from .models import OptimizationRequest, OptimizationResponse
from .optimizer import OptimizationError, optimize_schedule
from .validator import PlanValidationError, validate_plan


app = FastAPI(
    title="GridWise LLM Energy Optimizer",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
interpreter = LLMInterpreter(Settings.from_env())


@app.exception_handler(RequestValidationError)
async def request_validation_error(
    _request: Request, _exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": "invalid_request", "message": "Request JSON failed validation"},
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/optimize-energy", response_model=OptimizationResponse)
def optimize_energy(request: OptimizationRequest) -> OptimizationResponse | JSONResponse:
    try:
        directives = interpreter.interpret(request)
        plan, total_grid, total_cost, peak_grid = optimize_schedule(request, directives)
        validate_plan(
            request,
            directives,
            plan,
            total_grid,
            total_cost,
            peak_grid,
        )
    except InterpreterError as exc:
        return JSONResponse(
            status_code=500,
            content={"error": "interpretation_failed", "message": str(exc)},
        )
    except OptimizationError:
        return JSONResponse(
            status_code=422,
            content={
                "error": "infeasible_scenario",
                "message": "No valid schedule satisfies all scenario constraints",
            },
        )
    except PlanValidationError:
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_validation_failed",
                "message": "The generated schedule failed final validation",
            },
        )

    return OptimizationResponse(
        scenario_id=request.scenario_id,
        directive_interpretation=directives,
        hourly_plan=plan,
        total_grid_kwh=total_grid,
        total_cost_bdt=total_cost,
        peak_grid_kwh=peak_grid,
        plan_summary=(
            "Applied the validated operator directives, used available solar, and shifted "
            "battery energy across tariff periods while preserving all reserves, rate limits, "
            "grid caps, and end-of-day battery neutrality."
        ),
    )
