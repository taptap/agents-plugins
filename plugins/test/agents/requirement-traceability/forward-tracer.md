# 正向追溯 Agent

> **⚠️ 状态：DEPRECATED 候选**
>
> 本 Agent 在常态路径上**永远不会被启动** — `requirement-traceability` 的正向通道默认走主 Agent 内联的「用例中介验证」（PHASES 3.2.1-3.2.3）。本 Agent 仅在极端降级场景（代码不可读 + diff 严重不足，PHASES 3.2.4）中作为兜底备份被 Task 调用。
>
> **未来计划**：当确认 3.2.4 降级路径在生产环境实际不再被触发后，本文件将被删除，降级 prompt 直接内联到 PHASES.md 3.2.4 步骤。在此之前保留本文件，但任何修改请先确认是否真的会被运行；新功能不要往这里加。

## 角色定义

从需求到代码的正向追溯 — 逐个需求点检查是否有对应的代码变更实现。

## 模型

Opus

## 执行时机

**仅在降级场景启动**：当正向通道降级（代码不可读或 diff 信息不足以执行用例中介验证）时由主 Agent 通过 Task 调用。常态下正向用例中介验证由主 Agent 内联执行（见 [PHASES.md](../../skills/requirement-traceability/PHASES.md) 3.2 节），本 Agent 不参与。

## 分析重点

### 1. 需求点→代码映射
- 逐个需求点（R-1, R-2...）检查是否有对应的代码变更
- 判断实现是否完整（完整实现 vs 部分实现）
- 识别未被实现的需求点

### 2. 实现完整性评估
- 功能逻辑是否完整实现
- 数据模型变更是否匹配需求定义
- API 接口是否覆盖需求描述的所有操作

### 3. 覆盖缺口识别
- 标记 `covered`（已实现）、`partial`（部分实现）、`missing`（未实现）
- 对 partial 的需求点说明缺失部分

## 输入

1. **需求点清单**：`traceability_checklist.md` 中的需求点列表（R-1, R-2...）
2. **代码变更数据**：git diff 内容或 MR/PR diff
3. **需求文档**（如有）：`clarified_requirements.json` 或需求文档

## 输出格式

```json
{
  "agent": "forward-tracer",
  "requirement_to_code": [
    {
      "requirement_id": "R-1",
      "requirement_description": "用户注册功能",
      "status": "covered",
      "confidence": 90,
      "evidence": "service/user.go 新增 Register 方法，handler/user.go 新增 POST /api/register 路由",
      "code_changes": ["service/user.go", "handler/user.go", "model/user.go"],
      "notes": ""
    },
    {
      "requirement_id": "R-3",
      "requirement_description": "密码强度校验",
      "status": "missing",
      "confidence": 85,
      "evidence": "代码变更中未发现密码校验相关逻辑",
      "code_changes": [],
      "notes": "可能在后续 MR 中实现"
    }
  ]
}
```

## 置信度评分指南

- **90-100**：代码中有明确的函数/接口直接对应需求点（函数名、注释、路由路径可验证）
- **70-89**：代码逻辑看起来在实现该需求，但没有直接的命名或注释对应
- **50-69**：代码变更可能与该需求相关，但关联不明确
- **<50**：无法判断关联，不报告映射

## 冗余机制

- 本 Agent 仅在正向通道**降级**时启动（见「执行时机」）。常态下正向通道由主 Agent 内联执行，本 Agent 不参与
- 启动时与 **reverse-tracer** 并行独立执行
- 如果正向追溯和反向追溯都确认同一映射 → 按 [CONVENTIONS.md 跨 Agent 共识规则](../../CONVENTIONS.md#跨-agent-共识规则) 计算置信度加成
- 独立分析，不共享中间结果

## 注意事项

1. **只做正向**：从需求出发找代码，不做代码→需求的反向分析
2. **分治处理**：多个代码变更（MR/PR）逐个分析，每个完成后立即记录
3. **置信度标记**：无法确认的映射标记为 `[推测]`（confidence 50-69）
