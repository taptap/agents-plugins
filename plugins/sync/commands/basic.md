---
allowed-tools: Read, Bash(echo:*), Bash(test:*), Bash(ls:*), Bash(pwd:*), Bash(sort:*), Bash(tail:*), Task
description: 一键配置开发环境（MCP + Hooks + Cursor 同步）
---

## Context

此命令会一次性完成开发环境的基础配置，包括：
1. 配置 MCP 服务器（context7 + sequential-thinking）
2. 配置自动更新钩子（SessionStart hook）
3. 同步配置到 Cursor IDE
4. 同步 GitLab MR 模板
5. 同步 Claude Skills
6. 配置 Status Line

**架构**：Phase 0 用 1-2 条合并 Bash 解析所有路径，Phase 1 用 6 个命名 subagent 并行执行，Phase 2 汇总报告。

## Your Task

### Phase 0：准备工作（主 agent，目标 ≤ 2 个 Bash 调用）

**步骤 0.1：检查参数**

检查用户是否传入了参数：
- `--dev`：设置 `USE_CACHE_FIRST=true`（优先使用 cache 路径）
- `--with-spec`：设置 `SYNC_SPEC=true`（执行 Spec Skills 同步）
- 默认：`USE_CACHE_FIRST=false`，`SYNC_SPEC=false`

**步骤 0.2：执行合并路径解析命令**

根据参数选择对应的命令（二选一），在单条 Bash 中完成所有路径解析。

**默认模式**（`USE_CACHE_FIRST=false`，marketplace 优先）：

```bash
echo "PROJECT_ROOT=$(pwd)" && \
(test -d .git -o -f .gitignore && echo "GIT_CHECK=OK" || echo "GIT_CHECK=FAIL") && \
LATEST=$(ls -d ~/.claude/plugins/cache/taptap-plugins/sync/*/ 2>/dev/null | sort -V | tail -1) && \
echo "LATEST_VERSION=${LATEST}" && \
MP=~/.claude/plugins/marketplaces/taptap-plugins/plugins/sync && \
(test -d "${MP}/scripts" && echo "SCRIPTS_DIR=${MP}/scripts" || (test -n "${LATEST}" && test -d "${LATEST}scripts" && echo "SCRIPTS_DIR=${LATEST}scripts" || echo "SCRIPTS_DIR=none")) && \
(test -d "${MP}/skills/mcp-templates" && echo "MCP_TEMPLATES_DIR=${MP}/skills/mcp-templates" || (test -n "${LATEST}" && test -d "${LATEST}skills/mcp-templates" && echo "MCP_TEMPLATES_DIR=${LATEST}skills/mcp-templates" || echo "MCP_TEMPLATES_DIR=none")) && \
(test -d "${MP}/skills/cursor-templates" && echo "CURSOR_TEMPLATE_DIR=${MP}/skills/cursor-templates" || (test -n "${LATEST}" && test -d "${LATEST}skills/cursor-templates" && echo "CURSOR_TEMPLATE_DIR=${LATEST}skills/cursor-templates" || echo "CURSOR_TEMPLATE_DIR=none")) && \
(test -d "${MP}/skills/merge-request-templates" && echo "MR_TEMPLATE_DIR=${MP}/skills/merge-request-templates" || (test -n "${LATEST}" && test -d "${LATEST}skills/merge-request-templates" && echo "MR_TEMPLATE_DIR=${LATEST}skills/merge-request-templates" || echo "MR_TEMPLATE_DIR=none")) && \
(test -d "${MP}/skills" && echo "SKILLS_DIR=${MP}/skills" || (test -n "${LATEST}" && test -d "${LATEST}skills" && echo "SKILLS_DIR=${LATEST}skills" || echo "SKILLS_DIR=none"))
```

**开发模式**（`USE_CACHE_FIRST=true`，`--dev` 参数，cache 优先）：

