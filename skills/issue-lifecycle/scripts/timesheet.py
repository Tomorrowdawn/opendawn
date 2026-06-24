#!/usr/bin/env python3
"""Issue timesheet (net-effort tracking) for the issue-lifecycle skill.

Usage:
    timesheet.py <ISSUE-ID-or-path> pause   [--note "..."]
    timesheet.py <ISSUE-ID-or-path> resume   [--note "..."]
    timesheet.py <ISSUE-ID-or-path> status

Append-only, gitignored jsonl at:
    roadmap/issues/.timetracking/ISSUE-NNNN.jsonl
    roadmap/issues/.timetracking/archive/ISSUE-NNNN.jsonl   (post-implementation)

Each line is one event:
    {"ts":"2026-06-24T09:00:00+08:00","event":"resume","note":"started work"}
    {"ts":"2026-06-24T12:30:00+08:00","event":"pause","note":"lunch"}

State machine (within this file, independent of Issue lifecycle):
    - First event MUST be `resume`.
    - Alternates: resume → pause → resume → pause → ...
    - A file's "tail state" is either `active` (ends in resume) or `resting`
      (ends in pause).

This file is NOT git-tracked. transition.py reads it at →implemented to compute
net_effort_hours, then archives it (.timetracking/archive/ISSUE-NNNN.jsonl).
Leaving the timesheet empty is legal — the Issue then lacks net_effort/efficiency
metrics but cycle_hours (wall-clock) is still computed.
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

VALID_EVENTS = {"pause", "resume"}

TT_DIR_NAME = ".timetracking"
ARCHIVE_DIR_NAME = "archive"


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


def tt_dir(root):
    return root / "roadmap" / "issues" / TT_DIR_NAME


def archive_dir(root):
    return tt_dir(root) / ARCHIVE_DIR_NAME


def timesheet_path(root, issue_id):
    return tt_dir(root) / f"{issue_id}.jsonl"


def parse_frontmatter(text):
    """Parse simple flat YAML frontmatter. Returns dict (or {})."""
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


def find_issue_file(issues_dir, ref):
    """Resolve ISSUE-0001 / 0001 / 1 / path-to-file to a Path. Mirrors
    transition.py's resolver so the same ref shapes work everywhere."""
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


def resolve_issue_id(root, issue_ref):
    """Return the canonical ISSUE-NNNN id string for the given ref."""
    issues_dir = root / "roadmap" / "issues"
    issue_file = find_issue_file(issues_dir, issue_ref)
    fm = parse_frontmatter(issue_file.read_text())
    if not fm:
        die(f"no frontmatter in {issue_file}")
    issue_id = fm.get("id", "").strip()
    if not issue_id or not re.match(r"ISSUE-\d+$", issue_id):
        die(
            f"issue file {issue_file.name} has no valid `id:` frontmatter "
            f"(got {issue_id!r})"
        )
    return issue_id


def read_events(path):
    """Read all event dicts from a jsonl file. Returns list, possibly empty.
    Skips blank lines; dies on malformed json lines to keep the file honest."""
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
            die(f"malformed json at {path.name}:{ln_no}: {e}")
        out.append(rec)
    return out


def now_iso_local():
    """ISO 8601 with local tz offset (matches `git log %cI` format). Falls
    back to UTC if tz is-naive/unavailable."""
    now = datetime.now().astimezone()
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.isoformat(timespec="seconds")


def parse_iso(s):
    """Parse an ISO 8601 timestamp from a timesheet record into an aware
    datetime. Handles `Z` suffix."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def append_event(root, issue_id, event, note=None):
    p = timesheet_path(root, issue_id)
    p.parent.mkdir(parents=True, exist_ok=True)

    events = read_events(p)

    # State-machine validation.
    if events:
        tail = events[-1].get("event")
        if tail == event:
            if event == "resume":
                # Idempotent resume: a repeat resume when already active is a
                # no-op rather than an error. This keeps `/ytask-start` safe
                # to re-invoke without the caller having to remember the
                # current tail state — the natural loop is start → work →
                # pause, start → work → pause; calling start twice in a row
                # (e.g. agent re-ran the no-op worktree setup) must not fail.
                print(
                    f"no-op: {issue_id} already active (last event was `resume`)"
                )
                return
            # pause-after-pause is still an error: the user would otherwise
            # silently lose a "I want to pause now" signal against a state
            # that's already paused.
            die(
                f"illegal timesheet event: last event was `{tail}`, "
                f"cannot `{event}` again (must alternate — issue is already "
                "resting; resume before pausing again)"
            )
    else:
        if event != "resume":
            die(
                f"illegal timesheet event: first event must be `resume` "
                f"(got `{event}`)"
            )

    rec = {"ts": now_iso_local(), "event": event}
    if note:
        rec["note"] = note
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"{issue_id} {event} at {rec['ts']}")


def compute_segments(events, end_now=False):
    """Turn an event list into [(resume_dt, pause_dt), ...] segments.
    If end_now is True and the tail is an un-closed resume, close it with
    `now` (UTC). Returns (segments, un_closed_tail: bool)."""
    segs = []
    pending_resume = None
    un_closed = False
    for rec in events:
        ev = rec.get("event")
        ts = parse_iso(rec["ts"])
        if ev == "resume":
            if pending_resume is not None:
                # Shouldn't happen (validator prevents), but stay robust.
                continue
            pending_resume = ts
        elif ev == "pause":
            if pending_resume is None:
                continue
            segs.append((pending_resume, ts))
            pending_resume = None
    if pending_resume is not None and end_now:
        segs.append((pending_resume, datetime.now(timezone.utc)))
    elif pending_resume is not None:
        un_closed = True
    return segs, un_closed


def print_status(root, issue_id):
    p = timesheet_path(root, issue_id)
    events = read_events(p)
    if not events:
        print(f"{issue_id}: no timesheet events yet")
        print(f"  (file: {p})")
        return

    segs_closed, un_closed = compute_segments(events, end_now=False)
    segs_with_now, _ = compute_segments(events, end_now=True)
    closed_hours = sum(
        (b - a).total_seconds() / 3600.0 for a, b in segs_closed
    )
    with_now_hours = sum(
        (b - a).total_seconds() / 3600.0 for a, b in segs_with_now
    )

    tail = events[-1].get("event")
    if tail == "resume":
        state = "active (working — unclosed resume at tail)"
        net_str = f"net (incl. running segment up to now): {with_now_hours:.2f}h"
    else:
        state = "resting (last event was pause)"
        net_str = f"net: {closed_hours:.2f}h"

    print(f"{issue_id}: {state}")
    print(f"  events: {len(events)}  (closed segments: {len(segs_closed)})")
    print(f"  {net_str}")
    print(f"  first: {events[0]['ts']}  last: {events[-1]['ts']}")
    print(f"  (file: {p})")


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        die(
            "usage: timesheet.py <ISSUE-ID-or-path> "
            "<pause|resume|status> [--note \"...\"]",
            code=2,
        )

    issue_ref, cmd = args[0], args[1]
    if cmd not in VALID_EVENTS and cmd != "status":
        die(f"unknown command: {cmd} (valid: pause, resume, status)", code=2)

    note = None
    it = iter(args[2:])
    for a in it:
        if a == "--note":
            note = next(it, None)
            if note is None:
                die("--note requires a value", code=2)
        else:
            die(f"unknown option: {a}", code=2)

    root = repo_root()
    issue_id = resolve_issue_id(root, issue_ref)

    if cmd == "status":
        print_status(root, issue_id)
    else:
        append_event(root, issue_id, cmd, note=note)


if __name__ == "__main__":
    main()
