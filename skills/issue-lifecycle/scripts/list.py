#!/usr/bin/env python3
"""List Issues by status. Usage: list.py [status-filter]

Scans roadmap/issues/ISSUE-*.md, parses frontmatter, prints a table.
No filter → all Issues. Filter → one of draft|approved|in-progress|implemented.
"""
import subprocess
import sys
from pathlib import Path

VALID = {"draft", "approved", "in-progress", "implemented"}


def repo_root():
    res = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True
    )
    if res.returncode != 0:
        print(f"not in a git repo: {res.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return Path(res.stdout.strip())


def parse_frontmatter(text):
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}
    fm = {}
    for line in text[4:end].splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        fm[key.strip()] = val.strip()
    return fm


def first_h1(text):
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def main():
    filt = sys.argv[1] if len(sys.argv) > 1 else None
    if filt and filt not in VALID:
        print(
            f"invalid status filter: {filt} (valid: {sorted(VALID)})",
            file=sys.stderr,
        )
        sys.exit(2)

    issues_dir = repo_root() / "roadmap" / "issues"
    if not issues_dir.is_dir():
        suffix = f" with status={filt}" if filt else ""
        print(f"(no Issues{suffix} — roadmap/issues/ does not exist yet)")
        return

    rows = []
    for f in sorted(issues_dir.glob("ISSUE-*.md")):
        text = f.read_text()
        fm = parse_frontmatter(text)
        if not fm:
            continue
        status = fm.get("status", "?")
        if filt and status != filt:
            continue
        rows.append(
            (
                fm.get("id", f.stem),
                fm.get("slug", ""),
                status,
                fm.get("priority", ""),
                fm.get("milestone", ""),
                fm.get("estimated_work_hours", ""),
                fm.get("actual_work_hours", ""),
                first_h1(text),
            )
        )

    if not rows:
        suffix = f" with status={filt}" if filt else ""
        print(f"(no Issues{suffix})")
        return

    headers = ("ID", "Slug", "Status", "Pri", "Milestone", "Est.h", "Act.h", "Title")
    widths = [
        max(len(str(r[i])) for r in rows + [headers]) for i in range(len(headers))
    ]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    for r in rows:
        print(fmt.format(*[str(x) for x in r]))


if __name__ == "__main__":
    main()
