# quality Plugin

> AI 驱动的代码质量检查插件，支持多语言、多维度、高并行的自动化代码审查

## 简介

`quality` 插件为 Claude Code 提供智能代码审查能力，使用 **9 个并行 AI Agent** 对代码变更进行全方位检查。通过置信度评分和冗余确认机制，有效减少误报和漏报。

### 核心特性

- **🚀 高性能并行架构**: 9 个 Agent 同时执行，审查速度 ≈ 单个最慢 Agent 的时间
- **🎯 置信度过滤**: 基于 0-100 评分，阈值 80，自动过滤低置信度问题
- **🔄 冗余确认机制**: 每个维度 2 个 Agent 独立审查，同时发现的问题置信度 +20
- **🌐 多语言支持**: 支持 Go/Java/Python/Kotlin/Swift/TypeScript 等语言
- **📋 智能规范检查**: 自动检测项目中的 CLAUDE.md/CONTRIBUTING.md，无则跳过
- **🔍 四维度全覆盖**: Bug 检测、代码质量、安全检查、性能分析

## 架构设计

### 9 Agent 并行架构

```
                                /review 命令
                                      |
                    +-----------------+-----------------+
                    |                 |                 |
            Pre-check         Context Collection   Parallel Review
                |                     |                 |
                |                     |        +--------+--------+
                |                     |        |                 |
                |                     |    规范检查(可选)   4 维度并行
                |                     |        |                 |
                |                     |  project-standards   Bug × 2
                |                     |    -reviewer        质量 × 2
                |                     |                     安全 × 2
                |                     |                     性能 × 2
                |                     |                        |
                +---------------------+------------------------+
                                      |
                            Verification & Report
                                      |
                          终端输出 / GitLab MR 评论
```

### Agent 职责分工

| Agent | 模型 | 职责 | 审查重点 |
|-------|------|------|---------|
| **规范检查（可选）** | | | |
| project-standards-reviewer | Sonnet 4.5 | 项目规范检查 | CLAUDE.md/CONTRIBUTING.md 规范遵循 |
| **Bug 检测（2× 冗余）** | | | |
| bug-detector-1 | Opus 4.5 | Bug 检测 #1 | 逻辑错误、nil/null 指针、资源泄漏、死锁 |
| bug-detector-2 | Opus 4.5 | Bug 检测 #2 | 同上，独立分析减少漏报 |
| **代码质量（2× 冗余）** | | | |
| code-quality-analyzer-1 | Sonnet 4.5 | 代码质量 #1 | 可读性、命名规范、代码结构、复杂度 |
| code-quality-analyzer-2 | Sonnet 4.5 | 代码质量 #2 | 同上，独立分析减少漏报 |
| **安全检查（2× 冗余）** | | | |
| security-analyzer-1 | Opus 4.5 | 安全检查 #1 | SQL 注入、XSS、敏感信息泄漏、弱加密 |
| security-analyzer-2 | Opus 4.5 | 安全检查 #2 | 同上，独立分析减少漏报 |
| **性能分析（2× 冗余）** | | | |
| performance-analyzer-1 | Sonnet 4.5 | 性能分析 #1 | N+1 查询、循环优化、内存分配、算法复杂度 |
| performance-analyzer-2 | Sonnet 4.5 | 性能分析 #2 | 同上，独立分析减少漏报 |

### 置信度评分机制

```
基础置信度（0-100）
  ↓
判断是否有冗余确认
  ↓ 是
+20 冗余加成
  ↓
过滤阈值：80
  ↓
≥80: 高置信度（直接报告）
60-79: 中等置信度（标记需人工确认）
<60: 自动过滤
```

**冗余加成规则**：
- bug-detector-1 + bug-detector-2 都发现 → +20
- code-quality-analyzer-1 + code-quality-analyzer-2 都发现 → +20
- security-analyzer-1 + security-analyzer-2 都发现 → +20
- performance-analyzer-1 + performance-analyzer-2 都发现 → +20

## 快速开始

### 安装

插件会自动加载（通过 marketplace.json），无需手动安装。

### 基础使用

#### 1. 审查当前分支的变更

```bash
# 在项目根目录
/review
```

这将自动检测主分支（main/master）并审查当前分支的所有变更。

#### 2. 审查特定 Merge Request

```bash
/review --mr 123
```

