"""Schema introspection for the retail warehouse.

The model cannot see the database, so we describe it in the prompt. Two things
matter for accuracy: the exact column names, and the actual values of low
cardinality columns (category, region and friends). Without the value lists the
model invents labels like "Technology & Electronics".
"""

from __future__ import annotations

import pathlib

import duckdb

DEFAULT_DB = pathlib.Path(
    "/Users/user/projects/retail-bi-dashboard/data/retail.db"
)

TABLES = ["fact_sales", "dim_customer", "dim_product", "dim_location", "dim_date"]

ENUM_COLUMNS = [
    ("dim_product", "category"),
    ("dim_product", "sub_category"),
    ("dim_customer", "segment"),
    ("dim_location", "region"),
    ("dim_location", "state"),
    ("fact_sales", "ship_mode"),
]

TABLE_NOTES = {
    "fact_sales": "One row per order line. Measures: sales, quantity, discount, profit.",
    "dim_customer": "Join on customer_id.",
    "dim_product": "Join on product_id.",
    "dim_location": "Join on postal_code.",
    "dim_date": "Join on order_date. Has order_year, order_month, order_year_month.",
}


def connect(db_path: str | pathlib.Path = DEFAULT_DB, read_only: bool = True):
    return duckdb.connect(str(db_path), read_only=read_only)


def describe(con) -> str:
    """Return a compact text description of the warehouse for the prompt."""
    blocks = []
    for table in TABLES:
        rows = con.execute(
            "select column_name, data_type from information_schema.columns "
            "where table_schema = 'main' and table_name = ? order by ordinal_position",
            [table],
        ).fetchall()
        count = con.execute(f"select count(*) from {table}").fetchone()[0]
        lines = [f"TABLE {table} ({count} rows)", f"  note: {TABLE_NOTES[table]}"]
        for name, dtype in rows:
            lines.append(f"  {name} {dtype}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def enum_values(con) -> str:
    """Return the real distinct values for categorical columns."""
    lines = []
    for table, column in ENUM_COLUMNS:
        vals = con.execute(
            f"select distinct {column} from {table} "
            f"where {column} is not null order by 1"
        ).fetchall()
        clean = [str(v[0]) for v in vals]
        if len(clean) <= 30:
            lines.append(f"{column}: " + " | ".join(clean))
        else:
            lines.append(
                f"{column}: {len(clean)} distinct values, examples: "
                + " | ".join(clean[:10])
            )
    return "\n".join(lines)


def sample_rows(con, table: str, n: int = 2) -> str:
    """A couple of real rows so the model sees the shape of the data."""
    cur = con.execute(f"select * from {table} limit {n}")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    out = [f"{table}: " + " | ".join(cols)]
    for r in rows:
        out.append("  " + " | ".join(str(v) for v in r))
    return "\n".join(out)


def full_context(con) -> dict:
    return {
        "schema": describe(con),
        "enums": enum_values(con),
        "samples": "\n".join(sample_rows(con, t, 2) for t in TABLES),
    }
