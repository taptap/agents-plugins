---
allowed-tools: Read, Bash(echo:*), Bash(test:*), Bash(ls:*), Bash(pwd:*), Bash(sort:*), Bash(tail:*), Bash(command:*), Task
description: 一键配置开发环境（MCP + Hooks + MR 模板 + Claude Skills + Status Line）
---

## Context

此命令会完成 Claude Code 侧的基础环境配置：

1. 配置 `context7` MCP
2. 配置 SessionStart hooks
3. 同步 GitLab Merge Request 默认模板
4. 同步项目级 Claude Skills 模板
5. 配置 Status Line
6. 检测语言并启用 LSP 插件

## Your Task

### Phase 0：准备工作

**步骤 0.1：检查参数**

- `--dev`：设置 `USE_CACHE_FIRST=true`，优先使用 cache 路径
- 默认：`USE_CACHE_FIRST=false`

**步骤 0.2：解析路径**

在一条 Bash 命令中输出以下键值：

- `PROJECT_ROOT`
- `GIT_CHECK`
- `LATEST_VERSION`
- `SCRIPTS_DIR`
- `MCP_TEMPLATES_DIR`
- `MR_TEMPLATE_DIR`
- `SKILLS_DIR`

查找规则：

- marketplace 路径：`~/.claude/plugins/marketplaces/taptap-plugins/plugins/sync`
- cache 路径：`~/.claude/plugins/cache/taptap-plugins/sync/<latest>/`
- 默认模式优先 marketplace，`--dev` 模式优先 cache

确定 `BASE` 后，各变量的子目录映射：

- `SCRIPTS_DIR` = `{BASE}/scripts`
- `MCP_TEMPLATES_DIR` = `{BASE}/skills/mcp-templates`
- `MR_TEMPLATE_DIR` = `{BASE}/skills/merge-request-templates`
- `SKILLS_DIR` = `{BASE}/skills`

如果 `GIT_CHECK=FAIL`，立即停止并提示用户在项目根目录执行。

**步骤 0.3：检测项目语言**

如果 `SCRIPTS_DIR` 可用，执行：

```bash
bash {SCRIPTS_DIR}/detect-lsp.sh "$(pwd)"
```

提取 `DETECTED_LSP` 的值，供 Phase 2 使用。

### Phase 1：并行执行 5 个命名 Subagent

将 `none` 替换为 `无`，并在单条消息中同时发出以下 5 个 Task 调用：

| # | subagent_type | model | prompt 内容 |
|---|--------------|-------|------------|
| 1 | `sync:mcp-config` | haiku | `MCP_TEMPLATES_DIR={值}` |
| 2 | `sync:hooks-config` | haiku | `PROJECT_ROOT={值}`<br>`SCRIPTS_DIR={值}` |
| 3 | `sync:mr-template` | haiku | `PROJECT_ROOT={值}`<br>`MR_TEMPLATE_DIR={值}` |
| 4 | `sync:skills-sync` | haiku | `PROJECT_ROOT={值}`<br>`SKILLS_DIR={值}` |
| 5 | `sync:statusline-config` | haiku | `SCRIPTS_DIR={值}` |

### Phase 2：汇总结果并处理 LSP

等待所有 5 个 Task 返回结果后：

1. 汇总每个步骤的成功/失败状态
2. 如果 `DETECTED_LSP != none`：
   - 读取项目 `.claude/settings.json`
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
  [✅/❌/⏭️] LSP 代码智能

建议：
  - MCP 配置：`/sync:mcp`
  - 自动更新钩子：`/sync:hooks`
  - Status Line：`/sync:statusline`
  - LSP：`/sync:lsp --check`
```
