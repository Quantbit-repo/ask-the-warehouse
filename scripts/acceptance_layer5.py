"""Layer 5 acceptance check: the handoff actually works.

Acceptance criteria:
1. The setup script exists, is executable, and is idempotent (running it twice is safe).
2. The setup script fails with a clear message when the warehouse is missing,
   rather than failing silently or with a stack trace.
3. The setup script completes successfully against the real warehouse.
4. A user guide exists and covers the questions a user actually has:
   getting started, asking well, reading answers, failure modes, limits.
5. A discovery note exists and covers the handoff sections: the ask, the
   reasoning, the cuts, and what happens next.
6. The README points to both documents.
7. No unexplained jargon in the user guide: any technical term is either defined
   or avoided.

Run: python scripts/acceptance_layer5.py
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

JARGON = ["star schema", "foreign key", "etl", "olap", "embedding", "vector",
          "token", "prompt", "llm", "inference", "rag", "guardrail"]


def main() -> int:
    checks = []

    def record(name, ok, detail=""):
        checks.append((name, bool(ok), detail))

    setup = ROOT / "setup.sh"
    guide = ROOT / "docs" / "USER_GUIDE.md"
    discovery = ROOT / "docs" / "DISCOVERY.md"
    readme = ROOT / "README.md"

    # 1. setup script present and executable
    record("setup script exists and is executable",
           setup.exists() and bool(setup.stat().st_mode & 0o111),
           f"mode {oct(setup.stat().st_mode)[-3:]}" if setup.exists() else "missing")

    # 2. missing warehouse produces a clear message
    import os

    env = dict(os.environ)
    env["WAREHOUSE_PATH"] = "/tmp/does_not_exist_warehouse.db"
    env_result = subprocess.run(
        [str(setup)], cwd=str(ROOT), capture_output=True, text=True, env=env,
    )
    out = env_result.stdout + env_result.stderr
    clear = ("warehouse not found" in out
             and "build_database.py" in out
             and env_result.returncode != 0
             and "Traceback" not in out)
    record("missing warehouse gives a clear, actionable failure",
           clear, f"exit={env_result.returncode}")

    # 3. setup succeeds against the real warehouse
    ok_run = subprocess.run([str(setup)], cwd=str(ROOT), capture_output=True, text=True)
    ran = ok_run.returncode == 0 and "Setup complete" in (ok_run.stdout + ok_run.stderr)
    record("setup script completes against the real warehouse",
           ran, f"exit={ok_run.returncode}")

    # 3b. idempotent
    again = subprocess.run([str(setup)], cwd=str(ROOT), capture_output=True, text=True)
    record("setup script is safe to run twice",
           again.returncode == 0 and "already exists" in (again.stdout + again.stderr),
           f"exit={again.returncode}")

    # 4. user guide coverage
    guide_text = guide.read_text().lower() if guide.exists() else ""
    sections = {
        "getting started": "getting started" in guide_text,
        "how to ask": "asking good questions" in guide_text,
        "reading the answer": "reading the answer" in guide_text,
        "failure modes": "when something goes wrong" in guide_text,
        "limits stated": "will not do" in guide_text,
        "accuracy stated": "97.6" in guide_text,
    }
    missing = [k for k, v in sections.items() if not v]
    record("user guide covers getting started, asking, reading, failures and limits",
           not missing, f"missing: {missing or 'none'}")

    # 5. discovery note coverage
    disc = discovery.read_text().lower() if discovery.exists() else ""
    d_sections = {
        "the ask": "the ask" in disc,
        "reasoning": "reasoning" in disc,
        "cuts": "did not build" in disc,
        "next steps": "week one" in disc or "handover" in disc,
        "honest framing": "not a paying client" in disc or "self directed" in disc,
    }
    d_missing = [k for k, v in d_sections.items() if not v]
    record("discovery note covers the ask, reasoning, cuts and next steps",
           not d_missing, f"missing: {d_missing or 'none'}")

    # 6. README links
    readme_text = readme.read_text() if readme.exists() else ""
    linked = "docs/USER_GUIDE.md" in readme_text and "docs/DISCOVERY.md" in readme_text
    record("README links to the guide and the discovery note",
           linked, "both linked" if linked else "link missing")

    # 7. jargon check: every flagged term must be explained nearby
    unexplained = []
    for term in JARGON:
        idx = guide_text.find(term)
        while idx != -1:
            window = guide_text[max(0, idx - 120): idx + 220]
            explained = any(w in window for w in
                            ["means", "is a", "for example", "in other words", "that is"])
            if not explained:
                unexplained.append(term)
                break
            idx = guide_text.find(term, idx + 1)
    record("no unexplained jargon in the user guide",
           not unexplained, f"unexplained: {sorted(set(unexplained)) or 'none'}")

    print(f"{'CHECK':58} {'RESULT':7} DETAIL")
    print("-" * 106)
    passed = 0
    for name, ok, detail in checks:
        print(f"{name:58} {'PASS' if ok else 'FAIL':7} {detail}")
        passed += int(ok)
    print("-" * 106)
    print(f"=== LAYER 5 ACCEPTANCE: {passed}/{len(checks)} passed ===")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