```bash
echo "PROJECT_ROOT=$(pwd)" && \
(test -d .git -o -f .gitignore && echo "GIT_CHECK=OK" || echo "GIT_CHECK=FAIL") && \
LATEST=$(ls -d ~/.claude/plugins/cache/taptap-plugins/sync/*/ 2>/dev/null | sort -V | tail -1) && \
echo "LATEST_VERSION=${LATEST}" && \
MP=~/.claude/plugins/marketplaces/taptap-plugins/plugins/sync && \
(test -n "${LATEST}" && test -d "${LATEST}scripts" && echo "SCRIPTS_DIR=${LATEST}scripts" || (test -d "${MP}/scripts" && echo "SCRIPTS_DIR=${MP}/scripts" || echo "SCRIPTS_DIR=none")) && \
(test -n "${LATEST}" && test -d "${LATEST}skills/mcp-templates" && echo "MCP_TEMPLATES_DIR=${LATEST}skills/mcp-templates" || (test -d "${MP}/skills/mcp-templates" && echo "MCP_TEMPLATES_DIR=${MP}/skills/mcp-templates" || echo "MCP_TEMPLATES_DIR=none")) && \
(test -n "${LATEST}" && test -d "${LATEST}skills/cursor-templates" && echo "CURSOR_TEMPLATE_DIR=${LATEST}skills/cursor-templates" || (test -d "${MP}/skills/cursor-templates" && echo "CURSOR_TEMPLATE_DIR=${MP}/skills/cursor-templates" || echo "CURSOR_TEMPLATE_DIR=none")) && \
(test -n "${LATEST}" && test -d "${LATEST}skills/merge-request-templates" && echo "MR_TEMPLATE_DIR=${LATEST}skills/merge-request-templates" || (test -d "${MP}/skills/merge-request-templates" && echo "MR_TEMPLATE_DIR=${MP}/skills/merge-request-templates" || echo "MR_TEMPLATE_DIR=none")) && \
(test -n "${LATEST}" && test -d "${LATEST}skills" && echo "SKILLS_DIR=${LATEST}skills" || (test -d "${MP}/skills" && echo "SKILLS_DIR=${MP}/skills" || echo "SKILLS_DIR=none"))
```

**如果 `GIT_CHECK=FAIL`**：立即停止，提示用户在项目根目录执行。

**步骤 0.3：（仅 `--with-spec` 时）解析 Spec 路径**

追加一条 Bash 命令解析 spec 的 skills 路径：

```bash
MP_SPEC=~/.claude/plugins/marketplaces/taptap-plugins/plugins/spec && \
LATEST_SPEC=$(ls -d ~/.claude/plugins/cache/taptap-plugins/spec/*/ 2>/dev/null | sort -V | tail -1) && \
(test -d "${MP_SPEC}/skills" && echo "SPEC_SKILLS_DIR=${MP_SPEC}/skills" || (test -n "${LATEST_SPEC}" && test -d "${LATEST_SPEC}skills" && echo "SPEC_SKILLS_DIR=${LATEST_SPEC}skills" || echo "SPEC_SKILLS_DIR=none"))
```

如果 `USE_CACHE_FIRST=true`，反转优先级（先查 cache 再查 marketplace）。

如果 `SYNC_SPEC=false`，跳过此步骤，`SPEC_SKILLS_DIR=无`。

**步骤 0.4：检测项目语言，输出 LSP 插件列表**

执行语言检测脚本（需要 `SCRIPTS_DIR` 已解析）：

```bash
bash {SCRIPTS_DIR}/detect-lsp.sh "$(pwd)"
```

输出格式：`DETECTED_LSP=gopls-lsp@claude-plugins-official,typescript-lsp@claude-plugins-official` 或 `DETECTED_LSP=none`。

提取 `DETECTED_LSP` 的值，供 Phase 2 使用。

---

### Phase 1：并行执行 6 个命名 Subagent

从 Phase 0 输出中提取 `KEY=VALUE` 值，将 `none` 替换为 `无`，然后**在单条消息中同时发出所有 6 个 Task 调用**。

