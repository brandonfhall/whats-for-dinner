#!/usr/bin/env python
"""PostToolUse hook: lint edited Python files and flag model changes.

Reads the Claude Code hook payload on stdin. Runs flake8 on any edited file
under app/ or tests/ with the repo's .flake8 config (the same gate CI applies),
and reminds about the manual migration step when app/models.py changes, since
this project has no Alembic.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def venv_python():
    for candidate in (REPO / ".venv/Scripts/python.exe", REPO / ".venv/bin/python"):
        if candidate.exists():
            return str(candidate)
    return sys.executable


def edited_path(payload):
    for source in (payload.get("tool_response"), payload.get("tool_input")):
        if isinstance(source, dict):
            value = source.get("filePath") or source.get("file_path")
            if isinstance(value, str) and value:
                return value
    return None


def relative_python_file(path):
    """Repo-relative posix path if it is a .py file we lint, else None."""
    try:
        rel = Path(path).resolve().relative_to(REPO).as_posix()
    except (ValueError, OSError):
        return None
    if rel.endswith(".py") and rel.split("/")[0] in ("app", "tests"):
        return rel
    return None


def run_flake8(rel):
    """Return flake8 output for rel, or None if it passed or is unavailable."""
    result = subprocess.run(
        [venv_python(), "-m", "flake8", rel],
        cwd=REPO, capture_output=True, text=True,
    )
    if "No module named" in result.stderr:
        return None
    if result.returncode == 0:
        return None
    return (result.stdout + result.stderr).strip()


def emit(messages, blocking):
    text = "\n".join(messages)
    if blocking:
        payload = {"decision": "block", "reason": text}
    else:
        payload = {"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": text,
        }}
    print(json.dumps(payload))


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0

    path = edited_path(payload)
    rel = relative_python_file(path) if path else None
    if not rel:
        return 0

    messages = []
    lint_output = run_flake8(rel)
    if lint_output:
        messages.append("flake8 reported issues in %s (CI runs this same check):" % rel)
        messages.append(lint_output)

    if rel == "app/models.py":
        messages.append(
            "app/models.py changed. There is no Alembic here: add the matching "
            "PRAGMA table_info column check to _run_migrations() in "
            "app/database.py, or existing databases will not pick up the change."
        )

    if messages:
        emit(messages, blocking=bool(lint_output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
