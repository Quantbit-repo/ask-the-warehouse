"""Layer 2 acceptance check: guardrails and execution limits.

Acceptance criteria:
1. Write and DDL statements are refused.
2. Unknown tables are refused.
3. External readers and system catalogs are refused.
4. Multiple statements are refused.
5. Legitimate SELECT queries still pass.
6. A query returning more rows than the cap is truncated to the cap.
7. A runaway query is stopped by the timeout.

Run: python scripts/acceptance_layer2.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from src.execute import run as run_query  # noqa: E402
from src.guardrails import ALLOWED_TABLES, MAX_ROWS, GuardrailError, check  # noqa: E402
from src.schema import DEFAULT_DB  # noqa: E402

REFUSE_CASES = [
    ("DROP TABLE", "DROP TABLE fact_sales"),
    ("DELETE rows", "DELETE FROM fact_sales WHERE profit < 0"),
    ("UPDATE rows", "UPDATE fact_sales SET profit = 0"),
    ("unknown table", "SELECT * FROM users"),
    ("external reader", "SELECT * FROM read_csv('/etc/passwd')"),
    ("system catalog", "SELECT * FROM information_schema.tables"),
    ("two statements", "SELECT * FROM fact_sales LIMIT 5; DROP TABLE fact_sales"),
    ("not a select", "PRAGMA database_list"),
]

ALLOW_CASES = [
    ("simple aggregate", "SELECT p.category, SUM(f.sales) AS s FROM fact_sales f "
                        "JOIN dim_product p ON f.product_id = p.product_id GROUP BY 1"),
    ("with cte", "WITH x AS (SELECT category FROM dim_product) SELECT COUNT(*) FROM x"),
    ("join with alias", "SELECT p.category, SUM(f.sales) FROM fact_sales f "
                        "JOIN dim_product p ON f.product_id = p.product_id GROUP BY 1"),
    ("quoted literal", "SELECT * FROM dim_product WHERE category = 'Technology'"),
]

ROW_CAP_CASE = "SELECT * FROM fact_sales"

TIMEOUT_CASE = ("SELECT COUNT(*) FROM fact_sales a, fact_sales b, "
                "fact_sales c, fact_sales d")


def main() -> int:
    results = []

    for name, sql in REFUSE_CASES:
        try:
            check(sql)
            results.append((name, False, "was NOT refused"))
        except GuardrailError as exc:
            results.append((name, True, str(exc)[:70]))

    for name, sql in ALLOW_CASES:
        try:
            safe = check(sql)
        except GuardrailError as exc:
            results.append((name, False, f"wrongly refused: {exc}"))
            continue
        outcome = run_query(str(DEFAULT_DB), safe, timeout_s=10, max_rows=MAX_ROWS)
        if outcome["status"] == "ok":
            results.append((name, True, f"{len(outcome['rows'])} rows"))
        else:
            results.append((name, False, outcome["error"] or "unknown"))

    try:
        safe = check(ROW_CAP_CASE, max_rows=MAX_ROWS)
        outcome = run_query(str(DEFAULT_DB), safe, timeout_s=15, max_rows=MAX_ROWS)
        ok = outcome["status"] == "ok" and len(outcome["rows"]) == MAX_ROWS
        results.append(
            ("row cap enforced", ok,
             f"{len(outcome['rows'])} rows returned, cap {MAX_ROWS}")
        )
    except GuardrailError as exc:
        results.append(("row cap enforced", False, f"refused: {exc}"))

    try:
        safe = check(TIMEOUT_CASE)
        outcome = run_query(str(DEFAULT_DB), safe, timeout_s=2, max_rows=MAX_ROWS)
        ok = outcome["status"] == "timeout"
        results.append(("timeout stops runaway query", ok, outcome["status"]))
    except GuardrailError as exc:
        results.append(("timeout stops runaway query", False, f"refused: {exc}"))

    print(f"{'CHECK':32} {'RESULT':8} DETAIL")
    print("-" * 88)
    passed = 0
    for name, ok, detail in results:
        print(f"{name:32} {'PASS' if ok else 'FAIL':8} {detail}")
        passed += int(ok)

    print("-" * 88)
    print(f"=== LAYER 2 ACCEPTANCE: {passed}/{len(results)} passed ===")
    print(f"Allowed tables: {', '.join(sorted(ALLOWED_TABLES))}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
