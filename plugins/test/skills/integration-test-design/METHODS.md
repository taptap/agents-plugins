# 集成测试方法论与参考模板

> **init 阶段识别项目技术栈后，只 Read 对应语言的方法文件，不需要全部加载。**

**定位**：当项目中已有集成测试代码时，应优先从已有测试中学习框架、数据库策略和 Mock 方式（init 阶段完成）。本文件的模板仅在以下场景使用：
- 项目中完全没有已有集成测试（首次添加）
- 需要了解某种集成测试模式的通用写法（如 testcontainers、消息队列测试）

## 语言选择

| 技术栈 | 方法文件 | 说明 |
| --- | --- | --- |
| Go | [methods/go.md](methods/go.md) | httptest、testcontainers、事务回滚、Mock 外部服务、Auth 中间件、gRPC bufconn、Channel 异步验证、定时任务 |
| Python | [methods/python.md](methods/python.md) | pytest + httpx、pytest fixtures 事务回滚、responses Mock、asyncio 异步测试 |
| TypeScript / Node.js | [methods/typescript.md](methods/typescript.md) | supertest API 测试 |
| Swift / iOS | [methods/swift.md](methods/swift.md) | DeepLink 路由、URLProtocol Stub、通知处理、Combine Publisher、RxSwift、弱断言 vs 强断言、iOS 覆盖矩阵 |

## 跨语言通用原则

所有语言通用的测试设计原则见 [methods/general.md](methods/general.md)，包括：

- **测试数据策略** — 内联构造、Factory 函数、Fixture 文件、Builder 模式的选型对比
- **弱断言 vs 强断言** — API 正向/错误/删除场景的断言深度对比（含 Go、Python 代码示例）
- **测试场景覆盖矩阵** — 每个 API 接口应覆盖的维度（正向、参数验证、认证授权、业务规则、幂等性、并发）

## 使用方式

1. init 阶段识别项目语言 -> Read 对应语言的 `methods/{lang}.md`
2. 如需了解跨语言通用原则 -> Read `methods/general.md`
3. 复杂项目涉及多语言 -> 按需 Read 多个文件
