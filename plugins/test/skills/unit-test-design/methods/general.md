# 通用测试原则与跨语言参考

## Property-Based Testing（属性测试）

对纯函数、转换器、校验器等无副作用的代码，property-based testing 比固定样例更有效——它用随机输入验证不变量，而非只检查几个 AI 选定的值。

### 何时使用 Property-Based Testing

| 场景 | 属性示例 |
| --- | --- |
| 序列化/反序列化 | `decode(encode(x)) == x` |
| 校验器 | 不合法输入一定被拒绝 |
| 排序/过滤 | 输出是输入的子集且有序 |
| 数学运算 | `add(a, b) == add(b, a)`，`abs(x) >= 0` |
| 幂等操作 | `f(f(x)) == f(x)` |
| 范围约束 | `clamp(x, min, max)` 的结果在 `[min, max]` 内 |

各语言的 property-based testing 库和代码模板见对应语言文件：
- Go: `go.md` — rapid
- Python: `python.md` — hypothesis
- TypeScript: `typescript.md` — fast-check
- Swift: `swift.md` — Swift Testing 参数化（轻量替代）/ SwiftCheck

## 弱断言 vs 强断言

AI 生成测试时容易使用过弱的断言，导致测试永远通过。以下对比说明如何加强断言质量。

各语言的具体示例见对应语言文件（Go: `go.md`，Python: `python.md`）。

**通用规则**：

- 不要只检查 "不为空" / "没有错误"，要验证返回值的关键字段
- 错误路径不要只检查 "有错误"，要验证具体的错误类型
- 集合类型不要只检查 `len > 0`，要验证具体内容或结构

## 测试命名

| 语言 | 命名规则 | 示例 |
| --- | --- | --- |
| Go | `Test{Function}_{Scenario}_{Expected}` | `TestParseConfig_EmptyInput_ReturnsError` |
| Python | `test_{function}_{scenario}` | `test_parse_config_empty_input_raises` |
| TypeScript | describe + it 描述 | `it('should throw on empty input')` |
| Java | `should{Expected}When{Scenario}` | `shouldThrowWhenInputIsEmpty` |
| Kotlin | 反引号描述 | `` `should throw when input is empty` `` |
| Swift (XCTest) | `test{Function}{Scenario}` | `testParseConfigEmptyInput` |
| Swift (Swift Testing) | `@Suite("描述")` + `@Test("描述")` | `@Suite("ConfigParser") struct ConfigParserTests` + `@Test("空输入抛出错误") func parseEmptyInput()` |

## 测试用例覆盖矩阵

对每个被测函数，至少覆盖以下类型：

| 类型 | 说明 | 优先级 |
| --- | --- | --- |
| 正向路径 | 典型有效输入 → 正确输出（验证关键字段） | P0 |
| 边界值 | 零值、空值、最大值、最小值 | P1 |
| 错误处理 | 无效输入 → 预期错误（具体 error 类型） | P1 |
| 反例 | 验证不该通过的输入确实被拒绝 | P1 |
| 属性测试 | 纯函数/转换器的不变量验证（如适用） | P1 |
| Mock 验证 | 依赖调用次数和参数正确 | P1 |
| 并发安全 | 多 goroutine/线程并发调用（如适用） | P2 |
| 性能基准 | Benchmark（如适用） | P3 |
