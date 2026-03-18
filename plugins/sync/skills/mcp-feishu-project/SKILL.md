---
name: mcp-feishu-project
description: 当用户提供飞书项目 MCP URL 或请求配置飞书项目 MCP 时触发。自动同时配置到 Claude Code 和 Cursor，简化团队成员的环境设置流程。支持查询项目任务、工作项、需求等。
---

# 飞书项目 MCP 配置辅助

当用户提供飞书项目 MCP URL 或请求配置时，自动应用此 skill，**同时配置到 Claude Code 和 Cursor**。

## 触发场景

用户消息满足以下任一条件时触发：

1. 包含飞书项目 MCP URL（`https://project.feishu.cn/mcp_server/v1?...`）
2. 包含配置相关关键词 + "飞书项目"：
   - 「配置」「设置」「添加」「同步」+ 「飞书项目」
   - 「feishu project」「project mcp」
3. 需要查询项目任务、工作项、需求

## 核心原则

⚠️ **强制要求：必须完成所有必选任务**

此 skill 的目标是同时配置 Claude Code 和 Cursor。Codex 配置为**可选**，仅在用户传入 `--with-codex` 参数时执行。

**任务清单：**
1. ✅ 配置 Claude Code (`~/.claude.json`)（必选）
2. ✅ 配置 Cursor (`~/.cursor/mcp.json`)（必选）
3. ⏭️ 配置 Codex (`~/.codex/config.toml`)（可选，需 `--with-codex` 参数）

**Codex 为可选的原因：** Codex context window 较小（258K），MCP 工具定义会额外占用 context，默认不配置以节省空间。

**如果任一必选任务失败，必须：**
- 明确告知用户哪个任务失败
- 提供具体的错误信息和解决方案
- 不能只完成一个任务就结束

## 执行流程

### 阶段 0：准备工作

**0.1 提取 URL 或收集参数**

**情况 A：用户提供完整 URL**

从用户消息中提取飞书项目 MCP URL：
```regex
https://project\.feishu\.cn/mcp_server/v1\?mcpKey=[^&]+&projectKey=[^&]+&userKey=[^&\s]+
```

**情况 B：用户未提供 URL**

引导用户获取配置参数：

```
⚠️ 飞书项目 MCP 需要以下参数：

1. mcpKey: MCP 密钥
2. projectKey: 项目空间 ID
3. userKey: 用户 ID

获取步骤：
1. 打开飞书项目：https://project.feishu.cn
2. 进入目标项目空间，获取 MCP 配置（包含 mcpKey 和 projectKey）
3. 点击右上角头像获取 userKey（用户 ID）

参考文档：https://xd.feishu.cn/wiki/KIZrwBH1viRRGHkBTWmcSwyInwf#share-YnMwdzjOnohu9sxQqbKc3oFSnwI

请提供完整的 MCP URL 或以下参数：
- mcpKey:
- projectKey:
- userKey:
```

**0.2 构建 MCP URL**

如果用户提供分散参数，构建完整 URL：
```
https://project.feishu.cn/mcp_server/v1?mcpKey={mcpKey}&projectKey={projectKey}&userKey={userKey}
```

**0.3 检查参数**

检查用户是否传入 `--with-codex` 参数：
- 有 `--with-codex` → `SYNC_CODEX=true`
- 无 → `SYNC_CODEX=false`

**0.4 创建任务清单**

使用 TodoWrite 创建任务清单：
```
- 配置 Claude Code
- 配置 Cursor
- 配置 Codex（仅 --with-codex 时）
```

### 阶段 1：配置 Claude Code

**1.1 检查现有配置**

执行命令：
```bash
claude mcp get feishu-project-mcp
```

**判断逻辑：**
- 输出包含 `Status: ✓ Connected` → 已配置，跳至 1.4
- 输出包含 `No MCP server found` 或错误 → 需要配置，继续 1.2

**1.2 添加配置**

执行命令：
```bash
claude mcp add --transport http --scope user feishu-project-mcp "<完整 URL>"
```

**1.3 验证配置**

执行命令：
```bash
claude mcp get feishu-project-mcp
```

**验证标准：**
- ✅ 输出包含 `Status: ✓ Connected`
- ✅ 输出包含 `Type: http`
- ✅ 输出包含正确的 URL

