#!/usr/bin/env python3
"""Issue status transition tool for the issue-lifecycle skill.

Usage:
    transition.py <ISSUE-ID-or-path> <new-status> \
        [--implemented-by REF] [--regression-test REF] \
        [--deprecated-reason REASON] [--no-archive]

Validates the transition against the state machine, edits the frontmatter,
and commits if a transition actually occurred. No-op (exit 0, no commit) if
the Issue is already in the target status. Illegal transition → exit 1.

Timing is auto-derived, never supplied by the agent:

- `cycle_hours` (wall-clock) — at →implemented, reverse-looks-up the commit
  that moved this Issue to `in-progress` (via the formatted
  `chore(issue): ISSUE-NNNN …→in-progress` commit messages) and takes the
  wall-clock delta between that commit's committer date and now. Includes
  lunch, sleep, and cross-task interruptions — deliberately, because cycle
  length is itself a signal of environmental friction.

- `net_effort_hours` (true working time) — at →implemented, reads the local
  gitignored timesheet at `roadmap/issues/.timetracking/ISSUE-NNNN.jsonl`
  (populated by `timesheet.py pause/resume`), sums all resume→pause
  segments, auto-closes a trailing un-closed resume with `now`, and writes
  the total. If no timesheet exists, this field (and `efficiency`) is left
  unset and a warning is printed; cycle_hours is still computed.

- `efficiency` — net_effort_hours / cycle_hours (rounded to 0.01). Left unset
  if either input is missing or zero.

On →implemented, the timesheet jsonl is archived to
`.timetracking/archive/ISSUE-NNNN.jsonl` unless --no-archive is passed, in
which case it is deleted.

On →deprecated, no timing is computed, no timesheet is touched. The
--deprecated-reason flag writes a `deprecated_reason` frontmatter field.
Deprecated is terminal — no further transitions.
"""
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from _common import die, parse_frontmatter, repo_root, FRONTMATTER_ORDER, VALID

LEGAL_TRANSITIONS = {
    "draft": {"approved", "deprecated"},
    "approved": {"in-progress", "deprecated"},
    "in-progress": {"implemented", "deprecated"},
    "implemented": set(),  # terminal
    "deprecated": set(),   # terminal
}

TT_DIR_NAME = ".timetracking"
ARCHIVE_DIR_NAME = "archive"


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


def tt_dir(root):
    return root / "roadmap" / "issues" / TT_DIR_NAME


def timesheet_path(root, issue_id):
    return tt_dir(root) / f"{issue_id}.jsonl"


def archive_path(root, issue_id):
    return tt_dir(root) / ARCHIVE_DIR_NAME / f"{issue_id}.jsonl"


def read_timesheet_events(path):
    """Read event dicts from a jsonl timesheet. Returns list (possibly empty).
    Skips blank lines; dies on malformed json (keeps the file honest —
    we'd rather fail loud than silently miscount net effort)."""
    if not path.is_file():
        return []
    out = []
    for ln_no, ln in enumerate(path.read_text().splitlines(), 1):
        s = ln.strip()
        if not s:
            continue
        try:
            rec = json.loads(s)
        except json.JSONDecodeError as e:
            die(
                f"malformed timesheet {path.name}:{ln_no}: {e} — "
                "net_effort_hours left unset; fix or delete the file"
            )
        out.append(rec)
    return out


def compute_net_effort_hours(events):
    """Sum all resume→pause segments. If the tail is an un-closed resume,
    close it with `now` (UTC). Returns (hours: float, n_segments: int,
    had_un_closed_resume: bool, events_total: int).

    Robust to validator-violating sequences: consecutive resumes collapse,
    a pause with no preceding resume is skipped.
    """
    if not events:
        return 0.0, 0, False, 0
    segs = []
    pending = None
    un_closed = False
    for rec in events:
        ev = rec.get("event")
        try:
            ts = datetime.fromisoformat(
                rec["ts"].replace("Z", "+00:00")
            )
        except (KeyError, ValueError):
            die(f"malformed ts in timesheet record: {rec!r}")
        ts = ts.astimezone(timezone.utc) if ts.utcoffset() is not None else ts
        if ev == "resume":
            if pending is not None:
                continue  # double-resume; skip
            pending = ts
        elif ev == "pause":
            if pending is None:
                continue  # pause with no resume; skip
            segs.append((pending, ts))
            pending = None
    if pending is not None:
        un_closed = True
        segs.append((pending, datetime.now(timezone.utc)))
    hours = sum((b - a).total_seconds() / 3600.0 for a, b in segs)
    return round(hours, 1), len(segs), un_closed, len(events)


def archive_timesheet(root, issue_id, no_archive):
    """On →implemented: move jsonl to archive/, or delete if --no-archive.
    Missing file is a no-op (Issue may have been implemented without any
    timesheet events — that's legal)."""
    src = timesheet_path(root, issue_id)
    if not src.is_file():
        return
    if no_archive:
        src.unlink()
        return
    dst = archive_path(root, issue_id)
    dst.parent.mkdir(parents=True, exist_ok=True)
    # Preserve any prior archive (idempotency in case of re-run) by
    # appending rather than clobbering.
    with src.open("r", encoding="utf-8") as fin, dst.open(
        "a", encoding="utf-8"
    ) as fout:
        # Separator for append-safety when dst already exists.
        if dst.stat().st_size > 0:
            fout.write("\n")
        fout.write(fin.read())
    src.unlink()


