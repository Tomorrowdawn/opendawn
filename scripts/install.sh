#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────
# opendawn install — interactive, deep-merge, self-pruning
#
#   bash <(curl -sSL https://raw.githubusercontent.com/Tomorrowdawn/opendawn/main/scripts/install.sh)
#   bash <(curl -sSL https://raw.githubusercontent.com/Tomorrowdawn/opendawn/main/scripts/install.sh) -g
#
#   curl pipe + interactive = use bash <(...) so stdin stays on tty.
#
#   Tracks every opendawn-owned file in $OPENDOWN_TARGET/.opendawn-manifest
#   and prunes files that a previous run installed but this run no longer
#   ships. Third-party deps (ponytail) are never recorded and never pruned.
# ──────────────────────────────────────────────

usage() {
    echo "Usage: install.sh [-g] [-y]"
    echo "  (no flag)  Install into current directory (local project)"
    echo "  -g         Install globally (~/.config/opencode, ~/.claude)"
    echo "  -y         Non-interactive: overwrite all conflicts without asking"
    exit 1
}

GLOBAL=false
YES=false
while getopts "ghy" opt; do
    case "$opt" in
        g) GLOBAL=true ;;
        y) YES=true ;;
        h) usage ;;
        *) usage ;;
    esac
done

# ── determine source ──────────────────────────────────
REPO_CACHE="${OPENDOWN_REPO_CACHE:-$HOME/.cache/opendawn}"

SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo "")"
if [ -n "$SCRIPT_DIR" ] && [ -d "$SCRIPT_DIR/../skills" ]; then
    REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
    echo "==> Using existing clone at $REPO_ROOT"
else
    REPO_ROOT="$REPO_CACHE"
    if [ ! -d "$REPO_ROOT" ]; then
        echo "==> Fetching opendawn to $REPO_ROOT…"
        git clone --depth 1 https://github.com/Tomorrowdawn/opendawn.git "$REPO_ROOT"
    else
        echo "==> Updating $REPO_ROOT…"
        git -C "$REPO_ROOT" pull --ff-only 2>/dev/null || true
    fi
fi

SKILLS_SRC="$REPO_ROOT/skills"
OPENDOWN_SRC="$REPO_ROOT/.opencode"

# ponytail is an external MIT skill we depend on for lazy reflection.
# Installed alongside opendawn skills so YuuCoder can reference it at
# skills/ponytail/SKILL.md (YuuCoder inlines the ladder core; YuuDev loads
# it only on explicit user signal). License: MIT. See README for attribution.
PONYTAIL_REPO="${PONYTAIL_REPO:-https://github.com/DietrichGebert/ponytail.git}"
PONYTAIL_CACHE="${PONYTAIL_CACHE:-$HOME/.cache/opendawn-ponytail}"

# ── determine targets ────────────────────────────────
if $GLOBAL; then
    echo "==> Installing globally…"
    SKILL_TARGETS=(
        "$HOME/.config/opencode/skills"
        "$HOME/.claude/skills"
    )
    OPENDOWN_TARGET="$HOME/.config/opencode"
else
    echo "==> Installing to current project ($PWD)…"
    SKILL_TARGETS=(
        "$PWD/.agents/skills"
        "$PWD/.claude/skills"
    )
    OPENDOWN_TARGET="$PWD/.opencode"
fi

# ── conflict state ───────────────────────────────────
CONFLICT_MODE=""  # "" = ask, "overwrite" = overwrite-all, "skip" = skip-all
STATS_NEW=0
STATS_UPDATED=0
STATS_SKIPPED=0
STATS_PRUNED=0

# ── manifest (only opendawn's own files; never ponytail or user-added) ──
# Lives at $OPENDOWN_TARGET/.opendawn-manifest. One absolute path per line.
# Used to prune files opendawn installed in a previous run but no longer ships.
MANIFEST_FILE=""
MANIFEST_OLD=()    # paths recorded by a previous run
MANIFEST_NEW=()    # paths opendawn owns (will be written back to manifest)
MANIFEST_TOUCHED=() # every path written this run, managed or not (prune exclusion)
PRUNE_MODE=""     # "" = ask, "remove" = remove-all, "keep" = keep-all
# When false, merge_file records into MANIFEST_TOUCHED only (not MANIFEST_NEW),
# so opendawn never prunes third-party files (ponytail) it just installed,
# but also never claims ownership of them in the manifest.
MANIFEST_RECORDING=true

# Roots opendawn is allowed to manage. Pruning is restricted to files whose
# realpath is under one of these — anything else in the manifest is ignored.
MANAGED_ROOTS=()

manifest_load() {
    [ -f "$MANIFEST_FILE" ] || return 0
    local line
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        MANIFEST_OLD+=("$line")
    done < "$MANIFEST_FILE"
    return 0
}

