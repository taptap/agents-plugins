---
allowed-tools: Read, Write, Edit, Bash(pwd:*), Bash(test:*), Bash(bash:*), Bash(ls:*), Bash(sort:*), Bash(tail:*), Bash(echo:*), Bash(command:*), Bash(which:*)
description: 检测项目语言并配置 LSP 代码智能（自动检测 + 安装 binary + 启用插件）
---

## Context

此命令检测项目使用的编程语言，启用对应的 LSP 插件，并立即安装所需的 LSP binary。

**支持的语言（10 种）**：Go / TypeScript(JS) / Python / Rust / Java / Kotlin / Swift / C(C++) / C# / PHP

**参数**：
- 无参数：检测语言 → 启用插件 → 安装 binary → 输出报告
- `--check`：仅查看当前 LSP 状态（已启用插件、binary 是否存在、版本）
- `--install`：跳过检测，强制重新安装所有已启用 LSP 的 binary

## Your Task

### 第零步：确认在项目根目录

```bash
pwd
test -d .git -o -f .gitignore && echo "OK" || echo "FAIL"
```

如果 FAIL，提示用户在项目根目录执行。

### 第一步：解析参数

检查用户传入的参数：
- `--check` → 设置 `MODE=check`
- `--install` → 设置 `MODE=install`
- 无参数 → 设置 `MODE=default`

---

### MODE=check：查看 LSP 状态

**步骤 1：读取已启用的 LSP 插件**

读取 `.claude/settings.json`，提取 `enabledPlugins` 中以 `-lsp@claude-plugins-official` 结尾且值为 `true` 的条目。

如果文件不存在或无 LSP 插件启用，输出：

```
📋 LSP 状态

未检测到已启用的 LSP 插件。
运行 /sync:lsp 自动检测并配置。
```

**步骤 2：检查每个 LSP 的 binary 状态**

对每个启用的 LSP 插件，检查对应 binary 是否存在及版本：

| 插件 ID | Binary 命令 | 版本命令 |
|---------|------------|---------|
| gopls-lsp | `gopls` | `gopls version` |
| typescript-lsp | `typescript-language-server` | `typescript-language-server --version` |
| pyright-lsp | `pyright-langserver` | `pyright --version` |
| rust-analyzer-lsp | `rust-analyzer` | `rust-analyzer --version` |
| jdtls-lsp | `jdtls` | `jdtls --version` |
| kotlin-lsp | `kotlin-language-server` | `kotlin-language-server --version` |
| swift-lsp | `sourcekit-lsp` | `sourcekit-lsp --version` |
| clangd-lsp | `clangd` | `clangd --version` |
| csharp-lsp | `csharp-ls` | `csharp-ls --version` |
| php-lsp | `intelephense` | `intelephense --version` |

```bash
command -v <binary> && <version_command> 2>&1 | head -1 || echo "NOT_FOUND"
```

**步骤 3：输出状态报告**

```
📋 LSP 状态

已启用的 LSP 插件：
  [✅/❌] gopls-lsp          → gopls [版本号 / 未安装]
  [✅/❌] typescript-lsp      → typescript-language-server [版本号 / 未安装]
  ...

提示：
  - 运行 /sync:lsp --install 重新安装缺失的 binary
  - 日志位置: ~/.claude/plugins/logs/ensure-lsp-*.log
```

结束。

---

### MODE=install：强制安装已启用的 LSP binary

**步骤 1：读取已启用的 LSP 插件**

与 check 模式相同，读取 `.claude/settings.json` 中启用的 LSP 插件。

如果无 LSP 插件启用，提示先运行 `/sync:lsp`。

**步骤 2：定位 ensure-lsp.sh**

```bash
# 检查项目级 hooks 脚本
test -f .claude/hooks/scripts/ensure-lsp.sh && echo "PROJECT_SCRIPT=OK" || echo "PROJECT_SCRIPT=MISSING"
```

如果项目级脚本存在，使用项目级脚本。否则查找插件目录：

```bash
MP=~/.claude/plugins/marketplaces/taptap-plugins/plugins/sync && \
LATEST=$(ls -d ~/.claude/plugins/cache/taptap-plugins/sync/*/ 2>/dev/null | sort -V | tail -1) && \
(test -f "${MP}/scripts/ensure-lsp.sh" && echo "SCRIPTS_DIR=${MP}/scripts" || (test -n "${LATEST}" && test -f "${LATEST}scripts/ensure-lsp.sh" && echo "SCRIPTS_DIR=${LATEST}scripts" || echo "SCRIPTS_DIR=none"))
```

**步骤 3：执行安装**

```bash
bash <ensure-lsp.sh路径>
```

注意：ensure-lsp.sh 会读取 `.claude/settings.json` 中的 enabledPlugins 并安装缺失 binary。

**步骤 4：验证安装结果**

对每个启用的 LSP 插件执行 `command -v <binary>` 检查安装是否成功。

**步骤 5：输出安装报告**

```
🔧 LSP Binary 安装结果

  [✅/❌] gopls          → [安装成功 / 安装失败: 原因]
  [✅/❌] typescript-language-server → [已存在 / 安装成功 / 安装失败: 原因]
  ...

[如有失败]:
⚠️ 部分安装失败，请检查：
  - gopls: 需要 go 环境 → brew install go 或 https://go.dev/dl/
  - typescript-language-server: 需要 npm → brew install node
  ...

日志详情: ~/.claude/plugins/logs/ensure-lsp-$(date +%Y-%m-%d).log
```