如果验证失败，记录错误并继续执行 Cursor 配置（不要因为一个失败就放弃另一个）。

**1.4 更新任务清单**

使用 TodoWrite 标记 "配置 Claude Code" 为 completed。

### 阶段 2：配置 Cursor

**2.1 检查配置文件**

使用 Read 工具读取 `~/.cursor/mcp.json`。

**判断逻辑：**
- 文件不存在 → 需要创建，跳至 2.2
- 文件存在 → 检查内容，跳至 2.3

**2.2 创建配置文件**

使用 Write 工具创建 `~/.cursor/mcp.json`：

```json
{
  "mcpServers": {
    "feishu-project-mcp": {
      "type": "http",
      "url": "<完整 URL>"
    }
  }
}
```

完成后跳至 2.4。

**2.3 更新现有配置**

**情况 A：文件存在但没有 feishu-project-mcp**

使用 Edit 工具添加 `feishu-project-mcp` 配置。

**情况 B：文件存在且已有 feishu-project-mcp**

检查 URL 是否与新 URL 一致：
- 一致 → 已配置，无需修改，跳至 2.4
- 不一致 → 询问用户是否覆盖

**情况 C：文件存在且已有其他 MCP 配置**

使用 Edit 工具在 `mcpServers` 中添加 `feishu-project-mcp`，保持其他配置不变。

**注意事项：**
- 保持 JSON 格式正确
- 不覆盖或修改其他 MCP 配置
- 文件末尾保留一个空行

**2.4 更新任务清单**

使用 TodoWrite 标记 "配置 Cursor" 为 completed。

### 阶段 2.5：配置 Codex（可选，仅 `--with-codex` 时执行）

**如果 `SYNC_CODEX=false`，跳过此阶段，在汇总中标注 "跳过（未启用 --with-codex）"。**

**2.5.1 检查配置文件**

使用 Read 工具读取 `~/.codex/config.toml`。

**判断逻辑：**
- 文件不存在 → 跳过（Codex 未安装）
- 文件存在 → 检查是否已有 `[mcp_servers.feishu-project-mcp]` 段

**2.5.2 添加或更新配置**

**情况 A：文件中没有 `[mcp_servers.feishu-project-mcp]` 段**

使用 Edit 工具在文件末尾追加：

```toml

[mcp_servers.feishu-project-mcp]
url = "<提取的 URL>"
```

**情况 B：文件中已有 `[mcp_servers.feishu-project-mcp]` 段**

检查 `url` 是否与新 URL 一致：
- 一致 → 已配置，无需修改
- 不一致 → 使用 Edit 工具更新 url 值

**注意事项：**
- TOML 格式：section header 用 `[mcp_servers.feishu-project-mcp]`，键值对用 `url = "..."`
- 不覆盖或修改其他配置段
- 如果 `~/.codex/config.toml` 不存在，说明 Codex 未安装，跳过此步骤并在汇总中标注

**2.5.3 更新任务清单**

使用 TodoWrite 标记 "配置 Codex" 为 completed（或 skipped）。

### 阶段 3：汇总结果

**3.1 检查任务完成情况**

统计两个任务的状态：
- Claude Code: 成功 / 失败 / 已存在
- Cursor: 成功 / 失败 / 已存在

**3.2 输出结果**

**情况 A：所有必选任务都成功**

```
✅ 飞书项目 MCP 配置完成！

配置状态：
  Claude Code: ✅ [新增配置 / 已配置]
  Cursor:      ✅ [新增配置 / 已配置]
  Codex:       [✅ 新增配置 / 已配置 / ⏭️ 跳过（未启用 --with-codex）/ ⏭️ 跳过（未安装）]

配置位置：
  - Claude Code: ~/.claude.json（user scope，所有项目可用）
  - Cursor: ~/.cursor/mcp.json
  - Codex: ~/.codex/config.toml [mcp_servers] 段（需 --with-codex）

下一步：
  1. 重启 Claude Code 会话（如果是新增配置）
  2. 重启 Cursor IDE（如果是新增配置）
  3. 使用 /mcp 命令验证连接状态

注意：配置文件位于用户目录，不会提交到 git 仓库。
```

**情况 B：部分任务失败**

