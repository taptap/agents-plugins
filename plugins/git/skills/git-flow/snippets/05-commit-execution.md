# 提交执行流程

本文档描述如何 stage 文件并执行 commit 操作，包括敏感文件的排除规则。

## 执行步骤

### 第一步：检查敏感文件

在 stage 文件前，必须检查是否包含敏感文件。

#### 敏感文件列表

| 文件类型 | 示例 | 原因 |
|---------|------|------|
| 环境变量文件 | `.env`, `.env.local`, `.env.production` | 包含 API keys, 数据库密码等 |
| 凭证文件 | `credentials.json`, `service-account.json` | 包含认证凭证 |
| 配置文件（含密钥） | `config/secrets.yaml`, `*secret*`, `*password*`, `*token*` | 包含敏感配置 |
| 私钥文件 | `*.pem`, `*.key`, `id_rsa` | SSH/SSL 私钥 |

#### 检测方法

使用 `git status` 和 `git diff --name-only` 检查待提交文件：

```bash
# 检查未追踪的文件
git status --porcelain | grep '^??' | awk '{print $2}'

# 检查已修改的文件
git status --porcelain | grep '^ M' | awk '{print $2}'
```

**检测规则**：
- 文件名匹配：`.env*`, `*credentials*`, `*secret*`, `*password*`, `*token*`, `*.pem`, `*.key`
- 目录匹配：`secrets/`, `credentials/`

#### 处理策略

**如果检测到敏感文件**：

1. **警告用户**：
   ```
   ⚠️  检测到可能包含敏感信息的文件：

   - .env
   - config/secrets.yaml

   这些文件可能包含：
   - API keys
   - 数据库密码
   - 认证 token
   - 其他敏感凭证

   是否确认提交这些文件？
   ```

2. **询问用户**：
   使用 `AskUserQuestion` 询问：
   - **选项 1（推荐）**：排除这些文件，仅提交其他文件
   - **选项 2**：确认提交（用户需明确确认）

3. **排除敏感文件**：
   如果用户选择排除，使用 `git add` 时明确指定文件，避免使用 `git add .`

### 第二步：Stage 文件

根据第一步的结果，选择合适的 stage 方法。

#### 方法 A：Stage 所有文件（无敏感文件）

```bash
git add .
```

**适用场景**：
- 未检测到敏感文件
- 所有变更都应被提交

#### 方法 B：选择性 Stage（排除敏感文件）

```bash
# 仅 stage 特定文件
git add src/
git add package.json
git add README.md
```

**适用场景**：
- 检测到敏感文件且用户选择排除
- 需要保留某些文件不提交

#### 方法 C：Stage 部分变更

对于大型变更，可以分批提交：

```bash
# Stage 特定目录
git add src/components/
git add src/services/

# 或 Stage 特定文件类型
git add "*.ts"
git add "*.tsx"
```

### 第三步：验证 Staged 内容

在执行 commit 前，验证 staged 的内容是否正确：

```bash
# 查看 staged 文件列表
git diff --cached --name-only

# 查看 staged 内容摘要
git diff --cached --stat
```

**检查项**：
- ✅ 所有需要提交的文件都已 staged
- ✅ 没有不应提交的文件被 staged
- ✅ 敏感文件已被排除

### 第四步：生成 Commit 消息

根据以下规则生成符合规范的 commit 消息（详见 [03-commit-format.md](./03-commit-format.md)）：

#### 标题生成
```
type(scope): 中文描述 #TASK-ID
```

- **type**：根据变更内容确定（feat/fix/refactor/docs/test/chore/perf）
- **scope**：可选，影响的模块（如 api, auth, ui）
- **中文描述**：分析 `git diff` 内容，概括主要改动
- **TASK-ID**：使用第二步提取的任务 ID

#### Body 生成

分析 `git diff` 内容，生成详细的改动说明：

```
## 改动内容
- [从 diff 中提取的具体改动点]
- [每个改动应清晰、具体]

## 影响面
- [说明影响的模块、功能]
- [评估向后兼容性]
- [风险评估（如有）]

Generated-By: Claude Code <https://claude.ai/code>

Co-Authored-By: Claude <noreply@anthropic.com>
```

**验证清单（提交前必须确认）：**
- [ ] `## 改动内容` 章节存在且非空
- [ ] `## 影响面` 章节存在且非空
- [ ] 两行签名格式正确（Generated-By 在前，Co-Authored-By 在后）
- [ ] 签名不包含模型版本号（禁止 Claude Sonnet 4.5、Claude Opus 4.5 等）

