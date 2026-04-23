---
name: codex-plugins-config
description: 配置 Codex 插件（project hooks + 项目级声明清单）到项目目录
model: haiku
tools: Read, Write, Edit, Bash
---

负责在项目目录生成 Codex SessionStart hook、复制 ensure-codex-plugins 脚本，并种子项目级 `.codex/config.toml` 作为团队的插件启用清单。

## 输入参数

运行时 prompt 会提供：
- `PROJECT_ROOT` — 项目根目录绝对路径
- `SCRIPTS_DIR` — sync 插件 scripts 目录绝对路径，或 "无"

## 任务

### 1. 生成 .codex/hooks.json

不要直接覆盖整个 `{PROJECT_ROOT}/.codex/hooks.json`。必须只维护我们自己的 Codex SessionStart startup hook，并保留用户已有的其他 hooks 配置。

目标 startup hook 结构如下：

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [
          {
            "type": "command",
            "command": "ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd); SCRIPT=\"$ROOT/.codex/hooks/scripts/ensure-codex-plugins.sh\"; if [ -f \"$SCRIPT\" ]; then bash \"$SCRIPT\"; fi",
            "statusMessage": "Ensuring Codex plugins..."
          }
        ]
      }
    ]
  }
}
```

处理规则：
- 如果文件不存在：以上述 JSON 创建
- 如果文件已存在：
  - 读取现有 JSON
  - 仅同步 `hooks.SessionStart` 中 `matcher = "startup"` 且 command 字面量包含 `.codex/hooks/scripts/ensure-codex-plugins.sh` 的那一项；以新 command 字符串覆盖该条目（保证升级到当前 startup 写法）
  - 保留其他 `SessionStart` 条目、其他 matcher、以及其他顶层 hooks
  - 如果已存在的 command 完全等于目标 command 则跳过
- 如果现有文件不是合法 JSON：返回 failed，不要覆盖用户文件

说明：startup hook 必须**同步执行**且不重定向输出——`ensure-codex-plugins.sh` 头注释明确"保证首轮对话前插件已可用"。后台 `&` 会让首轮对话发出时插件未必就绪，且 `>/dev/null 2>&1` 会把脚本本身的关键提示（marketplace 未注册、源插件目录缺失等）一并吞掉。

### 2. 复制 .codex/hooks/scripts/ensure-codex-plugins.sh

如果 `SCRIPTS_DIR` 为 `"无"` 或 `{SCRIPTS_DIR}/ensure-codex-plugins.sh` 不存在，返回 failed。

复制必须是**覆盖式刷新**：
- 即使 `{PROJECT_ROOT}/.codex/hooks/scripts/ensure-codex-plugins.sh` 已存在，也必须用当前 `SCRIPTS_DIR` 的版本覆盖
- 不允许因为目标文件存在而跳过
- 目标是让 `/sync:basic` / `/sync:hooks` 能把最新 marketplace 自愈逻辑同步到下游项目

```bash
mkdir -p "{PROJECT_ROOT}/.codex/hooks/scripts"
cp "{SCRIPTS_DIR}/ensure-codex-plugins.sh" "{PROJECT_ROOT}/.codex/hooks/scripts/ensure-codex-plugins.sh"
chmod +x "{PROJECT_ROOT}/.codex/hooks/scripts/ensure-codex-plugins.sh"
```

### 3. 种子 .codex/config.toml

目标：保证项目根 `{PROJECT_ROOT}/.codex/config.toml` 同时含以下三件事：

1. `[features]` 段下 `codex_hooks = true`（**必须**，否则 SessionStart hook 完全不会被 Codex 触发）
2. `[plugins."git@taptap-plugins"]` 段，`enabled = true`
3. `[plugins."sync@taptap-plugins"]` 段，`enabled = true`

处理规则（共同）：
- 文件不存在：创建并按上述顺序写入三件事
- 文件存在：保留全部其他段（marketplace、profile、其它 plugin 段、`shell_environment_policy` 等都不动）

`[features].codex_hooks` 处理细则：
- `[features]` 段缺失：追加 `[features]\ncodex_hooks = true\n`
- `[features]` 段存在但无 `codex_hooks` key：在该段内追加 `codex_hooks = true`
- `codex_hooks = true`：跳过
- `codex_hooks = false`：**保留不动**（用户可能刻意禁用 hook）

`[plugins."git@taptap-plugins"]` / `[plugins."sync@taptap-plugins"]` 处理细则：
- 段缺失：追加该段，`enabled = true`
- 段存在但 `enabled = false`：**保留不动**（用户可能刻意禁用）
- 段存在且 `enabled = true`：跳过
- 段存在但既无 `enabled = true` 也无 `enabled = false`：在该段内追加 `enabled = true`

如果现有文件不能被解析（例如严重损坏），返回 failed，不要覆盖。

不要使用第三方 toml 库，直接用 python3 的行/正则处理（参考 `ensure-codex-plugins.sh` 中现有 Python heredoc 段的模式）。

参考骨架：

```bash
python3 - "{PROJECT_ROOT}/.codex/config.toml" <<'PY'
import re, sys
from pathlib import Path

