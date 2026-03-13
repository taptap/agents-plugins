# Sync Plugin

项目配置同步插件，提供 MCP 和开发环境配置同步功能。

## 快速开始

### 新成员环境配置（推荐）

一键配置开发环境：

```bash
/sync:basic
```

这个命令会自动完成：
- ✅ 配置 MCP 服务器（context7 + sequential-thinking）
- ✅ 启用自动更新钩子（Marketplace autoUpdate）+ CLI 工具检测
- ✅ 同步配置到 Cursor IDE（git-flow rules + commands）
- ✅ 同步 GitLab Merge Request 默认模板
- ✅ 同步 Claude Skills（grafana-dashboard-design）
- ✅ 配置 Status Line（项目/分支/Context/模型/Worktree）
- ✅ 启用 TapTap Plugins（spec/sync/git/quality）
- ✅ 检测项目语言并配置 LSP 代码智能（自动安装 binary）
- 📎 可选：`--with-spec` 同步 Spec Skills 到 Cursor

### 飞书 MCP 配置（可选）

如果团队使用飞书文档 MCP：

```bash
/sync:mcp-feishu https://open.feishu.cn/mcp/stream/mcp_xxxxx
```

如果团队使用飞书项目 MCP：

```bash
/sync:mcp-feishu-project https://project.feishu.cn/mcp_server/v1?mcpKey=xxx&projectKey=yyy&userKey=zzz
```

**功能：**
- ✅ 同时配置到 Claude Code 和 Cursor
- ✅ 验证连接状态
- ✅ 避免重复配置

### Grafana MCP 配置（可选）

配置 Grafana MCP 以查询 Dashboard、Prometheus/Loki 数据源：

```bash
/sync:mcp-grafana <username> <password>
```

**功能：**
- ✅ 自动安装 Golang 和 mcp-grafana（如果未安装）
- ✅ 同时配置到 Claude Code 和 Cursor
- ✅ 详细的安装日志

**Cursor 用户**：如果没有配置 Claude Code，可以使用 `/sync-mcp-grafana` 命令（需先运行 `/sync:cursor` 同步命令模板）

## 使用场景

### 场景 1: 新成员加入团队

1. 克隆代码仓库
2. 运行 `/sync:basic` 一键配置环境
3. （可选）运行 `/sync:mcp-feishu <URL>` 配置飞书
4. 重启 IDE

**效果：**
- ✅ MCP 服务器配置完成，可以自动获取最新文档
- ✅ 自动更新机制启用（Marketplace autoUpdate），更新插件后无需手动重装
- ✅ Cursor IDE 配置同步，两个工具无缝切换
- ✅ LSP 代码智能自动配置（检测语言 → 安装 binary → 启用插件）

### 场景 2: 学习新框架

在对话中提到 GitHub 仓库或框架名称，context7 自动获取最新文档：

```
用户: 我想了解 Next.js 14 的 App Router 实现
AI: 💡 正在使用 context7 获取 Next.js 的最新文档...
    根据最新文档，App Router 是...
```

### 场景 3: 插件开发

更新插件 → 重启会话 → 自动更新机制生效（前提：已运行 `/sync:basic`）

**效果：**
- 🔧 **开发者**：无需手动 uninstall + install
- 📦 **团队成员**：git pull 后自动获取最新插件

## 高级用法

如果需要单独执行某个配置步骤：

### （可选）启用 git pre-commit：自动同步 git-flow snippets

当你修改 `plugins/git/skills/git-flow/snippets/` 并准备提交时，可启用本仓库的版本化 `pre-commit` hook，自动运行同步脚本并暂存同步产物，避免漏提交。

启用方式（一次性）：

```bash
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit
```

详细说明见：`.githooks/README.md`

### `/sync:mcp`

配置 context7 和 sequential-thinking MCP 服务器。

```bash
/sync:mcp
```

**功能：**
- 同步到 `~/.claude.json`（Claude Code 用户级配置）
- 同步到 `~/.cursor/mcp.json`（Cursor 用户级配置）
- 跳过已存在的配置，不覆盖用户自定义内容

**MCP 说明：**
- **context7**: 拉取最新的库文档和代码示例（AI 自动调用）
- **sequential-thinking**: 提供结构化问题解决（AI 自动调用）

### `/sync:hooks`

配置 SessionStart 钩子，启用自动更新（Marketplace autoUpdate）。

```bash
/sync:hooks
```

