"""Ask the Warehouse: a plain English interface for a SQL warehouse.

Design intent: a non technical user should be able to ask a question and read
the answer without ever seeing SQL. The SQL is available, but it is behind a
disclosure control rather than in the way.

Run:
    streamlit run app.py
"""

from __future__ import annotations

import pathlib
import time

import streamlit as st

from src.execute import run as run_query
from src.generate import DEFAULT_MODEL, ModelError, generate, list_models
from src.guardrails import MAX_ROWS, GuardrailError, check, describe_policy
from src.prompt import DEFAULT_PROMPT_VERSION, build_prompt, get_system
from src.schema import DEFAULT_DB, connect, full_context

RESULTS_JSON = pathlib.Path(__file__).parent / "eval" / "results" / "results_v2.json"

EXAMPLES = [
    "What is total sales by category?",
    "Which region has the highest total profit?",
    "What are the top 5 sub categories by sales?",
    "Which sub category loses the most money?",
    "How many orders were placed in 2017?",
    "What percentage of order lines were sold at a loss?",
]


@st.cache_resource(show_spinner=False)
def load_context() -> dict:
    """Schema, categorical values and sample rows. Cached for the session."""
    con = connect(DEFAULT_DB, read_only=True)
    return full_context(con)


def accuracy_headline() -> str | None:
    """Read the measured accuracy from the evaluation results, if present."""
    try:
        import json

        payload = json.loads(RESULTS_JSON.read_text())
        return f"{payload['passed']}/{payload['questions']} ({payload['accuracy']:.1%})"
    except Exception:  # noqa: BLE001
        return None


def answer_question(question: str, model: str, timeout: float, max_rows: int,
                    prompt_version: str = DEFAULT_PROMPT_VERSION) -> dict:
    """Run the full pipeline for one question. Returns a result dict.

    Kept free of Streamlit calls so it can be tested directly.
    """
    outcome = {
        "status": None,
        "question": question,
        "sql": None,
        "safe_sql": None,
        "columns": [],
        "rows": [],
        "explanation": None,
        "message": None,
        "gen_latency_s": None,
        "exec_latency_s": None,
        "model": model,
    }

    context = load_context()

    try:
        gen = generate(build_prompt(context, question), get_system(prompt_version),
                       model=model)
    except ModelError as exc:
        outcome.update(status="model_error", message=str(exc))
        return outcome

    outcome["gen_latency_s"] = gen["latency_s"]
    outcome["explanation"] = gen["explanation"]
    outcome["sql"] = gen["sql"]

    if not gen["sql"]:
        outcome.update(status="no_sql",
                       message="The question could not be answered from this warehouse.")
        return outcome

    try:
        safe = check(gen["sql"], max_rows=max_rows)
    except GuardrailError as exc:
        outcome.update(status="refused", message=str(exc))
        return outcome

    outcome["safe_sql"] = safe
    result = run_query(str(DEFAULT_DB), safe, timeout_s=timeout, max_rows=max_rows)
    outcome["exec_latency_s"] = result["elapsed_s"]

    if result["status"] == "timeout":
        outcome.update(status="timeout", message=result["error"])
        return outcome
    if result["status"] == "error":
        outcome.update(status="query_error", message=result["error"])
        return outcome

    outcome.update(status="ok", columns=result["columns"], rows=result["rows"])
    return outcome


def render_answer(outcome: dict) -> None:
    status = outcome["status"]

    if status == "ok":
        if not outcome["rows"]:
            st.warning("The query ran but returned no rows.")
        else:
            st.dataframe(
                [dict(zip(outcome["columns"], row)) for row in outcome["rows"]],
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                f"{len(outcome['rows'])} row(s) returned in {outcome['exec_latency_s']}s. "
                f"Query written in {outcome['gen_latency_s']}s by {outcome['model']}."
            )
        with st.expander("What this query does"):
            st.write(outcome["explanation"] or "No explanation given.")
        with st.expander("Show the SQL behind this answer"):
            st.code(outcome["sql"], language="sql")
        with st.expander("Safety checks applied"):
            st.write(describe_policy())
            st.write("The statement passed every check before it was allowed to run.")
        return

    if status == "refused":
        st.error("That query was blocked by the safety layer.")
        st.write(outcome["message"])
        st.caption(describe_policy())
    elif status == "no_sql":
        st.info(outcome["message"])
    elif status == "model_error":
        st.error("The local model could not be reached.")
        st.write(outcome["message"])
    elif status == "timeout":
        st.error("The query took too long and was stopped.")
        st.write(outcome["message"])
    else:
        st.error("The query failed to run.")
        st.write(outcome["message"])

    if outcome.get("sql"):
        with st.expander("Show the SQL that was attempted"):
            st.code(outcome["sql"], language="sql")


def main() -> None:
    st.set_page_config(page_title="Ask the Warehouse", page_icon="🗄️", layout="wide")

    st.title("Ask the Warehouse")
    st.write(
        "Ask a question about the retail sales data in plain English. "
        "The system writes the SQL, checks it for safety, runs it, and shows you the answer."
    )

    with st.sidebar:
        st.header("Settings")
        try:
            models = list_models()
        except ModelError:
            models = [DEFAULT_MODEL]
            st.warning("Ollama is not reachable. Start it to run questions.")
        model = st.selectbox(
            "Model", options=models,
            index=models.index(DEFAULT_MODEL) if DEFAULT_MODEL in models else 0,
        )
        timeout = st.slider("Query time limit (seconds)", 2, 60, 15)
        max_rows = st.slider("Maximum rows returned", 10, 1000, MAX_ROWS, step=10)

        st.divider()
        st.header("Measured accuracy")
        headline = accuracy_headline()
        if headline:
            st.metric("Execution accuracy", headline)
            st.caption(
                "Measured on 41 unseen questions with verified reference answers. "
                "Every failure is classified, and the harness reruns in one command."
            )
        else:
            st.caption("Run `python -m eval.run_eval` to produce the accuracy figures.")

        st.divider()
        st.caption("Local model only. No API keys, no spend.")

    if "question" not in st.session_state:
        st.session_state.question = ""

    st.subheader("Try one of these")
    cols = st.columns(3)
    for i, example in enumerate(EXAMPLES):
        if cols[i % 3].button(example, use_container_width=True):
            st.session_state.question = example

    question = st.text_input(
        "Your question",
        value=st.session_state.question,
        placeholder="e.g. which state has the most loss making order lines?",
    )

    if st.button("Get the answer", type="primary") and question.strip():
        with st.spinner("Writing SQL, checking it, running it."):
            started = time.time()
            outcome = answer_question(question.strip(), model, float(timeout), max_rows)
        st.session_state.last = outcome
        st.caption(f"Total time {round(time.time() - started, 1)}s")

    if st.session_state.get("last"):
        st.divider()
        render_answer(st.session_state.last)


if __name__ == "__main__":
    main()
