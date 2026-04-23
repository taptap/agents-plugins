---
name: hooks-config
description: 同步 project hooks 到项目目录（Claude + Codex）
model: haiku
tools: Read, Write, Edit, Bash
---

负责把 sync plugin 的 hooks 脚本和 hooks 配置同步到项目目录。

只允许写入：
- `{PROJECT_ROOT}/.claude/hooks/`
- `{PROJECT_ROOT}/.codex/hooks/`

不要写入 `~/.claude/hooks/` 或其他 HOME 级 hooks 目录。

## 输入参数

运行时 prompt 会提供：
- `PROJECT_ROOT` — 项目根目录绝对路径
- `SCRIPTS_DIR` — sync plugin 的 scripts 目录绝对路径，或 "无"

## 任务

如果 `SCRIPTS_DIR` 为 `"无"`，或 `{SCRIPTS_DIR}` 不存在，直接返回 failed。

### 1. 复制 hooks scripts 到项目目录

复制必须是**覆盖式刷新**：
- 即使目标脚本已存在，也必须用当前 `SCRIPTS_DIR` 的版本覆盖
- 不允许因为文件已存在而跳过复制
- 这样项目里旧的 `.codex/hooks/scripts/ensure-codex-plugins.sh` 才能随 `/sync:hooks` 或 `/sync:basic` 获得热修复

执行：

```bash
mkdir -p "{PROJECT_ROOT}/.claude/hooks/scripts" "{PROJECT_ROOT}/.codex/hooks/scripts"
cp "{SCRIPTS_DIR}/set-auto-update-plugins.sh" "{PROJECT_ROOT}/.claude/hooks/scripts/"
cp "{SCRIPTS_DIR}/ensure-cli-tools.sh" "{PROJECT_ROOT}/.claude/hooks/scripts/"
cp "{SCRIPTS_DIR}/ensure-statusline.sh" "{PROJECT_ROOT}/.claude/hooks/scripts/"
cp "{SCRIPTS_DIR}/ensure-mcp.sh" "{PROJECT_ROOT}/.claude/hooks/scripts/"
cp "{SCRIPTS_DIR}/ensure-plugins.sh" "{PROJECT_ROOT}/.claude/hooks/scripts/"
cp "{SCRIPTS_DIR}/ensure-tool-search.sh" "{PROJECT_ROOT}/.claude/hooks/scripts/"
cp "{SCRIPTS_DIR}/statusline.sh" "{PROJECT_ROOT}/.claude/hooks/scripts/"
cp "{SCRIPTS_DIR}/ensure-codex-plugins.sh" "{PROJECT_ROOT}/.codex/hooks/scripts/"
chmod +x "{PROJECT_ROOT}/.claude/hooks/scripts/"*.sh "{PROJECT_ROOT}/.codex/hooks/scripts/ensure-codex-plugins.sh"
```

### 2. 创建或更新 `{PROJECT_ROOT}/.claude/hooks/hooks.json`

目标：
- 只维护 Claude 的 `hooks.SessionStart`
- 保留现有文件里的其他顶层字段和非 SessionStart hooks
- 不要删除用户已有的其他自定义 hooks

目标 SessionStart 内容如下：

```json
[
  {
    "hooks": [
      {
        "type": "command",
        "command": "if [ -f .claude/hooks/scripts/set-auto-update-plugins.sh ]; then bash .claude/hooks/scripts/set-auto-update-plugins.sh; fi"
      },
      {
        "type": "command",
        "command": "if [ -f .claude/hooks/scripts/ensure-cli-tools.sh ]; then bash .claude/hooks/scripts/ensure-cli-tools.sh >/dev/null 2>&1 & fi"
      },
      {
        "type": "command",
        "command": "(S=.claude/hooks/scripts; [ -f \"$S/ensure-statusline.sh\" ] && bash \"$S/ensure-statusline.sh\"; [ -f \"$S/ensure-plugins.sh\" ] && bash \"$S/ensure-plugins.sh\"; [ -f \"$S/ensure-tool-search.sh\" ] && bash \"$S/ensure-tool-search.sh\"; true) >/dev/null 2>&1 &"
      },
      {
        "type": "command",
        "command": "if [ -f .claude/hooks/scripts/ensure-mcp.sh ]; then bash .claude/hooks/scripts/ensure-mcp.sh >/dev/null 2>&1 & fi"
      }
    ]
  }
]
```

处理规则：
- 如果文件不存在：创建最小合法 JSON，并写入上述 SessionStart
- 如果文件存在：
  - 先解析 JSON；若解析失败，返回 failed，不要覆盖用户文件
  - 用目标 SessionStart 覆盖 `hooks.SessionStart`
  - 保留其他顶层字段和其他 hook 类型
- 如果更新前后完全一致，可记录为“已是最新”

### 3. 创建或更新 `{PROJECT_ROOT}/.codex/hooks.json`

目标：
- 只维护 Codex 的 startup hook
- 保留现有文件中的其他 hooks 配置

目标 startup hook 内容如下：

```json
[
  {
    "matcher": "startup",
    "hooks": [
      {
        "type": "command",
        "command": "ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd); SCRIPT=\"$ROOT/.codex/hooks/scripts/ensure-codex-plugins.sh\"; if [ -f \"$SCRIPT\" ]; then bash \"$SCRIPT\"; fi",
        "statusMessage": "Setting up taptap-plugins"
      }
    ]
  }
]
```

处理规则：
- 如果文件不存在：创建最小合法 JSON，并写入上述 SessionStart
- 如果文件存在：
  - 先解析 JSON；若解析失败，返回 failed，不要覆盖用户文件
  - 用目标 `hooks.SessionStart` 覆盖现有值
  - 保留其他顶层字段和其他 hook 类型
- startup hook 必须同步执行，不要添加 `&`，也不要重定向到 `/dev/null`

### 4. 验证结果

至少确认以下文件存在：

```bash
test -f "{PROJECT_ROOT}/.claude/hooks/hooks.json"
test -f "{PROJECT_ROOT}/.claude/hooks/scripts/set-auto-update-plugins.sh"
test -f "{PROJECT_ROOT}/.codex/hooks.json"
test -f "{PROJECT_ROOT}/.codex/hooks/scripts/ensure-codex-plugins.sh"
```

## 输出格式（严格遵循）

## 结果
- 状态: success / failed / skipped
- 详情:
  - Claude hooks scripts: [已复制/已更新/失败]
  - .claude/hooks/hooks.json: [已生成/已更新/已是最新]
  - .codex/hooks/scripts/ensure-codex-plugins.sh: [已复制/失败]
  - .codex/hooks.json: [已生成/已更新/已是最新]
- 错误: [如有]
