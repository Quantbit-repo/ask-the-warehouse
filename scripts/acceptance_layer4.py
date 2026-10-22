"""Layer 4 acceptance check: the interface path works end to end.

Acceptance criteria:
1. The app module imports without a Streamlit runtime running.
2. A real question returns a table of rows through the same function the UI calls.
3. The answer is presented before the SQL: the primary result path carries rows
   and columns, and the SQL is only exposed through a disclosure control.
4. A query that fails the safety layer is reported as refused, not as a crash.
5. A runaway query is reported as a timeout, not as a hang.
6. The measured accuracy headline is read from the evaluation results.

Note on structure: everything runs inside main() behind an __main__ guard. This
is not style. Query execution spawns a child process, and spawn re-imports the
entry module in that child. Unguarded top level code therefore re-runs the whole
script recursively, which shows up as a mysterious timeout rather than an error.

Run: python scripts/acceptance_layer4.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import app  # noqa: E402


def fake_generate(sql: str):
    def _inner(*args, **kwargs):
        return {"sql": sql, "explanation": "test", "latency_s": 0.0,
                "prompt_tokens": 0, "output_tokens": 0, "raw": ""}
    return _inner


def main() -> int:
    checks = []

    def record(name: str, ok: bool, detail: str = "") -> None:
        checks.append((name, ok, detail))

    # 1. import cleanly
    record("app module imports without a Streamlit runtime", True, "import app succeeded")

    # 2. real question through the UI code path
    outcome = app.answer_question("What is total sales by category?", "qwen3.5:9b", 30.0, 500)
    ok = outcome["status"] == "ok" and len(outcome["rows"]) == 3 and bool(outcome["columns"])
    record("a real question returns rows through the UI function", ok,
           f"status={outcome['status']} rows={len(outcome['rows'])}")

    # 3. answer before SQL
    has_table = bool(outcome["columns"]) and bool(outcome["rows"])
    record("answer is the primary result and SQL is exposed separately",
           has_table and outcome["sql"] is not None,
           "rows and columns returned; SQL held in its own field")

    source = pathlib.Path(app.__file__).read_text()
    dataframe_pos = source.find("st.dataframe")
    expander_pos = source.find("Show the SQL behind this answer")
    record("the table is rendered before any SQL disclosure",
           dataframe_pos != -1 and expander_pos != -1 and dataframe_pos < expander_pos,
           f"dataframe at {dataframe_pos}, sql expander at {expander_pos}")

    # 4. guardrail refusal is handled, not crashed
    real_generate = app.generate
    app.generate = fake_generate("DROP TABLE fact_sales")
    refused = app.answer_question("delete everything", "qwen3.5:9b", 30.0, 500)
    app.generate = real_generate
    record("a dangerous query is reported as refused",
           refused["status"] == "refused", f"status={refused['status']}")

    # 5. runaway query reported as timeout
    app.generate = fake_generate(
        "SELECT COUNT(*) FROM fact_sales a, fact_sales b, fact_sales c, fact_sales d")
    slow = app.answer_question("count everything four ways", "qwen3.5:9b", 2.0, 500)
    app.generate = real_generate
    record("a runaway query is reported as a timeout",
           slow["status"] == "timeout", f"status={slow['status']}")

    # 6. accuracy headline
    headline = app.accuracy_headline()
    record("accuracy headline is read from the evaluation results",
           bool(headline) and "%" in headline, f"headline={headline}")

    print(f"{'CHECK':56} {'RESULT':7} DETAIL")
    print("-" * 104)
    passed = 0
    for name, ok, detail in checks:
        print(f"{name:56} {'PASS' if ok else 'FAIL':7} {detail}")
        passed += int(ok)
    print("-" * 104)
    print(f"=== LAYER 4 ACCEPTANCE: {passed}/{len(checks)} passed ===")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
