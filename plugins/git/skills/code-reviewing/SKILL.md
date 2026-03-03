---
name: code-reviewing
description: 代码审查，支持本地变更、提交、分支和 MR/PR URL 审查。当用户说"review"、"代码审查"、"review this MR/PR"、"/review" 或要求审查代码变更时触发。
---

# 代码审查

本 Skill 为只读顾问 — 仅分析代码，不做任何修改。审查采用多层引擎：Claude Code Agent Team（深度 + 交叉验证）+ Codex CLI（不同模型视角）。

---

## 入口：意图识别

根据用户输入确定审查目标：

| 输入 | 动作 |
|------|------|
| MR/PR URL | → [MR 审查流程](#mr-审查流程) |
| 明确的本地变更 / `--uncommitted` | → [本地审查流程](#本地审查流程) |
| Commit SHA / `HEAD` / `HEAD~N` | → 本地审查 |
| 分支名 | → 本地审查 |
| 无参数 | → 自动检测，见下方 |
| 模糊输入 | → 使用 `AskUserQuestion` 澄清，不猜测 |

### 自动检测（无参数）

1. 执行 `git status --porcelain`
2. **有未提交变更** → 默认审查本地变更
3. **无未提交变更** → 收集上下文后询问用户：

```bash
git log --oneline -10
git branch --show-current
git log --oneline @{upstream}..HEAD 2>/dev/null        # 未推送的提交
git log --oneline HEAD..@{upstream} 2>/dev/null        # 远程领先的提交

# 检查当前分支是否有已开启的 MR/PR
# GitLab:
glab api "projects/{project_path_encoded}/merge_requests?source_branch=$(git branch --show-current)&state=opened" --repo {host}/{project_path} 2>/dev/null
# GitHub:
gh pr list --head "$(git branch --show-current)" --state open --json number,title,url 2>/dev/null
```

使用 `AskUserQuestion` 生成动态选项（最多 4 个），按相关性排序：
- 如果当前分支有已开启的 MR/PR → 推荐为首选
- 如果有未推送的提交 → 作为候选项
- 始终包含最近一次提交作为选项
- 如果最近的提交属于同一功能（消息前缀相似），则归为"最近 N 个提交"
- 兜底选项："指定 MR/PR URL"

---

## 审查引擎：Agent Team + Codex

此引擎同时用于 MR 审查流程和本地审查流程。

### 架构

```
Phase 1（subagent + Codex 并行）          Phase 2（Agent Team 讨论）
┌──────────────┐                         ┌──────────────────────────────┐
│ Claude Code  │──┐                      │     Debate Agent Team        │
│ subagent     │  │   发现列表            │                              │
│ Opus 完整审查 │  ├──────────▶           │  Debater-1 ◄─SendMsg─▶ Debater-2  │
└──────────────┘  │                      │    Opus          Opus        │
┌──────────────┐  │                      │  逐条讨论每个发现              │
│  Codex CLI   │──┘                      │  互相质疑/确认/补充            │
│  后台执行     │                         └──────────────┬───────────────┘
└──────────────┘                                        │
                                                  Lead 收集结论
                                                  → 最终报告
```

合计：3 个 Opus agent（1 个 subagent reviewer + 2 个 agent team debater）+ 1 次 Codex CLI 调用。
2 个顺序阶段，每个阶段内部并行。

### Phase 1 — 独立审查（2 个并行 subagent，无需互相通信）

使用 Agent tool 同时启动两个 subagent（在同一消息中发出，真正并行）：

**Subagent 1 — Claude Reviewer**（Agent tool, subagent_type="general-purpose", model="opus"）：
- 读取完整 diff + 在需要时读取源文件追踪调用链
- 应用 [review-checklist.md](review-checklist.md) — 全部 5 个维度：安全、逻辑、资源、API、质量
- 对每个发现输出：文件、行号、问题描述、严重级别、所属维度
- 深度分析：追踪完整调用链，不跳过可疑路径
- 与上次审查发现对比（如有）— 标记已修复/已忽略的问题

**Subagent 2 — Codex CLI**（Agent tool, subagent_type="general-purpose"）：
- 在 subagent 内部通过 Bash 执行 `codex review`
- 不同模型视角，弥补 Claude 的盲区
- 如果 codex 未安装或执行失败 → 优雅降级，返回 "CODEX_NOT_AVAILABLE"

收集两个 subagent 的结果并合并为发现列表（按文件 + 行号去重）。

### Phase 2 — Agent Team 辩论（2 个 debater 通过 SendMessage 通信）

1. 创建辩论团队（TeamCreate）
2. 为 Phase 1 的每个发现创建一个 TaskCreate
3. 同时启动 Debater-1 和 Debater-2（model="opus", run_in_background=true）
   - Prompt 描述期望行为即可，不要写通信协议步骤（Agent Teams 的 mailbox 系统会自动处理消息投递和 idle 唤醒）
   - Prompt 要点：你是 code review 辩论者，独立分析每个 finding 后与对方讨论，互相质疑和验证，像科学辩论一样尝试推翻对方的结论，达成共识后用 TaskUpdate 标记结论
4. Debater 通过 SendMessage 讨论**每个发现**：
   - 各自独立分析发现，读取源文件验证
   - 互相质疑："调用方是否在更高层处理了这个 nil？"
   - 互相补充："我还发现了另一条有相同问题的调用路径"
   - 达成共识并标记每个任务：
     - ✅ **confirmed** — 双方一致认为是真实问题
     - ⚠️ **uncertain** — 存在分歧，需人工审查
     - ❌ **dismissed** — 双方一致认为是误报
5. 所有发现讨论完毕后，debater 可以补充新发现（Phase 1 遗漏的）

### Lead 汇总

6. 从任务列表收集所有结论
7. 生成最终报告，按确认状态分类：
   - ❌ 阻塞问题（confirmed，必须修复）
   - ⚠️ 需人工审查（uncertain）
   - dismissed 的发现不包含在输出中
8. 关闭辩论团队，清理资源

---

## MR 审查流程

### 步骤 1：解析 MR/PR URL

从 URL 提取 `host`、`project_path`、`mr_iid`。

GitLab: `https://{host}/{namespace}/{project}/-/merge_requests/{iid}`
GitHub: `https://github.com/{owner}/{repo}/pull/{number}`

### 步骤 2：获取 MR/PR 元数据

对于自托管 GitLab（如 `git.gametaptap.com`），glab 不加 `--repo` 会默认指向 `gitlab.com`，导致 404。必须指定：

**GitLab**:
```bash
glab api projects/{project_path_encoded}/merge_requests/{mr_iid} --repo {host}/{project_path}
```
URL 编码 project_path：`/` → `%2F`

**GitHub**:
```bash
gh pr view {number} --repo {owner}/{repo} --json number,title,body,author,headRefName,baseRefName,url,commits
```

提取：`source_branch`、`target_branch`、`sha`、`title`、`author`、`web_url`

### 步骤 3：准备本地仓库 + Worktree

审查在隔离的 worktree 中运行，避免干扰用户的工作目录。

```
repo_dir:     ~/.cache/code-review/{host}/{project_path}
worktree_dir: ~/.cache/code-review/{host}/{project_path}/.worktrees/{YYYYMMDD}-{HHMMSS}-mr-{mr_iid}
```

```bash
cache_base=~/.cache/code-review
repo_dir="${cache_base}/{host}/{project_path}"
worktree_base="${cache_base}/{host}/{project_path}/.worktrees"
remote_url="git@{host}:{project_path}.git"

# 1. 复用本地已有仓库
local_origin=$(git remote get-url origin 2>/dev/null || true)

if [ -d "$repo_dir/.git" ]; then
    # 缓存仓库已存在
    cd "$repo_dir"
elif [ "$local_origin" = "$remote_url" ]; then
    # 当前工作目录就是目标仓库
    repo_dir="$(git rev-parse --show-toplevel)"
    cd "$repo_dir"
else
    # 全新克隆
    mkdir -p "$(dirname "$repo_dir")"
    git clone "$remote_url" "$repo_dir"
    cd "$repo_dir"
fi

# 2. 精确 fetch 只需要的分支
git fetch origin \
    "{source_branch}:refs/remotes/origin/{source_branch}" \
    "{target_branch}:refs/remotes/origin/{target_branch}"

# 3. 创建 worktree
worktree_name="$(date +%Y%m%d-%H%M%S)-mr-{mr_iid}"
worktree_dir="${worktree_base}/${worktree_name}"
mkdir -p "$worktree_base"
git worktree add "$worktree_dir" "origin/{source_branch}" --detach
```

### 步骤 4：获取准确 Diff

```bash
cd "$worktree_dir"
git diff "origin/${target_branch}...HEAD"
```

三点 `...` 仅显示源分支相对于合并基点的变更，与 MR/PR UI 一致。

### 步骤 5：查找已有审查评论

**GitLab**:
```bash
glab api projects/{project_id}/merge_requests/{mr_iid}/notes --repo {host}/{project_path}
```

**GitHub**:
```bash
gh api repos/{owner}/{repo}/issues/{number}/comments
```

查找以 `## Automated Code Review` 开头的评论。记录 `note_id`/`comment_id`，提取上次审查的 commit SHA，收集已报告的问题。

### 步骤 6：解析忽略状态

从步骤 5 获取的审查评论之后的回复中，扫描忽略关键词：

- `忽略: [问题关键词]` 或 `忽略：[问题关键词]`
- `ignore: [keyword]`

匹配到的 issue 在步骤 7 中传递给 Claude Reviewer，标记为 **已忽略**。

已修复的问题不需要手动标记 — re-review 时自动对比代码变更：如果相关代码确实修改了 → 自动标记为 **已修复**。

### 步骤 7：执行审查

运行[审查引擎](#审查引擎agent-team--codex)，以 `target_branch` 为基准。

将之前的审查发现（步骤 5）和已忽略的问题（步骤 6）传递给 Claude Reviewer，以便在报告中标记已修复/已忽略的问题。

### 步骤 8：确定评论方式

检测当前用户是否为 MR 作者：

```bash
# GitLab: 获取当前认证用户
current_user=$(glab api user --hostname={host} 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin).get('username',''))")
# GitHub:
current_user=$(gh api user --jq '.login')
```

| 条件 | 评论方式 | 自动批准 |
|------|---------|---------|
| 当前用户 == MR 作者（自己的 MR） | 发 comment | ❌ 不 approve |
| 当前用户 != MR 作者（别人的 MR） | 发 comment | ✅ 条件性 approve |

### 步骤 9：格式化并发布审查评论

格式参见[审查评论模板](#审查评论模板)。

将评论写入唯一的临时文件，然后通过 API 发布。使用 `-F`（不是 `-f`）上传文件内容 — `-f body="@file"` 会发送字面字符串 `@file` 而不是文件内容。

**发布策略判断**：

从步骤 5 获取的 notes 列表中判断更新还是新建：
1. 过滤掉 `system=true` 的 notes，得到用户评论列表
2. 取最后一条用户评论的 `note_id`
3. 如果最后一条用户评论就是已有审查评论（`note_id` 匹配步骤 5 找到的）→ **原地更新**
4. 否则 → **创建新评论**，并将旧审查评论（如有）折叠标注：更新旧评论 body，在开头加 `> ⚠️ 此评论已过期，最新审查见下方。`，原内容包裹在 `<details><summary>历史审查记录</summary>...</details>` 中

**GitLab**:
```bash
comment_file="/tmp/review_comment_${mr_iid}_$(date +%s).md"
# 使用 Write tool 写入评论内容

if [ "$last_user_note_id" = "$existing_review_note_id" ]; then
    # 审查评论仍是最后一条 → 原地更新
    glab api projects/{project_id}/merge_requests/{mr_iid}/notes/{note_id} \
      --repo {host}/{project_path} -X PUT -F body="@${comment_file}"
else
    # 有新评论插入 → 折叠旧评论 + 创建新评论
    if [ -n "$existing_review_note_id" ]; then
        fold_file="/tmp/review_fold_${mr_iid}_$(date +%s).md"
        # 使用 Write tool 写入折叠内容
        glab api projects/{project_id}/merge_requests/{mr_iid}/notes/${existing_review_note_id} \
          --repo {host}/{project_path} -X PUT -F body="@${fold_file}"
        rm -f "$fold_file"
    fi
    glab api projects/{project_id}/merge_requests/{mr_iid}/notes \
      --repo {host}/{project_path} -X POST -F body="@${comment_file}"
fi

rm -f "$comment_file"
```

**GitHub**:
```bash
comment_file="/tmp/review_comment_${number}_$(date +%s).md"

if [ "$last_user_comment_id" = "$existing_review_comment_id" ]; then
    gh api repos/{owner}/{repo}/issues/comments/{comment_id} \
      -X PATCH -F body="@${comment_file}"
else
    if [ -n "$existing_review_comment_id" ]; then
        fold_file="/tmp/review_fold_${number}_$(date +%s).md"
        gh api repos/{owner}/{repo}/issues/comments/${existing_review_comment_id} \
          -X PATCH -F body="@${fold_file}"
        rm -f "$fold_file"
    fi
    gh pr comment {number} --repo {owner}/{repo} --body-file "$comment_file"
fi

rm -f "$comment_file"
```

### 步骤 10：回复讨论（可选）

如果讨论中有未解决的问题，进行回复。

### 步骤 11：自动批准

**前提**：当前用户 != MR 作者（自己的 MR 不自动批准）。

**条件**：审查结果中无 HIGH 且无 MEDIUM 级别的 confirmed/uncertain finding。LOW 级别和建议不阻塞批准。

符合条件时执行批准：

**GitLab**:
```bash
glab api projects/{project_id}/merge_requests/{mr_iid}/approve --repo {host}/{project_path} -X POST
```

**GitHub**:
```bash
gh pr review {number} --repo {owner}/{repo} --approve
```

### 步骤 12：清理 Worktree

```bash
cd "$repo_dir"
git worktree remove "$worktree_dir" 2>/dev/null || true
```

---

## 本地审查流程

### 步骤 1：收集变更

在当前目录工作，无需 clone 或 worktree。

```bash
git diff --staged
git diff
git ls-files --others --exclude-standard
```

### 步骤 2：执行审查

运行[审查引擎](#审查引擎agent-team--codex)，以默认分支为基准。

Codex CLI 使用 `--uncommitted` 替代 `--base`：
```bash
codex review --uncommitted 2>&1
```

### 步骤 3：输出到终端

不发布评论。直接使用相同的清单格式输出：

```markdown
## Review Summary

**Scope**: [X files changed, Y insertions, Z deletions]
**Intent**: [Brief description]

### 检查清单

| 类别 | 状态 | 备注 |
|------|------|------|
| 安全性 | ✅/⚠️/❌ | ... |
| 逻辑正确性 | ✅/⚠️/❌ | ... |
| 资源管理 | ✅/⚠️/➖ | ... |
| API 与兼容性 | ✅/⚠️/➖ | ... |
| 代码质量 | ✅/⚠️ | ... |

### 🚫 阻塞问题 / ⚠️ 警告 / 💡 建议
...

### Conclusion
✅ LGTM. Ready for commit.
-- OR --
❌ Issues found. Please resolve blocking issues before committing.
```

### 步骤 4：用户确认（confirmed/uncertain 发现）

**当存在 confirmed 或 uncertain 的 finding 时，必须逐条让用户确认处理方式，禁止自动跳过。**

仅当所有 finding 均为 dismissed 时才可直接输出 LGTM 结论。

**确认流程：**

对每个 confirmed 或 uncertain 的 finding，使用 `AskUserQuestion` 询问处理方式：

```
问题："Finding #N：[简述问题] — 如何处理？"
选项：
  - "忽略（已知风险）" — 确认知悉，不修复
  - "后续 PR 处理" — 记录为待办，本次不修复
  - "立即修复" — 中断流程，先修复再重新审查
```

**处理规则：**
- 用户选择"忽略"或"后续 PR 处理" → 标记该 finding，继续下一条
- 用户选择"立即修复" → 中断审查流程，返回修复建议，等待用户修复后重新执行审查
- 所有 finding 确认完毕后，输出最终结论（附带用户决策记录）

**结论格式（含用户决策）：**
```markdown
### Conclusion
✅ LGTM（用户已确认所有非阻塞问题）

用户决策记录：
- Finding #1: [问题简述] → 后续 PR 处理
- Finding #2: [问题简述] → 忽略（已知风险）
```

---

## 审查评论模板

优先保证审查评论的可见性。如果上次审查评论是最后一条非系统评论，则原地更新；否则创建新评论（旧评论折叠标注），确保审查结果在评论区底部可见。

```markdown
## Automated Code Review

**概要**：[一句话总结变更内容]

### 检查清单

| 类别 | 状态 | 备注 |
|------|------|------|
| 安全性 | ✅/⚠️/❌ | [简述] |
| 逻辑正确性 | ✅/⚠️/❌ | [简述] |
| 资源管理 | ✅/⚠️/➖ | [简述] |
| API 与兼容性 | ✅/⚠️/➖ | [简述] |
| 代码质量 | ✅/⚠️ | [简述] |

说明：✅ 通过 | ⚠️ 警告 | ❌ 未通过 | ➖ 不适用

### 🚫 阻塞问题
- `file.go:42` — 问题描述

### ⚠️ 警告
- `util.py:8` — 警告描述

### 💡 建议
- 建议描述

### ✅ 已修复（自上次评审）
- ~~`file.go:10` - 之前报告的问题~~ ✓ 已在 {new_sha_short} 修复

### ✅ 已忽略（应评审者请求）
- ~~`config.go:5` - 问题描述~~ → 由 @reviewer 忽略

---

**状态**：已批准 ✅ / 待处理（还有 X 个阻塞问题）

---
*Powered by Claude Code (Opus 4.6) + Codex CLI*
*回复 `忽略: [问题关键词]` 可标记为已忽略，re-review 时自动识别。已修复的问题会自动检测。*
```

> 注：如果 Codex 不可用（降级），签名行显示为 `Powered by Claude Code (Opus 4.6)`。

---

## 约束规则

- **只读** — 审查者是观察者；审查与代码修改混在一起会模糊审计和修复的边界。禁止修改代码、commit、push 或 `git add`。
- **评论策略** — 所有 MR 均发布审查评论。自己的 MR 仅发 comment 不自动 approve；别人的 MR 发 comment + 条件性自动 approve。
- **评论可见性优先** — 如果上次审查评论仍是最后一条非系统评论则原地更新，否则创建新评论保证可见性。旧评论折叠标注。
- **Codex 优雅降级** — 如果 Codex 不可用，仅使用 Claude Code Agent Team 继续，不阻塞流程。
- **Worktree 隔离** — MR 审查在隔离的 worktree 中运行，审查后清理。
- **语言** — 审查评论使用简体中文。技术术语、文件路径、函数名和 commit SHA 保持原样。
- **自动批准** — 当审查结果无 HIGH 和 MEDIUM 级别问题时自动批准（仅限别人的 MR）。
- **Agent Team 清理** — 审查完成后必须关闭辩论团队并清理资源。
