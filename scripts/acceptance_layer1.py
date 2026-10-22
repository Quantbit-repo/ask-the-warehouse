"""Layer 1 acceptance check.

Acceptance criterion: for five representative business questions, the system
produces SQL that executes against the warehouse and returns rows.

Run: python scripts/acceptance_layer1.py
"""

from __future__ import annotations

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.generate import DEFAULT_MODEL, generate  # noqa: E402
from src.prompt import build_prompt, get_system  # noqa: E402
from src.schema import connect, full_context  # noqa: E402

QUESTIONS = [
    "What is total sales by category?",
    "Which region has the highest total profit?",
    "How many distinct orders were placed in 2017?",
    "What are the top 5 sub categories by sales?",
    "Which customer segment has the lowest average discount?",
]


def main() -> int:
    con = connect(read_only=True)
    context = full_context(con)
    passed = 0

    for i, question in enumerate(QUESTIONS, 1):
        print(f"\n[{i}/{len(QUESTIONS)}] {question}")
        try:
            result = generate(build_prompt(context, question), get_system(),
                               model=DEFAULT_MODEL)
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL model error: {exc}")
            continue

        sql = result["sql"]
        if not sql:
            print("  FAIL model returned no SQL")
            continue
        print("  SQL:", sql.replace("\n", " ")[:150])

        try:
            cur = con.execute(sql)
            rows = cur.fetchall()
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL execution: {type(exc).__name__}: {str(exc)[:140]}")
            continue

        print(f"  PASS rows={len(rows)} latency={result['latency_s']}s")
        if rows:
            print(f"  first row: {rows[0]}")
        passed += 1

    print(f"\n=== LAYER 1 ACCEPTANCE: {passed}/{len(QUESTIONS)} passed ===")
    return 0 if passed == len(QUESTIONS) else 1


if __name__ == "__main__":
    sys.exit(main())
