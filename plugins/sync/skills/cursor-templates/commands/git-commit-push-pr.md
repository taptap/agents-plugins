---
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*), Bash(git push), Bash(git push -u:*), Bash(git push --set-upstream:*), Bash(git push origin:*), Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(git checkout:*), Bash(glab mr create:*), Bash(glab auth status), Bash(glab api:*), Bash(which glab), Bash(gh pr create:*), Bash(gh auth status), Bash(gh api:*), Bash(gh run:*), Bash(gh pr checks:*), Bash(which gh), Bash(sleep:*), Bash(osascript:*), Bash(printenv:*), Bash(echo:*), Bash(head:*), Bash(python3:*), Bash(cat:*), Bash(grep:*)
description: 提交代码、推送分支、创建 MR/PR 并监控 Pipeline 状态
---

## Context

- 当前 git 状态: !`git status`
- 当前分支: !`git branch --show-current`
- Staged 和 unstaged 变更: !`git diff HEAD --stat`
- 最近提交历史: !`git log --oneline -5`
- 远程分支: !`git branch -r | head -10`
- no-ticket 配置: !`printenv GIT_ALLOW_NO_TICKET || echo true`

## Your Task

### 第一步：检查并创建分支

**特殊功能：** 本命令包含智能分支类型判断

1. **检测默认分支**（详见 [默认分支检测](../rules/git-flow/snippets/01-detect-default-branch.md)）

2. **智能创建分支**（如需要）：
   - 使用增强的智能分支创建逻辑
   - 自动分析 `git diff` 判断分支类型（docs/test/fix/feat/refactor等）
   - 详细逻辑参见：[智能分支创建](../rules/git-flow/snippets/04-branch-creation-smart.md)

### 第二步：提取任务 ID

**三级优先级策略**（详见 [任务ID提取](../rules/git-flow/snippets/02-extract-task-id.md)）：

1. 从分支名提取：`git branch --show-current | grep -oE 'TAP-[0-9]+'`
2. 从用户输入提取（飞书/Jira链接、直接ID）
3. 询问用户

**关键点：** 纯数字ID必须转换为 `TAP-xxx` 格式

### 第三步：提交变更

标准提交流程（详见 [提交执行](../rules/git-flow/snippets/05-commit-execution.md)）

**Commit格式**详见 [Commit格式规范](../rules/git-flow/snippets/03-commit-format.md)

### 第四步：自动代码审查（push 前）

检查用户输入是否包含 `--skip-code-review` 参数。

**如果包含 `--skip-code-review`：**

输出以下提示后直接进入第五步：
```
⏭️ 已跳过代码审查（--skip-code-review）
```

**如果不包含（默认）：**

先输出提示：
```
💡 提示：如需跳过代码审查，可使用 --skip-code-review 参数
```

然后对当前分支上的已提交变更执行代码审查：

1. 获取变更范围：`git diff HEAD~1 --stat` 和 `git diff HEAD~1`
2. 逐文件审查，关注：Bug 风险、安全漏洞、性能问题、代码质量
3. 输出审查结果

**审查结果处理：**
- 全部通过 → 自动继续推送
- 有问题 → 列出问题，让用户确认处理方式（修复 / 忽略），全部确认后再继续

### 第五步：推送并创建 MR

1. **检测 glab 是否可用**：
   ```bash
   which glab && glab auth status
   ```

   **安全限制（严格禁止）：**
   - `glab mr approve` - 禁止自动审批
   - `glab mr merge` - 禁止自动合并

2. **生成 MR 标题和描述**：

   **MR Title：**
   - 单个 commit：使用 commit 标题
   - 多个 commit：使用第一个 commit 标题或汇总

   **MR Description：**
   从 commit message 提取并汇总（使用 `git log origin/master..HEAD --pretty=format:"%B" --reverse`）：

   ```markdown
   ## 改动内容
   - [汇总所有 commit 的改动点]

   ## 影响面
   - [汇总所有 commit 的影响面]
   ```

   **关键规则：** MR description 必须从 commit message 提取，保持一致性