#### 3. 审查特定文件

```bash
/review app/regulation/internal/service/consumemessage/consume.go
```

### 使用示例

#### 场景 1: 日常代码审查（Go 项目）

```bash
$ /review

# 🔍 代码审查报告

## 📊 总览

- **审查范围**: feat-TAP-85924-ai-llm-channel-optimize → master
- **变更文件**: 5 个文件
- **涉及语言**: Go
- **发现问题**: 3 个（高置信度：2 个）
- **审查维度**: Bug 检测、代码质量、安全检查、性能分析

---

## 🐛 Bug 检测 (Bug Detection)

### Go

#### ⚠️ High Confidence (≥80)

**app/regulation/internal/service/consumemessage/consume.go:45** `90/100`
```go
result, _ := db.Query("SELECT * FROM users WHERE id = ?", userID)
```
**问题**: 忽略了数据库查询的错误返回值，可能导致程序在数据库故障时崩溃
**建议**: 始终检查并处理 error 返回值
```go
result, err := db.Query("SELECT * FROM users WHERE id = ?", userID)
if err != nil {
    return fmt.Errorf("查询用户失败: %w", err)
}
defer result.Close()
```
**检测来源**: bug-detector-1 + bug-detector-2（冗余确认）

---

## ⚡ 性能分析 (Performance Analysis)

### Go

#### ⚠️ High Confidence (≥80)

**app/regulation/internal/service/consumemessage/consume.go:78** `85/100`
```go
for _, user := range users {
    db.Query("SELECT * FROM orders WHERE user_id = ?", user.ID)
}
```
**问题**: N+1 查询问题，循环中执行数据库查询会导致性能瓶颈
**影响**: 当用户数量为 1000 时，将执行 1001 次查询（1 + 1000）
**建议**: 使用 IN 查询或 JOIN 一次性获取所有数据
```go
userIDs := make([]int, len(users))
for i, user := range users {
    userIDs[i] = user.ID
}
// 使用 IN 查询
query := "SELECT * FROM orders WHERE user_id IN (?)"
db.Query(query, userIDs)
```
**检测来源**: performance-analyzer-1 + performance-analyzer-2（冗余确认）

---

## ✅ 审查结论

### 高优先级修复（置信度 ≥80）
- [ ] consume.go:45 - 未检查数据库查询错误
- [ ] consume.go:78 - N+1 查询性能问题

### 统计信息
- **Bug 检测**: 1 个问题（高置信度：1）
- **代码质量**: 0 个问题
- **安全检查**: 0 个问题
- **性能分析**: 1 个问题（高置信度：1）
```

#### 场景 2: 跨语言项目审查

```bash
$ /review

# 审查范围包含 Go + TypeScript

## 🐛 Bug 检测

### Go
[Go 相关问题]

### TypeScript
[TypeScript 相关问题]

## 📐 代码质量

### Go
[Go 相关问题]

### TypeScript
[TypeScript 相关问题]
```

问题按语言分组展示，方便不同团队协作。

#### 场景 3: 智能规范检查

