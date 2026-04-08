#!/bin/bash
# ensure-codex-skills.sh - Sync Claude Code plugin skills to ~/.agents/skills/ for Codex
# SessionStart hook: runs in background, idempotent
# Uses manifest to track managed symlinks, never touches user-created files

set +e  # Don't exit on errors — background hook must complete gracefully

# ========== Config ==========

AGENTS_SKILLS="$HOME/.agents/skills"
CODEX_SKILLS="$HOME/.codex/skills"
CLAUDE_SKILLS="$HOME/.claude/skills"
MANIFEST_DIR="$HOME/.cache/codex-skills-sync"
MANIFEST_FILE="$MANIFEST_DIR/managed.txt"

# Only sync skills from our own marketplace (taptap-plugins)
# All other marketplaces (claude-plugins-official, pua-skills, etc.) are excluded
INCLUDE_MARKETPLACE="taptap-plugins"

# Retired plugins within our marketplace; keep cleanup so legacy HOME sync artifacts disappear
EXCLUDE_PLUGINS="ralph"

# Retired skill names cleaned on every run from both ~/.codex/skills and ~/.agents/skills
EXCLUDE_SKILLS="ralph-loop ralph-pause ralph-resume ralph-status ralph-adjust ralph-decompose ralph-workflow cancel-ralph prd-to-json"

# Log
LOG_DIR="$HOME/.claude/plugins/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/ensure-codex-skills-$(date +%Y-%m-%d).log"
exec >> "$LOG_FILE" 2>&1
echo ""
echo "===== $(date '+%Y-%m-%d %H:%M:%S') ====="

# ========== Step 0: Skip if Codex not installed ==========

if [ ! -d "$CODEX_SKILLS" ] && ! command -v codex >/dev/null 2>&1; then
  echo "⏭️  Codex 未安装，跳过"
  exit 0
fi

mkdir -p "$AGENTS_SKILLS"
mkdir -p "$MANIFEST_DIR"

# ========== Step 1: Clean retired skill symlinks from both directories ==========

for skill in $EXCLUDE_SKILLS; do
  for dir in "$CODEX_SKILLS" "$AGENTS_SKILLS"; do
    target="$dir/$skill"
    if [ -L "$target" ]; then
      rm -f "$target"
      echo "🗑️  已删除退役 skill symlink: $target"
    fi
  done
done

# ========== Step 2: Clean old managed symlinks from ~/.agents/skills/ ==========

if [ -f "$MANIFEST_FILE" ]; then
  while IFS= read -r name; do
    [ -z "$name" ] && continue
    target="$AGENTS_SKILLS/$name"
    # Only remove if it's a symlink (we created it), never remove real dirs
    if [ -L "$target" ]; then
      rm -f "$target"
    fi
  done < "$MANIFEST_FILE"
fi

# ========== Step 3: Migration — clean old symlinks from both dirs ==========

