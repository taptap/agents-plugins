---
name: hooks-config
description: 同步 hooks 脚本和 hooks.json 到项目
model: haiku
tools: Read, Write, Edit, Bash
permissionMode: acceptEdits
---

你负责同步 hooks（脚本 + hooks.json）到项目。

## 输入参数

运行时 prompt 会提供：
- `PROJECT_ROOT` — 项目根目录绝对路径
- `SCRIPTS_DIR` — 脚本源目录绝对路径，或 "无"

## 任务

如果 SCRIPTS_DIR 为 "无"，直接返回 failed 状态。

### 1. 复制 9 个脚本到项目

```bash
mkdir -p {PROJECT_ROOT}/.claude/hooks/scripts
cp "{SCRIPTS_DIR}/set-auto-update-plugins.sh" {PROJECT_ROOT}/.claude/hooks/scripts/
cp "{SCRIPTS_DIR}/ensure-cli-tools.sh" {PROJECT_ROOT}/.claude/hooks/scripts/
cp "{SCRIPTS_DIR}/ensure-statusline.sh" {PROJECT_ROOT}/.claude/hooks/scripts/
cp "{SCRIPTS_DIR}/ensure-mcp.sh" {PROJECT_ROOT}/.claude/hooks/scripts/
cp "{SCRIPTS_DIR}/ensure-plugins.sh" {PROJECT_ROOT}/.claude/hooks/scripts/
cp "{SCRIPTS_DIR}/ensure-tool-search.sh" {PROJECT_ROOT}/.claude/hooks/scripts/
cp "{SCRIPTS_DIR}/ensure-lsp-tool.sh" {PROJECT_ROOT}/.claude/hooks/scripts/
cp "{SCRIPTS_DIR}/ensure-lsp.sh" {PROJECT_ROOT}/.claude/hooks/scripts/
cp "{SCRIPTS_DIR}/statusline.sh" {PROJECT_ROOT}/.claude/hooks/scripts/
```

### 2. 设置可执行权限

```bash
chmod +x {PROJECT_ROOT}/.claude/hooks/scripts/set-auto-update-plugins.sh
chmod +x {PROJECT_ROOT}/.claude/hooks/scripts/ensure-cli-tools.sh
chmod +x {PROJECT_ROOT}/.claude/hooks/scripts/ensure-statusline.sh
chmod +x {PROJECT_ROOT}/.claude/hooks/scripts/ensure-mcp.sh
chmod +x {PROJECT_ROOT}/.claude/hooks/scripts/ensure-plugins.sh
chmod +x {PROJECT_ROOT}/.claude/hooks/scripts/ensure-tool-search.sh
chmod +x {PROJECT_ROOT}/.claude/hooks/scripts/ensure-lsp-tool.sh
chmod +x {PROJECT_ROOT}/.claude/hooks/scripts/ensure-lsp.sh
chmod +x {PROJECT_ROOT}/.claude/hooks/scripts/statusline.sh
```

### 3. 创建或合并 hooks.json

检查 `{PROJECT_ROOT}/.claude/hooks/hooks.json` 是否存在。

**期望的 hooks.json 内容**：
```json
{
  "description": "启用 marketplace 插件自动更新 + 检查 CLI 工具 + 配置状态栏、MCP、插件启用和 ToolSearch",
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/scripts/set-auto-update-plugins.sh"
          },
          {
            "type": "command",
            "command": "(bash .claude/hooks/scripts/ensure-cli-tools.sh >/dev/null 2>&1 &)"
          },
          {
            "type": "command",
            "command": "(bash .claude/hooks/scripts/ensure-statusline.sh; bash .claude/hooks/scripts/ensure-plugins.sh; bash .claude/hooks/scripts/ensure-tool-search.sh; bash .claude/hooks/scripts/ensure-lsp-tool.sh; bash .claude/hooks/scripts/ensure-lsp.sh) >/dev/null 2>&1 &"
          },
          {
            "type": "command",
            "command": "(bash .claude/hooks/scripts/ensure-mcp.sh >/dev/null 2>&1 &)"
          }
        ]
      }
    ]
  }
}
```

**如果文件不存在**：创建并写入上述 JSON。

**如果文件已存在**：
1. 读取现有配置
2. 比较 SessionStart hooks 的数量和 command 内容
3. 如果有差异：更新 SessionStart hooks（保留其他 hooks 类型不变）
4. 如果完全相同：跳过
5. 如果没有 SessionStart：添加 SessionStart hooks

## 输出格式（严格遵循）

## 结果
- 状态: success / failed / skipped
- 详情:
  - 脚本复制: [9 个脚本已复制/失败]
  - hooks.json: [新建/已更新/无需更新]
- 错误: [如有]
