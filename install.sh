#!/usr/bin/env bash
# /Volumes/onn/delegate/install.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$HOME/.claude/skills/delegate"
CMD_FILE="$HOME/.claude/commands/delegate.md"
USER_CFG_DIR="$HOME/.config/delegate"

echo "[install] installing delegate package (editable)..."
python3 -m pip install --user -e "$REPO_DIR"

echo "[install] symlinking skill dir -> $SKILL_DIR"
mkdir -p "$(dirname "$SKILL_DIR")"
rm -rf "$SKILL_DIR"
ln -s "$REPO_DIR" "$SKILL_DIR"

echo "[install] installing slash command -> $CMD_FILE"
mkdir -p "$(dirname "$CMD_FILE")"
cp "$REPO_DIR/install/delegate.md" "$CMD_FILE"

echo "[install] seeding user config -> $USER_CFG_DIR"
mkdir -p "$USER_CFG_DIR"
if [ ! -f "$USER_CFG_DIR/config.toml" ]; then
  cat > "$USER_CFG_DIR/config.toml" <<'EOF'
# delegate user config — overrides config.default.toml
# See docs/superpowers/specs/2026-04-17-delegate-skill-design.md for schema.
#
# If you've purchased $10+ in OpenRouter credits, uncomment to unlock 1000/day:
# [defaults]
# openrouter_has_credits = true
EOF
fi

mkdir -p "$HOME/.claude/skills/delegate/state"

echo "[install] done."
echo "Next: ensure kimi/opencode/gemini are on PATH; set OPENROUTER_API_KEY if using openrouter-free."
