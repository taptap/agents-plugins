# Sync Plugin

项目环境引导插件，负责 Claude Code 侧的基础开发环境配置。

## 快速开始

推荐新成员在项目根目录执行：

```bash
/sync:basic
```

`/sync:basic` 会完成这些事情：

- 配置 `context7` MCP
- 安装 SessionStart hooks，启用插件自动更新、CLI 检测、LSP 检测和状态栏
- 同步 GitLab Merge Request 默认模板
- 同步仓库级 Claude Skills 模板
- 配置 Status Line
- 检测项目语言并启用对应的 LSP 插件

## 常用命令

| 命令 | 说明 |
|------|------|
| `/sync:basic` | 一键配置基础开发环境 |
| `/sync:mcp` | 仅配置 `context7` MCP |
| `/sync:hooks` | 仅配置 SessionStart hooks |
| `/sync:lsp` | 检测语言并配置 LSP |
| `/sync:statusline` | 仅配置 Status Line |
| `/sync:mcp-feishu <url>` | 配置飞书文档 MCP |
| `/sync:mcp-feishu-project <url>` | 配置飞书项目 MCP |
| `/sync:mcp-grafana <user> <pass>` | 配置 Grafana MCP |
| `/sync:git-cli-auth` | 检测并配置 `gh` / `glab` 认证 |

## 设计约束

- `sync` 只负责 Claude Code 侧基础环境引导。
- 旧的 IDE 专用命令和模板已移除，不再写入其他 IDE 的配置目录。
- Codex 插件分发单独处理；`sync` 不再写入或维护 `~/.agents/skills`。

## MCP 相关

### `/sync:mcp`

同步 `context7` 到 `~/.claude.json` 的 `mcpServers`，不会覆盖已有的其他 MCP 配置，并会清理已退役的 `sequential-thinking`。

### `/sync:mcp-feishu`

当用户提供飞书文档 MCP URL 时，配置 `feishu-mcp` 到 Claude Code 的 user scope。

### `/sync:mcp-feishu-project`

当用户提供飞书项目 MCP URL 或 `mcpKey/projectKey/userKey` 时，配置 `feishu-project-mcp` 到 Claude Code 的 user scope。

### `/sync:mcp-grafana`

自动安装 `golang` 和 `mcp-grafana`，然后将 Grafana MCP 配置写入 `~/.claude.json`。

## 自动触发 Skills

- `context7`
  在询问公开仓库、框架或库的最新文档时自动触发。
- `mcp-feishu`
  在用户提供飞书文档 MCP URL 并请求配置时自动触发。
- `mcp-feishu-project`
  在用户提供飞书项目 MCP URL 或请求配置飞书项目 MCP 时自动触发。

## 兼容性说明

### Claude Skills

`/sync:basic` 会把少量仓库级 Claude Skills 模板复制到项目内 `.claude/skills/`，保留项目自定义文件，不覆盖已存在的 review 规则。

### Codex Skills

Codex 已支持插件原生分发 bundled skills，`sync` 不再通过 SessionStart hook 维护 `~/.agents/skills`。

## 维护说明

- 修改 `plugins/sync/**` 后，必须同时升级：
  - `plugins/sync/.claude-plugin/plugin.json`
  - `.claude-plugin/marketplace.json` 中 `sync.version`
  - `.claude-plugin/marketplace.json` 中 `metadata.version`
- 如需重新加载插件缓存，可执行 `/clear-cache`