manifest_record() {
    # Record a dest path opendawn just wrote.
    # Always added to MANIFEST_TOUCHED (prune exclusion).
    # Added to MANIFEST_NEW (ownership / writeback) only if recording is on.
    local path="$1"
    case "$path" in
        /*) ;;
        *)  path="$PWD/$path" ;;
    esac
    MANIFEST_TOUCHED+=("$path")
    if $MANIFEST_RECORDING; then
        MANIFEST_NEW+=("$path")
    fi
}

manifest_write() {
    mkdir -p "$(dirname "$MANIFEST_FILE")"
    if [ ${#MANIFEST_NEW[@]} -eq 0 ]; then
        : > "$MANIFEST_FILE"
    else
        printf '%s\n' "${MANIFEST_NEW[@]}" | sort -u > "$MANIFEST_FILE"
    fi
}

path_under_managed_root() {
    # echo the managed root that contains $1, or empty if none
    local target="$1"
    local rp
    rp="$(realpath "$target" 2>/dev/null || echo "$target")"
    local root
    for root in "${MANAGED_ROOTS[@]}"; do
        case "$rp/" in
            "$root/"*) echo "$root"; return 0 ;;
        esac
    done
    echo ""
}

# ── interactive merge helpers ────────────────────────
prompt_conflict() {
    local src="$1" dest="$2" rel="$3"

    echo ""
    echo "  ▸ $rel already exists."

    if $YES; then
        cp "$src" "$dest"
        ((++STATS_UPDATED))
        manifest_record "$dest"
        echo "    overwritten (-y)"
        return
    fi

    # read from tty explicitly — stdin may be a pipe from curl|bash
    local choice
    while true; do
        read -r -p "    [o]verwrite  [s]kip  O[verwrite all]  S[kip all]  [d]iff  " choice < /dev/tty
        case "$choice" in
            o)
                cp "$src" "$dest"
                ((++STATS_UPDATED))
                manifest_record "$dest"
                echo "    overwritten"
                return
                ;;
            s)
                ((++STATS_SKIPPED))
                echo "    skipped"
                return
                ;;
            O)
                CONFLICT_MODE="overwrite"
                cp "$src" "$dest"
                ((++STATS_UPDATED))
                manifest_record "$dest"
                echo "    overwritten (all)"
                return
                ;;
            S)
                CONFLICT_MODE="skip"
                ((++STATS_SKIPPED))
                echo "    skipped (all)"
                return
                ;;
            d)
                diff -u "$dest" "$src" 2>/dev/null || true
                ;;
            *)
                echo "    [o/s/O/S/d]"
                ;;
        esac
    done
}

merge_file() {
    local src="$1" dest="$2" rel="$3"

    if [ ! -e "$dest" ]; then
        mkdir -p "$(dirname "$dest")"
        cp "$src" "$dest"
        ((++STATS_NEW))
        manifest_record "$dest"
        echo "  + $rel"
        return
    fi

    # Same inode → skip
    if [ "$(stat -c '%i' "$src" 2>/dev/null)" = "$(stat -c '%i' "$dest" 2>/dev/null)" ] 2>/dev/null; then
        manifest_record "$dest"
        return
    fi

    # Identical content → skip silently
    if cmp -s "$src" "$dest" 2>/dev/null; then
        manifest_record "$dest"
        return
    fi

    case "$CONFLICT_MODE" in
        overwrite)
            cp "$src" "$dest"
            ((++STATS_UPDATED))
            manifest_record "$dest"
            echo "  ~ $rel (overwritten)"
            ;;
        skip)
            ((++STATS_SKIPPED))
            echo "  - $rel (skipped)"
            ;;
        *)
            prompt_conflict "$src" "$dest" "$rel"
            ;;
    esac
}

merge_tree() {
    local src_dir="$1" dest_dir="$2" prefix="$3"

    src_dir="${src_dir%/}"
    dest_dir="${dest_dir%/}"

    # Skip if src and dest are the same directory (local self-install)
    if [ "$(realpath "$src_dir" 2>/dev/null)" = "$(realpath "$dest_dir" 2>/dev/null)" ] 2>/dev/null; then
        return
    fi

    local item
    while IFS= read -r -d '' item; do
        local rel="${item#$src_dir/}"
        local dest="$dest_dir/$rel"
        [ -n "$prefix" ] && rel="$prefix/$rel"

        if [ -d "$item" ]; then
            mkdir -p "$dest"
        else
            merge_file "$item" "$dest" "$rel"
        fi
    done < <(find "$src_dir" -mindepth 1 -print0 | sort -z)
}

# ── manifest init (done after targets known) ─────────
MANIFEST_FILE="$OPENDOWN_TARGET/.opendawn-manifest"
MANAGED_ROOTS=()
for t in "${SKILL_TARGETS[@]}"; do
    MANAGED_ROOTS+=("$(realpath "$t" 2>/dev/null || echo "$t")")
done
MANAGED_ROOTS+=("$(realpath "$OPENDOWN_TARGET" 2>/dev/null || echo "$OPENDOWN_TARGET")")
manifest_load

# ── install skills ───────────────────────────────────
echo ""
echo "── Skills ──"
for skill_dir in "$SKILLS_SRC"/*/; do
    skill_name="$(basename "$skill_dir")"
    [ "$skill_name" = "*" ] && continue
    for target in "${SKILL_TARGETS[@]}"; do
        merge_tree "$skill_dir" "$target/$skill_name" "skills/$skill_name"
    done
done

# ── install ponytail dependency ──────────────────────
echo ""
echo "── Ponytail (lazy reflection skill, MIT) ──"
if [ ! -d "$PONYTAIL_CACHE" ]; then
    echo "==> Fetching ponytail to $PONYTAIL_CACHE…"
    git clone --depth 1 "$PONYTAIL_REPO" "$PONYTAIL_CACHE" >/dev/null 2>&1 || {
        echo "  ! Failed to clone ponytail; agents will not be able to load it."
        echo "    You can install it manually: npx skills add DietrichGebert/ponytail"
    }
else
    echo "==> Updating $PONYTAIL_CACHE…"
    git -C "$PONYTAIL_CACHE" pull --ff-only 2>/dev/null || true
fi

if [ -d "$PONYTAIL_CACHE/skills/ponytail" ]; then
    # Ponytail is a third-party dependency — never record its paths in the
    # manifest, so opendawn never prunes it (user may have installed it
    # separately too).
    MANIFEST_RECORDING=false
    for target in "${SKILL_TARGETS[@]}"; do
        merge_tree "$PONYTAIL_CACHE/skills/ponytail" "$target/ponytail" "skills/ponytail"
    done
    MANIFEST_RECORDING=true
else
    echo "  ! ponytail skill directory not found in clone; skipping."
fi

# ── install .opencode/ subdirs ───────────────────────
echo ""
echo "── OpenCode config (.opencode/) ──"
for subdir in agents commands; do
    src="$OPENDOWN_SRC/$subdir"
    [ -d "$src" ] || continue
    merge_tree "$src" "$OPENDOWN_TARGET/$subdir" "$subdir"
done

# ── prune: remove opendawn-installed files that this run no longer ships ──
#   OLD = paths recorded in a previous run's manifest.
#   TOUCHED = every path written this run, including third-party (ponytail).
#   A path is stale iff in OLD but not in TOUCHED. Ponytail is always
#   re-installed above and added to TOUCHED, so it's never pruned — yet it's
#   never written to MANIFEST_NEW, so opendawn never claims ownership of it.
#   Every deletion is also restricted to a path whose realpath is under one of
#   MANAGED_ROOTS, so a tampered manifest can't cause arbitrary deletion.
echo ""
echo "── Prune stale files ──"
prune_one() {
    local path="$1"
    [ -e "$path" ] || [ -L "$path" ] || return 0
    local root
    root="$(path_under_managed_root "$path")"
    if [ -z "$root" ]; then
        echo "  ! $path outside managed roots — leaving alone"
        return 0
    fi
    rm -f "$path"
    ((++STATS_PRUNED))
    echo "  × $(realpath --relative-to="$root" "$path" 2>/dev/null || echo "$path")"

    # remove now-empty parent dirs up to (not including) the managed root
    local d
    d="$(dirname "$path")"
    while [ "$d" != "$root" ] && [ -n "$d" ] && [ "$d" != "/" ]; do
        if rmdir "$d" 2>/dev/null; then
            d="$(dirname "$d")"
        else
            break
        fi
    done
}

prompt_prune() {
    local path="$1"
    echo ""
    echo "  ▸ stale: $path"
    if $YES; then
        prune_one "$path"
        return
    fi
    local choice
    while true; do
        read -r -p "    [r]emove  k[eep]  R[emove all]  K[eep all]  " choice < /dev/tty
        case "$choice" in
            r) prune_one "$path"; return ;;
            k) echo "    kept"; return ;;
            R) PRUNE_MODE="remove"; prune_one "$path"; return ;;
            K) PRUNE_MODE="keep"; echo "    kept (all)"; return ;;
            *) echo "    [r/k/R/K]" ;;
        esac
    done
}

