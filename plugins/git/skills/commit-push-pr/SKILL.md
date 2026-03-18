---
name: git-commit-push-pr
description: 提交代码、推送分支、创建 MR/PR 并监控 Pipeline 状态。当用户说"提交并创建 MR"、"创建合并请求"、"commit push pr"、"帮我创建 MR"时触发。
---

## Context

- 当前 git 状态：!`git status`
- 当前分支：!`git branch --show-current`
- Staged 和 unstaged 变更：!`git diff HEAD --stat`
- 最近提交历史：!`git log --oneline -5`
- 远程分支：!`git branch -r | head -10`
- no-ticket 配置：!`printenv GIT_ALLOW_NO_TICKET || echo true`

## Your Task

### 第一步：检查并创建分支

**概要：** 检测默认分支并在必要时智能创建新分支

1. **检测默认分支**：使用三级检测方法（详见 [默认分支检测](../git-flow/snippets/01-detect-default-branch.md)）
   - 方法一：`git symbolic-ref refs/remotes/origin/HEAD`
   - 方法二：检查常见分支（main/master/develop）
   - 方法三：询问用户

2. **智能创建分支**（如果在默认分支）：自动分析 diff 判断分支类型
   - 详细流程参见：[智能分支创建](../git-flow/snippets/04-branch-creation-smart.md)

### 第二步：提取任务 ID

**三级优先级策略**（详见 [任务ID提取](../git-flow/snippets/02-extract-task-id.md)）：

1. 从分支名提取：`git branch --show-current | grep -oE 'TAP-[0-9]+'`
2. 从用户输入提取（飞书/Jira链接、直接ID）
3. 询问用户

**关键：** 纯数字 ID 必须转换为 `TAP-xxx` 格式。**禁止 AI 自动推断使用 no-ticket**。

### 第三步：提交变更

**执行流程：**

1. 分析 `git diff` 确定 commit type
2. 使用提取的任务 ID
3. 生成符合规范的提交信息（格式详见 [Commit格式](../git-flow/snippets/03-commit-format.md)）
4. Stage文件并commit（详见 [提交执行](../git-flow/snippets/05-commit-execution.md)）

### 第四步：自动代码审查（push 前）

检查用户输入是否包含 `--skip-code-review` 参数。

**如果包含**：输出 `⏭️ 已跳过代码审查` 后直接进入第五步

**如果不包含（默认）**：

输出：`💡 提示：如需跳过代码审查，可使用 --skip-code-review 参数`

```
Skill(skill: "git:code-reviewing", args: "review committed changes on current branch before push")
```

**审查结果处理**：
- 全部通过 → 自动继续推送
- 有 confirmed/uncertain 问题 → 逐条列出，让用户确认后再继续
- 有阻塞问题（🚫）→ 必须等待用户决策

### 第五步：推送并创建 MR

#### 5.1 检测平台

```bash
which glab && glab auth status
```

**安全限制（严格禁止）**：`glab mr approve` / `glab mr merge`

#### 5.2 生成 MR 标题和描述

**MR 标题**：
- 单个 commit：使用 commit 标题
- 多个 commit：使用第一个 commit 标题或汇总
- 若 MR 标题为英文 → 先 `git commit --amend` 修正为中文

**MR 描述**：从 commit message 汇总（`git log origin/master..HEAD --pretty=format:"%B" --reverse`）：
```markdown
## 改动内容
- [汇总所有 commit 的改动点]

## 影响面
- [汇总所有 commit 的影响面]
```

#### 5.3 合成最终 MR 描述（模板优先）

- 若存在 `.gitlab/merge_request_templates/default.md`（或 `Default.md`）：读取模板，将汇总正文填充到 `## Description` 区块
- 若无模板：直接使用汇总正文

#### 5.4 推送并创建 MR

**如果 glab 可用**：

```bash
git push -u origin $(git branch --show-current)

# 检测项目是否有 claude reviewer（有则自动指派）
GIT_HOST=$(git remote get-url origin | sed 's|git@||;s|:.*||')
PROJECT_PATH=$(git remote get-url origin | sed 's|git@[^:]*:||;s|\.git$||')
PROJECT_ENC=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1],safe=''))" "$PROJECT_PATH")
HAS_CLAUDE=$(glab api "projects/${PROJECT_ENC}/members/all?query=claude" --hostname "$GIT_HOST" 2>/dev/null | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print('1' if any(u.get('username')=='claude' for u in d) else '0')" 2>/dev/null)
REVIEWER_FLAG=""
[ "$HAS_CLAUDE" = "1" ] && REVIEWER_FLAG="--reviewer claude"

glab mr create \
  --title "$(git log -1 --pretty=%s)" \
  --description "$MR_DESC" \
  --yes --remove-source-branch \
  $REVIEWER_FLAG
```

**如果 glab 不可用（fallback）**：
```bash
git push -u origin $(git branch --show-current) -o merge_request.create
```

### 第六步：输出结果并打开浏览器

1. 显示推送成功信息和 MR/PR 链接
2. 显示任务工单链接（如有）
3. 使用系统默认浏览器打开 MR/PR 链接

### 第七步：Pipeline Watch（MR/PR 创建后 **必须执行，禁止跳过**）

