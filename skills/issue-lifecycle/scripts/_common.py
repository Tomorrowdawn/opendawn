#!/usr/bin/env python3
"""Shared utilities for issue-lifecycle scripts.

Extracts duplicated functions (repo_root, parse_frontmatter, die) and
shared constants (VALID statuses, FRONTMATTER_ORDER) so both transition.py
and list.py operate from a single source of truth.
"""

import subprocess
import sys
from pathlib import Path

VALID: set[str] = {"draft", "approved", "in-progress", "implemented", "deprecated"}

FRONTMATTER_ORDER: list[str] = [
    "id",
    "slug",
    "status",
    "milestone",
    "priority",
    "estimated_work_hours",
    "cycle_hours",
    "net_effort_hours",
    "efficiency",
    "implemented_by",
    "regression_test",
    "deprecated_reason",
]


def die(msg: str, code: int = 1) -> None:
    print(msg, file=sys.stderr)
    sys.exit(code)


def repo_root() -> Path:
    res = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    if res.returncode != 0:
        die(f"not in a git repo: {res.stderr.strip()}")
    return Path(res.stdout.strip())


def parse_frontmatter(text: str) -> tuple[dict[str, str], int]:
    """Parse simple flat YAML frontmatter. Returns (dict, body_offset) or ({}, 0)."""
    if not text.startswith("---\n"):
        return {}, 0
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, 0
    fm: dict[str, str] = {}
    for line in text[4:end].splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        fm[key.strip()] = val.strip()
    return fm, end + len("\n---\n")