```
⚠️ 飞书项目 MCP 部分配置成功

配置状态：
  Claude Code: [✅ 成功 / ❌ 失败]
  Cursor:      [✅ 成功 / ❌ 失败]
  Codex:       [✅ 成功 / ❌ 失败 / ⏭️ 跳过（未启用 --with-codex）/ ⏭️ 跳过（未安装）]

失败详情：
  [具体错误信息]

建议：
  - 检查参数是否正确
  - 检查网络连接是否正常
  - 手动编辑配置文件
```

## MCP URL 格式

```
https://project.feishu.cn/mcp_server/v1?mcpKey={mcpKey}&projectKey={projectKey}&userKey={userKey}
```

## MCP 配置位置

| 工具        | 配置文件                                | 说明                 |
| ----------- | --------------------------------------- | -------------------- |
| Claude Code | `~/.claude.json` → `mcpServers`         | User scope，所有项目可用 |
| Cursor      | `~/.cursor/mcp.json` → `mcpServers`     | 用户级别，全局共用    |
| Codex       | `~/.codex/config.toml` → `[mcp_servers]` | 用户级别，TOML 格式  |

## MCP 参数说明

| 参数       | 说明                              |
| ---------- | --------------------------------- |
| type       | `http`（HTTP 类型 MCP 服务）       |
| mcpKey     | MCP 密钥，从飞书项目 MCP 配置获取   |
| projectKey | 项目空间 ID，从飞书项目 URL 获取   |
| userKey    | 用户 ID，从飞书项目头像菜单获取    |

## 错误处理

### Claude Code 配置失败

**常见错误：**
1. URL 格式错误 → 检查参数是否完整
2. 网络连接失败 → 检查网络连接
3. 命令执行失败 → 检查 Claude Code 是否正确安装

**解决方案：**
```bash
# 手动验证配置
claude mcp list

# 手动添加配置
claude mcp add --transport http --scope user feishu-project-mcp "<URL>"

# 查看详细错误
claude mcp get feishu-project-mcp
```

### Cursor 配置失败

**常见错误：**
1. 文件权限不足 → 检查 `~/.cursor/` 目录权限
2. JSON 格式错误 → 使用 JSON 验证工具检查格式
3. 文件被占用 → 关闭 Cursor 后重试

**解决方案：**
```bash
# 检查文件是否存在
ls -la ~/.cursor/mcp.json

# 查看文件内容
cat ~/.cursor/mcp.json
```

### Codex 配置失败

**常见错误：**
1. `~/.codex/config.toml` 不存在 → Codex 未安装，跳过
2. TOML 格式错误 → 检查缩进和引号
3. 文件权限不足 → 检查 `~/.codex/` 目录权限

**解决方案：**
```bash
# 手动添加 MCP 配置
cat >> ~/.codex/config.toml << 'EOF'

[mcp_servers.feishu-project-mcp]
url = "<URL>"
EOF

# 验证配置
grep -A 2 'feishu-project-mcp' ~/.codex/config.toml
```

## 配置验证

**Claude Code：**
```bash
claude mcp list
# 应该看到 feishu-project-mcp 且状态为 ✓ Connected

claude mcp get feishu-project-mcp
# 查看详细配置信息
```

**Cursor：**
```bash
grep -A 3 "feishu-project-mcp" ~/.cursor/mcp.json
# 检查配置是否正确
```

**Codex：**
```bash
grep -A 2 'feishu-project-mcp' ~/.codex/config.toml
# 检查 url 是否正确
```

## 示例对话

**用户：**
> 帮我配置飞书项目 MCP：https://project.feishu.cn/mcp_server/v1?mcpKey=xxx&projectKey=yyy&userKey=zzz

**Claude：**
> 我来帮你配置飞书项目 MCP 到 Claude Code 和 Cursor...
>
> [创建任务清单]
> [执行 Claude Code 配置]
> [执行 Cursor 配置]
>
> ✅ 飞书项目 MCP 配置完成！
>
> 配置状态：
>   Claude Code: ✅ 新增配置
>   Cursor:      ✅ 新增配置

## 相关文档

- [HTTP MCP 配置指南](../mcp-feishu/mcp-http-configuration.md)
- [飞书项目文档](https://xd.feishu.cn/wiki/KIZrwBH1viRRGHkBTWmcSwyInwf)
