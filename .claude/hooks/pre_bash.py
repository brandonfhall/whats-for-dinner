#!/usr/bin/env python
"""PreToolUse hook: refuse commits made directly on main or develop.

Reads the Claude Code hook payload on stdin. A cheap substring test in the
hook command has already found "git commit" somewhere in the payload; this
decides whether it is an actual command invocation rather than quoted prose,
so that a PR body or a `grep "git commit"` is not mistaken for a commit.
"""
import json
import re
import subprocess
import sys

PROTECTED = ("main", "develop")

# Positions where a command can begin: start of input, a newline, a separator
# (; & | ( {), or a shell keyword that introduces one. A backtick is
# deliberately absent -- `git commit` in a markdown code span is far more
# common than legacy backtick command substitution of a commit.
BOUNDARY = r"(?:^|[\n;&|({]|\bthen\b|\bdo\b|\belse\b)"
COMMIT_RE = re.compile(
    BOUNDARY + r"\s*(?:sudo\s+)?git(?:\s+-C\s+\S+|\s+-\S+)*\s+commit\b"
)


def command_text(payload):
    source = payload.get("tool_input")
    if not isinstance(source, dict):
        return ""
    value = source.get("command")
    return value if isinstance(value, str) else ""


def current_branch():
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def deny(branch):
    reason = (
        "CLAUDE.md: never commit directly to %s. Cut a feature branch from "
        "develop and open a PR into develop." % branch
    )
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0

    if not COMMIT_RE.search(command_text(payload)):
        return 0

    branch = current_branch()
    if branch in PROTECTED:
        deny(branch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
