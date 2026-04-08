# 验证用例生成各阶段详细操作指南

## 关于系统预取

通用预取机制见 [CONVENTIONS.md](../../CONVENTIONS.md#系统预取)。本 skill 额外预取：关联代码变更列表（GitLab MR / GitHub PR）。预取数据仅在 MR/PR 模式下可用；本地代码/diff 模式无预取。

## 阶段 1: init - 输入验证与路由

确认需求功能点来源和代码实现来源。需求功能点为空时硬性阻断。

### 1.1 确认需求功能点来源

按以下优先级判断（互斥，取第一个命中的）：

1. 工作目录中存在 `clarified_requirements.json` → 读取其中的 `functional_points` 作为功能点来源
2. 工作目录中存在 `requirement_points.json` → 直接读取作为功能点清单
3. `requirement_points` 参数提供了文件路径 → Read 该文件
4. `clarified_requirements` 参数提供了文件路径 → Read 该文件，提取 `functional_points`
5. 以上均不满足 → **停止**，报告错误「无法获取需求功能点」

### 1.2 确认代码实现来源

按以下优先级判断（互斥，取第一个命中的）：

1. `code_dir` 参数非空 → **目录模式**，记录代码目录路径
2. `code_diff_text` 参数非空 → **文本模式**，直接使用提供的 diff 文本
3. `code_diff` 参数提供了文件路径 → **文件模式**，Read 该文件获取 diff 内容
4. 预取数据中有关联代码变更列表 → **MR/PR 模式**，记录链接列表
5. 以上均不满足 → **降级模式**，仅生成用例不做验证推理

### 1.3 判定需求类型

根据功能点内容和代码文件扩展名，判定需求类型：

| 信号 | 需求类型 |
| --- | --- |
| `.vue`、`.tsx`、`.jsx`、`.svelte`、组件/页面/样式相关描述 | 前端交互 |
| `.go`、`.py`、`.java`、`.rs`、服务/模型/业务逻辑相关描述 | 后端逻辑 |
| 路由定义、handler、controller、OpenAPI spec | API 接口 |
| ETL、pipeline、transform、数据处理相关描述 | 数据处理 |

混合类型时标记为 `mixed`，后续各功能点独立判定。

### 1.4 检查 Figma 链接

如 `design_link` 参数非空且为 Figma 链接，标记为前端需求并在 analyze 阶段获取设计数据。

## 阶段 2: analyze - 需求与代码分析

### 2.1 解析需求功能点

读取功能点数据，逐项提取：

- 功能点 ID 和名称
- 验收标准（`acceptance_criteria`）
- 业务规则和数据约束
- 状态流转规则（如有）

对每个功能点，识别**可验证断言**——即可以用具体输入和预期输出表达的检查点。

示例：
```markdown
### FP-1: 优惠券金额计算

**验收标准**：
1. 优惠券抵扣金额不超过订单金额
2. 多张优惠券可叠加使用，总抵扣不超过订单金额

**可验证断言**：
- A1: coupon_amount > order_amount → actual_discount == order_amount
- A2: coupon_amount <= order_amount → actual_discount == coupon_amount
- A3: sum(coupons) > order_amount → total_discount == order_amount
```

### 2.2 获取代码实现

根据 init 阶段确定的模式：

**目录模式**：使用 Glob 和 Read 工具读取代码目录中的关键文件。根据需求类型筛选：
- 后端逻辑：查找包含功能点关键词的 service/model/handler 文件
- API 接口：查找路由定义和 handler 实现
- 前端交互：查找组件和页面文件

**文本模式 / 文件模式**：diff 内容已在 init 阶段获取。

**MR/PR 模式**：

```bash
# GitLab
python3 $SKILLS_ROOT/shared-tools/scripts/gitlab_helper.py mr-diff <project_path> <mr_iid>
# GitHub
python3 $SKILLS_ROOT/shared-tools/scripts/github_helper.py pr-diff <owner/repo> <pr_number>
```

**降级模式**：无代码，跳过此步。

### 2.3 获取设计数据（前端需求，可选）

有 Figma 链接时使用 `get_figma_data` 获取设计稿结构。关注：

- 组件层级和命名
- 交互状态（默认/悬停/禁用/错误）
- 条件展示逻辑
- 页面跳转关系

### 2.4 创建分析清单

写入 `verification_checklist.md`：

```markdown
# 验证用例分析清单

## 需求类型
{前端交互 | 后端逻辑 | API 接口 | 数据处理 | mixed}

## 代码可用性
{目录模式 | 文本模式 | 文件模式 | MR/PR 模式 | 降级模式（无代码）}

## 功能点清单

### FP-1: {名称}
- 验收标准：{列表}
- 可验证断言：{A1, A2, ...}
- 对应代码路径：{文件:行号 或 diff 片段引用}

### FP-2: ...

## 统计
- 功能点总数：N
- 可验证断言总数：M
- 代码文件数：K
```

## 阶段 3: generate - 验证用例生成

### 3.1 用例生成策略

根据需求类型为每个功能点生成验证用例：

**后端逻辑**：
- `functional`：正常输入参数 → 预期返回值和状态变更
- `boundary`：边界值参数（最小值、最大值、零值、空值）→ 预期行为
- `error`：非法输入、异常状态 → 预期错误处理
- `state`：状态流转触发条件 → 预期的新状态

**API 接口**：
- `functional`：合法请求 → 预期 HTTP status + response body
- `boundary`：极端参数值、空 body、超长字段 → 预期响应
- `error`：缺少必填字段、无效 token、权限不足 → 预期错误码和 message
- `state`：资源状态变更操作 → 预期资源新状态

**前端交互**：
- `functional`：用户操作（点击按钮/输入文本/选择选项）→ 预期 UI 状态变化
- `boundary`：极端输入（超长文本/特殊字符）→ 预期展示行为
- `error`：网络失败/数据异常 → 预期错误提示和降级展示
- `state`：页面状态切换（加载中/空数据/错误/正常）→ 预期 UI 呈现

**数据处理**：
- `functional`：标准输入数据集 → 预期输出数据集
- `boundary`：空数据、超大数据集、格式异常 → 预期处理行为
- `error`：数据源不可用、格式不匹配 → 预期错误处理

### 3.2 具体化要求

每条用例的 `input.params` 和 `expected.assertion` 必须是具体的：

| 类别 | 合格示例 | 不合格示例 |
| --- | --- | --- |
| 输入参数 | `{"coupon_amount": 100, "order_amount": 50}` | `{"coupon_amount": "某个值"}` |
| 预期断言 | `actual_discount == 50` | `应该正确计算` |
| 代码追踪 | `applyCoupon() -> min(100, 50) -> 50` | `调用了相关函数` |

### 3.3 使用子 Agent 并行生成（功能点 >= 3 个）

对每个功能点，通过 Task 工具调用 verification-test-writer 子 Agent。

**Task prompt 要点**：

1. 提供：功能点详情（ID、名称、验收标准、可验证断言）、对应代码片段、需求类型
2. 指定 `model="sonnet"`
3. 输出文件：`fp_{N}_cases.json`（N 为功能点索引，从 1 开始）

**并行策略**：在单条消息中同时发起所有功能点的 Task 调用。

**Task prompt 示例**：

```
你是验证用例生成 Agent。为以下功能点生成结构化验证用例。

## 功能点
- ID: FP-1
- 名称: 优惠券金额计算
- 验收标准: [列表]
- 可验证断言: [列表]
- 需求类型: 后端逻辑

## 代码实现
{代码片段或 diff 内容}

## 输出要求
1. 每条用例必须有具体的 input.params 和 expected.assertion
2. 至少覆盖 functional / boundary / error 三种 case_type
3. 每个验收标准至少 1 条用例
4. 输出 JSON 数组，写入 fp_1_cases.json
5. verification 部分先留空（由 verify 阶段填充）
```

### 3.4 直接生成（功能点 < 3 个）

在主 Agent 中按功能点顺序生成所有验证用例，写入 `fp_{N}_cases.json`。

### 3.5 子 Agent 失败处理

1. Task 返回后用 Glob 确认 `fp_{N}_cases.json` 是否存在
2. 文件不存在或为空：重试 1 次
3. 重试仍失败：在主 Agent 中直接生成该功能点的用例
4. 所有功能点处理完后再进入 verify 阶段

## 阶段 4: verify - AI 推理验证

### 4.0 前提检查

如 init 阶段确定为**降级模式**（无代码实现）：
- 跳过本阶段的逐条追踪
- 所有用例的 `verification` 填充为：
  ```json
  {
    "method": "ai_reasoning",
    "result": "inconclusive",
    "trace": "代码不可用，无法追踪执行路径。用例已生成但未经代码推理验证，下游应按本地策略决定保留或跳过。",
    "confidence": null
  }
  ```
- 直接进入阶段 5

### 4.1 合并用例文件

读取所有 `fp_{N}_cases.json`，合并为统一列表。分配全局递增的 `case_id`（VC-1, VC-2, ...）。

### 4.2 逐条代码追踪

#### 4.2.0 可追踪性评估（前置步骤）

对每条用例，在实际追踪前先评估代码路径的静态可追踪性：

| 条件 | 处理方式 |
| --- | --- |
| 调用链超过 3 层 | 强制标记 `inconclusive`，原因 `call_depth_exceeded` |
| 包含动态分派（接口多态、泛型、反射） | 强制标记 `inconclusive`，原因 `dynamic_dispatch` |
| diff-only 模式（无完整源码） | confidence 上限 70 |
| 调用目标跨服务或外部依赖 | 强制标记 `inconclusive`，原因 `external_dependency` |

仅通过可追踪性评估的用例才进入下方追踪流程。

#### 4.2.1 追踪流程

对每条验证用例：

1. **定位入口**：根据 `input.params` 找到代码中处理该输入的入口函数/方法
2. **追踪路径**：沿调用链追踪输入如何被处理，记录关键节点
3. **判定结果**：比对实际执行路径的输出与 `expected.assertion`
   - 输出匹配预期 → `pass`
   - 输出不匹配预期 → `fail`，记录实际输出
   - 无法确定（代码路径不可达、逻辑过于复杂、信息不足）→ `inconclusive`
4. **反证检查**（仅 `pass` 结论）：构造一个使该断言失败的代码变体场景。如果能轻易构造（如删除一行条件判断即可导致失败）→ 降低 confidence 10 分并在 trace 中追加 `risk_note`
5. **评估置信度**：
   - 90-100：代码路径清晰，断言可直接验证，反证检查未发现风险
   - 70-89：代码路径可追踪但存在间接调用或条件分支
   - 50-69：基于 diff 推断，无法看到完整上下文
   - <50：纯推测，代码路径不可达

### 4.3 追踪记录格式

`verification.trace` 采用调用链格式：

```
入口函数() -> 中间调用() -> 关键逻辑(参数) -> 结果 == 预期值
```

示例：
- pass: `applyCoupon(100, 50) -> min(coupon, order) -> min(100, 50) -> 50 == expected 50 ✓`
- fail: `applyCoupon(100, 50) -> coupon - order -> 100 - 50 -> 50, 但实际返回 100 ≠ expected 50 ✗`
- inconclusive（外部依赖）: `applyCoupon() 存在但内部调用 externalService.calculate()，外部服务逻辑不可见`
- inconclusive（调用链过深）: `handleOrder() -> processPayment() -> validateCoupon() -> applyCoupon() -> calculateDiscount()，超过 3 层调用链`
- inconclusive（动态分派）: `processor.Execute() 为接口方法，实际实现取决于运行时注入`

`inconclusive` 的原因分类（记录在 `verification` 对象中）：

| 原因 | 含义 |
| --- | --- |
| `call_depth_exceeded` | 调用链超过 3 层，静态分析不可靠 |
| `dynamic_dispatch` | 包含接口多态、泛型或反射，无法确定实际执行路径 |
| `external_dependency` | 依赖外部服务或跨服务调用 |
| `insufficient_context` | diff-only 模式下缺少完整源码上下文 |
| `complex_logic` | 条件分支嵌套过深或涉及事务/并发等复杂语义 |

### 4.4 写入结果

将验证结果填充到每条用例的 `verification` 字段，合并后写入 `verification_cases.json`。

## 阶段 5: report - 报告生成

**前提**：回读 `verification_cases.json` 和 `verification_checklist.md`。

### 5.1 按需求点汇总

对每个 `requirement_id`，统计：

- 用例总数、pass 数、fail 数、inconclusive 数
- 覆盖评估：`充分`（所有验收标准有对应用例且 pass）/ `部分`（有用例但存在 fail 或 inconclusive）/ `不足`（缺少关键验收标准的用例）
- 风险等级：`low`（全部 pass）/ `medium`（存在 inconclusive）/ `high`（存在 fail）/ `critical`（无用例或全部 inconclusive）

### 5.2 置信度分布统计

按区间统计所有用例的置信度分布：

| 区间 | 标签 |
| --- | --- |
| 90-100 | 高置信度 |
| 70-89 | 中置信度 |
| 50-69 | 低置信度 |
| <50 | 极低置信度 |

### 5.3 风险区域识别

识别以下风险场景并记录到 `risk_areas`：

- 某功能点全部用例为 inconclusive → 高风险，代码可能不可达
- 某功能点存在 fail 用例 → 高风险，需求实现可能有缺陷
- 某功能点平均置信度 < 60 → 中风险，验证结论不够可靠
- 某功能点仅有 functional 类型用例，缺少 boundary/error → 中风险，覆盖不全

### 5.4 缺口识别

扫描需求功能点清单，识别：

- 未生成任何用例的功能点 → 记录到 `gaps`，标注原因
- 仅有 1 条用例的功能点 → 标注覆盖可能不足

### 5.5 生成 verification_report.json

按「输出格式」章节定义的结构写入报告。

### 5.6 输出摘要

在最终回复中给出文本摘要：

```markdown
## 验证报告摘要

- 功能点数：N
- 验证用例总数：M
- 通过 / 失败 / 待定：X / Y / Z
- 验证率：{(pass + fail) / total * 100}%
- 平均置信度：{avg}
- 风险区域：{数量}
- 覆盖缺口：{数量}
```