结束。

---

### MODE=default：检测 + 启用 + 安装

**步骤 1：定位 detect-lsp.sh**

```bash
MP=~/.claude/plugins/marketplaces/taptap-plugins/plugins/sync && \
LATEST=$(ls -d ~/.claude/plugins/cache/taptap-plugins/sync/*/ 2>/dev/null | sort -V | tail -1) && \
(test -f "${MP}/scripts/detect-lsp.sh" && echo "SCRIPTS_DIR=${MP}/scripts" || (test -n "${LATEST}" && test -f "${LATEST}scripts/detect-lsp.sh" && echo "SCRIPTS_DIR=${LATEST}scripts" || echo "SCRIPTS_DIR=none"))
```

如果 SCRIPTS_DIR=none，提示用户更新 sync 插件。

**步骤 2：执行语言检测**

```bash
bash {SCRIPTS_DIR}/detect-lsp.sh "$(pwd)"
```

输出格式：`DETECTED_LSP=gopls-lsp@claude-plugins-official,typescript-lsp@claude-plugins-official` 或 `DETECTED_LSP=none`。

如果 `DETECTED_LSP=none`：

```
📋 LSP 检测结果

未检测到支持的编程语言。

支持的语言：Go / TypeScript(JS) / Python / Rust / Java / Kotlin / Swift / C(C++) / C# / PHP
检测依据：go.mod, tsconfig.json, package.json, pyproject.toml, Cargo.toml 等项目文件
```

结束。

**步骤 3：写入 enabledPlugins**

读取 `.claude/settings.json`（项目级），将检测到的 LSP 插件加入 `enabledPlugins`（不覆盖已有值）。

如果文件不存在，创建：
```json
{
  "enabledPlugins": {
    "<plugin-id>": true
  }
}
```

如果文件存在，使用 Edit 工具合并 `enabledPlugins`（保留所有已有字段）。

**步骤 4：安装 LSP binary**

对每个检测到的 LSP 插件，**逐个检查并安装**：

| 插件 ID | 检查命令 | 前置依赖 | 安装命令 |
|---------|---------|---------|---------|
| gopls-lsp | `command -v gopls` | go | `go install golang.org/x/tools/gopls@latest` |
| typescript-lsp | `command -v typescript-language-server` | npm | `npm install -g typescript-language-server typescript` |
| pyright-lsp | `command -v pyright-langserver` | npm 或 pip | `npm install -g pyright` 或 `pip install pyright` |
| rust-analyzer-lsp | `command -v rust-analyzer` | rustup | `rustup component add rust-analyzer` |
| jdtls-lsp | `command -v jdtls` | 手动 | 提示用户参考文档安装 |
| kotlin-lsp | `command -v kotlin-language-server` | brew | `brew install kotlin-language-server` |
| swift-lsp | `command -v sourcekit-lsp` | Xcode | 提示安装 Xcode |
| clangd-lsp | `command -v clangd` | brew | `brew install llvm` |
| csharp-lsp | `command -v csharp-ls` | dotnet | `dotnet tool install -g csharp-ls` |
| php-lsp | `command -v intelephense` | npm | `npm install -g intelephense` |

每个 LSP 执行流程：
1. `command -v <binary>` — 已存在则跳过
2. 检查前置依赖 `command -v <prerequisite>` — 缺失则记录失败原因
3. 执行安装命令
4. 再次 `command -v <binary>` 验证安装

**步骤 5：输出完整报告**

```
✅ LSP 代码智能配置完成！

检测到的语言：
  - Go (go.mod)
  - TypeScript (tsconfig.json)

已启用插件：
  - gopls-lsp@claude-plugins-official
  - typescript-lsp@claude-plugins-official

Binary 安装：
  [✅/❌] gopls                      → [已存在 v0.17.1 / 安装成功 / 安装失败]
  [✅/❌] typescript-language-server  → [已存在 v4.3.3 / 安装成功 / 安装失败]

[如有安装失败]:
⚠️ 部分 LSP binary 安装失败：
  - <binary>: <原因>
    安装方式: <手动安装命令>

配置文件: .claude/settings.json (enabledPlugins)
日志位置: ~/.claude/plugins/logs/ensure-lsp-*.log

提示：
  - 重启 Claude Code 会话使 LSP 插件生效
  - 运行 /sync:lsp --check 查看 LSP 状态
  - 运行 /sync:lsp --install 重新安装失败的 binary
  - 团队成员启动 session 时将通过 SessionStart hook 自动安装 LSP binary
```

---

## 前置依赖安装指引

当前置依赖缺失时，提供具体的安装指引：

| 依赖 | macOS | Linux |
|------|-------|-------|
| go | `brew install go` | `sudo apt install golang` 或 https://go.dev/dl/ |
| npm/node | `brew install node` | `sudo apt install nodejs npm` |
| pip | 随 Python 安装 | `sudo apt install python3-pip` |
| rustup | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` | 同左 |
| dotnet | `brew install dotnet` | https://dotnet.microsoft.com/download |
| brew | https://brew.sh | https://brew.sh |
| Xcode | `xcode-select --install` | N/A |

## 错误处理

1. **不在项目根目录**：提示在项目根目录执行
2. **detect-lsp.sh 不可用**：提示更新 sync 插件
3. **settings.json 格式错误**：报错并提示手动修复
4. **安装失败**：提供具体的手动安装命令和依赖安装指引