```bash
# 项目根目录存在 CLAUDE.md

$ /review

## 📋 项目规范检查 (Project Standards)

> 根据 CLAUDE.md 进行检查

### 规范文件: CLAUDE.md

#### ⚠️ High Confidence (≥80)

**app/regulation/internal/service/consume.go:23** `85/100`

**问题**: 提交信息缺少任务 ID，违反 Git 工作流规范
**规范引用**: CLAUDE.md - "Git 工作流规范 - 提交必须包含 #TAP-xxxxx"
**建议**: 在提交信息中添加任务 ID，格式：`feat: 实现消息消费 #TAP-85924`
```

## 支持的语言

### v0.0.1（当前版本）

| 语言 | 支持状态 | Bug 检测 | 代码质量 | 安全检查 | 性能分析 |
|------|---------|---------|---------|---------|---------|
| Go | ✅ 完整支持 | ✅ | ✅ | ✅ | ✅ |
| Java | 🚧 基础支持 | ✅ | ⚠️ | ⚠️ | ⚠️ |
| Python | 🚧 基础支持 | ✅ | ⚠️ | ⚠️ | ⚠️ |
| Kotlin | 🚧 基础支持 | ✅ | ⚠️ | ⚠️ | ⚠️ |
| Swift | 🚧 基础支持 | ✅ | ⚠️ | ⚠️ | ⚠️ |
| TypeScript | 🚧 基础支持 | ✅ | ⚠️ | ⚠️ | ⚠️ |

- ✅ 完整支持：包含语言特定的检查规则和示例
- 🚧 基础支持：使用通用规则，部分语言特性可能未覆盖
- ⚠️ 待完善：占位文件已创建，详细规则将在后续版本添加

### v0.0.2+（规划中）

更多语言支持：Rust、Ruby、C++、C#、PHP、C 等

详见：[docs/supported-languages.md](docs/supported-languages.md)

## 审查维度

### 1. 🐛 Bug 检测

检测潜在的运行时错误和逻辑缺陷：

**Go 示例**：
- Error handling 缺失或不当
- Nil pointer dereference
- Goroutine 泄漏
- Defer 陷阱（循环中的 defer）
- Mutex 死锁
- Range 变量捕获问题

**通用检测**：
- 逻辑错误
- 空指针/空引用
- 数组越界
- 资源泄漏
- 并发问题

### 2. 📐 代码质量

评估代码的可读性、可维护性和最佳实践：

- 命名规范（变量、函数、类型）
- 函数设计（长度、职责单一性）
- 代码组织（包/模块结构）
- 注释规范（必要性和清晰度）
- Magic number 和硬编码值
- 代码重复（DRY 原则）

### 3. 🔒 安全检查

识别安全漏洞和风险：

- SQL 注入
- 命令注入
- 路径遍历
- XSS（跨站脚本）
- CSRF（跨站请求伪造）
- 敏感信息泄漏（日志、错误信息）
- 弱加密算法
- 不安全的随机数生成

### 4. ⚡ 性能分析

发现性能瓶颈和优化机会：

- 数据库 N+1 查询
- 算法复杂度问题
- 不必要的内存分配
- 字符串拼接低效
- 锁竞争和锁粒度
- 并发调度优化
- 缓存缺失

详见：[skills/code-reviewing/review-dimensions.md](skills/code-reviewing/review-dimensions.md)

## 配置

### 基础配置（无需额外配置）

插件使用本地 git 命令获取代码变更，无需额外配置即可使用：

```bash
# 自动检测主分支（main/master）并获取差异
git diff <base_branch>...HEAD
```

### 高级配置（可选）

#### 1. 自定义置信度阈值

在项目根目录创建 `.claude/plugins/quality/config.yaml`：

```yaml
confidence_threshold: 80  # 默认值
show_medium_confidence: true  # 是否显示中等置信度问题（60-79）
```

#### 2. 自定义目标分支

```yaml
default_target_branch: master  # 默认值
# 或使用环境变量
# TARGET_BRANCH: develop
```

#### 3. GitLab 集成（v0.0.3+）

详见：[docs/gitlab-integration.md](docs/gitlab-integration.md)

## 工作原理

### 6 阶段工作流

```
1. Pre-check
   ├─ 检查 git 状态
   ├─ 确认是否在 git 仓库中
   └─ 获取当前分支信息

2. Context Collection
   ├─ 检测项目规范文件（CLAUDE.md, CONTRIBUTING.md）
   ├─ 获取代码变更（git diff）
   ├─ 识别变更的编程语言
   └─ 统计变更文件数量

3. Parallel Review（9 个 Agent 并行执行）
   ├─ project-standards-reviewer（如果有规范文件）
   ├─ bug-detector-1, bug-detector-2
   ├─ code-quality-analyzer-1, code-quality-analyzer-2
   ├─ security-analyzer-1, security-analyzer-2
   └─ performance-analyzer-1, performance-analyzer-2

4. Verification
   ├─ 合并 9 个 Agent 的结果
   ├─ 检测重复问题（同文件+同行+相似描述）
   ├─ 应用冗余加成（+20 置信度）
   └─ 过滤低置信度问题（<60）

5. Report Generation
   ├─ 按语言分组
   ├─ 按维度分类
   ├─ 生成统计信息
   └─ 应用报告模板

6. Output
   └─ 终端 Markdown 输出（v0.0.1）
   └─ GitLab MR 评论（v0.0.3+，可选）
