# test Plugin

> QA 工作流插件，覆盖需求澄清 → 测试设计 → 测试评审 → 需求回溯 → Bug 修复分析的完整 QA 流程

## 简介

`test` 插件为 Claude Code 提供一套完整的 QA 工作流 Skill，支持功能测试、单元测试、集成测试的设计与生成。

### 核心 Skills

| Skill | 类型 | 功能 |
|-------|------|------|
| **requirement-clarification** | 核心工作流 | 多维度结构化问答，拉齐需求理解 |
| **test-design** | 核心工作流 | 基于需求拆解功能模块并生成结构化测试用例 |
| **test-review** | 核心工作流 | 评审测试用例的覆盖度和质量（4 维度） |
| **requirement-traceability** | 核心工作流 | 双向追溯需求与代码变更的映射关系 |
| **bug-fix-review** | 独立 skill | 分析 Bug 修复代码变更的完整性和残余风险 |
| **unit-test-design** | 代码级生成 | 分析源代码，生成可执行的单元测试代码 |
| **integration-test-design** | 代码级生成 | 分析 API/服务，生成可执行的集成测试代码 |

### 支持 Skills

| Skill | 功能 |
|-------|------|
| **shared-tools** | 共享脚本集合（飞书文档获取、GitLab/GitHub MR/PR 分析） |

## 快速开始

本插件支持 3 条独立工作链路，可独立执行也可组合使用：

### 链路 A — 功能测试全流程（串行）

需求驱动的黑盒测试设计，从需求到用例到覆盖验证。

```
需求文档/链接
    ↓
requirement-clarification（需求澄清）
    ↓ clarified_requirements.json + requirement_points.json
test-design（测试设计）
    ↓ test_cases.json
test-review（测试评审）
    ↓ final_cases.json
requirement-traceability（需求回溯）
    ↓ traceability_matrix.json + coverage_report.json
```

### 链路 B — 代码级测试生成（可并行）

实现驱动的白盒测试代码生成，直接分析源码/API 定义。

```
源代码文件 ──→ unit-test-design ──→ *_test.go / test_*.py
API 定义   ──→ integration-test-design ──→ 集成测试代码
```

> 链路 B 可接收链路 A 的 `requirement_points.json` 作为可选输入，用于指导测试覆盖重点（优先为 P0/P1 功能点对应的代码模块生成测试）。

### 链路 C — Bug 修复分析（独立触发）

```
Bug 信息 + MR/PR ──→ bug-fix-review ──→ fix_analysis.json + risk_assessment.json
```

## 支持的语言

| 语言 | 单元测试 | 集成测试 | 测试框架 |
|------|---------|---------|---------|
| Go | ✅ | ✅ | testing + testify |
| Python | ✅ | ✅ | pytest |
| TypeScript | ✅ | ✅ | vitest / jest |
| Java | ✅ | ✅ | JUnit 5 + Mockito |
| Kotlin | ✅ | ✅ | JUnit 5 + MockK |
| Swift | ✅ | — | XCTest |

## 目录结构

```
plugins/test/
├── .claude-plugin/
│   └── plugin.json
├── CONVENTIONS.md              # 统一约定
├── CONTRACT_SPEC.md            # contract.yaml 编写规范
├── skills/
│   ├── shared-tools/           # 共享脚本
│   ├── requirement-clarification/
│   ├── test-design/
│   ├── test-review/
│   ├── requirement-traceability/
│   ├── bug-fix-review/
│   ├── unit-test-design/       # 单元测试代码生成
│   └── integration-test-design/ # 集成测试代码生成
└── README.md
```

## 环境变量

shared-tools 脚本依赖以下环境变量（按需配置）：

| 变量 | 说明 | 依赖脚本 |
|------|------|---------|
| `FEISHU_APP_ID` | 飞书应用 ID | fetch_feishu_doc.py |
| `FEISHU_APP_SECRET` | 飞书应用 Secret | fetch_feishu_doc.py |
| `GITLAB_URL` | GitLab 实例地址 | gitlab_helper.py, search_mrs.py |
| `GITLAB_TOKEN` | GitLab Access Token | gitlab_helper.py, search_mrs.py |
| `GITHUB_TOKEN` | GitHub Token | github_helper.py, search_prs.py |

## 版本历史

### v0.0.4

- 修复 search_mrs.py / search_prs.py 子串匹配误报（改用词边界正则）
- 修复 fetch_feishu_doc.py `from __future__` 位置（移到 docstring 之后）
- 修复 search_mrs.py 字符串类型项目映射值静默失败（新增类型校验）
- 修复 github_helper.py PR 文件列表未分页（新增 _get_pr_files 分页函数）
- 修复 Markdown 图片引用与 sanitized 文件名不一致
- 补充 contract.yaml 缺失的映射环境变量声明
- 统一 SKILL.md 项目映射文档为 int ID 格式

### v0.0.3

- 修复 .gitignore 排除 test-design / test-review 目录的阻塞问题
- 移除 Python 脚本中硬编码的内部 GitLab URL 和项目 ID
- 统一 Python 脚本类型注解为 typing 模块格式（兼容 Python 3.8+）
- 修复 fetch_feishu_doc.py image token 路径穿越风险
- 修复 fetch_feishu_doc.py tenant token 缓存无过期问题
- search_prs.py 新增分页支持、未配置时报错退出
- 添加 Python 脚本执行权限

### v0.0.2

- unit-test-design / integration-test-design 新增「测试质量防线」章节
- 防硬编码过测、断言质量要求、防 Mock 滥用、变异测试思维
- 新增 Property-Based Testing 方法论（Go rapid / Python hypothesis / TS fast-check）
- 新增弱断言 vs 强断言对比示例

### v0.0.1

- 从 skills-hub 迁移 6 个 QA 工作流 Skill + shared-tools
- 新增 unit-test-design（单元测试代码生成）
- 新增 integration-test-design（集成测试代码生成）