3. **合成最终 MR Description（模板优先）**：

   - 若仓库存在 MR 模板：读取模板并将“汇总后的 commit 正文”填充到模板的 `## Description` 区块
     - 兼容模板文件：`.gitlab/merge_request_templates/default.md`（优先）与 `.gitlab/merge_request_templates/Default.md`
     - 填充规则：替换 `## Description` 与下一个 `## ` 标题之间的所有内容（不包含下一个标题行）
   - 若仓库不存在 MR 模板：最终 MR description 直接使用“汇总后的 commit 正文”
   - 不再使用 `glab mr create --fill`

4. **推送并创建 MR**：

   **如果 glab 可用：**

   a. 推送分支：
   ```bash
   git push -u origin $(git branch --show-current)
   ```

   b. 创建 MR（模板优先；无模板则直接使用汇总正文）：

   ```bash
   TEMPLATE_FILE=""
   if [ -f ".gitlab/merge_request_templates/default.md" ]; then
     TEMPLATE_FILE=".gitlab/merge_request_templates/default.md"
   elif [ -f ".gitlab/merge_request_templates/Default.md" ]; then
     TEMPLATE_FILE=".gitlab/merge_request_templates/Default.md"
   fi

   COMMIT_SUMMARY="$(cat <<'EOF'
   ## 改动内容
   - 改动点 1

   ## 影响面
   - 影响的模块/功能
   EOF
   )"

   if [ -n "$TEMPLATE_FILE" ]; then
     MR_DESC="$(TEMPLATE_FILE="$TEMPLATE_FILE" COMMIT_SUMMARY="$COMMIT_SUMMARY" python3 - <<'PY'
   import os
   import re

   template_path = os.environ["TEMPLATE_FILE"]
   summary = os.environ["COMMIT_SUMMARY"].rstrip("\n")

   with open(template_path, "r", encoding="utf-8") as f:
     template = f.read()

   header_re = re.compile(r"(?m)^## Description\\s*$")
   m = header_re.search(template)

   block = f"\\n\\n{summary}\\n\\n"

   if not m:
     out = f"## Description{block}" + template.lstrip("\\n")
   else:
     start = m.end()
     rest = template[start:]
     m2 = re.search(r"(?m)^##\\s+.+$", rest)
     end = start + (m2.start() if m2 else len(rest))
     out = template[:start] + block + template[end:]

   print(out, end="")
   PY
   )"
   else
     MR_DESC="$COMMIT_SUMMARY"
   fi

   glab mr create \
     --title "$(git log -1 --pretty=%s)" \
     --description "$MR_DESC" \
     --yes --remove-source-branch
   ```

   **如果 glab 不可用（fallback）：**
   ```bash
   git push -u origin $(git branch --show-current) -o merge_request.create
   ```

### 第六步：输出结果并打开浏览器

1. 显示推送成功信息
2. 显示 GitLab/GitHub 返回的 MR/PR 链接
3. 显示任务工单链接（如有）
4. 使用系统默认浏览器打开 MR/PR 链接

### 第七步：Pipeline Watch（MR/PR 创建后自动执行）

MR/PR 创建成功后，自动进入 Pipeline 监控模式。根据第五步检测到的平台（GitLab/GitHub）选择对应 API。

#### 1. 获取 Pipeline/Check 状态

从第五步的 `glab mr create` 或 `gh pr create` 输出中提取 MR/PR 编号（`MR_IID` / `PR_NUMBER`）。

**GitLab**（glab）：

> **重要**：MR pipeline 的 ref 是 `refs/merge-requests/{iid}/head`，不是分支名。
> 使用 `pipelines?ref={branch}` **查不到** MR pipeline。必须使用 MR pipelines API。

