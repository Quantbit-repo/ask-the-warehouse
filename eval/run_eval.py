"""Evaluation harness: measure how often the system is actually right.

Method
------
Each golden question is answered by the model, passed through the guardrails,
executed, and compared against the reference result set computed by verified
hand written SQL. The headline metric is execution accuracy: the fraction of
questions whose returned rows match the reference rows.

Comparison is deliberately defined so it cannot be gamed:
- numbers are rounded to 2 decimals before comparing
- strings are stripped and compared case sensitively
- row order and column order are ignored
- the number of columns and rows must match exactly

Every failure is classified into the error taxonomy, because a single accuracy
number tells you nothing about what to fix.

Run:
    python -m eval.run_eval                  # full set
    python -m eval.run_eval --limit 5        # quick check
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import duckdb

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from eval.golden_set import CATEGORIES, GOLDEN  # noqa: E402
from src.execute import run as run_query  # noqa: E402
from src.generate import DEFAULT_MODEL, ModelError, generate  # noqa: E402
from src.guardrails import GuardrailError, check  # noqa: E402
from src.prompt import DEFAULT_PROMPT_VERSION, build_prompt, get_system  # noqa: E402
from src.schema import DEFAULT_DB, connect, full_context  # noqa: E402

RESULTS_DIR = pathlib.Path(__file__).resolve().parent / "results"

TAXONOMY = {
    "pass": "Answer matches the reference result set",
    "no_sql": "Model judged the question unanswerable",
    "guardrail_refused": "Generated SQL was rejected by the safety layer",
    "execution_error": "SQL failed to run against the warehouse",
    "timeout": "Query exceeded the execution time limit",
    "wrong_result": "SQL ran but the rows did not match the reference",
}


def normalize(rows) -> list[tuple]:
    """Make a result set comparable: round numbers, strip strings, sort."""
    out = []
    for row in rows:
        vals = []
        for v in row:
            if isinstance(v, bool):
                vals.append(v)
            elif isinstance(v, (int, float)):
                vals.append(round(float(v), 2))
            elif v is None:
                vals.append(None)
            else:
                vals.append(str(v).strip())
        out.append(tuple(sorted(vals, key=lambda x: (x is None, str(type(x)), str(x)))))
    return sorted(out, key=lambda r: [str(x) for x in r])


def compare(model_rows, ref_rows) -> bool:
    return normalize(model_rows) == normalize(ref_rows)


def diagnose(model_rows, ref_rows) -> str:
    """A short, honest description of how the rows differ."""
    if len(model_rows) != len(ref_rows):
        return f"row count {len(model_rows)} vs expected {len(ref_rows)}"
    m_cols = len(model_rows[0]) if model_rows else 0
    r_cols = len(ref_rows[0]) if ref_rows else 0
    if m_cols != r_cols:
        return f"column count {m_cols} vs expected {r_cols}"
    return "values differ"


def run_eval(model: str, limit: int | None, timeout: float, threshold: float,
             prompt_version: str = DEFAULT_PROMPT_VERSION) -> int:
    system_prompt = get_system(prompt_version)
    con = connect(DEFAULT_DB, read_only=True)
    context = full_context(con)

    questions = GOLDEN[:limit] if limit else GOLDEN
    results = []
    started = time.time()

    print(f"Evaluating {len(questions)} questions with {model} (prompt {prompt_version})")
    print("-" * 78)

    for i, q in enumerate(questions, 1):
        record = {
            "id": q["id"],
            "category": q["category"],
            "question": q["question"],
            "ref_sql": q["ref"],
            "status": None,
            "sql": None,
            "detail": None,
            "gen_latency_s": None,
            "exec_latency_s": None,
            "prompt_tokens": None,
            "output_tokens": None,
        }

        ref_rows = con.execute(q["ref"]).fetchall()

        try:
            gen = generate(build_prompt(context, q["question"]), system_prompt, model=model)
        except ModelError as exc:
            record.update(status="execution_error", detail=f"model unreachable: {exc}")
            results.append(record)
            print(f"[{i:2}/{len(questions)}] {q['id']:26} MODEL ERROR")
            continue

        record["sql"] = gen["sql"]
        record["gen_latency_s"] = gen["latency_s"]
        record["prompt_tokens"] = gen["prompt_tokens"]
        record["output_tokens"] = gen["output_tokens"]

        if not gen["sql"]:
            record.update(status="no_sql", detail="model returned empty SQL")
            results.append(record)
            print(f"[{i:2}/{len(questions)}] {q['id']:26} NO SQL")
            continue

        try:
            safe = check(gen["sql"])
        except GuardrailError as exc:
            record.update(status="guardrail_refused", detail=str(exc))
            results.append(record)
            print(f"[{i:2}/{len(questions)}] {q['id']:26} REFUSED")
            continue

        outcome = run_query(str(DEFAULT_DB), safe, timeout_s=timeout)
        record["exec_latency_s"] = outcome["elapsed_s"]

        if outcome["status"] == "timeout":
            record.update(status="timeout", detail=outcome["error"])
            results.append(record)
            print(f"[{i:2}/{len(questions)}] {q['id']:26} TIMEOUT")
            continue

        if outcome["status"] == "error":
            record.update(status="execution_error", detail=outcome["error"][:200])
            results.append(record)
            print(f"[{i:2}/{len(questions)}] {q['id']:26} EXEC ERROR")
            continue

        if compare(outcome["rows"], ref_rows):
            record.update(status="pass")
            print(f"[{i:2}/{len(questions)}] {q['id']:26} PASS")
        else:
            record.update(status="wrong_result", detail=diagnose(outcome["rows"], ref_rows))
            print(f"[{i:2}/{len(questions)}] {q['id']:26} WRONG ({record['detail']})")

        results.append(record)

    elapsed = round(time.time() - started, 1)
    passed = sum(1 for r in results if r["status"] == "pass")
    accuracy = passed / len(results) if results else 0.0

    # ---- summary ----
    print("-" * 78)
    print(f"EXECUTION ACCURACY: {passed}/{len(results)} = {accuracy:.1%}")
    print(f"total wall clock: {elapsed}s")

    print("\nBy category:")
    by_cat = {}
    for r in results:
        c = r["category"]
        by_cat.setdefault(c, [0, 0])
        by_cat[c][1] += 1
        by_cat[c][0] += int(r["status"] == "pass")
    for c in CATEGORIES:
        if c in by_cat:
            p, n = by_cat[c]
            print(f"  {c:12} {p}/{n}  {p / n:.0%}")

    print("\nError taxonomy:")
    tax = {}
    for r in results:
        tax[r["status"]] = tax.get(r["status"], 0) + 1
    for status, count in sorted(tax.items(), key=lambda kv: -kv[1]):
        print(f"  {status:18} {count:3}  {TAXONOMY.get(status, '')}")

    failures = [r for r in results if r["status"] != "pass"]
    if failures:
        print("\nFailures:")
        for r in failures:
            print(f"  {r['id']:26} {r['status']:18} {str(r['detail'])[:80]}")

    lat = [r["gen_latency_s"] for r in results if r["gen_latency_s"]]
    if lat:
        print(f"\nGeneration latency: mean {sum(lat) / len(lat):.1f}s "
              f"min {min(lat):.1f}s max {max(lat):.1f}s")

    # ---- persist ----
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": model,
        "prompt_version": prompt_version,
        "questions": len(results),
        "passed": passed,
        "accuracy": round(accuracy, 4),
        "wall_clock_s": elapsed,
        "by_category": {c: {"passed": v[0], "total": v[1]} for c, v in by_cat.items()},
        "taxonomy": tax,
        "results": results,
    }
    out = RESULTS_DIR / f"results_{prompt_version}.json"
    out.write_text(json.dumps(payload, indent=1))
    print(f"\nresults written to {out}")

    write_chart(by_cat, accuracy, model)

    if accuracy < threshold:
        print(f"\nFAIL: accuracy {accuracy:.1%} is below the {threshold:.0%} threshold")
        return 1
    print(f"\nPASS: accuracy {accuracy:.1%} meets the {threshold:.0%} threshold")
    return 0


def write_chart(by_cat: dict, accuracy: float, model: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cats = [c for c in CATEGORIES if c in by_cat]
    pct = [100 * by_cat[c][0] / by_cat[c][1] for c in cats]
    counts = [f"{by_cat[c][0]}/{by_cat[c][1]}" for c in cats]

    fig, ax = plt.subplots(figsize=(9, 4.5))
    bars = ax.bar(cats, pct, color="#4C6EF5")
    for bar, label in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.5,
                label, ha="center", fontsize=9)
    ax.set_ylim(0, 108)
    ax.set_ylabel("Execution accuracy (%)")
    ax.set_title(f"Natural language to SQL accuracy by question type\n"
                 f"{model}, overall {accuracy:.1%}")
    ax.axhline(100 * accuracy, color="#E8590C", linestyle="--", linewidth=1,
               label=f"overall {accuracy:.1%}")
    ax.legend(loc="lower right", frameon=False)
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    path = RESULTS_DIR / "accuracy_by_category.png"
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"chart written to {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate natural language to SQL accuracy")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, default=None, help="only run the first N questions")
    parser.add_argument("--timeout", type=float, default=15.0, help="per query execution timeout")
    parser.add_argument("--threshold", type=float, default=0.5,
                        help="exit nonzero if accuracy is below this fraction")
    parser.add_argument("--prompt-version", default=DEFAULT_PROMPT_VERSION,
                        choices=["v1", "v2"], help="which system prompt to evaluate")
    args = parser.parse_args()
    sys.exit(run_eval(args.model, args.limit, args.timeout, args.threshold,
                      args.prompt_version))


if __name__ == "__main__":
    main()
