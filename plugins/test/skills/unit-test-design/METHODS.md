# 单元测试方法论与参考模板

init 阶段识别项目技术栈后，只 Read 对应语言的方法文件，不需要全部加载。

**定位**：当项目中已有测试代码时，应优先从已有测试中学习框架、Mock 方式和风格约定（init 阶段完成）。本文件的模板仅在以下场景使用：
- 项目中完全没有已有测试文件（全新项目）
- 项目已有测试使用了不熟悉的框架，需要对照参考
- 需要了解某个测试设计模式的通用写法（如 property-based testing）

## 语言选择表

| 语言 | 文件 | 框架 | 主要内容 |
| --- | --- | --- | --- |
| Go | [methods/go.md](methods/go.md) | testing + testify | 表驱动测试、Mock 接口、HTTP Mock、DB Mock、rapid 属性测试、强/弱断言示例 |
| Python | [methods/python.md](methods/python.md) | pytest | 参数化测试、Mock 依赖、HTTP Mock (responses)、Fixture、hypothesis 属性测试、强/弱断言示例 |
| TypeScript | [methods/typescript.md](methods/typescript.md) | vitest / jest | describe/it 嵌套、Mock 模块、HTTP Mock (msw)、fast-check 属性测试 |
| Java | [methods/java.md](methods/java.md) | JUnit 5 + Mockito | 参数化测试、Mock 依赖 |
| Kotlin | [methods/kotlin.md](methods/kotlin.md) | JUnit 5 + MockK | Mock 依赖 |
| Swift | [methods/swift.md](methods/swift.md) | XCTest + Swift Testing | 基础测试、Protocol Mock、URLProtocol Mock、@testable import、参数化、XCTest vs Swift Testing 选型、Fixture 加载、SwiftCheck |

## 通用原则（所有语言适用）

[methods/general.md](methods/general.md) 包含：

- **Property-Based Testing**：何时使用属性测试、各语言库索引
- **弱断言 vs 强断言**：AI 生成测试的常见陷阱与改进规则
- **测试命名**：各语言命名规则速查表
- **覆盖矩阵**：每个被测函数应覆盖的用例类型（P0-P3）

## 使用方式

1. init 阶段识别项目语言 → Read 对应语言的 `methods/{lang}.md`
2. 如需了解 Property-Based Testing 或通用原则 → Read `methods/general.md`
3. 复杂项目涉及多语言 → 按需 Read 多个文件

## Swift 选型提示

Swift 项目需在 init 阶段做框架选择决策（XCTest vs Swift Testing）。详细选型规则见 [methods/swift.md](methods/swift.md) 的「XCTest 与 Swift Testing 选型策略」章节。
