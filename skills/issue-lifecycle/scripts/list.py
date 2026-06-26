#!/usr/bin/env python3
"""List Issues by status and/or milestone. Usage: list.py [status-filter] [--milestone M-N]

Scans roadmap/issues/ISSUE-*.md, parses frontmatter, prints a table.
No filter → all Issues, but capped at LIMIT (sorted by status-group then
priority, so active/incoming work surfaces first and terminal Issues
truncate first). Explicit filter → uncapped (agent wants all of one status).

--milestone M-N filters issues whose `milestone:` field matches M-N.
Combined with a status filter: only issues matching both criteria are shown.

Sort order: status-rank, then priority-rank, then filename (stable tie-break).
Unknown status sorts last; unknown priority sorts last within its group.
"""
import sys

from _common import die, parse_frontmatter, repo_root, VALID

# Smaller rank = higher in the listing. Unknown values get a sentinel so
# they sink to the bottom of their group rather than crashing the sort.
STATUS_RANK = {
    "in-progress": 0,
    "approved": 1,
    "draft": 2,
    "implemented": 3,
    "deprecated": 4,
}
PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
SENTINEL = len(STATUS_RANK)  # one past the last known rank

LIMIT = 15


def first_h1(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def sort_key(row: tuple[str, str, str, str, str, str, str, str, str, str]) -> tuple[int, int, str]:
    """Rank a row by (status, priority, filename). Pure, total, deterministic."""
    _id, _slug, status, priority, _ms, _e, _c, _n, _eff, _t = row
    return (
        STATUS_RANK.get(status, SENTINEL),
        PRIORITY_RANK.get(priority, SENTINEL),
        _id,
    )


def main() -> None:
    args = sys.argv[1:]
    filt: str | None = None
    milestone_filt: str | None = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--milestone":
            i += 1
            if i >= len(args):
                die("--milestone requires a value (e.g. --milestone M-01)", code=2)
            milestone_filt = args[i]
        elif a not in VALID:
            print(
                f"invalid status filter: {a} (valid: {sorted(VALID)})",
                file=sys.stderr,
            )
            sys.exit(2)
        else:
            filt = a
        i += 1

    issues_dir = repo_root() / "roadmap" / "issues"
    if not issues_dir.is_dir():
        suffix_parts = []
        if filt:
            suffix_parts.append(f"status={filt}")
        if milestone_filt:
            suffix_parts.append(f"milestone={milestone_filt}")
        suffix = " with " + " ".join(suffix_parts) if suffix_parts else ""
        print(f"(no Issues{suffix} — roadmap/issues/ does not exist yet)")
        return

    rows: list[tuple[str, str, str, str, str, str, str, str, str, str]] = []
    for f in sorted(issues_dir.glob("ISSUE-*.md")):
        text = f.read_text()
        fm, _ = parse_frontmatter(text)
        if not fm:
            continue
        status = fm.get("status", "?")
        if filt and status != filt:
            continue
        if milestone_filt and fm.get("milestone", "") != milestone_filt:
            continue
        eff_raw = fm.get("efficiency", "")
        eff_disp = ""
        if eff_raw:
            try:
                eff_disp = f"{float(eff_raw) * 100:.0f}%"
            except ValueError:
                eff_disp = eff_raw
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
        suffix_parts = []
        if filt:
            suffix_parts.append(f"status={filt}")
        if milestone_filt:
            suffix_parts.append(f"milestone={milestone_filt}")
        suffix = " with " + " ".join(suffix_parts) if suffix_parts else ""
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
