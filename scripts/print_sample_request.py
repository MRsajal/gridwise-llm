from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "public_sample_cases.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Print one organizer public request as JSON")
    parser.add_argument("--case", default="SAMPLE-01", help="Public case id")
    args = parser.parse_args()

    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    try:
        selected = next(case for case in cases if case["id"] == args.case)
    except StopIteration:
        choices = ", ".join(case["id"] for case in cases)
        raise SystemExit(f"Unknown case {args.case!r}. Choose one of: {choices}") from None
    print(json.dumps(selected["input"], separators=(",", ":")))


if __name__ == "__main__":
    main()
