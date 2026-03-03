---
allowed-tools: Bash(git add:*), Bash(git status:*), Bash(git commit:*), Bash(git push), Bash(git push -u:*), Bash(git push --set-upstream:*), Bash(git push origin:*), Bash(git diff:*), Bash(git log:*), Bash(git branch:*), Bash(printenv:*), Bash(echo:*), Bash(grep:*)
description: 提交代码并推送到远程分支
---

## Context

- 当前 git 状态: !`git status`
- 当前分支: !`git branch --show-current`
- Staged 和 unstaged 变更: !`git diff HEAD --stat`
- 最近提交历史: !`git log --oneline -5`
- no-ticket 配置: !`printenv GIT_ALLOW_NO_TICKET || echo true`

## Your Task

### 第一步：检查当前分支

**概要：** 检测默认分支并在必要时创建新分支

1. **检测默认分支**（详见 [默认分支检测](../rules/git-flow/snippets/01-detect-default-branch.md)）
2. **创建新分支**（如需要，详见 [分支创建](../rules/git-flow/snippets/04-branch-creation.md)）

### 第二步：提取任务 ID

**三级优先级策略**（详见 [任务ID提取](../rules/git-flow/snippets/02-extract-task-id.md)）：

1. 从分支名提取：`git branch --show-current | grep -oE 'TAP-[0-9]+'`
2. 从用户输入提取（飞书/Jira链接、直接ID）
3. 询问用户

**关键点：** 纯数字ID必须转换为 `TAP-xxx` 格式

### 第三步：提交变更

按照标准流程提交变更（详见 [提交执行](../rules/git-flow/snippets/05-commit-execution.md)）

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

### 第五步：推送到远程

检查并推送分支：

```bash
git branch --show-current
git push
```

**处理 upstream 未设置的情况：**
- 如果 push 失败并提示 "no upstream branch"
- 自动使用：`git push -u origin <current-branch>`

### 第六步：输出结果

显示执行结果：

```
✅ 提交并推送成功

分支: feat-TAP-85404-user-profile
Commit: feat(api): 新增用户资料接口 #TAP-85404
远程: origin/feat-TAP-85404-user-profile

下一步：
  - 使用 /git:commit-push-pr 命令创建 Merge Request
  - 或手动在 GitLab 中创建 MR
```

---

## 参考文档

- [Git 工作流规范](../rules/git-flow.mdc) - 完整规范
- [默认分支检测](../rules/git-flow/snippets/01-detect-default-branch.md)
- [任务ID提取](../rules/git-flow/snippets/02-extract-task-id.md)
- [分支创建](../rules/git-flow/snippets/04-branch-creation.md)
- [Commit格式](../rules/git-flow/snippets/03-commit-format.md)
- [提交执行](../rules/git-flow/snippets/05-commit-execution.md)
