# 基础分支创建逻辑

本文档描述在默认分支时如何创建新的功能分支。

## 前提条件

此逻辑仅在以下情况执行：
- 当前分支 == 默认分支（通过 [01-detect-default-branch.md](./01-detect-default-branch.md) 检测）
- 判断逻辑：`git branch --show-current` 的输出等于检测到的默认分支名

## 执行流程

### 第一步：检查用户输入

检查用户消息中是否包含任务链接或任务 ID：

#### 支持的格式
1. **飞书链接**：`https://*.feishu.cn/**`
   - 示例：`https://project.feishu.cn/pojq34/story/detail/6579933216`

2. **Jira 链接**：`https://xindong.atlassian.net/browse/TAP-xxxxx`
   - 示例：`https://xindong.atlassian.net/browse/TAP-85404`

3. **直接的任务 ID**：`TAP-xxxxx`
   - 示例：用户输入 "提交代码 TAP-85404"

#### 处理结果
- **如果找到任务 ID**：提取并转换（纯数字需补充 `TAP-` 前缀），继续第二步
- **如果没有任务 ID**：**中断命令**，提示用户提供任务链接/ID

**中断提示示例**：
```
❌ 无法创建分支

当前在默认分支（main），需要创建新的功能分支。
但未检测到任务 ID 或任务链接。

请提供以下任一信息：
  - 飞书任务链接：https://project.feishu.cn/xxx
  - Jira 任务链接：https://xindong.atlassian.net/browse/TAP-xxxxx
  - 任务 ID：TAP-xxxxx

提供任务信息后，重新运行此命令。
```

### 第二步：询问分支前缀和描述

#### 询问分支前缀（如果未自动判断）

使用 `AskUserQuestion` 询问用户选择分支前缀：

**问题**：这是什么类型的变更？

**选项**：
- **feat/**：新功能开发
- **fix/**：Bug 修复
- **refactor/**：代码重构
- **docs/**：文档更新
- **test/**：测试相关
- **chore/**：维护任务
- **perf/**：性能优化

#### 生成/确认分支描述（desc）

分支描述（desc）**不允许为空**。当用户未提供描述时，优先从本次变更自动生成一个英文短横线描述（生成失败再询问用户）。

**自动生成策略（autoFromDiff）**：
1. 获取变更文件列表：`git diff --name-only HEAD`（或基于实际比较范围）  
2. 结合变更类型与文件名生成 desc（英文短横线）：  
   - docs 变更优先：`update-doc` / `update-readme` / `update-api-doc`  
   - 仅注释变更：`add-comment`  
   - 关键词映射：`debug`→`debug`、`comment`→`comment`、`readme`→`readme` 等  
3. 若无法生成（例如无法获取 diff、文件名过于复杂）：进入“询问用户输入”

**询问用户输入（兜底）**：
使用 `AskUserQuestion` 询问用户输入分支描述（英文短横线）：

**问题**：请输入分支描述（英文，使用短横线分隔单词；不可为空）

**示例**：
- `user-profile`
- `fix-login-error`
- `add-unit-tests`

### 第三步：构建分支名

分支名格式：`{prefix}/{TASK-ID}-{desc}`（desc 不允许为空）

**示例**：
- `feat/TAP-85404-user-profile`
- `fix/TAP-85405-login-error`
- `docs/TAP-6579933216-update-doc`

**关键**：任务 ID 必须包含 `TAP-` 前缀（纯数字 ID 必须在此之前已转换）

### 第四步：获取远程最新代码

在创建分支前，先获取远程仓库的最新代码：

```bash
git fetch origin
```

**目的**：确保新分支基于最新的远程默认分支代码

### 第五步：创建并切换到新分支

使用 `git checkout -b` 基于远程默认分支创建新分支：

```bash
if ! git checkout -b "$new_branch" "origin/$default_branch"; then
  echo ""
  echo "❌ 创建分支失败"
  echo ""
  echo "💡 检测到本地有未提交的修改与远程代码冲突"
  echo ""
  echo "请选择以下方式之一处理："
  echo "  1. 提交修改：git add . && git commit -m \"描述\""
  echo "  2. 暂存修改：git stash"
  echo "  3. 放弃修改：git checkout -- <file>"
  echo ""
  echo "处理完成后，重新运行此命令创建分支。"
  exit 1
fi
```

#### 错误处理

**常见失败原因**：
1. 本地有未提交的修改与远程代码冲突
2. 分支名已存在
3. 网络问题导致 fetch 失败

**解决方案**：
1. 提交当前修改：`git add . && git commit -m "描述"`
2. 暂存当前修改：`git stash`
3. 放弃当前修改：`git checkout -- <file>`
4. 删除已存在的分支：`git branch -D <branch-name>`

### 第六步：确认分支创建成功

创建成功后，显示确认信息：

```
✅ 成功创建并切换到新分支

分支：feat/TAP-85404-user-profile
基于：origin/main

现在可以开始开发，完成后使用以下命令提交：
  /git:commit               - 仅提交
  /git:commit-push          - 提交并推送
  /git:commit-push-pr       - 提交、推送并创建 MR
```

## 使用场景

此基础分支创建逻辑用于：
- **commit 命令**：当在默认分支时创建新分支
- **commit-push 命令**：当在默认分支时创建新分支

**不用于**：
- **commit-push-pr 命令**：使用增强的 [04-branch-creation-smart.md](./04-branch-creation-smart.md) 逻辑

## 与智能分支创建的区别

| 特性 | 基础版本 | 智能版本 |
|-----|---------|---------|
| 自动判断分支类型 | ❌ 需要询问用户 | ✅ 分析 git diff 自动判断 |
| 分支前缀选择 | 用户手动选择 | 智能推荐 + 用户确认 |
| 使用命令 | commit, commit-push | commit-push-pr |
| 复杂度 | 简单 | 中等 |

## 流程图

```
开始（当前在默认分支）
  ↓
检查用户输入中的任务链接/ID
  ├─ 找到 → 提取任务 ID（纯数字需转换）
  └─ 未找到 → ❌ 中断命令，提示用户
  ↓
询问分支前缀（feat/fix/refactor...）
  ↓
询问分支描述
  ↓
构建分支名：{prefix}/{TAP-ID}-{desc}
  ↓
git fetch origin
  ↓
git checkout -b <new-branch> origin/<default-branch>
  ├─ 成功 → ✅ 显示确认信息
  └─ 失败 → ❌ 显示错误和解决方案
```