# Build NEW set lookup; iterate OLD. A path is stale only if opendawn
# recorded it before (OLD) AND did not touch it this run (not in TOUCHED).
for old_path in "${MANIFEST_OLD[@]}"; do
    is_touched=0
    for t in "${MANIFEST_TOUCHED[@]}"; do
        if [ "$t" = "$old_path" ]; then is_touched=1; break; fi
    done
    [ "$is_touched" = "1" ] && continue
    case "$PRUNE_MODE" in
        remove) prune_one "$old_path" ;;
        keep)   echo "  - $old_path (kept)" ;;
        *)      prompt_prune "$old_path" ;;
    esac
done

manifest_write

echo ""
echo "──────────────────────────────────────────"
echo "Done."
echo "  + $STATS_NEW new files"
echo "  ~ $STATS_UPDATED updated"
echo "  - $STATS_SKIPPED skipped"
echo "  × $STATS_PRUNED pruned (stale opendawn files removed)"
echo ""
echo "Includes ponytail (MIT, https://github.com/DietrichGebert/ponytail)"
echo "installed at skills/ponytail/. Referenced by YuuCoder (ladder inlined);"
echo "YuuDev loads it only on explicit user signal."
echo "──────────────────────────────────────────────────"
if [ "$STATS_SKIPPED" -gt 0 ]; then
    echo "Re-run with -y to overwrite all skipped files."
fi
