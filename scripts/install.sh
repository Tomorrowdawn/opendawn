#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────
# opendawn install — interactive, deep-merge
#
#   bash <(curl -sSL https://raw.githubusercontent.com/Tomorrowdawn/opendawn/main/scripts/install.sh)
#   bash <(curl -sSL https://raw.githubusercontent.com/Tomorrowdawn/opendawn/main/scripts/install.sh) -g
#
#   curl pipe + interactive = use bash <(...) so stdin stays on tty.
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

# ── interactive merge helpers ────────────────────────
prompt_conflict() {
    local src="$1" dest="$2" rel="$3"

    echo ""
    echo "  ▸ $rel already exists."

    if $YES; then
        cp "$src" "$dest"
        ((STATS_UPDATED++))
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
                ((STATS_UPDATED++))
                echo "    overwritten"
                return
                ;;
            s)
                ((STATS_SKIPPED++))
                echo "    skipped"
                return
                ;;
            O)
                CONFLICT_MODE="overwrite"
                cp "$src" "$dest"
                ((STATS_UPDATED++))
                echo "    overwritten (all)"
                return
                ;;
            S)
                CONFLICT_MODE="skip"
                ((STATS_SKIPPED++))
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
        ((STATS_NEW++))
        echo "  + $rel"
        return
    fi

    # Same inode → skip
    if [ "$(stat -c '%i' "$src" 2>/dev/null)" = "$(stat -c '%i' "$dest" 2>/dev/null)" ] 2>/dev/null; then
        return
    fi

    # Identical content → skip silently
    if cmp -s "$src" "$dest" 2>/dev/null; then
        return
    fi

    case "$CONFLICT_MODE" in
        overwrite)
            cp "$src" "$dest"
            ((STATS_UPDATED++))
            echo "  ~ $rel (overwritten)"
            ;;
        skip)
            ((STATS_SKIPPED++))
            echo "  - $rel (skipped)"
            ;;
        *)
            prompt_conflict "$src" "$dest" "$rel"
            ;;
    esac
}

merge_tree() {
    local src_dir="$1" dest_dir="$2" prefix="$3"

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

# ── install .opencode/ subdirs ───────────────────────
echo ""
echo "── OpenCode config (.opencode/) ──"
for subdir in agents commands; do
    src="$OPENDOWN_SRC/$subdir"
    [ -d "$src" ] || continue
    merge_tree "$src" "$OPENDOWN_TARGET/$subdir" "$subdir"
done

# ── summary ──────────────────────────────────────────
echo ""
echo "──────────────────────────────────────────"
echo "Done."
echo "  + $STATS_NEW new files"
echo "  ~ $STATS_UPDATED updated"
echo "  - $STATS_SKIPPED skipped"
echo "──────────────────────────────────────────"
if [ "$STATS_SKIPPED" -gt 0 ]; then
    echo "Re-run with -y to overwrite all skipped files."
fi