> **MANDATORY** — 此步骤不可省略。MR/PR 创建成功后，必须立即执行 Pipeline 监控。

#### 1. 获取 Pipeline 状态

从 `glab mr create` 输出提取 MR_IID。

**GitLab**（使用 MR pipelines API，不要用 `pipelines?ref={branch}`）：
```bash
PROJECT_ID=$(glab api projects/$(python3 -c "import urllib.parse; print(urllib.parse.quote('${project_path}', safe=''))") --hostname {host} | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
glab api "projects/${PROJECT_ID}/merge_requests/${MR_IID}/pipelines?per_page=1" --hostname {host}
```

**GitHub**：`gh pr checks {PR_NUMBER} --repo {owner}/{repo}`

#### 2. 轮询状态

使用**单个前台 Bash 命令**执行轮询循环。参数：首次等待 15s，间隔 30s，最多 60 次（约 30 分钟）。

**GitLab 轮询脚本**（变量由调用方填充）：

```bash
PROJECT_ID="{project_id}"
MR_IID="{mr_iid}"
HOST="{host}"
MR_URL="{mr_url}"
BRANCH="{branch}"
TARGET="{target_branch}"

sleep 15

for i in $(seq 1 60); do
  RESULT=$(glab api "projects/${PROJECT_ID}/merge_requests/${MR_IID}/pipelines?per_page=1" \
    --hostname "$HOST" 2>/dev/null)

  PIPELINE_ID=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['id'] if d else '')" 2>/dev/null)
  STATUS=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['status'] if d else 'waiting')" 2>/dev/null)

  if [ -z "$PIPELINE_ID" ]; then
    echo "⏳ 等待 Pipeline 创建... (${i}/60)"
    sleep 30
    continue
  fi

  JOBS=$(glab api "projects/${PROJECT_ID}/pipelines/${PIPELINE_ID}/jobs" \
    --hostname "$HOST" 2>/dev/null | python3 -c "
import json, sys
jobs = json.load(sys.stdin)
parts = []
icons = {'success':'✅','failed':'❌','running':'🔄','pending':'⏳','canceled':'🚫','created':'⏳'}
for j in jobs:
    parts.append(f\"{j['name']} {icons.get(j['status'],'❓')}\")
print(' | '.join(parts))
" 2>/dev/null)

  ELAPSED=$((i * 30 + 15))
  MINS=$((ELAPSED / 60))
  SECS=$((ELAPSED % 60))
  echo "⏳ Pipeline #${PIPELINE_ID}: ${STATUS} (${MINS}m${SECS}s) — ${JOBS}"

  case "$STATUS" in
    success)
      echo "✅ Pipeline #${PIPELINE_ID} passed (${MINS}m${SECS}s)"
      echo "   MR: ${MR_URL}"
      osascript -e "display notification \"Pipeline passed ✅\" with title \"CI/CD\" subtitle \"${BRANCH} → ${TARGET}\"" 2>/dev/null
      exit 0
      ;;
    failed)
      echo "❌ Pipeline #${PIPELINE_ID} failed (${MINS}m${SECS}s)"
      echo "   MR: ${MR_URL}"
      osascript -e "display notification \"Pipeline failed ❌\" with title \"CI/CD\" subtitle \"${BRANCH}\"" 2>/dev/null
      exit 1
      ;;
    canceled)
      echo "🚫 Pipeline #${PIPELINE_ID} canceled"
      exit 0
      ;;
  esac
  sleep 30
done
echo "⏰ 超时（30 分钟），请手动检查: ${MR_URL}"
```

#### 3. 失败分析

**拉取失败 job 日志**：
- GitLab：`glab api "projects/${PROJECT_ID}/jobs/${JOB_ID}/trace"`
- GitHub：`gh run view {run_id} --log-failed`

**分类处理**：

| 类型 | 判断依据 | 处理 |
|------|----------|------|
| merge 冲突 | job 名含 `merge-to-` 或日志含 `CONFLICT` | → `Skill("git:fix-conflict", ...)` |
| lint 错误 | golangci-lint / eslint / flake8 | → 自动修复 |
| 单元测试失败 | go test / jest / pytest | → 自动修复 |
| 编译错误 | build failed / compilation error | → 给出修复建议 |
| 基础设施问题 | timeout / network / docker pull | → 建议 retry |
| 其他 | 无法分类 | → 输出日志摘要 |

**自动修复（仅 lint + test）**：修复代码但**不 commit**，通知用户确认后执行 `/git:commit-push` 重新提交。

## 安全限制

- **禁止** `--force` / `-f` 推送
- **禁止** `glab mr approve` / `glab mr merge`

---

## 参考文档

- [默认分支检测](../git-flow/snippets/01-detect-default-branch.md) - 三级检测详细逻辑
- [任务ID提取](../git-flow/snippets/02-extract-task-id.md) - 提取和转换规则
- [智能分支创建](../git-flow/snippets/04-branch-creation-smart.md) - 分析 diff 自动判断分支类型
- [Commit格式](../git-flow/snippets/03-commit-format.md) - 消息格式和示例
- [提交执行](../git-flow/snippets/05-commit-execution.md) - Stage和提交流程
