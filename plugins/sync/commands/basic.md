---
allowed-tools: Read, Bash(echo:*), Bash(test:*), Bash(ls:*), Bash(pwd:*), Bash(sort:*), Bash(tail:*), Bash(command:*), Task
description: 一键配置开发环境（MCP + Hooks + MR 模板 + Claude Skills + Status Line）
---

## Context

此命令会完成 Claude Code 侧的基础环境配置，并补充 Codex remote marketplace 自愈与插件配置：

1. 配置 `context7` MCP
2. 配置 SessionStart hooks
3. 同步 GitLab Merge Request 默认模板
4. 同步项目级 Claude Skills 模板
5. 配置 Status Line
6. 配置 Codex 插件
7. 检测语言并启用 LSP 插件

重跑 `/sync:basic` 时，必须把当前 sync 源目录里的 project hooks scripts 重新覆盖到项目内。
不要因为目标文件已存在而跳过，尤其 `.codex/hooks/scripts/ensure-codex-plugins.sh` 必须用当前版本刷新，这样 zeus 这类下游仓库才能拿到最新的 marketplace 自愈逻辑。

## Your Task

### Phase 0：准备工作

**步骤 0.1：检查参数**

- `--dev`：设置 `USE_CACHE_FIRST=true`，优先使用 cache 路径
- 默认：`USE_CACHE_FIRST=false`

**步骤 0.2：解析路径**

在一条 Bash 命令中输出以下键值：

- `PROJECT_ROOT`
- `GIT_CHECK`
- `BASE_SOURCE`
- `LATEST_VERSION`
- `SCRIPTS_DIR`
- `MCP_TEMPLATES_DIR`
- `MR_TEMPLATE_DIR`
- `SKILLS_DIR`

查找规则：

1. **先检查 `${CLAUDE_PLUGIN_ROOT}`**
   - 如果 `${CLAUDE_PLUGIN_ROOT}` 已设置，且 `${CLAUDE_PLUGIN_ROOT}/scripts` 存在：
     - 设置 `BASE=${CLAUDE_PLUGIN_ROOT}`
     - 记为 `BASE_SOURCE=plugin_root`
   - 这是 Claude 官方提供的 plugin 根目录变量，适用于 marketplace、cache 和 `--plugin-dir` 加载的 inline 插件
   - 不要依赖用户个人 shell 配置、别名函数、固定 repo 路径或特定 rc 文件
2. marketplace 路径：`~/.claude/plugins/marketplaces/taptap-plugins/plugins/sync`
3. cache 路径：`~/.claude/plugins/cache/taptap-plugins/sync/<latest>/`

优先级规则：
- 默认模式：`plugin_root > marketplace > cache`
- `--dev` 模式：`plugin_root > cache > marketplace`

确定 `BASE` 后，各变量的子目录映射：

- `SCRIPTS_DIR` = `{BASE}/scripts`
- `MCP_TEMPLATES_DIR` = `{BASE}/skills/mcp-templates`
- `MR_TEMPLATE_DIR` = `{BASE}/skills/merge-request-templates`
- `SKILLS_DIR` = `{BASE}/skills`

如果 `GIT_CHECK=FAIL`，立即停止并提示用户在项目根目录执行。

如果 `BASE_SOURCE=plugin_root`，请在后续汇总里明确说明本次使用的是当前会话的 sync plugin 源目录，而不是额外猜测用户机器上的安装路径。

**步骤 0.3：检测项目语言**

如果 `SCRIPTS_DIR` 可用，执行：

```bash
bash {SCRIPTS_DIR}/detect-lsp.sh "$(pwd)"
```

提取 `DETECTED_LSP` 的值，供 Phase 2 使用。

### Phase 1：并行执行 6 个命名 Subagent

将 `none` 替换为 `无`，并在单条消息中同时发出以下 6 个 Task 调用：