```

### 语言识别

自动识别代码变更中的编程语言：

```bash
# 基于文件扩展名
.go      → Go
.java    → Java
.py      → Python
.kt      → Kotlin
.swift   → Swift
.ts, .tsx, .vue → TypeScript
```

每个 Agent 会自动引用对应的语言检查规则（`skills/language-checks/{language}-checks.md`）。

### 置信度计算示例

```
# 示例：bug-detector-1 发现一个问题

1. Agent 自评置信度: 75（基于代码上下文、模式匹配等）

2. 检查是否有冗余确认:
   - bug-detector-2 也发现了相同问题（同文件+同行+相似描述）
   - 应用冗余加成: 75 + 20 = 95

3. 置信度过滤:
   - 95 ≥ 80 → 高置信度，直接报告
   - 标记为"冗余确认"

4. 输出:
   **文件路径:行号** `95/100`
   **检测来源**: bug-detector-1 + bug-detector-2（冗余确认）
```

## 适用场景

### 1. Merge Request 代码审查

```bash
# 在 MR 分支上
/review

# 自动审查相对于 master 的所有变更
# 发现潜在问题并生成报告
```

### 2. 日常开发自查

```bash
# 提交代码前自查
git add .
/review

# 快速发现问题，避免提交有缺陷的代码
```

### 3. 项目规范遵循检查

```bash
# 项目有 CLAUDE.md 规范文件
/review

# 自动检查代码是否遵循项目规范
# 例如：Git 提交格式、命名规范、代码组织等
```

### 4. 跨部门协作

```bash
# 多语言项目（如 Mono Repo）
/review

# 报告按语言分组
# Server 团队查看 Go/Java 问题
# Android 团队查看 Kotlin 问题
# iOS 团队查看 Swift 问题
# Web 团队查看 TypeScript 问题
```

## 目录结构

```
.claude/plugins/quality/
├── .claude-plugin/
│   └── plugin.json              # 插件元数据
├── commands/
│   └── review.md                # /review 命令定义
├── agents/                      # 9 个 Agent 定义
│   ├── project-standards-reviewer.md
│   ├── bug-detector-1.md
│   ├── bug-detector-2.md
│   ├── code-quality-analyzer-1.md
│   ├── code-quality-analyzer-2.md
│   ├── security-analyzer-1.md
│   ├── security-analyzer-2.md
│   ├── performance-analyzer-1.md
│   └── performance-analyzer-2.md
├── skills/
│   ├── code-reviewing/          # 通用审查 Skill
│   │   ├── SKILL.md
│   │   ├── review-dimensions.md
│   │   └── confidence-scoring.md
│   └── language-checks/         # 语言特定检查规则
│       ├── go-checks.md         # ✅ 完整
│       ├── java-checks.md       # 🚧 占位
│       ├── python-checks.md     # 🚧 占位
│       ├── kotlin-checks.md     # 🚧 占位
│       ├── swift-checks.md      # 🚧 占位
│       └── typescript-checks.md # 🚧 占位
├── templates/
│   ├── review-report.md         # 终端报告模板
│   └── issue-comment.md         # GitLab MR 评论模板
├── docs/
│   ├── supported-languages.md   # 支持的语言详情
│   ├── gitlab-integration.md    # GitLab 集成指南
│   └── future-roadmap.md        # 未来路线图
└── README.md                    # 本文档
```

## 常见问题

### Q1: 为什么需要 9 个 Agent？

**答**:
1. **并行性能**: 9 个 Agent 同时执行，总耗时 ≈ 单个最慢 Agent
2. **维度专业化**: 每个维度有专门的 Agent，审查更深入
3. **冗余确认**: 每个维度 2 个 Agent 独立审查，减少漏报
4. **规范检查**: 智能检测项目规范，有则检查，无则跳过

对比串行执行：
- 串行：Agent1 → Agent2 → ... → Agent9（耗时累加）
- 并行：Agent1 + Agent2 + ... + Agent9（耗时 ≈ max(Agent[i])）

### Q2: 置信度评分如何计算？

**答**: 置信度由 Agent 基于以下因素自评（0-100）：

- **代码模式匹配度**: 问题模式是否明确匹配已知缺陷
- **上下文完整性**: 代码上下文是否足够判断
- **语言特定规则**: 是否符合语言特定的最佳实践
- **静态分析确定性**: 问题是否可以静态确定（非推测）

**冗余加成**: 当 2 个同类 Agent 都发现相同问题时 +20

### Q3: 如何处理误报？

**答**:
1. **置信度阈值**: 默认 80，过滤大部分误报
2. **冗余确认**: 2 个 Agent 同时发现的问题更可靠
3. **中等置信度标记**: 60-79 的问题标记为"需人工确认"
4. **持续优化**: 根据反馈调整 Agent prompt 和检查规则

如果发现误报，请在项目 issues 中反馈，帮助我们改进。

### Q4: 为什么有些语言只有基础支持？

**答**: v0.0.1 优先完成 Go 语言的完整支持（包含详细的检查规则和示例）。其他语言：

- **基础支持**: 使用通用的 Bug 检测规则，可以发现明显的问题
- **占位文件**: 已创建文件框架，包含规划的检查项
- **逐步完善**: 后续版本会补充其他语言的详细规则

你可以参与贡献，为其他语言编写检查规则！

### Q5: 如何与 GitLab 集成？

**答**:
- **v0.0.1**: 使用本地 git 命令，无需额外配置
- **v0.0.3+**: 支持 GitLab MCP Server 或 glab CLI，可以直接在 MR 中发布评论

详见：[docs/gitlab-integration.md](docs/gitlab-integration.md)

### Q6: 可以自定义检查规则吗？

**答**:
可以！在项目根目录创建 `.claude/plugins/quality/custom-checks/` 目录，添加自定义规则：

```markdown
# custom-checks/my-project-rules.md

