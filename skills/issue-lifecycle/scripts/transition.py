#!/usr/bin/env python3
"""Issue status transition tool for the issue-lifecycle skill.

Usage:
    transition.py <ISSUE-ID-or-path> <new-status> \
        [--implemented-by REF] [--regression-test REF]

Validates the transition against the state machine, edits the frontmatter,
and commits if a transition actually occurred. No-op (exit 0, no commit) if
the Issue is already in the target status. Illegal transition → exit 1.

Timing is auto-derived from git: when transitioning to `implemented`, the
script reverse-looks-up the commit that moved this Issue to `in-progress`
(via the formatted `chore(issue): ISSUE-NNNN …→in-progress` commit messages)
and computes `actual_work_hours` as the wall-clock delta between that commit's
committer date and now. Agents never pass timing manually.
"""
import re
import subprocess
import sys
from datetime import datetime, timezone
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


def find_transition_commit_date(issue_id, target_status, root):
    """Return the committer date (aware UTC datetime) of the most recent commit
    whose formatted subject records this Issue transitioning *to* target_status.

    Commit subjects have the shape `chore(issue): ISSUE-NNNN <old>→<new>`, so a
    transition *to* in-progress is matched on the `→in-progress` suffix. We
    enumerate commit subjects in Python rather than using `git log --grep`,
    because git's regex engine varies (BRE/ERE) and would mis-handle the
    parentheses / Unicode arrow that `re.escape` produces.
    Returns None if no such commit is found.
    """
    pattern = re.compile(
        rf"^chore\(issue\): {re.escape(issue_id)} .+→{re.escape(target_status)}$"
    )
    for use_all in (False, True):
        argv = ["git", "log", "--format=%cI %s"]
        if use_all:
            argv.append("--all")
        res = subprocess.run(argv, cwd=root, capture_output=True, text=True)
        if res.returncode != 0:
            continue
        for line in res.stdout.splitlines():
            # %cI contains no spaces; split off the date, keep the rest as subject.
            date_str, _, subject = line.partition(" ")
            if pattern.match(subject):
                return parse_git_iso(date_str)
    return None


def parse_git_iso(s):
    """Parse a git %cI timestamp (ISO 8601 with explicit offset, e.g.
    2026-06-24T12:30:45+08:00) into an aware UTC datetime."""
    # fromisoformat handles `2026-06-24T12:30:45+08:00` on Py3.7+ and the
    # bare `Z` suffix on Py3.11+; normalize just in case.
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        die(
            "usage: transition.py <ISSUE-ID-or-path> <new-status> "
            "[--implemented-by REF] [--regression-test REF]",
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

    issue_id = fm.get("id", issue_file.stem)

    if new_status == "implemented":
        # Timing is auto-derived from git — agents never pass --actual-hours.
        start = find_transition_commit_date(issue_id, "in-progress", root)
        if start is None:
            print(
                f"warning: no in-progress transition commit found for {issue_id}"
                " — actual_work_hours left unset",
                file=sys.stderr,
            )
        else:
            hours = round(
                (datetime.now(timezone.utc) - start).total_seconds() / 3600.0, 1
            )
            if hours < 0:
                print(
                    f"warning: computed negative actual_work_hours ({hours}h) — "
                    "transition commits may have skewed clocks; leaving unset",
                    file=sys.stderr,
                )
            else:
                fm["actual_work_hours"] = f"{hours:g}"
        if "implemented_by" in opts and opts["implemented_by"] is not None:
            fm["implemented_by"] = opts["implemented_by"]
        if "regression_test" in opts and opts["regression_test"] is not None:
            fm["regression_test"] = opts["regression_test"]

    new_text = serialize_frontmatter(fm) + text[body_off:]
    issue_file.write_text(new_text)

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
