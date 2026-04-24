# 单测 vs 集成测 vs E2E 边界

本文档定义 `unit-test-design`、`integration-test-design`、以及上游 `test-case-generation`（E2E 用例）三者的职责边界，避免对同一行为重复生成测试。

## 一句话判断

> **能在 5 分钟内写成独立的纯函数测试吗？能 → unit。不能 → 涉及网络/SDK/IO 边界？是 → integration（mock 边界）。否 → E2E。**

## 分层定义

| 层 | 行为主体 | 真相来源 | 谁来生成 |
| --- | --- | --- | --- |
| L1 数据解析 | JSON → Model | 真实 API fixture | unit-test-design |
| L2 类型识别 | Model 上的复合谓词 | 产品文档 | unit-test-design |
| L3 业务逻辑 | ViewModel / Service 决策 | 产品规则 | unit-test-design |
| L4 展示决策 | ViewModel 主/副选取、过滤 | 回归用例 | unit-test-design |
| L5 接口/模块协作 | 网络请求、路由跳转、跨模块通知 | API 契约 + 模块协议 | integration-test-design |
| L6 端到端业务流 | 用户操作 → UI 反馈 | 验收标准 | test-case-generation（E2E）|

L1-L4 是 unit 范围；L5 是 integration 范围；L6 是 E2E 范围。当一个功能点可拆到多层时，**优先下沉**：纯函数能覆盖的就不进 integration，integration 能覆盖的就不进 E2E。

## 重叠场景的归属规则

| 行为类型 | 归属 | 理由 |
| --- | --- | --- |
| API 入参序列化（含字段命名、大数包装） | integration | 涉及网络层契约，需 mock URLProtocol/HTTP client |
| API 响应反序列化 | unit | 纯函数：JSON → Model |
| 多分支业务推断（如「这条消息要操作哪个 moment」）| unit | 纯函数枚举即可 |
| 路由跳转分发 | integration | 涉及 Router/导航栈 |
| 通知监听 + 副作用 | integration | 跨模块协作 |
| 埋点字段格式 | integration | 涉及 SDK 边界，需 mock SDK 抓 payload |
| 埋点触发条件（什么场景该埋）| E2E | 用户行为驱动，单测验证不了「什么时候会调用」 |
| UI 渲染 / 手势 / 视觉对齐 | E2E | 必须看到画面 |
| 跨端契约一致性 | 由 api-contract-validation 处理，不重复 |

## 跳过原则（两个 skill 都遵守）

不为以下场景生成测试：

- 单行委托、纯 getter/setter
- 无业务规则的简单包装（如 DTO copy）
- 框架/语言层默认行为（如 Codable 自动生成的 init）
- 已经有更高层覆盖且更高层失败时能定位到这里的场景

跳过的场景必须在各自的 plan 文件（`test_plan.md` / `integration_test_plan.md`）的「跳过的用例」表格中记录原因。

## 给上游的信号

`test-case-generation` 不再做分层判断 — E2E 用例集默认覆盖 L6 验收行为。开发完成后由开发者自行触发 `unit-test-design` 和 `integration-test-design`，两个 skill 各自按本文档的归属规则做价值评估，跳过不属于自己范围或价值不足的场景。

如果两个 skill 都判断「不该我测」，说明这是 L6 行为，由 E2E 用例兜底。
