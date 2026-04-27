[English](./README.en.md) | 中文

# TapTap Agents Plugins

TapTap 团队维护的插件库，面向 AI 开发工具提供工作流自动化能力。

## 团队配置

对于团队项目，可以在项目根目录配置 `.claude/settings.json`，Claude Code 会自动安装插件，无需手动执行安装命令。

### 1. 配置 settings

在项目根目录执行以下命令：

```bash
mkdir -p .claude && echo '{
  "extraKnownMarketplaces": {
    "taptap-plugins": {
      "source": {
        "source": "github",
        "repo": "taptap/agents-plugins"
      }
    }
  },
  "enabledPlugins": {
    "spec@taptap-plugins": true,
    "sync@taptap-plugins": true,
    "git@taptap-plugins": true
  }
}' > .claude/settings.json
```

**可选：按仓库配置 Git 插件行为**

在 `.claude/settings.json` 的 `env` 字段中可配置 Git 插件行为：

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `GIT_ALLOW_NO_TICKET` | `"true"` | 是否允许 no-ticket 提交，设为 `"false"` 可禁用 |

示例（禁用 no-ticket，要求必须提供任务 ID）：

```json
{
  "env": {
    "GIT_ALLOW_NO_TICKET": "false"
  },
  "enabledPlugins": { ... }
}
```

### 2. 执行 /sync

一键配置 MCP、自动更新和开发环境模板：

```bash
# 在 Claude Code 中执行
/sync:basic

# 配置完成后，重启 Claude Code 即可使用
```

**包含功能：**

- ✅ 配置 context7 MCP（自动获取最新文档）
- ✅ 启用插件自动重载 + CLI 工具检测（修改后重启会话即可生效）
- ✅ 同步 GitLab Merge Request 默认模板
- ✅ 支持 GitHub Pull Request 模板

### 3. 验证安装

```bash
# 查看已安装插件
/plugin

# 查看可用命令
/help
```

## 插件列表


| 插件      | 版本    | 描述                                                                |
| ------- | ----- | ----------------------------------------------------------------- |
| spec    | 0.1.8 | Spec-Driven Development 工作流插件                                     |
| git     | 0.1.16 | Git 工作流自动化插件（提交/推送/MR + 自动代码审查 + 远程平台操作）            |
| sync    | 0.1.30 | 开发环境配置同步插件（MCP + LSP + Hooks + Claude Skills） |
| test    | 0.0.7 | QA 工作流插件（需求澄清/测试用例生成/变更分析/需求回溯/代码级测试生成） |


详细说明请查看各插件目录下的 README.md。

**版本历史**：查看 [CHANGELOG.md](./CHANGELOG.md) 了解各版本更新内容。

## 日常使用

### Git 工作流（推荐）

适用于需要创建 MR 的开发场景：

```bash
# 1. 提供任务链接，自动创建分支、提交、推送并创建 MR
/git:commit-push-pr https://xindong.atlassian.net/browse/TAP-12345

# 或提供飞书任务链接
/git:commit-push-pr https://project.feishu.cn/pojq34/story/detail/12345
```

**命令执行流程：**

- 自动从任务链接提取 Task ID
- **智能判断分支前缀**：分析 `git diff` 内容自动选择合适的前缀
  - `docs/`：仅修改文档文件
  - `test/`：仅修改测试文件
  - `fix/`：包含 bug 修复关键词
  - `feat/`：新增功能或文件
  - `refactor/`：代码重构
  - `perf/`：性能优化
  - `chore/`：配置或维护任务
- 如果在 main/master 分支，会询问分支描述并创建功能分支（如 `feat/TAP-12345-description`）
- 分析代码变更，生成符合规范的提交信息
- 推送代码并自动创建 Merge Request / Pull Request

**平台支持：**


| 平台     | CLI 工具 | 模板路径                                         |
| ------ | ------ | -------------------------------------------- |
| GitLab | `glab` | `.gitlab/merge_request_templates/default.md` |
| GitHub | `gh`   | `.github/PULL_REQUEST_TEMPLATE.md`           |


> 💡 命令会自动检测仓库类型和可用的 CLI 工具，选择合适的方式创建 MR/PR。

**CLI 工具配置：** 使用 `/sync:git-cli-auth` 命令检测和配置认证

```bash
# 配置 git cli Token
/sync:git-cli-auth

# 或使用原始命令
gh auth login        # GitHub
glab auth login      # GitLab
```

### 快速提交与推送

Git 插件提供三种提交方式，根据需求选择：

**1. 仅提交（本地开发）**

```bash
# 适用于：还需要多次提交，暂不推送
/git:commit
```