**功能：**
- 同步 plugin hooks 配置到项目级 `.claude/hooks/hooks.json`
- 启用 SessionStart 自动更新（autoUpdate）
- 智能合并现有 hooks 配置

**效果：**
- 会话启动时自动启用 marketplace 插件自动更新（autoUpdate）
- 会话启动时自动检测并尝试安装 `gh`/`glab`，并提示认证环境变量配置方式
- 支持本地插件开发和团队插件更新

**管理 hooks：**
- 禁用：删除 `.claude/hooks/hooks.json` 中的 SessionStart 配置
- 卸载：直接删除 `.claude/hooks/hooks.json` 文件

### `/sync:cursor`

同步配置到 Cursor IDE。

```bash
/sync:cursor
```

**功能：**
- 同步 Git Flow Rules 到 `.cursor/rules/git-flow.mdc`
- 同步 Spec Skills 规则到 `.cursor/rules/`（需 `/sync:basic --with-spec`）
  - `doc-auto-sync.mdc` - AI 改动模块代码时自动同步文档（alwaysApply: true）
  - `module-discovery.mdc` - 开发前必须读取模块索引定位目标（alwaysApply: true）
  - `generate-module-map.mdc` - 生成模块索引的 prompt（alwaysApply: false）
  - 已跳过：`implementing-from-task`、`merging-parallel-work`（测试中）
- 同步 Git Commands 到 `.cursor/commands/`
- 直接覆盖（每次重新生成最新内容）
- 自动删除旧的 `sync-claude-plugin.mdc` 文件

### `/sync:lsp`

检测项目语言并配置 LSP 代码智能。

```bash
/sync:lsp            # 检测 + 启用插件 + 安装 binary
/sync:lsp --check    # 查看 LSP 状态（已启用插件、binary 是否存在、版本）
/sync:lsp --install  # 强制重新安装所有已启用 LSP 的 binary
```

**功能：**
- 自动检测项目语言（Go / TypeScript / Python / Rust / Java / Kotlin / Swift / C++ / C# / PHP）
- 启用对应 LSP 插件到 `.claude/settings.json`
- 立即安装缺失的 LSP binary（不等下次 session）
- 输出安装状态和版本信息

**SessionStart Hook：**
- 团队成员启动 session 时，`ensure-lsp.sh` 自动检查并安装缺失的 LSP binary
- 日志位置：`~/.claude/plugins/logs/ensure-lsp-*.log`

## 自动触发 Skills

插件包含两个自动触发的 skills，无需手动调用：

### `context7`

当检测到 GitHub URL 或询问开源库时，自动使用 context7 MCP 获取最新文档。

**触发条件：**
- 消息包含 GitHub URL（`github.com`）
- 询问特定框架/库的使用方法
- 需要最新版本的 API 参考

**行为：**
- 自动检测需求
- 告知用户正在使用 context7（透明提示）
- 基于最新文档提供准确回答

**详细文档：**
- [context7 使用指南](skills/context7/context7-usage.md)

### `mcp-feishu`

当用户提供飞书文档 MCP URL 并请求配置时触发，自动同时配置到 Claude Code 和 Cursor。

### `mcp-feishu-project`

当用户提供飞书项目 MCP URL 或请求配置飞书项目 MCP 时触发，自动同时配置到 Claude Code 和 Cursor。支持查询项目任务、工作项、需求等。

## Commands 列表

| 命令 | 说明 | 推荐度 |
|------|------|--------|
| `/sync:basic` | 一键配置开发环境 | ⭐ 推荐 |
| `/sync:mcp-feishu <URL>` | 配置飞书文档 MCP | 可选 |
| `/sync:mcp-feishu-project <URL>` | 配置飞书项目 MCP | 可选 |
| `/sync:mcp-grafana <user> <pass>` | 配置 Grafana MCP（自动安装依赖） | 可选 |
| `/sync:lsp` | 检测语言并配置 LSP 代码智能 | 高级 |
| `/sync:mcp` | 仅配置 MCP 服务器 | 高级 |
| `/sync:hooks` | 仅配置自动更新钩子（autoUpdate） | 高级 |
| `/sync:cursor` | 仅同步到 Cursor | 高级 |
| `/sync:statusline` | 配置 Status Line（状态栏） | 高级 |
| `/sync:git-cli-auth` | 检测并配置 gh/glab 认证 | 高级 |

**Cursor 专用命令**（通过 `/sync:cursor` 同步到项目）：