| # | subagent_type | model | prompt 内容 |
|---|--------------|-------|------------|
| 1 | `sync:mcp-config` | haiku | `MCP_TEMPLATES_DIR={值}` |
| 2 | `sync:hooks-config` | haiku | `PROJECT_ROOT={值}`<br>`SCRIPTS_DIR={值}` |
| 3 | `sync:cursor-sync` | haiku（`--with-spec` 时用 sonnet） | `PROJECT_ROOT={值}`<br>`CURSOR_TEMPLATE_DIR={值}`<br>`SYNC_SPEC={true/false}`<br>`SPEC_SKILLS_DIR={值}` |
| 4 | `sync:mr-template` | haiku | `PROJECT_ROOT={值}`<br>`MR_TEMPLATE_DIR={值}` |
| 5 | `sync:skills-sync` | haiku | `PROJECT_ROOT={值}`<br>`SKILLS_DIR={值}` |
| 6 | `sync:statusline-config` | haiku | `SCRIPTS_DIR={值}` |

**注意**：
- prompt 只传运行时参数（几行 KEY=VALUE），agent 的完整指令由 agents/ 目录中的 .md 文件定义
- description 字段用简短中文描述（如 "配置 MCP 服务器"、"配置 Hooks" 等）

---

### Phase 2：汇总报告（主 agent 串行）

等待所有 6 个 Task 返回结果后，从每个 agent 的返回值中提取状态和详情，生成执行报告。

**步骤 2.1：提取结果**

从每个 Task 返回值中提取：
- Agent 1 → step1_mcp
- Agent 2 → step2_hooks
- Agent 3 → step3_cursor（含 spec_skills 信息）
- Agent 4 → step4_mr_template
- Agent 5 → step5_claude_skills
- Agent 6 → step6_statusline

**步骤 2.2：写入 LSP 插件配置并安装 binary**

如果 `DETECTED_LSP` 不为 `none`：
1. 读取项目 `.claude/settings.json`
2. 将检测到的 LSP 插件逐个加入 `enabledPlugins`（不覆盖已有值）
3. 写回 `.claude/settings.json`
4. **立即安装 LSP binary**：对每个检测到的 LSP 插件，检查 binary 是否存在，缺失则安装：
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
5. 记录结果（插件启用 + binary 安装状态）→ step7_lsp

如果 `DETECTED_LSP` 为 `none`：
- 跳过，step7_lsp = "未检测到支持的语言"

**步骤 2.3：输出执行报告**

根据执行结果输出相应的报告：

**情况 A：所有步骤都成功**

```
✅ 开发环境配置完成！

执行结果：
  ✅ MCP 配置: 成功
     - ~/.claude.json: [新增/已存在] context7, sequential-thinking
     - ~/.cursor/mcp.json: [新增/已存在] context7, sequential-thinking

  ✅ 自动更新钩子: 成功
     - 配置文件: .claude/hooks/hooks.json
     - 自动更新脚本: .claude/hooks/scripts/set-auto-update-plugins.sh
     - 插件启用: .claude/hooks/scripts/ensure-plugins.sh
     - MCP 懒加载: .claude/hooks/scripts/ensure-tool-search.sh

  ✅ Cursor 同步: 成功
     - Rules: git-flow.mdc
     - Commands: git-commit.md, git-commit-push.md, git-commit-push-pr.md, sync-mcp-grafana.md
     （以下仅在 --with-spec 时显示）
     - Spec Skills (alwaysApply: true):
       - doc-auto-sync.mdc
       - module-discovery.mdc
     - Spec Skills (alwaysApply: false):
       - generate-module-map.mdc
     - 已跳过（测试中）: implementing-from-task, merging-parallel-work
     - 已删除旧文件: sync-claude-plugin.mdc（如果存在）

  ✅ GitLab MR 模板: 成功
     - 模板文件: .gitlab/merge_request_templates/default.md [新创建/已存在]

  ✅ Claude Skills 同步: 成功
     - grafana-dashboard-design（Grafana Dashboard 设计规范）
     - 位置: .claude/skills/grafana-dashboard-design/

  ✅ Status Line 配置: 成功
     - 脚本: ~/.claude/scripts/statusline.sh
     - 配置: ~/.claude/settings.json
     - 显示: [模型] 项目 git:(分支) [进度条] % | 版本 计划

  [✅/⏭️ ] LSP 代码智能: [已配置/未检测到支持的语言]
     - 检测到语言: [Go, TypeScript, ...]
     - 已启用插件: [gopls-lsp, typescript-lsp, ...]
     - Binary 安装: [✅ gopls 已存在/安装成功, ✅ typescript-language-server 已存在/安装成功, ...]
     - [如有安装失败]: ⚠️ <binary> 安装失败: <原因>
     - 团队成员启动 session 时将通过 Hook 自动安装
     - 运行 /sync:lsp --check 查看详细状态

下一步：
  1. 重启 Claude Code 会话（MCP 配置生效）
  2. 重启 Cursor IDE（配置生效）
  3. 配置将自动生效

💡 提示：
  - 更新插件后重启会话，自动更新机制会生效
  - 在 Cursor 中输入 / 可查看所有命令
  - 使用 --with-spec 参数可同步 Spec Skills 到 Cursor
```

