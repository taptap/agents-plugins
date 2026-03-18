---
name: codex-statusline
description: 安装/更新 Codex statusline
user_invocable: true
---

# Codex Statusline 安装

安装 Codex statusline 到 tmux + iTerm2。

## 步骤 1：定位脚本目录

```bash
MP=~/.claude/plugins/marketplaces/taptap-plugins/plugins/sync && \
LATEST=$(ls -d ~/.claude/plugins/cache/taptap-plugins/sync/*/ 2>/dev/null | sort -V | tail -1) && \
(test -d "${MP}/scripts" && echo "SCRIPTS_DIR=${MP}/scripts" || (test -n "${LATEST}" && test -d "${LATEST}scripts" && echo "SCRIPTS_DIR=${LATEST}scripts" || echo "SCRIPTS_DIR=none"))
```

如果 `SCRIPTS_DIR=none`，提示插件未安装并停止。

## 步骤 2：执行安装

```bash
bash "{SCRIPTS_DIR}/ensure-codex-statusline.sh"
```

## 步骤 3：检查结果

```bash
echo "=== 检查结果 ===" && \
(test -f ~/.local/bin/codex-status && echo "✅ codex-status: 已安装" || echo "❌ codex-status: 未安装") && \
(grep -q "codex-statusline BEGIN" ~/.zshrc.local 2>/dev/null && echo "✅ zsh hooks: 已配置" || echo "❌ zsh hooks: 未配置")
```

向用户报告结果。如果是首次安装 iTerm2 配置，提示需要重启 iTerm2。
