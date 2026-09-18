# GridWise LLM Energy Optimizer

A submission-ready implementation of the BUP CSE Fest 2026 preliminary challenge. The service interprets
1-3 natural-language operator notes with a language model, validates the model's structured output, applies the
resulting constraints to a linear program, replays the returned schedule, and exposes the exact required HTTP API.

## Architecture

```text
POST /optimize-energy
        |
        v
Pydantic request validation
        |
        v
Language model -> strict internal JSON schema
        |
        v
Deterministic directive guardrails
        |
        v
SciPy/HiGHS linear optimizer
        |
        v
Independent replay validator
        |
        v
Exact challenge response JSON
```

The language model is in the operator-note interpretation path; it is not used only for cosmetic text. No phrase
matcher silently replaces it. Model output remains untrusted until deterministic code verifies note ordering,
directive types, applies semantics, hours, numeric bounds, and type-specific adjustment shapes.

The default OpenAI integration uses the Responses API with Structured Outputs. OpenAI's current API reference
recommends JSON Schema Structured Outputs over the older JSON mode: [Responses API reference](https://developers.openai.com/api/reference/resources/responses).
The model and base URL are environment variables, and an OpenAI-compatible Chat Completions mode is also included.

## Endpoints

- `GET /health` -> `{"status":"ok"}`
- `POST /optimize-energy` -> directive interpretation plus a valid, cost-minimized 24-hour plan

Malformed or structurally invalid requests return HTTP 400. Infeasible well-formed scenarios return HTTP 422.
Provider and unexpected internal failures return controlled JSON errors without stack traces or secret values.

## Clean local quickstart

Prerequisites: Python 3.12 and a language-model credential, or a reachable local OpenAI-compatible server.

```bash
python -m venv .venv
```

Activate the environment:

```bash
# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install and configure:

```bash
python -m pip install -r requirements.txt
cp .env.example .env
```

Export the variables from `.env` with your shell or hosting provider. Do not commit `.env`.

```bash
# Linux/macOS example
export LLM_API_KEY="your-key"
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_MODEL="gpt-5.6-luna"
export LLM_API_STYLE="responses"

# Windows PowerShell example
$env:LLM_API_KEY="your-key"
$env:LLM_BASE_URL="https://api.openai.com/v1"
$env:LLM_MODEL="gpt-5.6-luna"
$env:LLM_API_STYLE="responses"
```

Start the service:

```bash
python -m app
```

Verify readiness:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

Send a complete organizer sample request with `curl`:

```bash
python scripts/print_sample_request.py --case SAMPLE-01 | \
  curl -X POST http://127.0.0.1:8000/optimize-energy \
  -H "Content-Type: application/json" --data-binary @-
```

The exact sample request and expected response are preserved together in
`tests/fixtures/public_sample_cases.json` under `cases[0].input` and `cases[0].expected_output`. The response's
free-text explanations and an equivalent optimal action sequence may differ; directive semantics and recalculated
cost must match.

Run all public cases through the live endpoint. This checks model interpretation semantics and optimal cost:

```bash
python scripts/test_live_api.py --base-url http://127.0.0.1:8000
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `LLM_API_KEY` | empty | Bearer credential. Required for OpenAI; may be empty for an unauthenticated local server. |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | Provider API root, without a trailing slash. |
| `LLM_MODEL` | `gpt-5.6-luna` | Model identifier sent to the provider. |
| `LLM_API_STYLE` | `responses` | `responses` or `chat_completions`. |
| `LLM_TIMEOUT_SECONDS` | `18` | Timeout for each provider request. |
| `LLM_MAX_ATTEMPTS` | `2` | One initial interpretation plus at most one schema-repair attempt. Range: 1-3. |
| `PORT` | `8000` | HTTP listen port. |

For an OpenAI-compatible provider that implements Chat Completions rather than Responses, set:

```bash
export LLM_BASE_URL="https://provider.example/v1"
export LLM_MODEL="provider-model-id"
export LLM_API_STYLE="chat_completions"
```

The provider must support strict `json_schema` response formatting. This is deliberate: accepting unconstrained free
text would make the judging path less reliable.

## Optimization model

The linear program has hourly grid, solar-use, battery-charge, battery-discharge, and battery-energy variables.
It minimizes:

```text
sum(grid_kwh[h] * tariff_bdt_per_kwh[h]) for h = 0..23
```

Subject to:

- hourly demand balance;
- effective solar after every `solar_reduction`;
- battery capacity, active reserve, charge rate, and discharge rate;
- `no_charge_window`, `no_discharge_window`, and `max_grid_window` constraints;
- final battery energy equal to initial battery energy.

The solver may mathematically produce simultaneous charge and discharge in a degenerate solution because the
challenge specifies 100% battery accounting. The response layer safely collapses that pair to its equivalent net
action before replay validation.

## Tests

Install the development dependencies:

```bash
python -m pip install -r requirements-dev.txt
pytest
```

The test suite covers:

- the exact health response and controlled malformed-input behavior;
- rejection of malformed, out-of-order, out-of-range, or semantically inconsistent model output;
- all 10 organizer public scenarios, including directive application, independent schedule replay, and optimal cost.

To verify the optimizer without spending model tokens or starting the API:

```bash
python scripts/verify_optimizer.py
```

This offline command deliberately supplies the organizer's public expected directives to the same guardrail and
optimizer used in production. It validates the mathematical half of the pipeline; `test_live_api.py` validates the
complete language-model-to-optimizer path.

## Docker fallback

Build and run locally:

```bash
docker build -t your-dockerhub-user/gridwise-llm:1.0.0 .
docker run --rm -p 8000:8000 \
  -e LLM_API_KEY="your-key" \
  -e LLM_MODEL="gpt-5.6-luna" \
  your-dockerhub-user/gridwise-llm:1.0.0
```

Verify the container:

```bash
curl http://127.0.0.1:8000/health
python scripts/test_live_api.py --base-url http://127.0.0.1:8000
```

Push an exact public tag or digest before submission:

```bash
docker push your-dockerhub-user/gridwise-llm:1.0.0
```

Do not bake credentials into the image. Supply them at runtime.

## Deployment

Deploy the repository to any public container or Python platform that:

- binds the service to `0.0.0.0`;
- exposes the configured `PORT`;
- permits outbound HTTPS to the model provider;
- keeps the endpoint warm and reachable throughout judging;
- provides enough memory for NumPy/SciPy (512 MB minimum; 1 GB preferred).

The generic process command is:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
```

After deployment, test from a different network and run:

```bash
python scripts/test_live_api.py --base-url https://your-public-service.example
```

## Reliability and security decisions

- Operator notes are explicitly treated as untrusted data in the model prompt.
- Strict Structured Outputs reduce malformed responses; deterministic guardrails still verify every field.
- A bounded in-memory cache avoids repeated model calls for identical notes and battery capacity.
- No request, prompt, credential, or provider response body is logged.
- API errors contain only safe, controlled messages.
- `.env` and local virtual environments are excluded from Git and Docker build context.
- The final schedule is independently replayed before it is returned.

## Known limitations

- A valid model credential, quota, and reachable provider are required during judging unless a compatible local model
  is deployed alongside the service.
- The compatibility mode expects the provider to implement strict JSON Schema output.
- The in-memory interpretation cache is per process and resets on deployment restart.
- Organizer scoring scenarios are specified as feasible; arbitrary conflicting directives return HTTP 422.

## Submission checklist

- Replace placeholder image names with your real registry tag/digest.
- Keep the GitHub repository private during the event and make it public only after the submission deadline, per the
  participant guide.
- Deploy one public base URL and verify both required endpoints externally.
- Run `pytest`, `scripts/verify_optimizer.py`, and `scripts/test_live_api.py`.
- Record the required video at no more than three minutes: problem, architecture, LLM -> guardrails -> optimizer flow,
  and a short run/test demonstration.
- Keep the endpoint, repository, Docker image, and video accessible throughout evaluation.

## Dependency credits

- [FastAPI](https://fastapi.tiangolo.com/) and [Pydantic](https://docs.pydantic.dev/) for the HTTP contract and validation.
- [Uvicorn](https://www.uvicorn.org/) for ASGI serving.
- [SciPy HiGHS](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linprog.html) and
  [NumPy](https://numpy.org/) for linear optimization.
- The configured external or local language model for operator-note interpretation.

The core directive guardrails, constraint construction, replay validator, API orchestration, and tests in this
repository are project code.
