# API 契约校验各阶段详细操作指南

## 关于系统预取

通用预取机制见 [CONVENTIONS.md](../commons/CONVENTIONS.md#系统预取)。本 skill 额外预取：关联代码变更列表（GitLab MR / GitHub PR）。预取数据仅在 MR/PR 模式下可用；本地 diff 模式无预取。

## 阶段 1: init - 输入验证

### 1.1 确认前端代码变更来源

按以下优先级判断（互斥，取第一个命中的）：

1. `frontend_diff_text` 参数非空 → **文本模式**，直接使用提供的 diff 文本
2. `frontend_diff` 参数提供了文件路径 → **文件模式**，Read 该文件获取 diff 内容
3. `frontend_changes` 参数提供了 MR/PR 链接列表 → **MR/PR 模式**，记录链接列表
4. 预取数据中有关联代码变更列表 → **MR/PR 模式**，使用预取列表
5. 以上均不满足 → **停止**

### 1.2 确认后端变更来源

按以下优先级判断（互斥，取第一个命中的）：

1. `backend_diff_text` 参数非空 → **后端文本模式**
2. `backend_diff` 参数提供了文件路径 → **后端文件模式**
3. `backend_changes` 参数提供了 MR/PR 链接列表 → **后端 MR/PR 模式**
4. `openapi_spec` 参数提供了 OpenAPI spec 文件 → **OpenAPI 基准模式**
5. 以上均不满足 → **降级模式**，仅提取前端接口签名

### 1.3 MR/PR 模式下的 provider 判断

同 requirement-traceability，从链接或预取数据的 `provider` 字段判断代码托管平台。

## 阶段 2: fetch - 数据获取

### 2.1 获取前端 diff

根据 init 阶段确定的模式获取前端代码变更 diff。

MR/PR 模式下：

```bash
# GitLab
python3 $SKILLS_ROOT/test-shared-tools/scripts/gitlab_helper.py mr-diff <project_path> <mr_iid>
# GitHub
python3 $SKILLS_ROOT/test-shared-tools/scripts/github_helper.py pr-diff <owner/repo> <pr_number>
```

### 2.2 获取后端 diff（可选）

后端 MR/PR 模式同上。OpenAPI 基准模式下直接 Read spec 文件。

### 2.3 获取 OpenAPI spec（可选）

如果提供了 `openapi_spec` 参数：

1. Read 文件（JSON 或 YAML 格式）
2. 提取所有 endpoint 的路径、方法、请求参数、响应结构
3. 作为三方对比的基准

### 2.4 创建检查清单

扫描前后端 diff，识别 API 相关文件并分类：

**前端文件分类**：
- **路径定义** — 网络请求路径枚举/常量文件（如 `TapNetworkPath.swift`、`api.ts`、`routes.go`）
- **请求模型** — API 请求参数模型（DTO/Request 类型）
- **响应模型** — API 响应数据模型（Codable/Decodable/interface 等）
- **网络调用** — 实际发起网络请求的代码（参数构造 + 路径引用）

**后端文件分类**：
- **路由定义** — URL 路由注册（router/controller mapping）
- **Handler/Controller** — 请求处理逻辑（参数解析 + 响应构造）
- **响应结构** — 返回的数据结构定义（序列化器/DTO）
- **数据库模型** — 底层数据模型（仅当字段变更可能影响响应结构时纳入）

写入 `contract_checklist.md`：前端 API 文件清单、后端 API 文件清单、识别出的端点列表。

非 API 相关的文件（纯 UI、配置、测试等）不纳入检查范围。

## 阶段 3: analyze - 启动 api-contract-validator Agent

通过 Task 工具启动 `api-contract-validator` Agent（Agent 定义见 [test-shared-tools/agents/api-contract-validator.md](../test-shared-tools/agents/api-contract-validator.md)），把签名提取、4 维度交叉比对、Breaking Change 检测、命名风格归一全部委托给 Agent。这个 Agent 是无副作用的纯计算单元，同时被 `requirement-traceability` §3.2.5 复用，避免逻辑重复实现。

### 3.1 启动 Agent

通过 Task 工具启动子 Agent，指定 `model="opus"`。Codex 环境不注册自定义 agent 类型：先 Read `$SKILLS_ROOT/test-shared-tools/agents/api-contract-validator.md`，默认由主 Agent 内联执行；仅当用户明确要求并行/子 agent 时，使用 Codex 内置 `worker` 并将该 Agent 定义全文嵌入 prompt。

**Task prompt**：

```
你是 API 契约校验 Agent。请先 Read $SKILLS_ROOT/test-shared-tools/agents/api-contract-validator.md 获取你的完整角色定义和输出格式要求。

## 前端 diff
{从阶段 2.1 获取的 diff 内容；按 contract_checklist.md 中识别出的 API 相关文件过滤}

## 后端来源
{二选一}
{后端 diff：从阶段 2.2 获取的内容；同样按 API 相关文件过滤}
{OpenAPI spec：从阶段 2.3 解析后的端点定义}

## 任务
按 agent 定义中的 4 个维度（路径、请求参数、响应字段、Breaking Change）做交叉比对，输出 JSON 格式的 findings。每个 issue 必须包含 confidence 评分（0-100）。
```

### 3.2 写入分析记录

将 Agent 返回的 findings JSON 落盘到 `contract_analysis.md`（中间文件，便于人工排查 Agent 推理路径），同时保留原始 JSON 用于阶段 4 包装。

## 阶段 4: output - 包装 Agent findings 为最终报告

### 4.1 取 Agent 输出

从阶段 3 取 Agent 返回的 JSON。Agent 已经计算好 `overall_consistency` / `checked_endpoints` / `issues_found` / `endpoints[]`，主 skill 不重新计算。

### 4.2 包装为 api_contract_report.json

在 Agent 输出基础上添加元数据字段：
- `frontend_source` ← 阶段 1.1 确定的前端来源（type + ref）
- `backend_source` ← 阶段 1.2 确定的后端来源（type + ref）
- `metadata` ← skill 名 / 版本号 / 生成时间戳

最终 schema 见 [TEMPLATES.md](TEMPLATES.md#api_contract_reportjson)，与历史版本兼容。

### 4.4 生成摘要

在终端输出人类可读的摘要：

```markdown
## API 契约校验结果

- 一致性：inconsistent
- 检查端点数：5
- 问题数：2（high: 1, medium: 1）

### 问题列表

| # | 端点 | 类型 | 严重度 | 描述 |
| --- | --- | --- | --- | --- |
| 1 | POST /api/v2/user/profile | field_mismatch | high | 前端期望 `user_name: String`，后端提供 `username: String` |
| 2 | GET /api/v2/games | missing_param | medium | 后端新增可选参数 `sort_by`，前端未传递 |
```

## 降级策略

| 场景 | 降级方式 |
| --- | --- |
| 无后端变更且无 OpenAPI spec | 仅提取前端接口签名，不做一致性校验，`overall_consistency: "N/A"` |
| diff 信息不足以提取签名 | 标记为 `inconclusive`，在报告中注明原因 |
| MR/PR 脚本执行失败 | 按 CONVENTIONS 重试策略处理，3 次失败后降级 |
| OpenAPI spec 格式无法解析 | 跳过 OpenAPI 基准，仅做前后端 diff 直接对比 |
