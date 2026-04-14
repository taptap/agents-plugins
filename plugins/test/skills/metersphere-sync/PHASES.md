# MeterSphere 同步各阶段详细操作指南

## 阶段 1: init - 环境检查与输入路由

### 1.0 环境检查

1. 检查 `pycryptodome` 是否可用：`python3 -c "from Crypto.Cipher import AES"`
   - 不可用 → 提示用户 `pip install pycryptodome`，**停止**
2. 执行连通性检查：
   ```bash
   python3 $SKILLS_ROOT/shared-tools/scripts/metersphere_helper.py ping
   ```
   - 返回 `status: ok` → 继续
   - 失败 → **停止**，输出错误信息

### 1.1 输入路由

按 [CONVENTIONS.md](../../CONVENTIONS.md#上游输入消费) 定义的优先级确认输入：

1. 工作目录中存在 `final_cases.json` → 作为主输入
2. 工作目录中存在 `supplementary_cases.json` → 作为主输入
3. 以上均不存在 → **停止**

### 1.2 确定执行模式

- 用户指定 `mode=execute` 且工作目录中存在 `verification_cases.json` → execute 模式
- 否则 → sync 模式

### 1.3 确定参数

- `parent_module_id`：优先使用参数值，否则读取 `MS_DEFAULT_NODE_ID` 环境变量
- `plan_name`：优先使用参数值，否则询问用户提供需求名称
- `confidence_threshold`：优先使用参数值，否则默认 90

---

## 阶段 2: import - 创建模块与导入用例

### 2.1 导入用例

调用 `import-cases` 一次性完成模块创建和用例导入：

```bash
python3 $SKILLS_ROOT/shared-tools/scripts/metersphere_helper.py \
  import-cases <parent_module_id> <cases_file> [--requirement <需求名>]
```

- `--requirement`（推荐）：指定需求名称，会先在 `parent_module_id` 下创建需求级父模块，子模块再挂在其下。结构为：`父模块 / 需求名 / 子模块A, 子模块B...`
- 不指定时，子模块直接挂在 `parent_module_id` 下（向后兼容）

该命令自动：
- 按用例的 `module` 字段分组
- 为每个 module 创建子模块（已存在则复用），支持 `/` 分隔的多层路径
- 逐条导入用例，统一打上 `AI 用例生成` 标签
- 格式转换：`{action, expected}` → `{num, desc, result}`
- 名称清洗：去除内部标记（AC-1, RP-3）、截断超长名称（250 字）、处理重名

### 2.2 保存映射文件

将 `import-cases` 的 stdout 输出保存为 `ms_case_mapping.json`：

```json
{
  "imported": 28,
  "failed": 2,
  "modules_created": 5,
  "case_mapping": [
    {"local_id": "M1-TC-01", "ms_id": "uuid-xxx", "module": "登录模块", "name": "..."}
  ],
  "metersphere_url": "https://metersphere.tapsvc.com/#/track/case/all/..."
}
```

如有失败用例，在 stderr 中输出详情，但不中断流程。

---

## 阶段 3: plan - 查找或创建测试计划

### 3.1 查找或创建计划

```bash
python3 $SKILLS_ROOT/shared-tools/scripts/metersphere_helper.py \
  find-or-create-plan "<plan_name>" --stage smoke
```

- 已存在同名计划（限定在 AI 工作流分类下）→ 复用，输出 `is_new: false`
- 不存在 → 创建新计划，输出 `is_new: true`

### 3.2 关联用例

从 `ms_case_mapping.json` 提取所有 `ms_id`，关联到计划：

```bash
python3 $SKILLS_ROOT/shared-tools/scripts/metersphere_helper.py \
  add-cases-to-plan <plan_id> --case-ids <ms_id1>,<ms_id2>,...
```

### 3.3 保存计划信息

将计划信息保存为 `ms_plan_info.json`：

```json
{
  "plan_id": "uuid-zzz",
  "plan_name": "优惠券功能",
  "plan_url": "https://metersphere.tapsvc.com/#/track/plan/view/uuid-zzz",
  "is_new": false,
  "associated_cases": 28
}
```

---

## 阶段 4: execute - 验证结果回写（仅 mode=execute）

此阶段仅在 `mode=execute` 时执行，需要 `verification_cases.json` 输入。

### 4.0 冒烟测试报告前置检查

读取 `smoke_test_report.json`（如存在）。若文件存在且 `verdict == "fail"`：

1. 提取 P0 缺陷摘要：`defect_summary.by_priority.P0` 数量 + `fail_reason`
2. **全量降级**：跳过正常 VC 判定逻辑（4.3-4.4），将计划中**所有用例**标记为 `Prepare`：
```bash
python3 $HELPER update-case-result <plan_case_id> Prepare \
  --comment "冒烟测试未通过（P0 缺陷 {N} 个：{fail_reason}），需人工验证"
```
3. 降级完成后直接跳到 4.5

若文件不存在或 `verdict == "pass"`，继续正常流程（4.1-4.4）。Pass 时将 `traceability_summary` 追加到回写评论中作为补充信息。

### 4.1 加载验证数据

读取 `verification_cases.json`，提取每条 VC 的：
- `case_id`（VC-N 格式）
- `requirement_id`（FP-N 格式）
- `verification.result`（pass / fail / inconclusive）
- `verification.confidence`（0-100）

### 4.2 获取计划用例

```bash
python3 $SKILLS_ROOT/shared-tools/scripts/metersphere_helper.py \
  list-plan-cases <plan_id>
```

### 4.3 匹配 VC 到计划用例

通过 `requirement_points.json`（如存在）桥接：
1. VC 的 `requirement_id`（FP-N）→ `requirement_points` 的 `name`
2. `requirement_points` 的 `name` → `final_cases` 的 `module` → MS 计划用例的 `node_path`

匹配粒度为**需求点（FP）级别**，同一 FP 下聚合所有 VC 的验证结果。

### 4.4 判定与回写

对每个需求点（FP），聚合关联 VC 的结果后判定：

**Pass 判定**：该 FP 下所有 VC 的 `confidence >= threshold` 且 `result == "pass"`
```bash
python3 $HELPER update-case-result <plan_case_id> Pass \
  --actual-result "AI 验证通过，平均置信度 95%" \
  --comment "AI 自动验证：所有关联验证用例均通过"
```

**Failure 判定**：该 FP 下任一 VC 的 `confidence >= 70` 且 `result == "fail"`
```bash
python3 $HELPER update-case-result <plan_case_id> Failure \
  --actual-result "AI 验证失败，VC-3 未通过" \
  --comment "AI 自动验证：验证用例 VC-3 未通过（置信度 80%）"
```

**Manual 判定**：其余情况
- 保持 `Prepare` 状态
- 添加评论注明原因：
```bash
python3 $HELPER update-case-result <plan_case_id> Prepare \
  --comment "AI 置信度不足（平均 65%），需人工验证"
```

### 4.5 重新执行场景

- **有补充用例**（`supplementary_cases.json` 存在）：先执行 Phase 2 导入 + Phase 3 追加关联，再执行 Phase 4 回写
- **无补充用例**：直接对计划中已有用例重新验证回写（覆盖之前的状态和评论）

---

## 阶段 5: output - 生成报告

### 5.1 生成 ms_sync_report.json

汇总所有阶段的结果：

```json
{
  "sync_mode": "execute",
  "timestamp": "2026-04-08T15:30:00+08:00",
  "import": {
    "source_files": ["final_cases.json"],
    "total_cases": 30,
    "imported": 28,
    "failed": 2,
    "modules_created": 5,
    "metersphere_url": "https://metersphere.tapsvc.com/#/track/case/all/..."
  },
  "plan": {
    "plan_id": "uuid-zzz",
    "plan_name": "优惠券功能",
    "plan_url": "https://metersphere.tapsvc.com/#/track/plan/view/uuid-zzz",
    "is_existing_plan": false,
    "associated_cases": 28
  },
  "execution": {
    "auto_passed": 15,
    "auto_failed": 3,
    "manual_required": 10,
    "confidence_threshold": 90,
    "details": [
      {"requirement_id": "FP-1", "verdict": "pass", "avg_confidence": 95, "tc_count": 5},
      {"requirement_id": "FP-2", "verdict": "fail", "failed_vcs": ["VC-3"], "tc_count": 3},
      {"requirement_id": "FP-3", "verdict": "manual", "reason": "置信度不足(avg 65)", "tc_count": 2}
    ]
  }
}
```

### 5.2 输出摘要

在聊天中向用户展示：
- 导入统计：N 条用例导入成功 / M 条失败
- 测试计划链接
- 执行回写统计（execute 模式）：N 条自动通过 / M 条自动失败 / K 条需人工验证

### 5.3 完成验证

检查 `ms_sync_report.json`、`ms_case_mapping.json`、`ms_plan_info.json` 是否已生成且内容有效。
