"""Layer 3 acceptance check: the evaluation harness itself must be trustworthy.

Acceptance criteria:
1. Every golden question has a reference query that executes and returns rows.
   An unverified oracle makes the accuracy score meaningless.
2. Single answer questions are not brittle to ties.
3. The harness produced a results file with the expected fields.
4. Every recorded status belongs to the documented error taxonomy.
5. The accuracy figure in the file matches the per question records.
6. The chart artifact exists.

Run: python scripts/acceptance_layer3.py
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import duckdb  # noqa: E402

from eval.golden_set import GOLDEN  # noqa: E402
from eval.run_eval import TAXONOMY  # noqa: E402
from src.schema import DEFAULT_DB  # noqa: E402

RESULTS = pathlib.Path(__file__).resolve().parents[1] / "eval" / "results"


def main() -> int:
    checks = []

    con = duckdb.connect(str(DEFAULT_DB), read_only=True)

    # 1. oracle integrity
    broken = []
    for q in GOLDEN:
        try:
            if not con.execute(q["ref"]).fetchall():
                broken.append((q["id"], "returned no rows"))
        except Exception as exc:  # noqa: BLE001
            broken.append((q["id"], str(exc)[:80]))
    checks.append(("every reference query executes and returns rows",
                   not broken, f"{len(GOLDEN)} questions, problems: {broken or 'none'}"))

    # 2. tie brittleness on single answer questions
    ties = []
    for q in GOLDEN:
        if "LIMIT 1" not in q["ref"]:
            continue
        try:
            top2 = con.execute(q["ref"].replace("LIMIT 1", "LIMIT 2")).fetchall()
            if len(top2) == 2 and top2[0][-1] == top2[1][-1]:
                ties.append(q["id"])
        except Exception:  # noqa: BLE001
            pass
    checks.append(("single answer questions have no ties",
                   not ties, f"ties found: {ties or 'none'}"))

    # 3. results file (prefer the current prompt version)
    results_path = RESULTS / "results_v2.json"
    if not results_path.exists():
        results_path = RESULTS / "results.json"
    if not results_path.exists():
        checks.append(("results file exists", False, f"missing results_v2.json in {RESULTS}"))
        payload = None
    else:
        payload = json.loads(results_path.read_text())
        required = {"model", "prompt_version", "questions", "passed", "accuracy",
                    "by_category", "taxonomy", "results"}
        missing = required - set(payload)
        checks.append(("results file has required fields",
                       not missing, f"missing: {missing or 'none'}"))

    if payload:
        # 4. taxonomy coverage
        unknown = {r["status"] for r in payload["results"]} - set(TAXONOMY)
        checks.append(("every status is in the documented taxonomy",
                       not unknown, f"unknown statuses: {unknown or 'none'}"))

        # 5. accuracy arithmetic
        recomputed = sum(1 for r in payload["results"] if r["status"] == "pass")
        ok = (recomputed == payload["passed"]
              and abs(recomputed / payload["questions"] - payload["accuracy"]) < 0.0001)
        checks.append(("accuracy matches the per question records",
                       ok, f"{recomputed} passes of {payload['questions']}"))

        # every question accounted for
        ok = len(payload["results"]) == len(GOLDEN) == payload["questions"]
        checks.append(("every golden question appears in the results",
                       ok, f"{len(payload['results'])} records for {len(GOLDEN)} questions"))

    # 6. chart
    chart = RESULTS / "accuracy_by_category.png"
    checks.append(("accuracy chart written", chart.exists(),
                   f"{chart.name}, {chart.stat().st_size if chart.exists() else 0} bytes"))

    print(f"{'CHECK':52} {'RESULT':7} DETAIL")
    print("-" * 100)
    passed = 0
    for name, ok, detail in checks:
        print(f"{name:52} {'PASS' if ok else 'FAIL':7} {detail}")
        passed += int(ok)
    print("-" * 100)
    print(f"=== LAYER 3 ACCEPTANCE: {passed}/{len(checks)} passed ===")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