| 命令 | 说明 |
|------|------|
| `/sync-mcp-grafana <user> <pass>` | 配置 Grafana MCP 到 Cursor |

## MCP 懒加载配置

当配置了多个 MCP 服务器时，所有工具描述会占用大量 context。Claude Code 支持懒加载配置，超过阈值时延迟加载 MCP 工具描述。

### 配置方法

在 `~/.claude/settings.json` 或项目级 `.claude/settings.json` 中添加：

```json
{
  "env": {
    "ENABLE_TOOL_SEARCH": "auto:1"
  }
}
```

### 参数说明

| 值 | 行为 |
|---|---|
| `auto` | 默认值，超过 10% context 时延迟加载 |
| `auto:1` | 超过 1% context 时延迟加载（推荐） |
| `auto:N` | 超过 N% context 时延迟加载 |
| `true` | 始终启用工具搜索 |
| `false` | 禁用，所有 MCP 工具预加载 |

### 工作原理

1. 会话启动时计算 MCP 工具描述占 context 的百分比
2. 超过阈值时，工具描述不预加载
3. 需要使用时通过 MCPSearch 工具按需发现

### 验证

1. 配置后重启 Claude Code
2. 配置多个 MCP 后观察是否有工具被延迟加载
3. 使用 MCP 工具时会先通过 MCPSearch 发现

## 配置文件位置

### Claude Code
- `~/.claude.json` - MCP 配置（context7 + sequential-thinking + 飞书/Grafana，用户级）
- `.claude/hooks/hooks.json` - Hooks 配置（项目级）
- `~/.claude/settings.json` - 用户级配置（MCP 懒加载等）

### Cursor
- `~/.cursor/mcp.json` - MCP 配置（context7 + sequential-thinking + 飞书/Grafana，全局）
- `.cursor/rules/git-flow.mdc` - Git 工作流规范
- `.cursor/rules/doc-auto-sync.mdc` - 模块文档自动同步规则（--with-spec）
- `.cursor/rules/module-discovery.mdc` - 模块发现规则（--with-spec）
- `.cursor/rules/generate-module-map.mdc` - 模块索引生成 prompt（--with-spec）
- `.cursor/commands/git-*.md` - Git 命令
- `.cursor/commands/sync-mcp-grafana.md` - Grafana MCP 配置命令
- `~/.claude/scripts/statusline.sh` - Status Line 脚本

### LSP 代码智能
- `.claude/settings.json` - LSP 插件启用配置（`enabledPlugins` 中 `*-lsp@claude-plugins-official`）
- `~/.claude/plugins/logs/ensure-lsp-*.log` - LSP binary 安装日志
- 支持语言：Go / TypeScript(JS) / Python / Rust / Java / Kotlin / Swift / C(C++) / C# / PHP

### Golang & mcp-grafana（由 `/sync:mcp-grafana` 安装）
- `~/go-sdk/current/` - Golang 安装目录
- `~/go/bin/mcp-grafana` - mcp-grafana 二进制
- `~/.claude/plugins/logs/ensure-golang-*.log` - 安装日志

## 配置模板

插件提供了标准的 MCP 配置模板，位于 `skills/mcp-templates/` 目录：

- `context7.json` - context7 MCP 配置
- `sequential-thinking.json` - sequential-thinking MCP 配置

这些模板会被 `/sync:mcp` 和 `/sync:basic` 命令使用，确保团队成员使用统一的配置格式。

## 自动更新机制（Marketplace autoUpdate）

### 工作原理

配置 SessionStart hook 后：

1. **会话启动时**：自动执行 `set-auto-update-plugins.sh`
2. **脚本行为**：
   - 自动启用 marketplace `taptap-plugins` 的 `autoUpdate=true`
   - 写入位置：`~/.claude/plugins/known_marketplaces.json`
3. **效果**：后续插件更新将由 Claude 的 marketplace 自动更新机制接管（无需手动配置）
4. **额外行为**：执行 `ensure-cli-tools.sh`（macOS/Linux）检测 `gh`/`glab` 状态并提示认证配置

### 脚本位置

- 自动更新脚本：`.claude/hooks/scripts/set-auto-update-plugins.sh`
- CLI 工具检测：`.claude/hooks/scripts/ensure-cli-tools.sh`
- Hook 配置：`.claude/hooks/hooks.json`

### 自动发现插件

脚本会自动发现所有本地插件，无需手动维护插件列表：
- ✅ 新增插件自动生效
- ✅ 删除插件自动清理
- ✅ 无需手动更新配置

