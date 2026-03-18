#!/bin/bash
# ensure-codex-statusline.sh - 自动安装 Codex statusline (tmux + iTerm2)
# SessionStart hook: 后台执行，不阻塞 session 启动
# 幂等：每步都检查是否已配置

set -e

# 日志配置
LOG_DIR="$HOME/.claude/plugins/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/ensure-codex-statusline-$(date +%Y-%m-%d).log"
exec >> "$LOG_FILE" 2>&1
echo ""
echo "===== $(date '+%Y-%m-%d %H:%M:%S') ====="

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ========== 第一步：安装 codex-status 到 ~/.local/bin/ ==========

SRC_BIN="$SCRIPT_DIR/codex-status"
DST_DIR="$HOME/.local/bin"
DST_BIN="$DST_DIR/codex-status"

if [ ! -f "$SRC_BIN" ]; then
  echo "⚠️  源文件 $SRC_BIN 不存在，跳过"
  exit 0
fi

mkdir -p "$DST_DIR"

needs_copy=true
if [ -f "$DST_BIN" ]; then
  src_hash=$(shasum "$SRC_BIN" 2>/dev/null | awk '{print $1}')
  dst_hash=$(shasum "$DST_BIN" 2>/dev/null | awk '{print $1}')
  if [ "$src_hash" = "$dst_hash" ]; then
    needs_copy=false
    echo "✅ codex-status 已是最新，无需复制"
  fi
fi

if [ "$needs_copy" = "true" ]; then
  cp "$SRC_BIN" "$DST_BIN"
  chmod +x "$DST_BIN"
  echo "✅ 已复制 codex-status → $DST_BIN"
fi

# ========== 第二步：安装 zsh hooks 到 ~/.zshrc.local ==========

SRC_ZSH="$SCRIPT_DIR/codex-statusline.zsh"
DST_ZSH="$HOME/.zshrc.local"
ZSHRC="$HOME/.zshrc"
BEGIN_MARKER="# >>> codex-statusline BEGIN >>>"
END_MARKER="# <<< codex-statusline END <<<"

if [ ! -f "$SRC_ZSH" ]; then
  echo "⚠️  源文件 $SRC_ZSH 不存在，跳过 zsh hooks"
elif [ ! -f "$ZSHRC" ]; then
  echo "⏭️  ~/.zshrc 不存在（非 zsh 环境），跳过 zsh hooks"
else
  # 确保 .zshrc 会 source .zshrc.local
  if ! grep -q 'zshrc.local' "$ZSHRC" 2>/dev/null; then
    echo '' >> "$ZSHRC"
    echo '[ -f ~/.zshrc.local ] && source ~/.zshrc.local' >> "$ZSHRC"
    echo "✅ 已在 ~/.zshrc 中添加 source ~/.zshrc.local"
  fi
  src_content="$(cat "$SRC_ZSH")"

  if [ -f "$DST_ZSH" ] && grep -q "$BEGIN_MARKER" "$DST_ZSH" 2>/dev/null; then
    # 已有标记块 — 比较内容是否需要更新
    existing="$(sed -n "/$BEGIN_MARKER/,/$END_MARKER/p" "$DST_ZSH")"
    if [ "$existing" = "$src_content" ]; then
      echo "✅ zsh hooks 已是最新，无需更新"
    else
      # 替换标记块
      # 先删除旧块，再追加新块
      tmp_file="${DST_ZSH}.codex-tmp"
      sed "/$BEGIN_MARKER/,/$END_MARKER/d" "$DST_ZSH" > "$tmp_file"
      echo "" >> "$tmp_file"
      cat "$SRC_ZSH" >> "$tmp_file"
      mv "$tmp_file" "$DST_ZSH"
      echo "✅ 已更新 zsh hooks"
    fi
  elif [ -f "$DST_ZSH" ] && grep -q "codex_status_preexec" "$DST_ZSH" 2>/dev/null; then
    # 有旧版（无标记块）— 不自动覆盖，提示手动处理
    echo "⚠️  ~/.zshrc.local 已有 codex hooks（无标记块），跳过自动更新"
  else
    # 全新安装 — 追加到文件末尾
    [ -f "$DST_ZSH" ] && echo "" >> "$DST_ZSH"
    cat "$SRC_ZSH" >> "$DST_ZSH"
    echo "✅ 已追加 zsh hooks 到 $DST_ZSH"
  fi
fi

# ========== 第三步：配置 iTerm2（仅 macOS） ==========

if [ "$(uname)" = "Darwin" ]; then
  # 运行 codex-status --setup-iterm2（内部幂等）
  if "$DST_BIN" --setup-iterm2 2>/dev/null; then
    echo "✅ iTerm2 Status Bar 配置完成"
  else
    echo "⚠️  iTerm2 配置跳过（可能非 iTerm2 环境）"
  fi
else
  echo "⏭️  非 macOS，跳过 iTerm2 配置"
fi

echo "===== 完成 ====="
