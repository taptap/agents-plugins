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
  if [ -f "$DST_ZSH" ] && grep -q "$BEGIN_MARKER" "$DST_ZSH" 2>/dev/null; then
    # 已有标记块 — 用 hash 比较是否需要更新（避免空行/换行符差异导致误判）
    existing_hash="$(sed -n "/$BEGIN_MARKER/,/$END_MARKER/p" "$DST_ZSH" | shasum | awk '{print $1}')"
    src_hash="$(shasum "$SRC_ZSH" | awk '{print $1}')"
    if [ "$existing_hash" = "$src_hash" ]; then
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

# ========== 第三步：配置 tmux passthrough（tmux -CC 模式需要） ==========

PASSTHROUGH_LINE="set -g allow-passthrough on"

if command -v tmux >/dev/null 2>&1; then
  # 检查 ~/.tmux.conf 和 ~/.tmux.conf.local 是否已配置
  passthrough_found=false
  for conf in "$HOME/.tmux.conf" "$HOME/.tmux.conf.local"; do
    if [ -f "$conf" ] && grep -q "allow-passthrough" "$conf" 2>/dev/null; then
      passthrough_found=true
      break
    fi
  done
  if [ "$passthrough_found" = "true" ]; then
    echo "✅ tmux allow-passthrough 已配置"
  else
    # 优先写 .tmux.conf.local（gpakosz/.tmux 等框架的自定义文件）
    TMUX_TARGET="$HOME/.tmux.conf.local"
    [ ! -f "$TMUX_TARGET" ] && TMUX_TARGET="$HOME/.tmux.conf"
    echo "" >> "$TMUX_TARGET"
    echo "# Allow iTerm2 escape sequences to pass through tmux (required for tmux -CC mode)" >> "$TMUX_TARGET"
    echo "$PASSTHROUGH_LINE" >> "$TMUX_TARGET"
    echo "✅ 已在 $(basename "$TMUX_TARGET") 中启用 allow-passthrough"
  fi
  # 如果当前在 tmux 内，立即生效
  if [ -n "${TMUX:-}" ]; then
    tmux set -g allow-passthrough on 2>/dev/null || true
  fi
else
  echo "⏭️  tmux 未安装，跳过 passthrough 配置"
fi

# ========== 第四步：配置 iTerm2（仅 macOS） ==========

if [ "$(uname)" = "Darwin" ]; then
  # 运行 codex-status --setup-iterm2（内部幂等）
  if "$DST_BIN" --setup-iterm2 2>/dev/null; then
    echo "✅ iTerm2 Status Bar 配置完成（首次配置需完全退出并重启 iTerm2）"
  else
    echo "⚠️  iTerm2 配置跳过（可能非 iTerm2 环境）"
  fi
else
  echo "⏭️  非 macOS，跳过 iTerm2 配置"
fi

echo "===== 完成 ====="
