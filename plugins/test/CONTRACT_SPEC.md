# contract.yaml 编写规范

本文件定义 test 插件中 `contract.yaml` 的结构和编写规则。每个 skill 目录下必须包含一个 `contract.yaml`，声明该 skill 的输入输出接口，供编排层和开发者使用。

## 与 SKILL.md 的关系

- `SKILL.md` 是给 AI Agent 读的执行指令，描述分析逻辑和工具调用方式
- `contract.yaml` 是给编排层和开发者读的接口定义，描述输入输出契约
- 两者职责不同，不应混在一起；但必须保持一致

## 结构定义

```yaml
name: string          # skill 目录名，与目录名一致
version: "1.0"        # 语义化版本，接口不兼容变更时递增主版本
description: string   # 一句话描述 skill 的功能

input:
  required:
    field_name:
      type: string | file | file[] | string[]
      description: string
  one_of:                             # 可选：至少提供其中一个字段（互斥选择），编排层负责校验
    field_name:
      type: string | file | file[] | string[]
      description: string
  any_of:                             # 可选：至少提供其中一个字段（可同时提供多个），编排层负责校验
    field_name:
      type: string | file | file[] | string[]
      description: string
  optional:
    field_name:
      type: string | file | file[] | string[]
      description: string
      from_upstream: skill_name  # 可选：标注哪个上游 skill 能提供此输入

output:
  files:
    - name: string              # 输出文件名
      description: string       # 文件内容说明
      format: json | markdown   # 文件格式
  structured:                   # 可选：结构化摘要字段，供编排层快速消费
    field_name:
      type: string | number | boolean | string[] | object
      description: string

dependencies:
  skills:                       # 可选：依赖的其他 skill（目录名）
    - shared-tools
  scripts:                      # 依赖的脚本列表（相对于 skills/ 目录）
    - shared-tools/scripts/fetch_feishu_doc.py
  env_vars:                     # 必需的环境变量
    - FEISHU_APP_ID
    - FEISHU_APP_SECRET
  mcp_servers:                  # 可选：依赖的 MCP server（仅依赖外部 MCP 服务的 skill 使用）
    - plugin-figma-figma
  tools:                        # 可选：依赖的 MCP 工具（仅依赖外部 MCP 服务的 skill 使用）
    - get_screenshot
```

## 编写规则

1. `name` 必须与 skill 目录名一致
2. `input.required` 中的字段是 skill 执行的前提条件，缺失则 skill 无法启动。当所有输入均为必填（无可选替代）时使用 `required`；当多个输入互为替代（至少提供一个）时使用 `one_of`
3. `input.one_of` 中的字段至少需要提供一个（互斥选择，skill 按优先级取第一个命中的），编排层负责校验；skill 内部按 CONVENTIONS.md 定义的输入路由优先级处理
4. `input.any_of` 中的字段至少需要提供一个（可同时提供多个，skill 合并处理所有提供的输入），编排层负责校验
5. `input.optional` 中标注 `from_upstream` 的字段，编排层会自动从上游 skill 的输出中填充。`from_upstream` 支持数组语法表示多个可能的上游来源：`from_upstream: [unit-test-design, integration-test-design]`（语义：任一上游都可提供此输入）
6. `output.files` 列出所有 skill 会产出的文件，文件名必须确定（不使用通配符）
7. `output.structured` 用于编排层快速判断 skill 执行结果，无需解析文件
8. `version` 遵循语义化版本：主版本号变更表示接口不兼容，次版本号变更表示向后兼容的功能新增
9. 所有 `description` 使用中文
10. 对于支持型 guide 或共享工具型 skill（仅作为参考文档被其他 skill 引用，自身不执行分析流程），`input` 和 `output` 可为空对象 `{}`。此时仍需声明 `dependencies`（如有脚本或环境变量依赖）

## 验证方式

使用 `validate_contracts.py` 脚本验证所有 contract.yaml 的格式正确性：

```bash
python3 plugins/test/skills/shared-tools/scripts/validate_contracts.py plugins/test/skills/
```

脚本检查：name 与目录名一致、required/one_of/any_of 字段类型合法、output.files 格式正确、from_upstream 引用的 skill 存在。
