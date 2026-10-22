"""Prompt construction for the natural language to SQL task.

Design notes:
- The model gets the schema, the real categorical values, and two sample rows.
- Output is forced to JSON so parsing is deterministic.
- The rules are short and concrete. Long rule lists make small models worse.
"""

from __future__ import annotations

SYSTEM_V1 = """You are a senior SQL analyst. You translate a business question into one
DuckDB SQL query against a retail warehouse.

Rules:
1. Return exactly one SELECT statement. Never write INSERT, UPDATE, DELETE, DROP,
   CREATE or ALTER.
2. Use only the tables and columns listed in the schema. Never invent a column.
3. Join tables using the keys given in the schema.
4. Use the exact category, region, segment and ship mode labels from the value lists.
5. Round money to 2 decimals with ROUND(x, 2).
6. For questions about the top or bottom N, use ORDER BY and LIMIT.
7. When the question asks for a count of orders, count distinct order_id.
8. If the question cannot be answered from this warehouse, set sql to an empty string.

Reply with JSON only, in this shape:
{"sql": "<the query>", "explanation": "<one sentence on what the query does>"}
"""

# Version 2 adds four rules, each one targeting a failure mode observed in the
# v1 evaluation rather than a guess:
#   - dialect errors (TIMESTAMPDIFF does not exist in DuckDB)
#   - averages of ratios used where a weighted ratio was meant
#   - extra identifier columns that the question did not ask for
#   - subquery aliases referenced outside their scope
SYSTEM_V2 = """You are a senior SQL analyst. You translate a business question into one
DuckDB SQL query against a retail warehouse.

Rules:
1. Return exactly one SELECT statement. Never write INSERT, UPDATE, DELETE, DROP,
   CREATE or ALTER.
2. Use only the tables and columns listed in the schema. Never invent a column.
3. Join tables using the keys given in the schema.
4. Use the exact category, region, segment and ship mode labels from the value lists.
5. Round money to 2 decimals with ROUND(x, 2).
6. For questions about the top or bottom N, use ORDER BY and LIMIT.
7. When the question asks for a count of orders, count distinct order_id.
8. If the question cannot be answered from this warehouse, set sql to an empty string.
9. This is DuckDB, not MySQL. Measure time between dates with
   DATEDIFF('day', start_date, end_date). Functions such as TIMESTAMPDIFF do not exist.
10. A margin or rate is a weighted ratio: compute SUM(numerator) / SUM(denominator).
    Never average per row ratios, which gives a different and usually wrong number.
11. Return only the columns the question asks for. Do not add identifier columns such
    as ids or segments unless the question asks for them.
12. If you use a subquery, alias it and refer to its output columns by name. Never refer
    to a table alias from inside a subquery in an outer query.

Reply with JSON only, in this shape:
{"sql": "<the query>", "explanation": "<one sentence on what the query does>"}
"""

SYSTEMS = {"v1": SYSTEM_V1, "v2": SYSTEM_V2}
DEFAULT_PROMPT_VERSION = "v2"


def get_system(version: str = DEFAULT_PROMPT_VERSION) -> str:
    if version not in SYSTEMS:
        raise ValueError(f"unknown prompt version: {version}")
    return SYSTEMS[version]


def build_prompt(context: dict, question: str, error: str | None = None) -> str:
    """Compose the user prompt. If error is given, ask for a repair."""
    parts = [
        "SCHEMA",
        context["schema"],
        "",
        "CATEGORICAL VALUES (use these exact strings)",
        context["enums"],
        "",
        "SAMPLE ROWS",
        context["samples"],
        "",
        f"QUESTION: {question}",
    ]
    if error:
        parts += [
            "",
            "The previous attempt failed with this error:",
            error,
            "Return a corrected query.",
        ]
    return "\n".join(parts)


def build_repair_prompt(context: dict, question: str, bad_sql: str, error: str) -> str:
    return "\n".join(
        [
            "SCHEMA",
            context["schema"],
            "",
            "CATEGORICAL VALUES (use these exact strings)",
            context["enums"],
            "",
            f"QUESTION: {question}",
            "",
            "A previous attempt produced this SQL:",
            bad_sql,
            "",
            "It failed with this error:",
            error,
            "",
            "Return a corrected query in the same JSON shape.",
        ]
    )