### 第五步：执行 Commit

使用 heredoc 格式传递 commit 消息，确保格式正确：

```bash
git commit -m "$(cat <<'EOF'
feat(api): 新增用户资料接口 #TAP-85404

## 改动内容
- 实现 GET /api/v1/users/:id 接口
- 添加用户资料数据验证逻辑
- 实现缓存机制提升性能

## 影响面
- 新增接口，不影响现有功能
- 向后兼容
- 数据库查询增加，需关注性能

Generated-By: Claude Code <https://claude.ai/code>

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

**关键点**：
- 使用 `<<'EOF'` 而非 `<<EOF`，避免变量展开
- 确保格式严格遵循规范（空行位置、签名格式）

### 第六步：验证 Commit 成功

执行 commit 后，验证是否成功：

```bash
# 查看最新 commit
git log -1 --pretty=format:"%h - %s%n%b"

# 验证 commit 消息格式
git log -1 --pretty=format:"%s" | grep -E '^(feat|fix|docs|style|refactor|test|chore|perf|revert)(\(.+\))?:.+#(TAP-\d+|no-ticket)$'
```

**成功指标**：
- ✅ Commit 已创建（git log 显示新 commit）
- ✅ Commit 消息格式正确（通过正则验证）
- ✅ 工作区变为干净状态（git status 无待提交变更）

### 第七步：输出结果

显示提交成功信息：

```
✅ 提交成功

Commit：a1b2c3d
标题：feat(api): 新增用户资料接口 #TAP-85404
分支：feat/TAP-85404-user-profile

下一步：
  - 使用 /git:commit-push 推送到远程
  - 或使用 /git:commit-push-pr 创建 Merge Request
```

## 错误处理

### 常见错误

#### 1. Nothing to commit

**错误信息**：
```
On branch feat/TAP-85404-user-profile
nothing to commit, working tree clean
```

**原因**：没有变更需要提交

**解决方案**：
- 检查是否有文件修改：`git status`
- 确认文件已保存
- 检查是否遗漏 `git add`

#### 2. Commit 消息格式不符合规范

**错误信息**（远程 hook 拒绝）：
```
remote: error: commit message does not follow the required format
remote: expected: type(scope): 中文描述 #TASK-ID
```

**原因**：Commit 消息不符合正则验证

**解决方案**：
- 使用 `git commit --amend` 修改消息
- 确保格式：`type(scope): 中文描述 #TAP-xxxxx`
- 确保任务 ID 格式正确（`TAP-\d+` 或 `no-ticket`）

#### 3. 包含二进制文件或大文件

**警告信息**：
```
warning: adding large file: dist/bundle.js (5.2 MB)
```

**解决方案**：
- 检查是否应提交该文件
- 考虑使用 `.gitignore` 排除
- 对于必须提交的大文件，使用 Git LFS

## 最佳实践

### 1. 原子性提交
每次 commit 应该是一个独立、完整的变更单元：
- ✅ 一次 commit 完成一个功能
- ✅ 一次 commit 修复一个 bug
- ❌ 不要在一次 commit 中混合多个不相关的变更

### 2. 有意义的提交消息
- ✅ 描述 "为什么" 而不仅是 "是什么"
- ✅ 使用主动语态："新增功能" 而非 "功能被新增"
- ❌ 避免无意义的描述："更新代码"、"修改文件"

### 3. 频繁提交
- ✅ 完成一个小功能就提交
- ✅ 保持 commit 历史清晰
- ❌ 不要积累大量变更后一次性提交

### 4. 提交前测试
- ✅ 确保代码可以编译/运行
- ✅ 运行相关测试
- ❌ 不要提交未经测试的代码

## 使用场景

此提交执行流程用于所有 git 命令：
- commit 命令
- commit-push 命令（第三步）
- commit-push-pr 命令（第三步）

## 流程图

```
开始
  ↓
检查敏感文件
  ├─ 检测到 → 警告用户 → 询问是否排除
  │              ├─ 排除 → 选择性 stage
  │              └─ 确认提交 → stage 所有文件
  └─ 未检测到 → stage 所有文件
  ↓
验证 staged 内容（git diff --cached）
  ↓
生成 commit 消息
  ├─ 分析 git diff 确定 type
  ├─ 概括改动生成标题
  └─ 提取详细改动生成 body
  ↓
执行 git commit
  ├─ 成功 → 验证 commit → ✅ 输出结果
  └─ 失败 → ❌ 显示错误和解决方案
```