**情况 B：部分步骤失败**

```
⚠️ 开发环境配置部分完成

执行结果：
  [✅/❌/⏭️ ] MCP 配置: [成功/失败/跳过]
     详情: [具体信息]

  [✅/❌/⏭️ ] 自动更新钩子: [成功/失败/跳过]
     详情: [具体信息]

  [✅/❌/⏭️ ] Cursor 同步: [成功/失败/跳过]
     详情: [具体信息]
     - git-flow: [成功/失败]
     （以下仅在 --with-spec 时显示）
     - Spec Skills: [成功/失败/跳过]
       - 已同步: [文件列表]
       - 已跳过（测试中）: [skill 列表]

  [✅/❌/⏭️ ] GitLab MR 模板: [成功/失败/跳过]
     详情: [具体信息]

  [✅/❌/⏭️ ] Claude Skills 同步: [成功/失败/跳过]
     详情: [具体信息]

  [✅/❌/⏭️ ] Status Line 配置: [成功/失败/跳过]
     详情: [具体信息]

失败步骤详情：
  [具体错误信息和建议]

建议：
  - 对于失败的步骤，可以单独运行对应的命令重试：
    - MCP 配置: /sync:mcp
    - 自动更新钩子: /sync:hooks
    - Cursor 同步: /sync:cursor
```

**情况 C：所有步骤都失败**

```
❌ 开发环境配置失败

所有步骤都失败了，详情：
  ❌ MCP 配置: [错误信息]
  ❌ 自动更新钩子: [错误信息]
  ❌ Cursor 同步: [错误信息]
     - git-flow: [错误信息]
     （以下仅在 --with-spec 时显示）
     - Spec Skills: [错误信息]
  ❌ GitLab MR 模板: [错误信息]
  ❌ Claude Skills 同步: [错误信息]
  ❌ Status Line 配置: [错误信息]

请检查：
  1. 文件权限是否正确
  2. JSON 格式是否有误
  3. 目录结构是否完整
  4. spec 插件是否已安装（仅 --with-spec 时相关）

或者尝试单独运行：
  - /sync:mcp
  - /sync:hooks
  - /sync:cursor
```

---

## 配置说明

### MCP 服务器
- **context7**: 自动获取 GitHub 公开库的最新文档和代码示例
- **sequential-thinking**: 提供结构化问题解决能力

### 自动更新钩子
- **SessionStart hook**: 会话启动时自动启用 marketplace 插件自动更新（autoUpdate）
- **插件启用 hook**: 确保 `enabledPlugins` 包含 spec, sync, git, quality 插件
- **ToolSearch hook**: 确保 `env.ENABLE_TOOL_SEARCH` 已配置（不覆盖已有值）
- **效果**: 插件更新将由 Claude marketplace 自动更新机制接管（无需手动 uninstall + install）

