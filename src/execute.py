"""Query execution with a hard wall clock timeout.

DuckDB has no statement timeout, so a runaway query cannot be cancelled in
process. Instead the query runs in a child process, which can be terminated.
The tradeoff is roughly half a second of process start up per query, which is
small next to model latency.

Ordering matters. The parent must read the result pipe while the child is still
alive. If it waits in join() first, a large result fills the pipe buffer, the
child blocks inside put(), and neither side can move. That deadlock is real and
was caught by the row cap test.
"""

from __future__ import annotations

import multiprocessing as mp
import queue as queue_module
import time


def _worker(db_path: str, sql: str, max_rows: int, result_queue) -> None:
    import duckdb

    try:
        con = duckdb.connect(db_path, read_only=True)
        cur = con.execute(sql)
        columns = [d[0] for d in cur.description]
        rows = cur.fetchmany(max_rows)
        result_queue.put(("ok", columns, rows))
    except Exception as exc:  # noqa: BLE001 - the message is shown to the user
        result_queue.put(("error", type(exc).__name__, str(exc)))


def _stop(process) -> None:
    process.terminate()
    process.join(2)
    if process.is_alive():
        process.kill()
        process.join(1)


def run(db_path: str, sql: str, timeout_s: float = 10.0, max_rows: int = 500) -> dict:
    """Execute SQL in a child process. Never raises for query errors.

    Returns a dict with status in {ok, error, timeout}.
    """
    ctx = mp.get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(target=_worker, args=(str(db_path), sql, max_rows, result_queue))
    started = time.time()
    process.start()

    deadline = started + timeout_s
    payload = None
    timed_out = False

    # Read while the child is alive so a large result cannot deadlock the pipe.
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            timed_out = process.is_alive()
            break
        try:
            payload = result_queue.get(timeout=min(0.1, remaining))
            break
        except queue_module.Empty:
            if not process.is_alive():
                # The child has exited. Its data may still be in flight.
                try:
                    payload = result_queue.get(timeout=1.0)
                except queue_module.Empty:
                    payload = None
                break

    elapsed = round(time.time() - started, 2)

    if timed_out:
        _stop(process)
        return {
            "status": "timeout",
            "error": f"Query exceeded the {timeout_s:g} second limit and was stopped.",
            "columns": [],
            "rows": [],
            "elapsed_s": elapsed,
        }

    process.join(1)
    if process.is_alive():
        _stop(process)

    if payload is None:
        return {
            "status": "error",
            "error": "The query process ended without returning a result.",
            "columns": [],
            "rows": [],
            "elapsed_s": elapsed,
        }

    if payload[0] == "ok":
        return {
            "status": "ok",
            "columns": payload[1],
            "rows": payload[2],
            "error": None,
            "elapsed_s": elapsed,
        }

    return {
        "status": "error",
        "error": f"{payload[1]}: {payload[2]}",
        "columns": [],
        "rows": [],
        "elapsed_s": elapsed,
    }