```bash
# 获取 project_id
PROJECT_ID=$(glab api projects/$(python3 -c "import urllib.parse; print(urllib.parse.quote('${project_path}', safe=''))") --hostname {host} | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 通过 MR API 获取关联的 pipeline（推荐，可查到 merge_request_event 类型的 pipeline）
glab api "projects/${PROJECT_ID}/merge_requests/${MR_IID}/pipelines?per_page=1" \
  --hostname {host}
```

**GitHub**（gh）：
```bash
# 获取 PR 关联的 check runs
gh pr checks {PR_NUMBER} --repo {owner}/{repo}
```

#### 2. 轮询状态

使用 **单个 Bash 命令** 执行轮询循环。
**禁止**用多个独立的 `sleep N && 查询` 命令手动轮询 — 必须使用下方的循环脚本。

**轮询参数**：
- 首次查询前等待：15 秒（pipeline 创建有延迟）
- 轮询间隔：30 秒
- 最大轮询次数：60 次（约 30 分钟）

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
      echo ""
      echo "✅ Pipeline #${PIPELINE_ID} passed (${MINS}m${SECS}s)"
      echo "   MR: ${MR_URL}"
      osascript -e "display notification \"Pipeline passed ✅\" with title \"CI/CD\" subtitle \"${BRANCH} → ${TARGET}\"" 2>/dev/null
      exit 0
      ;;
    failed)
      echo ""
      echo "❌ Pipeline #${PIPELINE_ID} failed (${MINS}m${SECS}s)"
      echo "   MR: ${MR_URL}"
      osascript -e "display notification \"Pipeline failed ❌\" with title \"CI/CD\" subtitle \"${BRANCH}\"" 2>/dev/null
      exit 1
      ;;
    canceled)
      echo ""
      echo "🚫 Pipeline #${PIPELINE_ID} canceled"
      exit 0
      ;;
  esac

  sleep 30
done

echo "⏰ 超时（30 分钟），请手动检查: ${MR_URL}"
```

**GitHub 轮询**：同理，用 `gh pr checks` 替代 glab api。

**轮询结束后处理**：
- 脚本 exit 0（success/canceled/超时）→ 结束
- 脚本 exit 1（failed）→ 进入步骤 3（失败分析）

#### 3. 失败分析

**3a. 拉取失败 job 日志**

**GitLab**：
```bash
glab api "projects/${PROJECT_ID}/pipelines/${PIPELINE_ID}/jobs" --hostname {host}
glab api "projects/${PROJECT_ID}/jobs/${JOB_ID}/trace" --hostname {host}
```

**GitHub**：
```bash
gh run view {run_id} --repo {owner}/{repo} --log-failed
```

**3b. 分析失败原因并分类**

| 类型 | 判断依据 | 处理 |
|------|----------|------|
| lint 错误 | golangci-lint / eslint / flake8 等输出 | → 自动修复 |
| 单元测试失败 | `go test` / jest / pytest 等输出 | → 自动修复 |
| 编译错误 | `build failed` / `compilation error` | → 分析并给出修复建议 |
| 基础设施问题 | timeout / network / docker pull | → 通知用户，建议 retry |
| 其他 | 无法分类 | → 输出日志摘要，让用户判断 |

**3c. 自动修复（仅 lint + test 类错误）**

- 读取错误日志，定位具体文件和行号
- 读取源文件，修复问题
- **不 commit** — 修复完毕后通知用户确认

**3d. 非自动修复类型**

终端输出失败日志摘要 + 修复建议。

---

## 参考文档

- [Git 工作流规范](../rules/git-flow.mdc) - 完整规范
- [默认分支检测](../rules/git-flow/snippets/01-detect-default-branch.md)
- [智能分支创建](../rules/git-flow/snippets/04-branch-creation-smart.md) - 本命令特有
- [任务ID提取](../rules/git-flow/snippets/02-extract-task-id.md)
- [Commit格式](../rules/git-flow/snippets/03-commit-format.md)
- [提交执行](../rules/git-flow/snippets/05-commit-execution.md)
