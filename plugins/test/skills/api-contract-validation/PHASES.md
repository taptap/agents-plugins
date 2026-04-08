# API 契约校验各阶段详细操作指南

## 关于系统预取

通用预取机制见 [CONVENTIONS.md](../../CONVENTIONS.md#系统预取)。本 skill 额外预取：关联代码变更列表（GitLab MR / GitHub PR）。预取数据仅在 MR/PR 模式下可用；本地 diff 模式无预取。

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
python3 $SKILLS_ROOT/shared-tools/scripts/gitlab_helper.py mr-diff <project_path> <mr_iid>
# GitHub
python3 $SKILLS_ROOT/shared-tools/scripts/github_helper.py pr-diff <owner/repo> <pr_number>
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

## 阶段 3: analyze - 接口签名提取与交叉比对

### 3.1 提取前端接口签名

对 `contract_checklist.md` 中的每个前端 API 相关文件，从 diff 中提取：

1. **端点签名**：
   - 请求路径（URL path）
   - HTTP 方法（GET/POST/PUT/DELETE）
   - 请求参数（参数名、类型、是否必填）
   - 响应模型（字段名、类型、是否可选）

2. **变更类型**：
   - `added` — 新增端点或字段
   - `modified` — 修改已有端点的参数或响应
   - `removed` — 删除端点或字段

### 3.2 提取后端接口签名

同上规则提取后端的接口签名。如为 OpenAPI 基准模式，直接从 spec 中读取。

### 3.3 交叉比对

对每个涉及的端点，执行以下对比：

**3.3.1 路径一致性**

| 检查项 | 前端 | 后端/OpenAPI | 严重度 |
| --- | --- | --- | --- |
| 路径值不匹配 | `/api/v2/user` | `/api/v2/users` | high |
| HTTP 方法不匹配 | `POST` | `PUT` | high |
| 路径参数名不匹配 | `:userId` | `:user_id` | medium |

**3.3.2 请求参数一致性**

| 检查项 | 前端 | 后端/OpenAPI | 严重度 |
| --- | --- | --- | --- |
| 后端必填参数前端未传 | 缺失 `page_size` | `required: true` | high |
| 参数类型不匹配 | `String` | `Integer` | high |
| 参数名不匹配（非风格差异） | `userName` | `nickname` | high |
| 参数名风格差异 | `userName` | `user_name` | low（信息级别） |

**3.3.3 响应字段一致性**

| 检查项 | 前端 | 后端/OpenAPI | 严重度 |
| --- | --- | --- | --- |
| 字段类型不匹配 | `String` | `Int` | high |
| 前端期望的必填字段后端不提供 | `avatar_url: String` | 字段不存在 | high |
| 字段名不匹配（非风格差异） | `user_name` | `display_name` | high |
| 字段名风格差异 | `userName` | `user_name` | low（信息级别） |
| 前端有冗余可选字段 | `extra_info: String?` | 字段不存在 | low |
| 后端新增字段前端未处理 | 未声明 | `new_field: String` | medium |

**3.3.4 Breaking Change 检测**

仅在有变更前后对比（diff 的 +/- 行）时执行：

| Breaking Change 类型 | 严重度 |
| --- | --- |
| 删除已有必填响应字段 | high |
| 修改已有字段的类型 | high |
| 新增必填请求参数 | high |
| 修改路径或 HTTP 方法 | high |
| 将可选响应字段改为不返回 | medium |
| 修改枚举值范围 | medium |

### 3.4 命名风格自动转换

在比对前，尝试自动识别命名风格并做标准化：

1. 检测前端命名风格（camelCase / PascalCase / snake_case）
2. 检测后端命名风格
3. 将两端转换为统一风格后再比较
4. 纯风格差异标记为 `low` severity，附带原始名和转换后名

### 3.5 写入分析记录

将逐端点的分析结果追加到 `contract_analysis.md`。

## 阶段 4: output - 报告生成

### 4.1 汇总问题

回读 `contract_analysis.md`，汇总所有端点的对比结果。

### 4.2 计算 overall_consistency

| 条件 | overall_consistency |
| --- | --- |
| 所有端点无问题 | `consistent` |
| 存在 high severity 问题 | `inconsistent` |
| 仅存在 medium/low severity 问题 | `partial` |
| 降级模式（无法做对比） | `N/A` |

### 4.3 生成 api_contract_report.json

格式见 [TEMPLATES.md](TEMPLATES.md#api_contract_reportjson)。

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
