"""Model client for local Ollama inference.

Everything runs locally and costs nothing. Two settings matter for
reproducibility: temperature 0 and a fixed seed.
"""

from __future__ import annotations

import json
import re
import time

import requests

HOST = "http://localhost:11434"
DEFAULT_MODEL = "qwen3.5:9b"


class ModelError(RuntimeError):
    pass


def _extract_json(text: str) -> dict:
    """Parse the model output, tolerating code fences and stray prose."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    raise ModelError(f"Model did not return JSON. Raw output: {text[:400]}")


def generate(
    prompt: str,
    system: str,
    model: str = DEFAULT_MODEL,
    host: str = HOST,
    timeout: int = 300,
) -> dict:
    """Call Ollama and return a dict with sql, explanation, latency and raw text."""
    payload = {
        "model": model,
        "system": system,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0, "seed": 42, "num_ctx": 4096},
    }
    started = time.time()
    try:
        resp = requests.post(f"{host}/api/generate", json=payload, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise ModelError(
            f"Could not reach Ollama at {host}. Is it running? ({exc})"
        ) from exc

    latency = time.time() - started
    body = resp.json()
    raw = body.get("response", "")
    data = _extract_json(raw)

    sql = (data.get("sql") or "").strip()
    if sql.endswith(";"):
        sql = sql[:-1]

    return {
        "sql": sql,
        "explanation": (data.get("explanation") or "").strip(),
        "latency_s": round(latency, 2),
        "prompt_tokens": body.get("prompt_eval_count"),
        "output_tokens": body.get("eval_count"),
        "raw": raw,
    }


def list_models(host: str = HOST) -> list[str]:
    try:
        resp = requests.get(f"{host}/api/tags", timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise ModelError(f"Ollama not reachable at {host}: {exc}") from exc
    return [m["name"] for m in resp.json().get("models", [])]
