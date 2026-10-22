"""SQL guardrails.

A language model is an untrusted SQL author. Before anything reaches the
database it must pass these checks:

1. Exactly one statement, and it must be a SELECT (or a WITH that ends in SELECT).
2. Only the five warehouse tables may be referenced.
3. No external readers, no system catalogs, no table functions.
4. A hard row cap is applied by wrapping the query.

Every rejection carries a reason that can be shown to a user, because a silent
refusal teaches nobody anything.
"""

from __future__ import annotations

import re

ALLOWED_TABLES = {
    "fact_sales",
    "dim_customer",
    "dim_product",
    "dim_location",
    "dim_date",
}

MAX_ROWS = 500

# Statements that must never appear. Checked on literal stripped SQL.
FORBIDDEN = [
    "insert", "update", "delete", "drop", "create", "alter", "truncate",
    "copy", "attach", "detach", "install", "load", "pragma", "export",
    "import", "call", "execute", "vacuum", "checkpoint", "replace",
    "grant", "revoke", "begin", "commit", "rollback",
]

# Readers and catalogs that could escape the warehouse.
FORBIDDEN_PATTERNS = [
    r"\bread_csv\b", r"\bread_parquet\b", r"\bread_json\b", r"\bread_text\b",
    r"\bparquet_scan\b", r"\bcsv_scan\b", r"\bjson_scan\b", r"\bglob\b",
    r"\bsqlite_scan\b", r"\bpostgres_scan\b", r"\bmysql_scan\b",
    r"\binformation_schema\b", r"\bduckdb_[a-z_]+\b", r"\bpg_[a-z_]+\b",
    r"\bsystem\.[a-z_]+\b", r"\bscratch\.[a-z_]+\b",
]


class GuardrailError(ValueError):
    """Raised when SQL fails a safety check. The message is user facing."""


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql


def _strip_literals(sql: str) -> str:
    """Remove quoted strings so keyword checks do not trip on data values."""
    out = []
    i = 0
    quote = None
    while i < len(sql):
        ch = sql[i]
        if quote:
            if ch == quote:
                if i + 1 < len(sql) and sql[i + 1] == quote:
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(" ")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _split_statements(sql: str) -> list[str]:
    """Split on semicolons that are outside quoted strings."""
    parts, buf, quote, i = [], [], None, 0
    while i < len(sql):
        ch = sql[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                if i + 1 < len(sql) and sql[i + 1] == quote:
                    buf.append(sql[i + 1])
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
        elif ch == ";":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def _cte_names(clean: str) -> set[str]:
    names = set()
    for match in re.finditer(r"(?:with|,)\s+([a-z_][a-z0-9_]*)\s+as\s*\(", clean, re.I):
        names.add(match.group(1).lower())
    return names


def _referenced_tables(clean: str) -> set[str]:
    found = set()
    for match in re.finditer(r"\b(?:from|join)\s+([a-z_][a-z0-9_\.]*)", clean, re.I):
        name = match.group(1).lower()
        if name.startswith("("):
            continue
        found.add(name.split(".")[-1])
    return found


def check(sql: str, max_rows: int = MAX_ROWS) -> str:
    """Validate and return a row capped query. Raises GuardrailError."""
    if not sql or not sql.strip():
        raise GuardrailError("No SQL was produced.")

    cleaned = _strip_comments(sql).strip()

    statements = _split_statements(cleaned)
    if len(statements) != 1:
        raise GuardrailError(
            f"Only one statement is allowed, found {len(statements)}. "
            "Queries must be a single SELECT."
        )
    statement = statements[0]

    snapshot = _strip_literals(statement).lower()

    first_word = re.match(r"\s*([a-z]+)", snapshot)
    if not first_word or first_word.group(1) not in ("select", "with"):
        raise GuardrailError(
            "Only SELECT queries are allowed. The statement must begin with SELECT or WITH."
        )

    for word in FORBIDDEN:
        if re.search(rf"\b{word}\b", snapshot):
            raise GuardrailError(
                f"The query contains a forbidden keyword: {word.upper()}. "
                "Only read only SELECT statements are permitted."
            )

    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, snapshot):
            raise GuardrailError(
                "The query references a table function, catalog or external reader "
                "that is not permitted. Only the five warehouse tables may be read."
            )

    allowed_with_ctes = ALLOWED_TABLES | _cte_names(snapshot)
    referenced = _referenced_tables(snapshot)
    unknown = referenced - allowed_with_ctes
    if unknown:
        raise GuardrailError(
            "The query references unknown table(s): "
            + ", ".join(sorted(unknown))
            + ". Allowed tables are: "
            + ", ".join(sorted(ALLOWED_TABLES))
            + "."
        )

    if not referenced:
        raise GuardrailError("The query does not read from any warehouse table.")

    body = statement.rstrip().rstrip(";")
    return f"SELECT * FROM (\n{body}\n) AS guarded_result LIMIT {max_rows}"


def describe_policy() -> str:
    return (
        f"Read only. One SELECT statement. Tables: {', '.join(sorted(ALLOWED_TABLES))}. "
        f"Maximum {MAX_ROWS} rows returned."
    )
