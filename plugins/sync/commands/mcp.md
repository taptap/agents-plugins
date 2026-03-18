---
allowed-tools: Bash(pwd:*), Read, Write, Edit, TodoWrite
description: 同步 context7 MCP 配置到 Claude Code 和 Cursor
---

## Context

- 当前工作目录: !`pwd`
- MCP 配置模板路径: `.claude/plugins/sync/skills/mcp-templates/`
- 目标配置文件:
  - `~/.claude.json` (Claude Code 读取，用户级)
  - `~/.cursor/mcp.json` (Cursor 读取，用户级)

## Your Task

**目标：从模板同步 context7 MCP 配置到两个配置文件**

⚠️ **重要原则：不覆盖已存在的配置**

### 执行流程

#### 阶段 0：准备工作

**步骤 0.1：定义常量**

```
MCP 列表: ["context7"]
模板目录: .claude/plugins/sync/skills/mcp-templates/
目标文件:
  - ~/.claude.json (Claude Code，用户级)
  - ~/.cursor/mcp.json (Cursor，用户级)
```

**步骤 0.2：创建任务跟踪**

使用 TodoWrite 创建任务清单：
```
- 读取配置模板
- 同步到 ~/.claude.json
- 同步到 ~/.cursor/mcp.json
```

#### 阶段 1：读取配置模板

**步骤 1.1：读取 context7 模板**

```
使用 Read 工具读取: .claude/plugins/sync/skills/mcp-templates/context7.json
```

**步骤 1.2：解析配置**

将读取的 JSON 内容解析为对象，准备用于同步。

#### 阶段 2：同步到 ~/.claude.json

**步骤 2.1：读取 ~/.claude.json**

使用 Read 工具读取 `~/.claude.json`。

**判断逻辑：**
- 文件不存在 → 跳至步骤 2.2（创建文件）
- 文件存在 → 跳至步骤 2.3（更新文件）

**步骤 2.2：创建 ~/.claude.json（文件不存在时）**

使用 Write 工具创建 `~/.claude.json`：

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"],
      "env": {}
    }
  }
}
```

完成后跳至阶段 3。

**步骤 2.3：更新 ~/.claude.json（文件存在时）**

- 对于 context7：如果不存在，使用 Edit 工具添加；如果已存在，跳过
- 清理废弃 MCP：如果存在 sequential-thinking，使用 Edit 工具删除

**注意事项：**
- 保持 JSON 格式正确
- 不覆盖或修改已存在的其他 MCP 配置

#### 阶段 3：同步到 ~/.cursor/mcp.json

同阶段 2 逻辑。

#### 阶段 4：汇总结果

```
✅ MCP 配置同步完成！

同步结果：
  ~/.claude.json:
    - context7: [新增配置 / 已存在]

  ~/.cursor/mcp.json:
    - context7: [新增配置 / 已存在]

下一步：
  1. 重启 Claude Code 会话（如果有新增配置）
  2. 重启 Cursor IDE（如果有新增配置）

MCP 功能说明：
  - context7: 拉取最新的库文档和代码示例（AI 自动调用）
```

## 配置说明

### context7
- **功能**：拉取最新的、特定版本的文档和代码示例到 AI 上下文
- **使用方法**：自动被 AI 调用，无需手动触发（也可手动使用 "use context7"）
- **适用场景**：需要参考 GitHub 公开库、获取最新文档、避免生成过时代码

## 相关文档

- [MCP 配置模板](../skills/mcp-templates/)
- [context7 使用指南](../skills/context7/context7-usage.md)
- [Sync Plugin README](../README.md)
