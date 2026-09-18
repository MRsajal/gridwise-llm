# GridWise LLM Energy Optimizer

GridWise is a 24-hour energy scheduling service created for the **BUP CSE FEST 2026 GridWise preliminary challenge**.

The service accepts hourly electricity demand, solar availability, electricity tariff, battery information, and 1–3 natural-language operator notes. It interprets the notes, applies the required operating restrictions, and returns a valid low-cost 24-hour energy plan.

## What the Service Does

For every optimization request, GridWise:

1. Reads the 24-hour demand, solar, tariff, and battery data.
2. Uses an LLM to understand the operator notes.
3. Validates the interpreted directives before using them.
4. Applies supported restrictions such as solar reduction, battery reserve, charging/discharging restrictions, and grid-import limits.
5. Uses **SciPy HiGHS linear optimization** to minimize electricity cost.
6. Re-checks the final 24-hour schedule before returning it.

The battery must finish the day with the same energy with which it started.

## Requirements

You need:

- Python 3.12 or newer
- Internet access if using a hosted LLM provider
- An LLM API key if your provider requires one
- Optional: Docker

## 1. Download or Clone the Project

Open a terminal inside the project directory.

## 2. Create a Virtual Environment

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Windows Command Prompt

```cmd
python -m venv .venv
.venv\Scripts\activate.bat
```

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install Dependencies

```bash
python -m pip install -r requirements.txt
```

## 4. Configure the LLM

The default configuration uses the OpenAI Responses API.

Set the required environment variables before starting the service.

### Windows PowerShell

```powershell
$env:LLM_API_KEY="YOUR_API_KEY"
$env:LLM_BASE_URL="https://api.openai.com/v1"
$env:LLM_MODEL="gpt-5.6-luna"
$env:LLM_API_STYLE="responses"
$env:LLM_TIMEOUT_SECONDS="18"
$env:LLM_MAX_ATTEMPTS="2"
$env:PORT="8000"
```

### Windows Command Prompt

```cmd
set LLM_API_KEY=YOUR_API_KEY
set LLM_BASE_URL=https://api.openai.com/v1
set LLM_MODEL=gpt-5.6-luna
set LLM_API_STYLE=responses
set LLM_TIMEOUT_SECONDS=18
set LLM_MAX_ATTEMPTS=2
set PORT=8000
```

### Linux/macOS

```bash
export LLM_API_KEY="YOUR_API_KEY"
export LLM_BASE_URL="https://api.openai.com/v1"
export LLM_MODEL="gpt-5.6-luna"
export LLM_API_STYLE="responses"
export LLM_TIMEOUT_SECONDS="18"
export LLM_MAX_ATTEMPTS="2"
export PORT="8000"
```

The included `.env.example` file shows the available settings. Do not place a real API key in a public repository or shared ZIP file.

## 5. Start the Service

Run:

```bash
python -m app
```

The service will normally start at:

```text
http://127.0.0.1:8000
```

## 6. Check Service Health

Open another terminal and run:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## 7. Run an Organizer Public Sample

The repository already includes the public sample cases.

Generate `SAMPLE-01` as a JSON file:

```bash
python scripts/print_sample_request.py --case SAMPLE-01 > sample-request.json
```

Send it to the API:

### Linux/macOS

```bash
curl -X POST http://127.0.0.1:8000/optimize-energy \
  -H "Content-Type: application/json" \
  --data-binary @sample-request.json
```

### Windows PowerShell / Command Prompt

```cmd
curl.exe -X POST http://127.0.0.1:8000/optimize-energy -H "Content-Type: application/json" --data-binary "@sample-request.json"
```

A successful request returns HTTP `200` and a JSON response containing:

- `scenario_id`
- `directive_interpretation`
- `hourly_plan`
- `total_grid_kwh`
- `total_cost_bdt`
- `peak_grid_kwh`
- `plan_summary`

The hourly schedule may differ from the organizer's example schedule when multiple equally optimal schedules exist. The schedule must still satisfy all constraints and achieve the correct optimal cost within the allowed numeric tolerance.

## 8. Check All 10 Public Samples

With the API running, execute:

```bash
python scripts/test_live_api.py --base-url http://127.0.0.1:8000
```

A fully working setup should finish with:

```text
10/10 live API cases passed
```

The public reference optimal costs are:

| Sample | Optimal Cost (BDT) |
|---|---:|
| SAMPLE-01 | 38,365 |
| SAMPLE-02 | 42,885 |
| SAMPLE-03 | 35,480 |
| SAMPLE-04 | 40,495 |
| SAMPLE-05 | 33,950 |
| SAMPLE-06 | 34,090 |
| SAMPLE-07 | 38,550 |
| SAMPLE-08 | 37,665 |
| SAMPLE-09 | 34,873 |
| SAMPLE-10 | 41,620 |

## API Endpoints

### `GET /health`

Checks whether the service is running.

Response:

```json
{
  "status": "ok"
}
```

### `POST /optimize-energy`

Accepts one complete 24-hour GridWise scenario.

The request contains:

- `scenario_id` — scenario name or identifier
- `operator_notes` — 1 to 3 natural-language operator instructions
- `hours` — exactly 24 hourly records for hours 0 through 23
- `battery` — battery capacity, initial energy, minimum reserve, and charge/discharge limits

Each hourly record contains:

- `hour`
- `demand_kwh`
- `solar_kwh`
- `tariff_bdt_per_kwh`

## Supported Operator Instructions

GridWise supports the directive types required by the challenge:

- Solar availability reduction
- Minimum battery reserve
- No-charge time window
- No-discharge time window
- Maximum grid-import window
- Irrelevant notes, which are treated as `no_op`

Examples of valid operator notes include:

```text
Solar output will drop to about 20% from 1 PM to 3 PM.
```

```text
Do not charge the battery between 2 PM and 4 PM.
```

```text
Keep at least 120 kWh in reserve from 6 PM until 9 PM.
```

## Configuration Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_API_KEY` | empty | API credential for the selected LLM provider |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | LLM provider API base URL |
| `LLM_MODEL` | `gpt-5.6-luna` | Model used for operator-note interpretation |
| `LLM_API_STYLE` | `responses` | `responses` or `chat_completions` |
| `LLM_TIMEOUT_SECONDS` | `18` | Timeout for one LLM request |
| `LLM_MAX_ATTEMPTS` | `2` | Maximum interpretation attempts |
| `PORT` | `8000` | Port used by the API service |

If you use another OpenAI-compatible provider, change `LLM_BASE_URL`, `LLM_MODEL`, and `LLM_API_STYLE` as required by that provider.

## Running with Docker

Build the image:

```bash
docker build -t gridwise-llm .
```

Run it:

```bash
docker run --rm -p 8000:8000 \
  -e LLM_API_KEY="YOUR_API_KEY" \
  -e LLM_BASE_URL="https://api.openai.com/v1" \
  -e LLM_MODEL="gpt-5.6-luna" \
  -e LLM_API_STYLE="responses" \
  gridwise-llm
```

On Windows Command Prompt, the same command can be written on one line:

```cmd
docker run --rm -p 8000:8000 -e LLM_API_KEY="YOUR_API_KEY" -e LLM_BASE_URL="https://api.openai.com/v1" -e LLM_MODEL="gpt-5.6-luna" -e LLM_API_STYLE="responses" gridwise-llm
```

Then verify:

```bash
curl http://127.0.0.1:8000/health
```

## Common Errors

### `interpretation_failed`

The LLM provider could not interpret the operator notes successfully.

Check:

- API key
- model name
- provider URL
- internet connection
- API quota

### `invalid_request`

The submitted JSON does not match the required request format.

Check that:

- all 24 hours are present exactly once
- hours are numbered 0 through 23
- there are 1–3 non-empty operator notes
- numeric values are valid and non-negative where required
- battery values are valid

### `infeasible_scenario`

No schedule can satisfy all supplied constraints at the same time.

### `internal_validation_failed`

The generated plan failed the final safety/consistency check and was not returned as a successful optimization response.

## Security Notes

- Never commit or share your real `.env` file.
- Never publish an API key in GitHub, Docker images, screenshots, videos, or README files.
- Provide secrets through environment variables or your hosting platform's secret manager.
- If an API key has already been included in a shared archive, revoke or rotate that key before deployment.

## Known Limitations

- A working LLM provider is required for natural-language operator-note interpretation.
- The configured provider must support the selected API style and structured JSON output expected by the service.
- Arbitrary contradictory user-created constraints may result in an infeasible scenario response.
- The public sample schedule does not need to match hour-for-hour when another equally valid optimal schedule exists.

## Challenge Compliance Summary

The service provides the required:

- `GET /health`
- `POST /optimize-energy`
- LLM-based operator-note interpretation
- deterministic directive validation
- 24-hour cost optimization using SciPy/HiGHS
- battery end-of-day neutrality
- final schedule replay validation
- public-sample verification tools
- Docker support

