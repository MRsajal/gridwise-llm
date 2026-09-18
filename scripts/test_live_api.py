from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "public_sample_cases.json"


def post_json(url: str, payload: dict) -> tuple[int, dict]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = json.loads(exc.read().decode("utf-8"))
        return exc.code, body


def semantic_directive_view(entries: list[dict]) -> list[dict]:
    return [
        {
            "note_index": item["note_index"],
            "applies": item["applies"],
            "directive_type": item["directive_type"],
            "structured_adjustment": item["structured_adjustment"],
        }
        for item in entries
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Exercise all public cases against a live API")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]

    failures = 0
    for case in cases:
        status, output = post_json(f"{args.base_url.rstrip('/')}/optimize-energy", case["input"])
        expected = case["expected_output"]
        ok = (
            status == 200
            and semantic_directive_view(output.get("directive_interpretation", []))
            == semantic_directive_view(expected["directive_interpretation"])
            and abs(float(output.get("total_cost_bdt", -1)) - float(expected["total_cost_bdt"]))
            <= 0.01
        )
        print(f"{'PASS' if ok else 'FAIL'} {case['id']} (HTTP {status})")
        failures += 0 if ok else 1

    if failures:
        raise SystemExit(f"{failures}/{len(cases)} live API cases failed")
    print(f"{len(cases)}/{len(cases)} live API cases passed")


if __name__ == "__main__":
    main()