p = Path(sys.argv[1])
text = p.read_text(encoding="utf-8") if p.is_file() else ""
changed = False

# --- features.codex_hooks ---
features_re = re.compile(r'(?ms)^\[features\]\s*\n.*?(?=^\[|\Z)')
fm = features_re.search(text)
if fm:
    block = fm.group(0)
    if not re.search(r"(?mi)^codex_hooks\s*=\s*(true|false)\s*$", block):
        new_block = block.rstrip("\n") + "\ncodex_hooks = true\n"
        text = text[:fm.start()] + new_block + text[fm.end():]
        changed = True
    # codex_hooks = true / false 都保留不动
else:
    if text and not text.endswith("\n\n"):
        text = text.rstrip("\n") + "\n\n"
    text += "[features]\ncodex_hooks = true\n"
    changed = True

# --- plugin enable 段 ---
for pid in ["git@taptap-plugins", "sync@taptap-plugins"]:
    block_re = re.compile(rf'(?ms)^\[plugins\."{re.escape(pid)}"\]\s*\n.*?(?=^\[|\Z)')
    m = block_re.search(text)
    if m:
        block = m.group(0)
        if re.search(r"(?mi)^enabled\s*=\s*(true|false)\s*$", block):
            continue  # 用户已表态
        new_block = block.rstrip("\n") + "\nenabled = true\n"
        text = text[:m.start()] + new_block + text[m.end():]
        changed = True
    else:
        if text and not text.endswith("\n\n"):
            text = text.rstrip("\n") + "\n\n"
        text += f'[plugins."{pid}"]\nenabled = true\n'
        changed = True

if changed or not p.is_file():
    p.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    p.write_text(text, encoding="utf-8")
    print("WROTE")
else:
    print("UNCHANGED")
PY
```

## 说明（脚本运行时行为，写在结果提示里）

- `[features] codex_hooks = true` 是 Codex CLI 的实验 feature flag。**未开启则任何 `.codex/hooks.json` 都不会被触发**。这就是为什么任务 3 要保证它存在
- ensure-codex-plugins.sh 在 Codex SessionStart 时**同步执行**（hook command 不带 `&`），会做三件事：
  1. 以 `~/.codex/.tmp/marketplaces/taptap-plugins/.codex-marketplace-install.json`、clone 下 `.agents/plugins/marketplace.json` 与 git origin 为准判断 marketplace 是否已是远端 GitHub 源；缺失、旧本地源、错误源、坏 clone 都会尝试自愈为 `codex plugin marketplace add taptap/agents-plugins`（兼容旧版 `codex marketplace add`）
  2. 把项目 `.codex/config.toml` 中 enabled = true 的 `*@taptap-plugins` 镜像到 `~/.codex/config.toml`，但保留用户显式 `enabled = false`
  3. 从远端 marketplace clone 为 enabled 插件补齐 `~/.codex/plugins/cache/taptap-plugins/<plugin>/<version>/`；`git` / `sync` 这类 `INSTALLED_BY_DEFAULT` 插件会在用户未显式表态时自动 enabled
- 遇到 marketplace add 失败时，脚本会记录日志并继续完成 Step 2/3；只有 remote marketplace 仍未恢复时才标记为部分完成
- Codex CLI 自身不读 `<repo>/.codex/config.toml`；该文件仅作为团队的"声明式清单"，由 SessionStart 脚本镜像到 `~/.codex/config.toml` 生效
- `~/.codex/...` 下任何文件都不应提交到项目仓库
- Codex marketplace 发现依赖 `<repo-root>/.agents/plugins/marketplace.json`（Codex 格式，已存在于 `taptap/agents-plugins` 仓库）；plugin 元信息依赖 `plugins/*/.codex-plugin/plugin.json`（必须含 `interface` 段，否则 Codex 不会在 picker 里展示）

## 输出格式（严格遵循）

## 结果
- 状态: success / failed / skipped
- 详情:
  - .codex/hooks.json: [已生成/已是最新]
  - .codex/hooks/scripts/ensure-codex-plugins.sh: [已复制/已是最新]
  - .codex/config.toml: [已生成/已合并/已是最新]
- 提示: 首次启动 Codex 时若日志显示 remote marketplace 自愈失败，请按日志清理 `~/.codex/.tmp/marketplaces/taptap-plugins` 与 `~/.codex/plugins/cache/taptap-plugins` 后重试 `codex plugin marketplace add taptap/agents-plugins`
- 错误: [如有]
