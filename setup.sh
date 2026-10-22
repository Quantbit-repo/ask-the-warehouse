#!/usr/bin/env bash
# One command setup for Ask the Warehouse.
#
# Checks every prerequisite before installing anything, and says exactly what to
# do when something is missing. A handoff that fails silently is worse than no
# handoff at all.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

WAREHOUSE="${WAREHOUSE_PATH:-$HOME/projects/retail-bi-dashboard/data/retail.db}"
VENV=".venv"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"

ok()   { printf '  [ok]   %s\n' "$1"; }
warn() { printf '  [warn] %s\n' "$1"; }
fail() { printf '  [fail] %s\n' "$1"; }

echo "Ask the Warehouse: setup"
echo "========================"
echo

echo "1. Checking Python"
if command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    ok "$($PYTHON_BIN --version)"
else
    fail "$PYTHON_BIN not found. Install Python 3.11 or set PYTHON_BIN."
    exit 1
fi

echo
echo "2. Checking Ollama (the local model runtime)"
if curl -s -m 5 http://localhost:11434/api/tags >/dev/null 2>&1; then
    ok "Ollama is running"
    if curl -s -m 5 http://localhost:11434/api/tags | grep -q "qwen3.5:9b"; then
        ok "model qwen3.5:9b is available"
    else
        warn "model qwen3.5:9b not found. Pull it with: ollama pull qwen3.5:9b"
    fi
else
    warn "Ollama is not reachable at localhost:11434."
    warn "Start it with: ollama serve"
    warn "The app will run, but questions cannot be answered without it."
fi

echo
echo "3. Checking the warehouse"
if [ -f "$WAREHOUSE" ]; then
    ok "found $WAREHOUSE"
else
    fail "warehouse not found at $WAREHOUSE"
    echo
    echo "  This project reads a DuckDB warehouse built by the retail BI project."
    echo "  Build it with:"
    echo
    echo "      cd ~/projects/retail-bi-dashboard && python scripts/build_database.py"
    echo
    echo "  Or point at a different file:"
    echo
    echo "      WAREHOUSE_PATH=/path/to/retail.db ./setup.sh"
    exit 1
fi

echo
echo "4. Installing Python packages"
if [ ! -d "$VENV" ]; then
    "$PYTHON_BIN" -m venv "$VENV"
    ok "created $VENV"
else
    ok "$VENV already exists, reusing it"
fi
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r requirements.txt
ok "packages installed"

echo
echo "5. Verifying the pipeline"
if "$VENV/bin/python" -c "
import sys
sys.path.insert(0, '.')
from src.guardrails import check
from src.schema import connect, full_context
con = connect('$WAREHOUSE', read_only=True)
ctx = full_context(con)
rows = con.execute('select count(*) from fact_sales').fetchone()[0]
assert rows > 0
safe = check('SELECT category FROM dim_product')
print(f'  [ok]   warehouse readable, {rows} fact rows')
print(f'  [ok]   guardrails active')
"; then
    ok "verification passed"
else
    fail "verification failed"
    exit 1
fi

echo
echo "========================"
echo "Setup complete."
echo
echo "Start the app:"
echo "    source $VENV/bin/activate && streamlit run app.py"
echo
echo "Or ask from the command line:"
echo "    $VENV/bin/python -m src.ask \"What is total sales by category?\""
echo
echo "Re-measure accuracy:"
echo "    $VENV/bin/python -m eval.run_eval"
