---
name: git-commit-push
description: 提交代码并推送到远程分支。当用户说"提交并推送"、"commit and push"、"push 一下"、"推送代码"时触发。
---

## Context

- 当前 git 状态：!`git status`
- 当前分支：!`git branch --show-current`
- Staged 和 unstaged 变更：!`git diff HEAD --stat`
- 最近提交历史：!`git log --oneline -5`
- no-ticket 配置：!`printenv GIT_ALLOW_NO_TICKET || echo true`

## Your Task

### 第一步：检查当前分支

**概要：** 检测默认分支并在必要时创建新分支

1. **检测默认分支**：使用三级检测方法（详见 [默认分支检测](../git-flow/snippets/01-detect-default-branch.md)）
   - 方法一：`git symbolic-ref refs/remotes/origin/HEAD`
   - 方法二：检查常见分支（main/master/develop）
   - 方法三：询问用户

2. **判断是否需要创建分支**：如果当前在默认分支，需要创建新的功能分支
   - 详细流程参见：[分支创建逻辑](../git-flow/snippets/04-branch-creation.md)

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

先输出：`💡 提示：如需跳过代码审查，可使用 --skip-code-review 参数`

然后调用：
```
Skill(skill: "git:code-reviewing", args: "review committed changes on current branch before push")
```

**审查结果处理**：
- 全部通过 → 自动继续推送
- 有 confirmed/uncertain 问题 → 逐条列出，让用户确认后再继续
- 有阻塞问题（🚫）→ 必须等待用户决策

### 第五步：推送到远程

```bash
git push
```

如果失败提示 "no upstream branch"：
```bash
git push -u origin $(git branch --show-current)
```

### 第六步：输出结果

```
✅ 提交并推送成功

分支：feat-TAP-85404-user-profile
Commit：feat(api): 新增用户资料接口 #TAP-85404
远程：origin/feat-TAP-85404-user-profile

下一步：
  - 使用 /git:commit-push-pr 命令创建 Merge Request
  - 或手动在 GitLab 中创建 MR
```

### 第七步：Pipeline Watch（仅已有 MR 时自动执行）

推送成功后，检查当前分支是否已有关联的 MR。

#### 1. 检查是否存在 MR

```bash
which glab && glab auth status
```

glab 不可用 → 跳过。可用则：

```bash
REMOTE_URL=$(git remote get-url origin)
BRANCH=$(git branch --show-current)
# 从 remote URL 提取 project_path 和 host
PROJECT_ID=$(glab api projects/$(python3 -c "import urllib.parse; print(urllib.parse.quote('${project_path}', safe=''))") --hostname {host} | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
MR_RESULT=$(glab api "projects/${PROJECT_ID}/merge_requests?source_branch=${BRANCH}&state=opened&per_page=1" --hostname {host})
MR_IID=$(echo "$MR_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['iid'] if d else '')" 2>/dev/null)
```

- `MR_IID` 为空 → `ℹ️ 当前分支无关联 MR，跳过 Pipeline 监控`
- `MR_IID` 有值 → 进入轮询

#### 2. 轮询 Pipeline 状态

使用后台 Bash 命令（`run_in_background=true`）轮询。参数：首次等待 15s，间隔 30s，最多 60 次（约 30 分钟）。

使用 MR pipelines API：`glab api "projects/${PROJECT_ID}/merge_requests/${MR_IID}/pipelines?per_page=1"`

- success → macOS 通知 + 结束
- failed → 拉取失败 job 日志，分析并自动修复（lint/test 类），或输出建议
- canceled/超时 → 结束

## 安全限制

- **禁止** `--force` / `-f` 推送
- **禁止** `glab mr approve` / `glab mr merge`

---

## 参考文档

- [默认分支检测](../git-flow/snippets/01-detect-default-branch.md) - 三级检测详细逻辑
- [任务ID提取](../git-flow/snippets/02-extract-task-id.md) - 提取和转换规则
- [分支创建](../git-flow/snippets/04-branch-creation.md) - 分支创建流程
- [Commit格式](../git-flow/snippets/03-commit-format.md) - 消息格式和示例
- [提交执行](../git-flow/snippets/05-commit-execution.md) - Stage和提交流程
