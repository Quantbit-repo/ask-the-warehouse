"""Ask a question in plain English. Get guarded SQL, then rows.

Usage:
    python -m src.ask "What is total sales by category?" --show-sql
    python -m src.ask "Top 5 sub categories by profit" --timeout 15
"""

from __future__ import annotations

import argparse
import sys

from src.execute import run as run_query
from src.generate import DEFAULT_MODEL, ModelError, generate
from src.guardrails import MAX_ROWS, GuardrailError, check, describe_policy
from src.prompt import SYSTEM, build_prompt
from src.schema import DEFAULT_DB, connect, full_context


def print_table(columns: list, rows: list) -> None:
    if not rows:
        print("(no rows returned)")
        return
    widths = [len(str(c)) for c in columns]
    for row in rows:
        for i, val in enumerate(row):
            widths[i] = max(widths[i], len(str(val)))
    print(" | ".join(str(c).ljust(widths[i]) for i, c in enumerate(columns)))
    print("-" * (sum(widths) + 3 * (len(columns) - 1)))
    for row in rows:
        print(" | ".join(str(v).ljust(widths[i]) for i, v in enumerate(row)))
    print(f"\n{len(rows)} row(s)")


def run(db: str, question: str, model: str, show_sql: bool, timeout: float,
        max_rows: int) -> int:
    con = connect(db, read_only=True)
    context = full_context(con)

    result = generate(build_prompt(context, question), SYSTEM, model=model)
    raw_sql = result["sql"]

    if not raw_sql:
        print("The model judged this question unanswerable from the warehouse.")
        print("Explanation:", result["explanation"] or "no explanation given")
        return 1

    if show_sql:
        print("Proposed SQL:")
        print("  " + raw_sql.replace("\n", "\n  "))
        print()

    try:
        safe_sql = check(raw_sql, max_rows=max_rows)
    except GuardrailError as exc:
        print("REFUSED BY GUARDRAIL")
        print(exc)
        print("\nPolicy:", describe_policy())
        return 4

    print("Explanation:", result["explanation"])
    print(f"Model: {model} | generation: {result['latency_s']}s")
    print()

    execution = run_query(db, safe_sql, timeout_s=timeout, max_rows=max_rows)

    if execution["status"] == "timeout":
        print("QUERY STOPPED:", execution["error"])
        return 5
    if execution["status"] == "error":
        print("QUERY FAILED:", execution["error"])
        return 2

    print_table(execution["columns"], execution["rows"])
    print(f"execution: {execution['elapsed_s']}s | row cap: {max_rows}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Natural language analytics over the retail warehouse")
    parser.add_argument("question", help="the business question in plain English")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model name")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="path to the DuckDB warehouse")
    parser.add_argument("--show-sql", action="store_true", help="print the generated SQL")
    parser.add_argument("--timeout", type=float, default=10.0, help="query timeout in seconds")
    parser.add_argument("--max-rows", type=int, default=MAX_ROWS, help="row cap")
    args = parser.parse_args()

    try:
        code = run(args.db, args.question, args.model, args.show_sql,
                   args.timeout, args.max_rows)
    except ModelError as exc:
        print("MODEL ERROR:", exc)
        code = 3
    sys.exit(code)


if __name__ == "__main__":
    main()
