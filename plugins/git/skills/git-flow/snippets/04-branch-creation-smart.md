# 智能分支创建逻辑（commit-push-pr 专用）

本文档描述 `commit-push-pr` 命令专用的增强分支创建逻辑，包括自动判断分支类型。

## 前提条件

此逻辑仅在以下情况执行：
- 当前分支 == 默认分支（通过 [01-detect-default-branch.md](./01-detect-default-branch.md) 检测）
- 使用 `commit-push-pr` 命令

## 与基础版本的区别

相比 [04-branch-creation.md](./04-branch-creation.md)，本逻辑增加了：
- ✅ **智能判断分支类型**：自动分析 `git diff` 内容推荐分支前缀
- ✅ **更高准确性**：基于实际代码变更推荐，而非用户手动选择
- ✅ **用户确认机制**：自动推荐后仍可让用户确认或修改

## 执行流程

### 第一步：检查用户输入

与基础版本相同，检查用户消息中是否包含任务链接或任务 ID（详见 [04-branch-creation.md](./04-branch-creation.md#第一步检查用户输入)）

- **如果找到任务 ID**：继续第二步
- **如果没有任务 ID**：**中断命令**，提示用户提供

### 第二步：智能判断分支前缀类型

分析 `git diff --stat` 和 `git diff` 的内容，按**优先级**判断变更类型：

#### 优先级表

| 优先级 | 前缀 | 判断条件 |
|-------|------|---------|
| 1 | **docs/** | 仅修改文档文件（`*.md`, `*.txt`） |
| 2 | **test/** | 仅修改测试文件（`*_test.go`, `*.test.js`, `*_test.*`, `test_*`） |
| 3 | **fix/** | diff 中包含关键词："fix"、"修复"、"bug"、"error"、"issue" |
| 4 | **feat/** | 新增文件、或包含关键词："feat"、"feature"、"新增"、"add" |
| 5 | **refactor/** | 包含关键词："refactor"、"重构"、"rename" |
| 6 | **perf/** | 包含关键词："perf"、"performance"、"优化"、"optimize" |
| 7 | **chore/** | 配置文件（`*.json`, `*.yaml`, `*.yml`）、依赖更新、其他维护任务 |
| 8 | **revert/** | diff 中包含关键词："revert"、"回滚" |

#### 分析逻辑

**步骤 1：获取变更统计**
```bash
git diff --stat
```

分析输出，检查修改的文件类型：
- 如果**仅**修改 `.md` 或 `.txt` 文件 → `docs/`
- 如果**仅**修改测试文件 → `test/`

**步骤 2：获取详细 diff**
```bash
git diff
```

在 diff 内容中搜索关键词（大小写不敏感）：
1. 搜索 `fix|修复|bug|error|issue` → `fix/`
2. 搜索 `feat|feature|新增|add`（且有新增文件）→ `feat/`
3. 搜索 `refactor|重构|rename` → `refactor/`
4. 搜索 `perf|performance|优化|optimize` → `perf/`
5. 搜索 `revert|回滚` → `revert/`

**步骤 3：检查配置文件**
- 如果主要修改 `.json`、`.yaml`、`.yml`、`package.json`、`go.mod` 等配置文件 → `chore/`

**步骤 4：默认选择**
- 如果以上都不匹配 → `chore/`（默认）

#### Fallback：询问用户

如果自动判断失败或不确定，使用 `AskUserQuestion` 询问用户：

**问题**：检测到以下变更，请选择分支类型

**选项**（包含推荐）：
- **feat/**（如果检测到新增文件）
- **fix/**（如果检测到 bug 相关关键词）
- **refactor/**
- **docs/**
- **test/**
- **chore/**
- **perf/**

### 第三步：生成/确认分支描述（desc）

分支描述（desc）**不允许为空**。优先基于 `git diff --stat` / `git diff` 的分析结果自动生成一个英文短横线描述（生成失败再询问用户），再让用户确认或修改。

**自动生成策略（autoFromDiff）**：
- docs 变更优先：`update-doc` / `update-readme` / `update-api-doc`
- 仅注释变更：`add-comment`
- 关键词映射：`debug`→`debug`、`comment`→`comment`、`readme`→`readme` 等

**兜底询问（不可为空）**：如果无法自动生成，使用 `AskUserQuestion` 询问用户输入分支描述（英文短横线；不可为空）

### 第四步：构建分支名并转换任务 ID

**重要**：在构建分支名前，必须确保任务 ID 包含 `TAP-` 前缀

```bash
# 从飞书链接或用户输入提取的纯数字 ID
task_id="6579933216"  # 示例

# 立即转换为 TAP-xxx 格式
if [[ "$task_id" =~ ^[0-9]+$ ]]; then
  task_id="TAP-${task_id}"
fi

# 创建分支名（使用转换后的 task_id）
new_branch="${prefix}/${task_id}-${desc}"
# 结果示例：docs/TAP-6579933216-add-comment
```

**关键原因**：
1. 后续从分支名提取任务 ID 使用正则 `grep -oE 'TAP-[0-9]+'`
2. 如果分支名使用纯数字（如 `docs/6579933216-xxx`），后续**无法**从分支名提取任务 ID
3. 必须在创建分支前转换，确保分支名格式正确

**分支名格式**：`{prefix}/TAP-xxxxx-{desc}`（desc 不允许为空）

**示例**：
- `docs/TAP-6579933216-api-docs`
- `feat/TAP-85404-user-profile`
- `fix/TAP-85405-login-error`

#### 分支名长度限制（60 字符）

分支名总长度不得超过 60 个字符。构建完成后检查长度：
- **<= 60 字符**：直接使用
- **> 60 字符**：缩短 desc 部分，用更简洁的英文表达替代（如 `implement-user-authentication-service` → `impl-user-auth`），保持语义可理解，直到总长度 <= 60 字符。若仍超限，截断到最后一个完整单词（`-` 边界）

### 第五步：获取远程最新代码

```bash
git fetch origin
```

### 第六步：创建并切换到新分支

与基础版本相同，使用 `git checkout -b` 创建新分支（详见 [04-branch-creation.md](./04-branch-creation.md#第五步创建并切换到新分支)）

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

### 第七步：确认分支创建成功

创建成功后，显示确认信息（包含智能推荐的前缀）：

```
✅ 成功创建并切换到新分支

分支：docs/TAP-6579933216-api-docs
类型：docs（文档更新）- 智能推荐
基于：origin/main

现在可以开始开发，完成后此命令会自动创建 MR。
```

## 智能判断示例

### 示例 1：文档更新

**变更**：
```
 README.md           | 10 ++++++++--
 docs/api.md         |  5 +++++
```

**判断结果**：`docs/`
**原因**：仅修改 `.md` 文件

### 示例 2：Bug 修复

**diff 内容**：
```diff
-  if (token.isExpired()) {
+  if (token.isExpired() || token.expiresIn() < 300) {
     // 修复 token 过期问题
```

**判断结果**：`fix/`
**原因**：diff 中包含 "修复"、"过期问题" 关键词

### 示例 3：新功能

**变更**：
```
 A  src/services/user-profile.ts  | 50 +++++++++++++++++++++++
 M  src/api/routes.ts             |  3 ++
```

**判断结果**：`feat/`
**原因**：新增文件 `user-profile.ts`

### 示例 4：性能优化

**diff 内容**：
```diff
-  SELECT * FROM users WHERE id = ?
+  SELECT id, name, email FROM users WHERE id = ?
   // 优化查询性能，仅获取必要字段
```

**判断结果**：`perf/`
**原因**：diff 中包含 "优化"、"性能" 关键词

### 示例 5：配置文件更新

**变更**：
```
 package.json        |  2 +-
 .eslintrc.json      |  1 +
```

**判断结果**：`chore/`
**原因**：主要修改配置文件

## 使用场景

此智能分支创建逻辑**仅用于**：
- **commit-push-pr 命令**

**不用于**：
- commit 命令：使用基础版本 [04-branch-creation.md](./04-branch-creation.md)
- commit-push 命令：使用基础版本 [04-branch-creation.md](./04-branch-creation.md)

## 流程图

```
开始（当前在默认分支）
  ↓
检查用户输入中的任务链接/ID
  ├─ 找到 → 提取任务 ID（纯数字需转换为 TAP-xxx）
  └─ 未找到 → ❌ 中断命令
  ↓
分析 git diff --stat 和 git diff
  ├─ 仅文档文件 → 推荐 docs/
  ├─ 仅测试文件 → 推荐 test/
  ├─ 包含 fix 关键词 → 推荐 fix/
  ├─ 新增文件或 feat 关键词 → 推荐 feat/
  ├─ 包含 refactor 关键词 → 推荐 refactor/
  ├─ 包含 perf 关键词 → 推荐 perf/
  ├─ 配置文件 → 推荐 chore/
  └─ 无法判断 → 询问用户
  ↓
询问分支描述
  ↓
构建分支名：{prefix}/TAP-{id}-{desc}
（确保任务 ID 包含 TAP- 前缀）
  ↓
检查长度（> 60 字符？→ 缩短 desc 语义表达）
  ↓
git fetch origin
  ↓
git checkout -b <new-branch> origin/<default-branch>
  ├─ 成功 → ✅ 显示确认信息
  └─ 失败 → ❌ 显示错误和解决方案
```

## 关键差异总结

| 特性 | 基础版本 | 智能版本（本文档） |
|-----|---------|------------------|
| 分支类型判断 | ❌ 用户手动选择 | ✅ 自动分析 diff 推荐 |
| 准确性 | 依赖用户判断 | 基于实际代码变更 |
| 用户交互 | 必须选择类型 | 自动推荐 + 可确认 |
| 适用命令 | commit, commit-push | **仅** commit-push-pr |
| 复杂度 | 简单 | 中等 |
| 任务 ID 转换 | 支持 | **强制**（创建分支前必须转换） |