## Go 自定义规则

### 禁止使用 panic
置信度: 90

#### 检测模式
```go
panic("错误")
```

#### 建议
使用 error 返回值代替 panic
```

### Q7: 审查会修改我的代码吗？

**答**: 不会。`/review` 命令只进行静态分析和报告生成，不会修改任何代码。修复建议仅作为参考，由开发者决定是否采纳。

### Q8: 支持私有 GitLab 实例吗？

**答**: 支持（v0.0.3+）。配置 GitLab MCP Server 或 glab CLI 时指定私有实例的 URL：

```yaml
# .mcp.json
{
  "servers": {
    "gitlab": {
      "command": "gitlab-mcp",
      "env": {
        "GITLAB_URL": "https://your-gitlab.company.com",
        "GITLAB_TOKEN": "${GITLAB_TOKEN}"
      }
    }
  }
}
```

## 贡献指南

欢迎为 quality plugin 贡献代码和文档！

### 贡献语言检查规则

1. 选择一个语言（如 Java）
2. 编辑 `skills/language-checks/java-checks.md`
3. 参考 `go-checks.md` 的结构，添加：
   - Bug 检测规则和示例
   - 代码质量规则和示例
   - 安全检查规则和示例
   - 性能优化规则和示例
4. 提交 MR

### 贡献 Agent 改进

1. 编辑 `agents/[agent-name].md`
2. 优化 Agent prompt，提高准确率
3. 在本地测试验证
4. 提交 MR

### 报告问题

在项目 issues 中报告：
- 误报案例（包含代码片段和审查结果）
- 漏报案例（应该发现但未发现的问题）
- 功能建议

## 版本历史

### v0.0.4

- 将 `code-reviewing` skill 迁移至 git 插件（集中化审查流程）

### v0.0.3

- 修复 review 命令 allowed-tools 缺失 mkdir、echo、date 权限声明

### v0.0.1

- ✅ 9 个并行 Agent 架构
- ✅ 置信度评分和冗余确认机制
- ✅ Go 语言完整支持（Bug/质量/安全/性能）
- ✅ 智能规范检查（CLAUDE.md/CONTRIBUTING.md）
- ✅ 终端 Markdown 报告输出
- ✅ 其他 5 种语言基础支持（Java/Python/Kotlin/Swift/TypeScript）

### 未来计划

详见：[docs/future-roadmap.md](docs/future-roadmap.md)

**v0.0.2**：
- 补充 Java/Python/Kotlin/Swift/TypeScript 的详细检查规则
- 添加更多语言（Rust, Ruby, C++, C#）
- 优化语言识别算法

**v0.0.3**：
- GitLab MR inline comments 支持
- 自动发布审查结果到 MR
- 审查历史和趋势分析

**v0.1.0**：
- `/lint` 命令（运行语言特定 linter）
- `/format` 命令（代码格式化）
- `/coverage` 命令（测试覆盖率）
