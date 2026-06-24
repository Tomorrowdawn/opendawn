#!/usr/bin/env python3
"""List Issues by status. Usage: list.py [status-filter]

Scans roadmap/issues/ISSUE-*.md, parses frontmatter, prints a table.
No filter → all Issues, but capped at LIMIT (sorted by status-group then
priority, so active/incoming work surfaces first and terminal Issues
truncate first). Explicit filter → uncapped (agent wants all of one status).

Sort order: status-rank, then priority-rank, then filename (stable tie-break).
Unknown status sorts last; unknown priority sorts last within its group.
"""
import subprocess
import sys
from pathlib import Path

VALID = {"draft", "approved", "in-progress", "implemented"}

# Smaller rank = higher in the listing. Unknown values get a sentinel so
# they sink to the bottom of their group rather than crashing the sort.
STATUS_RANK = {"in-progress": 0, "approved": 1, "draft": 2, "implemented": 3}
PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
SENTINEL = len(STATUS_RANK)  # one past the last known rank

LIMIT = 15


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


def sort_key(row):
    """Rank a row by (status, priority, filename). Pure, total, deterministic."""
    _id, _slug, status, priority, _ms, _e, _c, _n, _eff, _t = row
    return (
        STATUS_RANK.get(status, SENTINEL),
        PRIORITY_RANK.get(priority, SENTINEL),
        _id,  # stable, human-readable tie-break
    )


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
        eff_raw = fm.get("efficiency", "")
        eff_disp = ""
        if eff_raw:
            try:
                eff_disp = f"{float(eff_raw) * 100:.0f}%"
            except ValueError:
                eff_disp = eff_raw  # leave as-is if not numeric
        rows.append(
            (
                fm.get("id", f.stem),
                fm.get("slug", ""),
                status,
                fm.get("priority", ""),
                fm.get("milestone", ""),
                fm.get("estimated_work_hours", ""),
                fm.get("cycle_hours", ""),
                fm.get("net_effort_hours", ""),
                eff_disp,
                first_h1(text),
            )
        )

    if not rows:
        suffix = f" with status={filt}" if filt else ""
        print(f"(no Issues{suffix})")
        return

    rows.sort(key=sort_key)

    capped = False
    if filt is None and len(rows) > LIMIT:
        total = len(rows)
        rows = rows[:LIMIT]
        capped = True

    headers = (
        "ID", "Slug", "Status", "Pri", "Milestone",
        "Est.h", "Cyc.h", "Net.h", "Eff%", "Title",
    )
    widths = [
        max(len(str(r[i])) for r in rows + [headers]) for i in range(len(headers))
    ]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    for r in rows:
        print(fmt.format(*[str(x) for x in r]))

    if capped:
        print(f"(showing {LIMIT} of {total} — filtered by status→priority; use a status-filter to see all of one status)")


if __name__ == "__main__":
    main()