def main() -> None:
    args = sys.argv[1:]
    if len(args) < 2:
        die(
            "usage: transition.py <ISSUE-ID-or-path> <new-status> "
            "[--implemented-by REF] [--regression-test REF] "
            "[--deprecated-reason REASON] [--no-archive]",
            code=2,
        )

    issue_ref, new_status = args[0], args[1]
    if new_status not in VALID:
        die(f"invalid status: {new_status} (valid: {sorted(VALID)})", code=2)

    opts: dict[str, str | bool] = {}
    it = iter(args[2:])
    for a in it:
        if a == "--implemented-by":
            opts["implemented_by"] = next(it, None)
        elif a == "--regression-test":
            opts["regression_test"] = next(it, None)
        elif a == "--deprecated-reason":
            opts["deprecated_reason"] = next(it, None)
        elif a == "--no-archive":
            opts["no_archive"] = True
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

    accounting_lines: list[str] = []

    if new_status == "deprecated":
        reason = opts.get("deprecated_reason")
        if reason and isinstance(reason, str):
            fm["deprecated_reason"] = reason
        # No timing computed; no timesheet archived.

    elif new_status == "implemented":
        # --- cycle_hours (wall-clock, always available from git) ---
        start = find_transition_commit_date(issue_id, "in-progress", root)
        cycle_hours = None
        if start is None:
            print(
                f"warning: no in-progress transition commit found for {issue_id}"
                " — cycle_hours left unset",
                file=sys.stderr,
            )
        else:
            cycle_hours = round(
                (datetime.now(timezone.utc) - start).total_seconds() / 3600.0, 1
            )
            if cycle_hours < 0:
                print(
                    f"warning: computed negative cycle_hours ({cycle_hours}h) — "
                    "transition commits may have skewed clocks; leaving unset",
                    file=sys.stderr,
                )
                cycle_hours = None
            else:
                fm["cycle_hours"] = f"{cycle_hours:g}"

        # --- net_effort_hours (from local, gitignored timesheet jsonl) ---
        ts_path = timesheet_path(root, issue_id)
        events = read_timesheet_events(ts_path)
        net_hours = None
        if events:
            net_hours, n_segs, un_closed, _ = compute_net_effort_hours(events)
            if net_hours < 0:
                print(
                    f"warning: negative net_effort_hours ({net_hours}h) "
                    "— timesheet timestamps may cross timezones weirdly; "
                    "leaving unset",
                    file=sys.stderr,
                )
                net_hours = None
            else:
                fm["net_effort_hours"] = f"{net_hours:g}"
                if un_closed:
                    accounting_lines.append(
                        "(trailing resume auto-closed with now)"
                    )
        else:
            print(
                f"warning: no timesheet events for {issue_id} "
                f"({ts_path}) — net_effort_hours and efficiency "
                "left unset; cycle_hours is still computed. "
                "Use `timesheet.py ... pause/resume` next time to capture "
                "true work time.",
                file=sys.stderr,
            )

        # --- efficiency (density signal) ---
        if cycle_hours and net_hours is not None and cycle_hours > 0:
            eff = round(net_hours / cycle_hours, 2)
            if 0 <= eff <= 1:
                fm["efficiency"] = f"{eff:g}"
            else:
                # net > cycle means timesheet ran longer than the issue
                # lived — possible if clocks skew or timesheet was edited.
                # Surface as warning, leave field unset.
                print(
                    f"warning: efficiency {eff} > 1 (net {net_hours}h > "
                    f"cycle {cycle_hours}h) — timesheet may be corrupt; "
                    "efficiency left unset",
                    file=sys.stderr,
                )

        # --- archive the timesheet (local, never commit) ---
        archive_timesheet(root, issue_id, opts.get("no_archive", False))

        if "implemented_by" in opts and opts["implemented_by"] is not None:
            fm["implemented_by"] = opts["implemented_by"]
        if "regression_test" in opts and opts["regression_test"] is not None:
            fm["regression_test"] = opts["regression_test"]

        # --- commit body accounting line ---
        if cycle_hours is not None and net_hours is not None:
            eff_str = (
                f"efficiency {fm.get('efficiency', '?')}"
                if "efficiency" in fm
                else "efficiency n/a"
            )
            accounting_lines.append(
                f"actual: net={net_hours:g}h / cycle={cycle_hours:g}h "
                f"({eff_str})"
            )
        elif cycle_hours is not None:
            accounting_lines.append(
                f"actual: cycle={cycle_hours:g}h (no timesheet; "
                "net_effort not tracked)"
            )
        elif net_hours is not None:
            accounting_lines.append(
                f"actual: net={net_hours:g}h (cycle unavailable)"
            )

    new_text = serialize_frontmatter(fm) + text[body_off:]
    issue_file.write_text(new_text)

    msg = f"chore(issue): {issue_id} {cur}→{new_status}"
    if accounting_lines:
        # Git commit -m can be passed multiple times for paragraphs.
        # We build a single message with body.
        body = "\n\n".join(accounting_lines)
        msg = msg + "\n\n" + body
    subprocess.run(["git", "add", str(issue_file)], check=True, cwd=root)
    res = subprocess.run(
        ["git", "commit", "-m", msg], cwd=root, capture_output=True, text=True
    )
    if res.returncode != 0:
        die(f"commit failed: {res.stderr.strip() or res.stdout.strip()}")
    print(f"{issue_id} {cur}→{new_status} committed: {msg.splitlines()[0]}")


if __name__ == "__main__":
    main()
