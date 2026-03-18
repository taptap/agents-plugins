---
name: git-commit
description: 创建符合规范的 git commit，自动从分支名提取 Task ID。当用户说"帮我提交"、"commit"、"提交代码"、"commit 一下"时触发。
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

**关键点：** 纯数字ID必须转换为 `TAP-xxx` 格式

### 第三步：提交变更

**执行流程：**

1. 分析 `git diff` 确定 commit type（feat/fix/refactor等）
2. 使用提取的任务 ID
3. 生成符合规范的提交信息（格式详见 [Commit格式](../git-flow/snippets/03-commit-format.md)）
4. Stage文件并commit（详见 [提交执行](../git-flow/snippets/05-commit-execution.md)）

**Commit格式速览：**
```
type(scope): 中文描述 #TASK-ID

## 改动内容
- 列出主要改动点

## 影响面
- 说明影响的模块、功能

Generated-By: Claude Code <https://claude.ai/code>

Co-Authored-By: Claude <noreply@anthropic.com>
```

**必填项验证：** `## 改动内容` 和 `## 影响面` 两个章节必须填写，缺一不可。

---

## 参考文档

- [默认分支检测](../git-flow/snippets/01-detect-default-branch.md) - 三级检测详细逻辑
- [任务ID提取](../git-flow/snippets/02-extract-task-id.md) - 提取和转换规则
- [分支创建](../git-flow/snippets/04-branch-creation.md) - 分支创建流程
- [Commit格式](../git-flow/snippets/03-commit-format.md) - 消息格式和示例
- [提交执行](../git-flow/snippets/05-commit-execution.md) - Stage和提交流程
