#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────
# opendawn install — one-liner compatible
#
#   curl -sSL https://raw.githubusercontent.com/Tomorrowdawn/opendawn/main/scripts/install.sh | bash
#
# Default: installs skills + agents into the current project (./.agents, ./.claude, ./.opencode).
# With -g:  installs globally (~/.config/opencode, ~/.claude).
# Idempotent — safe to run multiple times.
# ──────────────────────────────────────────────

usage() {
    echo "Usage: install.sh [-g]"
    echo "  (no flag)  Install into current directory (local project)"
    echo "  -g         Install globally (~/.config/opencode, ~/.claude)"
    exit 1
}

GLOBAL=false
while getopts "gh" opt; do
    case "$opt" in
        g) GLOBAL=true ;;
        h) usage ;;
        *) usage ;;
    esac
done

# ── determine source (where skills/agents live) ──
INSTALL_DIR="${OPENDOWN_INSTALL_DIR:-$HOME/.local/share/opendawn}"

SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo "")"
if [ -n "$SCRIPT_DIR" ] && [ -d "$SCRIPT_DIR/../skills" ]; then
    REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
    echo "==> Using existing clone at $REPO_ROOT"
else
    REPO_ROOT="$INSTALL_DIR"
    if [ ! -d "$REPO_ROOT" ]; then
        echo "==> Cloning opendawn to $REPO_ROOT…"
        git clone https://github.com/Tomorrowdawn/opendawn.git "$REPO_ROOT"
    else
        echo "==> Updating $REPO_ROOT…"
        git -C "$REPO_ROOT" pull --ff-only 2>/dev/null || true
    fi
fi

SKILLS_SRC="$REPO_ROOT/skills"
AGENTS_SRC="$REPO_ROOT/.opencode/agents"

# ── determine targets ──────────────────────────
if $GLOBAL; then
    echo "==> Installing globally…"
    SKILL_TARGETS=(
        "$HOME/.config/opencode/skills"
        "$HOME/.claude/skills"
    )
    AGENT_TARGETS=(
        "$HOME/.config/opencode/agents"
    )
else
    echo "==> Installing to current project ($PWD)…"
    SKILL_TARGETS=(
        "$PWD/.agents/skills"
        "$PWD/.claude/skills"
    )
    AGENT_TARGETS=(
        "$PWD/.opencode/agents"
    )
fi

# ── helpers ────────────────────────────────────
symlink_dir() {
    local src="$1" dest_root="$2" name="$3"
    mkdir -p "$dest_root"
    local dest="$dest_root/$name"

    if [ -L "$dest" ]; then
        local current; current="$(readlink "$dest")"
        [ "$current" = "$src" ] && return 0
        rm -f "$dest"
    elif [ -d "$dest" ]; then
        rm -rf "$dest"
    fi

    ln -sfn "$src" "$dest"
    echo "  $name → $dest"
}

symlink_file() {
    local src="$1" dest_root="$2" name="$3"
    mkdir -p "$dest_root"
    local dest="$dest_root/$name"

    # Skip if src and dest are the same file (e.g. agents already in .opencode/agents/)
    [ "$(realpath "$src")" = "$(realpath "$dest" 2>/dev/null || echo "")" ] 2>/dev/null && return 0

    if [ -L "$dest" ]; then
        local current; current="$(readlink "$dest")"
        [ "$current" = "$src" ] && return 0
        rm -f "$dest"
    fi

    ln -sf "$src" "$dest"
    echo "  $name → $dest"
}

# ── install ────────────────────────────────────
for skill_dir in "$SKILLS_SRC"/*/; do
    skill_name="$(basename "$skill_dir")"
    [ "$skill_name" = "*" ] && continue
    for target in "${SKILL_TARGETS[@]}"; do
        symlink_dir "$skill_dir" "$target" "$skill_name"
    done
done

for agent_file in "$AGENTS_SRC"/*.md; do
    agent_name="$(basename "$agent_file" .md)"
    [ "$agent_name" = "*" ] && continue
    for target in "${AGENT_TARGETS[@]}"; do
        symlink_file "$agent_file" "$target" "$agent_name.md"
    done
done

echo ""
echo "Done. Skills and agents installed."
echo ""
echo "  npx skills CLI users, also run:"
echo "    npx skills add $REPO_ROOT"