## 相关文档

- [context7 使用指南](skills/context7/context7-usage.md)
- [飞书 MCP 配置指南](skills/mcp-feishu/mcp-http-configuration.md)
- [Plugin 开发指南](../../docs/plugin-guidelines.md)
- [Skill 编写指南](../../docs/skill-guidelines.md)

## 版本历史

- **v0.1.17** - skills-sync 新增 review-rules 模板同步（不覆盖项目已有规则）
- **v0.1.16** - review-checklist 不覆盖项目自定义版本；修正覆盖策略文档；修复 4 个 hook 脚本缺少可执行权限；Cursor 模板新增 Pipeline Watch
- **v0.1.15** - 新增 `/sync:lsp` 命令（检测语言+安装 binary+启用插件）；`/sync:basic` LSP 首次即装不再延迟；Cursor 模板新增 code review 步骤（含 --skip-code-review）；修复 MR 模板覆盖问题（原子 bash）；hooks 新增 LSP 脚本；更新 statusline/ensure-golang
- **v0.1.14** - 修复 10 个命令文件 allowed-tools 缺失问题；补齐 printenv、head、pwd、cp、ls、sort、tail、echo、wc、claude、bash、mv、tr 等命令权限声明；cursor-templates 同步修复
- **v0.1.13** - 镜像 git 插件 no-ticket 按需配置改动到 cursor-templates；Cursor 命令模板新增 `GIT_ALLOW_NO_TICKET` 环境变量上下文；git-flow.mdc 新增仓库级配置段；更新 snippets（02-extract-task-id.md、03-commit-format.md）匹配 git 插件规则
- **v0.1.12** - 重构 `/sync:basic` 为并行 agent 架构（Phase 0 路径解析 + 6 个命名 subagent）；命令执行行数从 ~550 精简至 ~150（Phase 0: ≤2 Bash 调用）；新增 4 个辅助脚本（ensure-mcp.sh、ensure-plugins.sh、ensure-statusline.sh、ensure-tool-search.sh）；新增 agents/ 目录包含 6 个专用 subagent；更新 hooks、mcp-feishu、mcp-feishu-project、mcp-grafana 命令的错误处理和路径解析；更新 hooks.json 配置结构；更新 mcp-feishu 和 mcp-feishu-project skill 定义
- **v0.1.11** - MCP 配置（context7 + sequential-thinking）改为写入用户级文件（`~/.claude.json` + `~/.cursor/mcp.json`），跨项目复用；新增 `/sync:statusline` 命令（配置状态栏：项目/分支/Context/模型/Worktree）；`/sync:basic` 新增 Status Line 配置阶段、TapTap Plugins 自动启用、MCP 懒加载配置；Spec Skills 改为 `--with-spec` 可选参数；ensure-cli-tools 改为后台静默运行；新增 MCP 懒加载配置文档；清理 statusline.sh debug 输出
- **v0.1.10** - 新增 `/sync:mcp-feishu-project` 命令，配置飞书项目 MCP（project.feishu.cn）；新增 `mcp-feishu-project` skill 自动触发
- **v0.1.9** - 新增 `/sync:mcp-grafana` 命令（自动安装 Golang 和 mcp-grafana）；新增 `--dev` 开发模式参数；新增 Claude Skills 同步（`grafana-dashboard-design`）；新增 Cursor 命令 `sync-mcp-grafana.md`
- **v0.1.8** - 重构 Spec Skills 同步：删除单一索引文件 `sync-claude-plugin.mdc`，改为独立 `.mdc` 规则文件（`doc-auto-sync.mdc`、`module-discovery.mdc`、`generate-module-map.mdc`）；过滤测试中的 skills
- **v0.1.6** - 重构 hooks 架构为项目相对路径；新增自动更新脚本 (`set-auto-update-plugins.sh`)；新增 git-flow snippets 自动同步脚本和 pre-commit hook；移除 Windows 支持；脚本日志增强
- **v0.1.5** - `/sync:basic` 增加 GitLab MR 默认模板同步；SessionStart hooks 增加 gh/glab 检测脚本；新增 `/sync:git-cli-auth`
- **v0.1.4** - 新增 Claude Plugin Skills 索引同步（`sync-claude-plugin.mdc`）
- **v0.1.3** - 新增 Cursor 模板直接复制方式
- **v0.1.0** - 命令简化、自动发现插件
- **v0.0.1** - 初始版本