### Cursor 同步
- **Rules**: Git 工作流规范（git-flow.mdc）
- **Commands**: git-commit、git-commit-push、git-commit-push-pr 命令
- **Spec Skills**（需 `--with-spec` 参数启用）: 自动同步 spec 插件的 skills 规则
  - `doc-auto-sync.mdc` - AI 改动模块代码时自动同步文档（alwaysApply: true）
  - `module-discovery.mdc` - 开发前必须读取模块索引定位目标（alwaysApply: true）
  - `generate-module-map.mdc` - 生成模块索引的 prompt（alwaysApply: false）
  - 已跳过：`implementing-from-task`、`merging-parallel-work`（测试中）

### GitLab MR 模板
- **default.md**: GitLab Merge Request 默认模板
- **位置**: `.gitlab/merge_request_templates/default.md`
- **效果**: 创建 MR 时自动使用此模板

### Claude Skills
- **grafana-dashboard-design**: Grafana Dashboard 设计规范
  - 包含：SKILL.md（主技能）、design-patterns.md（设计模式）、platform-templates.md（多平台模板）
- **位置**: `.claude/skills/grafana-dashboard-design/`
- **效果**: Claude Code 在创建/修改 Grafana Dashboard 时自动应用设计规范

### Status Line
- **statusline.sh**: 自定义状态栏脚本
- **位置**: `~/.claude/scripts/statusline.sh`
- **配置**: `~/.claude/settings.json` 中的 `statusLine` 字段
- **显示内容**:
  - 模型名（蓝色）
  - 项目名
  - Git 分支（绿色）
  - Context 使用率（进度条 + 百分比，颜色随阈值变化）
  - Worktree 名（青色，如有）
  - 版本号（灰色）
  - 订阅计划（紫色）
- **颜色阈值**:
  - 绿色：0-59%（正常）
  - 黄色：60-79%（注意）
  - 红色：80-100%（警告）

---

## 注意事项

1. **覆盖策略**：
   - **MCP 配置**：已存在则跳过，不覆盖
   - **Hooks 配置**：检测差异并更新（如果配置有变化则自动更新）
   - **Cursor 同步**：直接覆盖（rules 和 commands 每次重新生成）
   - **Spec Skills**：直接覆盖（每次从 spec 插件重新生成 .mdc 文件）（仅 --with-spec 时执行）
   - **GitLab MR 模板**：已存在则跳过，不覆盖（保留项目自定义配置）
   - **Claude Skills**：直接覆盖（每次从 sync 插件重新复制）
   - **Status Line**：直接覆盖（每次重新复制脚本并更新配置）
   - 某步骤失败不影响后续步骤

2. **配置生效**：
   - MCP 配置：重启 Claude Code 会话
   - 自动更新钩子：下次会话启动时生效
   - Cursor 配置：重启 Cursor IDE
   - GitLab MR 模板：立即生效，创建 MR 时使用
   - Claude Skills：重启 Claude Code 会话后生效
   - Status Line：重启 Claude Code 会话后生效

3. **单独命令**：
   如果某个步骤需要更详细的控制，可以单独运行：
   - `/sync:mcp` - 仅配置 MCP
   - `/sync:hooks` - 仅配置钩子
   - `/sync:cursor` - 仅同步 Cursor（包含冲突处理）
   - `/sync:statusline` - 仅配置 Status Line
   - `/sync:lsp` - 检测语言并配置 LSP（支持 `--check` 和 `--install`）

4. **开发模式**：
   如果你是插件开发者，可以使用 `--dev` 参数优先从 cache 读取最新版本：
   ```
   /sync:basic --dev
   ```
   这会让查找逻辑优先使用 `~/.claude/plugins/cache/` 路径，而不是 `~/.claude/plugins/marketplaces/` 路径。

5. **Spec Skills 同步**：
   默认不同步 Spec Skills，如需同步请使用 `--with-spec` 参数：
   ```
   /sync:basic --with-spec
   ```