MIGRATION_MARKER="$MANIFEST_DIR/.v3_migrated"
if [ ! -f "$MIGRATION_MARKER" ]; then
  # Clean symlinks pointing to plugin/marketplace paths from BOTH directories
  # In ~/.agents/skills/: only keep symlinks pointing to our marketplace (taptap-plugins)
  # In ~/.codex/skills/: remove all symlinks pointing to plugin paths
  for dir in "$AGENTS_SKILLS" "$CODEX_SKILLS"; do
    [ -d "$dir" ] || continue
    for entry in "$dir"/*/; do
      [ -e "$entry" ] || [ -L "${entry%/}" ] || continue
      skill_name="$(basename "$entry")"

      target_path="${dir}/${skill_name}"
      if [ -L "$target_path" ]; then
        link_target="$(readlink "$target_path" 2>/dev/null || true)"
        case "$link_target" in
          */.claude/plugins/*|*/claude-plugins-marketplace/*)
            # In agents dir: keep our own marketplace symlinks (will be re-managed)
            # In codex dir: remove all plugin symlinks
            if [ "$dir" = "$CODEX_SKILLS" ]; then
              rm -f "$target_path"
              echo "🔗 已清理旧 symlink: $dir/$skill_name"
            elif echo "$link_target" | grep -qv "/$INCLUDE_MARKETPLACE/"; then
              # agents dir: remove symlinks from other marketplaces
              rm -f "$target_path"
              echo "🔗 已清理非本 marketplace symlink: $skill_name"
            fi
            ;;
        esac
      fi
    done
  done

  # Clean hardlinks in ~/.agents/skills/ (same inode as ~/.codex/skills/)
  if [ -d "$CODEX_SKILLS" ]; then
    for entry in "$AGENTS_SKILLS"/*/; do
      [ -d "$entry" ] || continue
      skill_name="$(basename "$entry")"
      [ -L "$AGENTS_SKILLS/$skill_name" ] && continue
      agents_file="$AGENTS_SKILLS/$skill_name/SKILL.md"
      codex_file="$CODEX_SKILLS/$skill_name/SKILL.md"
      if [ -f "$agents_file" ] && [ -f "$codex_file" ]; then
        agents_inode="$(stat -f '%i' "$agents_file" 2>/dev/null || stat -c '%i' "$agents_file" 2>/dev/null)"
        codex_inode="$(stat -f '%i' "$codex_file" 2>/dev/null || stat -c '%i' "$codex_file" 2>/dev/null)"
        if [ -n "$agents_inode" ] && [ "$agents_inode" = "$codex_inode" ]; then
          rm -rf "${AGENTS_SKILLS:?}/${skill_name:?}"
          echo "🔗 已清理硬链接: $skill_name"
        fi
      fi
    done
  fi

  touch "$MIGRATION_MARKER"
  echo "✅ 迁移完成（v3）"
fi

# ========== Step 4: Sync plugin skills to ~/.agents/skills/ ==========

new_manifest=""

MP_DIR="$HOME/.claude/plugins/marketplaces/$INCLUDE_MARKETPLACE"
for skill_md in \
  "$MP_DIR"/plugins/*/skills/*/SKILL.md \
  "$MP_DIR"/.claude/skills/*/SKILL.md; do
  [ -f "$skill_md" ] || continue
  skill_dir="$(dirname "$skill_md")"
  skill_name="$(basename "$skill_dir")"

  # Check if plugin is excluded
  excluded=false
  for ep in $EXCLUDE_PLUGINS; do
    if echo "$skill_dir" | grep -q "/plugins/$ep/"; then
      excluded=true
      break
    fi
  done
  [ "$excluded" = "true" ] && continue

  # Check if skill name is excluded
  for es in $EXCLUDE_SKILLS; do
    if [ "$skill_name" = "$es" ]; then
      excluded=true
      break
    fi
  done
  [ "$excluded" = "true" ] && continue

  # Skip if already exists as a real directory (user-created, not our symlink)
  if [ -e "$AGENTS_SKILLS/$skill_name" ] && [ ! -L "$AGENTS_SKILLS/$skill_name" ]; then
    continue
  fi

  # Create symlink in ~/.agents/skills/
  ln -sf "$skill_dir" "$AGENTS_SKILLS/$skill_name"
  new_manifest="$new_manifest
$skill_name"
done

# ========== Step 5: Sync ~/.claude/skills/ ==========

if [ -d "$CLAUDE_SKILLS" ]; then
  for skill_dir in "$CLAUDE_SKILLS"/*/; do
    [ -d "$skill_dir" ] || continue
    [ -f "$skill_dir/SKILL.md" ] || continue
    skill_name="$(basename "$skill_dir")"

    # Check exclusions
    excluded=false
    for es in $EXCLUDE_SKILLS; do
      [ "$skill_name" = "$es" ] && excluded=true && break
    done
    [ "$excluded" = "true" ] && continue

    # Skip if already exists (real dir, user symlink, or already managed)
    if [ -e "$AGENTS_SKILLS/$skill_name" ] || [ -L "$AGENTS_SKILLS/$skill_name" ]; then
      continue
    fi

    ln -sf "${skill_dir%/}" "$AGENTS_SKILLS/$skill_name"
    new_manifest="$new_manifest
$skill_name"
  done
fi

# ========== Step 6: Update manifest ==========

echo "$new_manifest" | sed '/^$/d' | sort -u > "$MANIFEST_FILE"
managed_count="$(wc -l < "$MANIFEST_FILE" | tr -d ' ')"
echo "✅ 同步完成: $managed_count 个 managed symlinks in ~/.agents/skills/"

echo "===== 完成 ====="
