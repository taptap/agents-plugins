---
name: clean-codex-statusline
description: 清理本地 Codex statusline 配置（codex-status 脚本、zsh hooks、tmux status-left、iTerm2 Status Bar、缓存）
---

## 执行流程

按顺序执行以下清理步骤，每步都检查是否存在再删除。

### 步骤 1：删除 codex-status 脚本

```bash
rm -f ~/.local/bin/codex-status && echo "✅ codex-status 已删除" || echo "⏭️ 不存在"
```

### 步骤 2：清理 zsh hooks

检查 `~/.zshrc.local` 中是否有 codex-statusline 标记块，有则删除：

```bash
if grep -q "codex-statusline BEGIN" ~/.zshrc.local 2>/dev/null; then
  sed '/# >>> codex-statusline BEGIN >>>/,/# <<< codex-statusline END <<</d' ~/.zshrc.local > ~/.zshrc.local.tmp && mv ~/.zshrc.local.tmp ~/.zshrc.local
  echo "✅ zsh hooks 已清理"
else
  echo "⏭️ 无 zsh hooks"
fi
```

### 步骤 3：重置 tmux status-left

如果当前在 tmux 中，重置 status bar 为默认值：

```bash
if [ -n "${TMUX:-}" ]; then
  tmux set -g status-left "[#S]" 2>/dev/null
  tmux set -gu window-status-format 2>/dev/null
  tmux set -gu window-status-current-format 2>/dev/null
  tmux set -gu status-right 2>/dev/null
  echo "✅ tmux status bar 已重置"
else
  echo "⏭️ 不在 tmux 中，跳过"
fi
```

### 步骤 4：清理 iTerm2 Status Bar

仅 macOS 执行。**必须通过 osascript 操作运行中的 iTerm2**（直接改 plist 会被 iTerm2 退出时覆盖）：

```bash
python3 -c "
import subprocess, plistlib, sys

# 通过 defaults export/import 操作（走 cfprefsd，不会被 iTerm2 退出时覆盖）
result = subprocess.run(['defaults', 'export', 'com.googlecode.iterm2', '-'], capture_output=True)
if result.returncode != 0:
    print('⏭️ iTerm2 配置不存在')
    sys.exit(0)

data = plistlib.loads(result.stdout)
bookmarks = data.get('New Bookmarks', [])
changed = False
for b in bookmarks:
    layout = b.get('Status Bar Layout', {})
    comps = layout.get('components', [])
    new_comps = [c for c in comps if 'codex_status' not in str(c.get('configuration', {}).get('knobs', {}).get('expression', ''))]
    if len(new_comps) != len(comps):
        layout['components'] = new_comps
        changed = True
    if not new_comps and b.get('Show Status Bar'):
        b['Show Status Bar'] = False
        changed = True

if changed:
    xml = plistlib.dumps(data)
    result = subprocess.run(['defaults', 'import', 'com.googlecode.iterm2', '-'], input=xml, capture_output=True)
    if result.returncode == 0:
        print('✅ iTerm2 codex_status 组件已清除（Cmd+Q 重启 iTerm2 生效）')
    else:
        print('❌ iTerm2 配置写入失败')
        sys.exit(1)
else:
    print('⏭️ iTerm2 无 codex_status 组件')
"
```

### 步骤 5：清理缓存

```bash
rm -rf ~/.cache/codex-status && echo "✅ 缓存已清理" || echo "⏭️ 不存在"
```

### 步骤 6：输出结果

汇总报告并提示。**必须包含以下完整提示，不可省略：**

```
✅ Codex statusline 已完全清理

清理项目：
  - ~/.local/bin/codex-status
  - ~/.zshrc.local codex-statusline 块
  - tmux status bar
  - iTerm2 Status Bar codex_status 组件
  - ~/.cache/codex-status/

提示：
  - 新开终端窗口使 zsh 变更生效
  - 如需重新安装：/sync:codex-statusline
```