**2. 提交并推送（备份到远程）**

```bash
# 适用于：功能完成，需要备份到远程，但不创建 MR
/git:commit-push
```

**3. 提交、推送并创建 MR（完整流程）**

```bash
# 适用于：功能完成，立即创建合并请求
/git:commit-push-pr https://xindong.atlassian.net/browse/TAP-12345
```

**说明**：

- 所有命令都会自动从分支名提取 Task ID
- 在 main/master 分支会自动创建功能分支
- `/git:commit-push-pr` 支持智能分支前缀判断

### Spec 驱动开发

> ⚠️ **警告**：此功能正在开发中，暂不推荐使用

从需求文档生成技术方案并执行开发：

```bash
# 根据任务需求生成完整的技术方案和执行计划
/spec https://xindong.atlassian.net/browse/TAP-12345
```

#### 模块发现（module-discovery）

AI 仅在采用模块索引协作机制的项目中按需读取模块索引，快速了解项目结构：


| 路径                                    | 说明                                   |
| ------------------------------------- | ------------------------------------ |
| `tap-agents/tap-agents-configs.md`    | 项目配置文件（项目类型、项目名称、业务模块目录、主要类后缀、文件扩展名） |
| `tap-agents/prompts/module-map.md`    | 模块索引（P0/P1/P2 优先级分类 + 关键词定位表）        |
| `tap-agents/prompts/modules/[模块名].md` | 各模块详细文档                              |


**工作流程：**

1. 先判断仓库是否真的使用 `tap-agents` 模块索引体系，且团队是否将其作为模块定位入口
2. 仅在相关模块定位任务中检查 `module-map.md` 是否存在
3. 如不存在且用户明确要启用该体系，再询问是否生成
4. 读取模块索引，利用关键词快速定位代码

#### 文档自动同步（doc-auto-sync）

AI 修改代码时**自动维护**模块文档：


| 触发场景 | AI 行为                                      |
| ---- | ------------------------------------------ |
| 新增模块 | 创建 `modules/[模块名].md` + 更新 `module-map.md` |
| 修改模块 | 检查并更新对应文档                                  |
| 文档缺失 | 自动创建文档（强制执行）                               |
| 文档过期 | 信任代码，自动更新文档                                |


**配置项（在 `tap-agents/tap-agents-configs.md` 中定义）：**

- `「项目类型」`：iOS / Android / Web / Backend 等
- `「项目名称」`：项目名称
- `「业务模块目录」`：主要业务代码目录（如 `TapTap`、`src/modules`）
- `「主要类后缀」`：识别主要类的后缀（如 `ViewController`、`Service`）
- `「文件扩展名」`：代码文件扩展名（如 `.swift`、`.kt`、`.go`）

### 代码审查

使用 Git 插件内置的审查能力检查本地变更或 MR：

```bash
# 审查当前工作区/分支改动
/git:code-reviewing

# 审查特定 Merge Request / Pull Request
/git:code-reviewing https://gitlab.example.com/group/project/-/merge_requests/123

# 审查特定提交或分支
/git:code-reviewing HEAD~1
```

**功能亮点：**

- **双引擎审查**：Claude Agent Team + Codex 双视角交叉验证
- **本地/MR 双模式**：支持未提交变更、提交、分支和 MR/PR URL
- **项目规则接入**：自动读取 review checklist 和 review rules
- **风险优先输出**：先给阻塞问题，再给剩余风险和验证缺口

### 开发环境同步

```bash
# 一键配置开发环境（推荐新成员使用）
/sync:basic

# 或单独执行各项配置
/sync:mcp            # 配置 context7 MCP
/sync:hooks          # 启用插件自动重载

# 配置飞书文档 MCP（可选）
/sync:mcp-feishu https://open.feishu.cn/mcp/stream/mcp_xxxxx

# 配置飞书项目 MCP（可选）
/sync:mcp-feishu-project https://project.feishu.cn/mcp_server/v1?mcpKey=xxx&projectKey=yyy&userKey=zzz

# 配置 Grafana MCP（可选，自动安装 Golang 和 mcp-grafana）
/sync:mcp-grafana <username> <password>
```

**功能说明：**

- **MCP 服务器**：自动获取 GitHub 库的最新文档（context7）
- **自动重载**：修改插件后重启会话自动生效，无需手动重装

## 更新插件

```bash
# 更新指定插件
/plugin update spec@taptap-plugins

# 或重新安装
/plugin uninstall spec@taptap-plugins
/plugin install spec@taptap-plugins
```

## 问题反馈

请在 [GitHub Issues](https://github.com/taptap/agents-plugins/issues) 提交问题。