| # | subagent_type | model | prompt 内容 |
|---|--------------|-------|------------|
| 1 | `sync:mcp-config` | haiku | `MCP_TEMPLATES_DIR={值}` |
| 2 | `sync:hooks-config` | haiku | `PROJECT_ROOT={值}`<br>`SCRIPTS_DIR={值}` |
| 3 | `sync:mr-template` | haiku | `PROJECT_ROOT={值}`<br>`MR_TEMPLATE_DIR={值}` |
| 4 | `sync:skills-sync` | haiku | `PROJECT_ROOT={值}`<br>`SKILLS_DIR={值}` |
| 5 | `sync:statusline-config` | haiku | `SCRIPTS_DIR={值}` |
| 6 | `sync:codex-plugins-config` | haiku | `PROJECT_ROOT={值}`<br>`SCRIPTS_DIR={值}` |

额外要求：
- `sync:hooks-config` 和 `sync:codex-plugins-config` 都必须把当前 `SCRIPTS_DIR` 下的脚本覆盖复制到项目目录，不能因为目标文件已存在而跳过
- 特别是 `.codex/hooks/scripts/ensure-codex-plugins.sh`，必须确保内容升级到当前源目录版本

### Phase 2：汇总结果并处理 LSP

等待所有 6 个 Task 返回结果后：

1. 汇总每个步骤的成功/失败状态
2. 如果 `DETECTED_LSP != none`：
   - 读取项目 `.claude/settings.json`
   - 如果 `extraKnownMarketplaces.taptap-plugins.source.repo` 存在且值为旧官方仓库 `taptap/claude-plugins-marketplace`，迁移为 `taptap/agents-plugins`
   - 如果该 `repo` 已是其他非空值（例如用户 fork），保留不动
   - 将检测到的 LSP 插件加入 `enabledPlugins`
   - 立即安装缺失 binary
3. 输出最终报告

#### LSP 安装规则

- `gopls-lsp` → `command -v gopls || go install golang.org/x/tools/gopls@latest`
- `typescript-lsp` → `command -v typescript-language-server || npm install -g typescript-language-server typescript`
- `pyright-lsp` → `command -v pyright-langserver || npm install -g pyright`
- `rust-analyzer-lsp` → `command -v rust-analyzer || rustup component add rust-analyzer`
- `jdtls-lsp` → 提示手动安装
- `kotlin-lsp` → `command -v kotlin-language-server || brew install kotlin-language-server`
- `swift-lsp` → 提示安装 Xcode
- `clangd-lsp` → `command -v clangd || brew install llvm`
- `csharp-lsp` → `command -v csharp-ls || dotnet tool install -g csharp-ls`
- `php-lsp` → `command -v intelephense || npm install -g intelephense`

## 输出要求

### 全部成功

```text
✅ 开发环境配置完成！

执行结果：
  ✅ MCP 配置
  ✅ 自动更新钩子
  ✅ GitLab MR 模板
  ✅ Claude Skills 同步
  ✅ Status Line 配置
  ✅ Codex 插件配置
  [✅/⏭️] LSP 代码智能

下一步：
  1. 重启 Claude Code 会话
  2. 如有新增 LSP，等待第一次 SessionStart 自动补齐缺失 binary
```

### 部分失败

```text
⚠️ 开发环境配置部分完成

执行结果：
  [✅/❌/⏭️] MCP 配置
  [✅/❌/⏭️] 自动更新钩子
  [✅/❌/⏭️] GitLab MR 模板
  [✅/❌/⏭️] Claude Skills 同步
  [✅/❌/⏭️] Status Line 配置
  [✅/❌/⏭️] Codex 插件配置
  [✅/❌/⏭️] LSP 代码智能

建议：
  - MCP 配置：`/sync:mcp`
  - 自动更新钩子：`/sync:hooks`
  - Status Line：`/sync:statusline`
  - LSP：`/sync:lsp --check`
```
