#!/usr/bin/env python3
"""Issue status transition tool for the issue-lifecycle skill.

Usage:
    transition.py <ISSUE-ID-or-path> <new-status> \
        [--implemented-by REF] [--regression-test REF] [--actual-hours N]

Validates the transition against the state machine, edits the frontmatter,
and commits if a transition actually occurred. No-op (exit 0, no commit) if
the Issue is already in the target status. Illegal transition → exit 1.
"""
import re
import subprocess
import sys
from pathlib import Path

LEGAL_TRANSITIONS = {
    "draft": {"approved"},
    "approved": {"in-progress"},
    "in-progress": {"implemented"},
    "implemented": set(),  # terminal
}

FRONTMATTER_ORDER = [
    "id",
    "slug",
    "status",
    "milestone",
    "priority",
    "estimated_work_hours",
    "actual_work_hours",
    "implemented_by",
    "regression_test",
]


def repo_root():
    res = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    if res.returncode != 0:
        die(f"not in a git repo: {res.stderr.strip()}")
    return Path(res.stdout.strip())


def die(msg, code=1):
    print(msg, file=sys.stderr)
    sys.exit(code)


def parse_frontmatter(text):
    """Parse simple flat YAML frontmatter. Returns (dict, body_offset) or ({}, 0)."""
    if not text.startswith("---\n"):
        return {}, 0
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, 0
    fm = {}
    for line in text[4:end].splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        fm[key.strip()] = val.strip()
    return fm, end + len("\n---\n")


def serialize_frontmatter(fm):
    lines = ["---"]
    seen = set()
    for key in FRONTMATTER_ORDER:
        if key in fm:
            lines.append(f"{key}: {fm[key]}")
            seen.add(key)
    for key, val in fm.items():  # any leftover keys
        if key not in seen:
            lines.append(f"{key}: {val}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def find_issue_file(issues_dir, ref):
    """Resolve ISSUE-0001 / 0001 / 1 / path-to-file to a Path."""
    p = Path(ref)
    if p.is_file():
        return p
    m = re.match(r"ISSUE-(\d+)$", ref)
    num = m.group(1) if m else (ref if ref.isdigit() else None)
    if num is None:
        die(f"unrecognized Issue reference: {ref}")
    n = int(num)
    for pad in (4, 3, 2, 1):
        candidates = sorted(issues_dir.glob(f"ISSUE-{n:0{pad}d}-*.md"))
        if candidates:
            return candidates[0]
    die(f"Issue not found: {ref}")


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        die(
            "usage: transition.py <ISSUE-ID-or-path> <new-status> "
            "[--implemented-by REF] [--regression-test REF] [--actual-hours N]",
            code=2,
        )

    issue_ref, new_status = args[0], args[1]
    opts = {}
    it = iter(args[2:])
    for a in it:
        if a == "--implemented-by":
            opts["implemented_by"] = next(it, None)
        elif a == "--regression-test":
            opts["regression_test"] = next(it, None)
        elif a == "--actual-hours":
            opts["actual_work_hours"] = next(it, None)
        else:
            die(f"unknown option: {a}", code=2)

    root = repo_root()
    issues_dir = root / "roadmap" / "issues"
    issue_file = find_issue_file(issues_dir, issue_ref)

    text = issue_file.read_text()
    fm, body_off = parse_frontmatter(text)
    if not fm:
        die(f"no frontmatter in {issue_file}")

    cur = fm.get("status", "").strip()
    if cur == new_status:
        print(f"no-op: {issue_file.name} already {new_status}")
        sys.exit(0)

    legal = LEGAL_TRANSITIONS.get(cur, set())
    if new_status not in legal:
        legal_str = ", ".join(sorted(legal)) if legal else "(none — terminal)"
        die(f"illegal transition: {cur} → {new_status} (legal from {cur}: {legal_str})")

    fm["status"] = new_status
    if new_status == "implemented":
        if "implemented_by" in opts and opts["implemented_by"] is not None:
            fm["implemented_by"] = opts["implemented_by"]
        if "regression_test" in opts and opts["regression_test"] is not None:
            fm["regression_test"] = opts["regression_test"]
        if "actual_work_hours" in opts and opts["actual_work_hours"] is not None:
            fm["actual_work_hours"] = opts["actual_work_hours"]

    new_text = serialize_frontmatter(fm) + text[body_off:]
    issue_file.write_text(new_text)

    issue_id = fm.get("id", issue_file.stem)
    msg = f"chore(issue): {issue_id} {cur}→{new_status}"
    subprocess.run(["git", "add", str(issue_file)], check=True, cwd=root)
    res = subprocess.run(
        ["git", "commit", "-m", msg], cwd=root, capture_output=True, text=True
    )
    if res.returncode != 0:
        die(f"commit failed: {res.stderr.strip() or res.stdout.strip()}")
    print(f"{issue_id} {cur}→{new_status} committed: {msg}")


if __name__ == "__main__":
    main()
