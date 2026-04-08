# Spec-Driven Development Plugin

Spec-Driven Development 插件，从任务工单和 PRD 自动执行完整开发流程，并提供模块发现与文档自动同步能力。

## 功能概述

通过贴入任务工单链接和 PRD 链接触发完整的开发工作流：

```
用户：实现 https://your-project-system.example.com/story/detail/123456 https://your-docs.example.com/wiki/DOC001

→ 解析任务 ID (123456)
→ 读取任务工单标题
→ 创建工作分支 (feat-PROJ-12345-xxx)
→ 读取 PRD 内容
→ 生成 spec/plan/tasks
→ ⏸️ 输出文档摘要，等待用户确认
→ 用户确认后开始实现
→ 自动判断并行/顺序执行
→ 实现代码
→ 自动提交并创建 MR
```

## Skills

### module-discovery

**触发条件**：仅适用于已维护 `tap-agents/prompts/module-map.md` 且明确采用模块索引协作机制的仓库；需要按模块索引定位代码或查看模块结构时触发

**功能**：
- 读取 `module-map.md` 获取项目模块索引
- 根据关键词快速定位相关模块
- 支持按优先级（P0/P1/P2）组织模块
- 提供关键词到模块的映射表

**使用场景**：
- 收到开发需求时，快速定位代码模块
- 需要了解模块详情时，读取模块文档
- 新增或修改模块时，配合 doc-auto-sync 同步更新
- 未采用该协作机制的仓库、无 module-map 的仓库和通用问答场景不使用该 skill

### doc-auto-sync

**触发条件**：修改模块代码时（强制执行）

**功能**：
- 维护分层文档系统（module-map.md + 模块文档）
- 新增模块时自动创建文档
- 修改模块时自动更新文档
- 处理文档与代码不一致情况
- 提供文档检查脚本（check-docs.py、check-stale-docs.py）

**文档结构**：
```
tap-agents/prompts/
├── module-map.md           # 根索引
└── modules/
    ├── ModuleA.md          # 模块A详情
    └── ModuleB.md          # 模块B详情
```

### implementing-from-task

**触发条件**：识别用户输入的任务工单链接 + PRD 链接

**功能**：
- 自动解析任务 ID 创建分支
- 从 PRD 链接获取内容
- 生成 spec/plan/tasks 文档
- 智能判断执行方式（并行/顺序）
- 自动实现并提交

### merging-parallel-work

**触发条件**：用户明确指定执行时（测试中）

**功能**：
- 使用 git worktree 管理并行开发
- 按顺序合并各模块分支到主分支
- AI 自动解决冲突（import 合并、配置智能合并）
- 生成合并报告与验证结果
- 提供回退策略

**工作流程**：
1. 创建 worktree（每个独立模块一个）
2. 分配任务到各 worktree
3. 各 agent 在 worktree 中独立工作
4. 合并分支并解决冲突
5. 清理 worktree 和临时分支
6. 创建统一 MR

## Commands

| 命令 | 功能 |
|------|------|
| `/workflow-status` | 查看当前 SDD 工作流状态 |

## 动作词映射

| 动作词 | 分支前缀 | Commit Type |
|--------|---------|-------------|
| 实现/新增/开发 | feat- | feat |
| 修复/修 bug | fix- | fix |
| 重构 | refactor- | refactor |
| 优化 | perf- | perf |

## 并行执行判断

系统自动分析任务依赖：

- **存在依赖** → 按顺序执行
- **完全独立 且 任务数 >= 2** → 并行执行

团队成员无需理解多 agent 机制，完全自动化。

## 生成的文件结构

```
specs/
└── PROJ-12345/
    ├── spec.md      # 功能规范
    ├── plan.md      # 实现计划
    └── tasks.md     # 任务清单
```

## 依赖

- 文档读取工具（读取任务工单和 PRD）
- git 插件（使用 GitLab push options 创建 MR）

## 使用示例

```bash
# 实现新功能（贴任务工单链接 + PRD 链接）
实现 https://your-project-system.example.com/story/detail/123456 https://your-docs.example.com/wiki/DOC001

# 修复 Bug
修复 https://your-project-system.example.com/story/detail/123456 https://your-docs.example.com/doc/DOC002

# 省略动作词（默认 feat）
https://your-project-system.example.com/story/detail/123456 https://your-docs.example.com/wiki/DOC003

# 简写任务 ID
修复 123456 https://your-docs.example.com/wiki/DOC004

# 查看工作流状态
/workflow-status
```

## 输入格式

支持以下输入组合：

| 格式 | 示例 |
|------|------|
| 动作词 + 任务工单链接 + PRD 链接 | `实现 https://your-project-system.example.com/.../123456 https://your-docs.example.com/wiki/xxx` |
| 动作词 + 任务 ID + PRD 链接 | `修复 123456 https://your-docs.example.com/wiki/xxx` |
| 任务工单链接 + PRD 链接 | `https://your-project-system.example.com/.../123456 https://your-docs.example.com/wiki/xxx` |

**链接识别规则**：
- 任务工单：项目管理系统的任务详情页 URL
- PRD：文档系统的文档链接
- 根据项目实际使用的系统调整 URL 匹配规则

## 环境配置

确保已配置：
- 文档访问权限
- Git 远程仓库（remote origin）
