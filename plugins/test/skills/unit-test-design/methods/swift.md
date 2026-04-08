# Swift 单元测试参考模板

## XCTest

### 基础测试

```swift
class ConfigParserTests: XCTestCase {

    func testParseValidJSON() throws {
        let data = #"{"key": "value"}"#.data(using: .utf8)!
        let config = try ConfigParser.parse(data)
        XCTAssertEqual(config.key, "value")
    }

    func testParseEmptyInput() {
        XCTAssertThrowsError(try ConfigParser.parse(Data())) { error in
            XCTAssertTrue(error is ParseError)
        }
    }

    func testParseNilInput() {
        XCTAssertThrowsError(try ConfigParser.parse(nil))
    }
}
```

### Protocol Mock（手写 Mock）

Swift 没有运行时 Mock 框架（如 Mockito），通过 protocol + 手写 Mock 实现依赖隔离：

```swift
protocol UserRepository {
    func getByID(_ id: Int64) throws -> User?
}

final class MockUserRepository: UserRepository {
    var stubbedResult: User?
    var stubbedError: Error?
    private(set) var getByIDCallCount = 0
    private(set) var lastRequestedID: Int64?

    func getByID(_ id: Int64) throws -> User? {
        getByIDCallCount += 1
        lastRequestedID = id
        if let error = stubbedError { throw error }
        return stubbedResult
    }
}

class UserServiceTests: XCTestCase {

    func testGetUser() throws {
        let mockRepo = MockUserRepository()
        mockRepo.stubbedResult = User(id: 1, name: "Alice")
        let svc = UserService(repository: mockRepo)

        let user = try svc.getUser(id: 1)

        XCTAssertEqual(user?.name, "Alice")
        XCTAssertEqual(mockRepo.getByIDCallCount, 1)
        XCTAssertEqual(mockRepo.lastRequestedID, 1)
    }
}
```

### URLProtocol Mock（网络请求拦截）

通过 URLProtocol 子类拦截 URLSession 请求，无需真实网络：

```swift
final class StubURLProtocol: URLProtocol {
    static var requestHandler: ((URLRequest) throws -> (HTTPURLResponse, Data?))?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        guard let handler = Self.requestHandler else {
            client?.urlProtocol(self, didFailWithError: URLError(.unknown))
            return
        }
        do {
            let (response, data) = try handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            if let data { client?.urlProtocol(self, didLoad: data) }
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {}
}

class NetworkServiceTests: XCTestCase {

    override func setUp() {
        super.setUp()
        URLProtocol.registerClass(StubURLProtocol.self)
    }

    override func tearDown() {
        URLProtocol.unregisterClass(StubURLProtocol.self)
        StubURLProtocol.requestHandler = nil
        super.tearDown()
    }

    func testFetchUserProfile() async throws {
        StubURLProtocol.requestHandler = { request in
            XCTAssertEqual(request.url?.path, "/api/user/1")
            let response = HTTPURLResponse(url: request.url!, statusCode: 200,
                                           httpVersion: nil, headerFields: nil)!
            let data = #"{"id":1,"name":"Alice"}"#.data(using: .utf8)
            return (response, data)
        }

        let config = URLSessionConfiguration.ephemeral
        config.protocolClasses = [StubURLProtocol.self]
        let session = URLSession(configuration: config)

        let svc = NetworkService(session: session)
        let user = try await svc.fetchUser(id: 1)

        XCTAssertEqual(user.name, "Alice")
    }
}
```

### `@testable import`

使用 `@testable import` 访问模块的 `internal` 符号，无需将被测类型改为 `public`：

```swift
@testable import MyApp

class InternalLogicTests: XCTestCase {
    func testInternalParser() {
        let result = InternalParser.parse("input")
        XCTAssertEqual(result.count, 3)
    }
}
```

## Swift Testing

Swift Testing 是 Apple 推出的现代测试框架（Xcode 16+ / Swift 6+），使用 `@Suite`、`@Test`、`#expect` 替代 XCTest 的类继承模式。**新项目或新增测试文件优先使用 Swift Testing**，已有 XCTest 测试保持不变。

### 基础测试

```swift
import Testing
@testable import MyApp

@Suite("ConfigParser 解析")
struct ConfigParserTests {

    @Test("解析合法 JSON")
    func parseValidJSON() throws {
        let data = #"{"key": "value"}"#.data(using: .utf8)!
        let config = try ConfigParser.parse(data)
        #expect(config.key == "value")
    }

    @Test("空输入抛出错误")
    func parseEmptyInput() {
        #expect(throws: ParseError.self) {
            try ConfigParser.parse(Data())
        }
    }

    @Test("nil 输入抛出错误")
    func parseNilInput() {
        #expect(throws: (any Error).self) {
            try ConfigParser.parse(nil)
        }
    }
}
```

### 参数化测试（表驱动）

Swift Testing 原生支持参数化，通过 `@Test(arguments:)` 实现表驱动测试：

```swift
import Testing
@testable import MyApp

@Suite("Processer 文本替换")
struct ProcesserTests {

    struct TestCase: CustomTestStringConvertible {
        let input: String
        let path: String
        let shouldReplace: Bool
        var testDescription: String {
            "path=\(path), input=\(input), shouldReplace=\(shouldReplace)"
        }
    }

    static let whitelistCases: [TestCase] = [
        TestCase(input: "安卓手机", path: "/app/v4/detail", shouldReplace: true),
        TestCase(input: "Google Play", path: "/app/v6/detail", shouldReplace: true),
    ]

    static let nonWhitelistCases: [TestCase] = [
        TestCase(input: "安卓手机", path: "/other/path", shouldReplace: false),
        TestCase(input: "正常文本", path: "/app/v4/detail", shouldReplace: false),
    ]

    @Test("白名单路径替换敏感词", arguments: whitelistCases)
    func whitelistReplace(testCase: TestCase) {
        let data = testCase.input.data(using: .utf8)!
        let result = Processer.adjust(data, for: testCase.path)
        let output = String(data: result, encoding: .utf8)!
        #expect(output != testCase.input, "白名单路径应替换敏感词")
    }

    @Test("非白名单路径保持原样", arguments: nonWhitelistCases)
    func nonWhitelistPreserve(testCase: TestCase) {
        let data = testCase.input.data(using: .utf8)!
        let result = Processer.adjust(data, for: testCase.path)
        let output = String(data: result, encoding: .utf8)!
        #expect(output == testCase.input, "非白名单路径不应替换")
    }
}
```

### 多参数组合

`@Test(arguments:, :)` 支持两个参数集合的笛卡尔积：

```swift
@Suite("URL 校验")
struct URLValidatorTests {

    static let schemes = ["http", "https", "ftp"]
    static let hosts = ["example.com", "localhost", ""]

    @Test("scheme + host 组合", arguments: schemes, hosts)
    func validateURL(scheme: String, host: String) {
        let url = "\(scheme)://\(host)"
        let result = URLValidator.validate(url)
        if host.isEmpty {
            #expect(!result, "\(url) 不应通过验证")
        } else {
            #expect(result, "\(url) 应通过验证")
        }
    }
}
```

### XCTest 与 Swift Testing 选型策略

| 维度 | XCTest | Swift Testing |
| --- | --- | --- |
| 语法 | class 继承 + `test` 前缀方法 | struct + `@Suite` + `@Test` |
| 断言 | `XCTAssert*` 系列 | `#expect` / `#require` |
| 参数化 | 无原生支持，需手写循环 | `@Test(arguments:)` 原生支持 |
| setUp/tearDown | `override func setUp()` | `init()` / `deinit` |
| 适用 | 已有测试、UI 测试（XCUITest）、性能测试 | 新增单元测试、参数化场景 |

**共存规则**：同一 test target 可同时包含 XCTest 和 Swift Testing 文件，Xcode 会自动识别并运行两种框架的测试。

**批次一致性规则**：unit-test-design skill 在同一次执行中生成的所有测试文件**必须使用同一个框架**。init 阶段的选择逻辑：

1. 项目已有测试**全部**使用 XCTest → 新测试使用 XCTest
2. 项目已有测试**全部**使用 Swift Testing → 新测试使用 Swift Testing
3. 项目中两种框架共存 → 优先使用 Swift Testing（除非待测模块的已有测试全部使用 XCTest）
4. 项目无已有测试 → 使用 Swift Testing（Xcode 16+ 项目的默认选择）

选择结果记录在 `test_plan.md` 的「项目测试约定」章节中，Phase 4 生成代码时严格遵循。

## iOS/Swift 项目 Fixture 加载最佳实践

Fixture（JSON / Protobuf / plist 等真实 API 响应文件）放在 test target 的 `Fixtures/` 子目录中。以下方式适用于 XCTest 和 Swift Testing，按优先级选用：

**方式 1：`#filePath` 相对路径（推荐，XCTest 和 Swift Testing 通用）**

```swift
import Foundation

enum FixtureLoader {
    static func load(_ filename: String, relativeTo filePath: String = #filePath) throws -> Data {
        let fixtureURL = URL(fileURLWithPath: filePath)
            .deletingLastPathComponent()
            .appendingPathComponent("Fixtures")
            .appendingPathComponent(filename)
        return try Data(contentsOf: fixtureURL)
    }

    static func loadJSON<T: Decodable>(_ filename: String, as type: T.Type, relativeTo filePath: String = #filePath) throws -> T {
        let data = try load(filename, relativeTo: filePath)
        return try JSONDecoder().decode(type, from: data)
    }
}
```

使用示例：

```swift
@Test("解析游戏详情 fixture")
func parseGameDetail() throws {
    let data = try FixtureLoader.load("game_detail_response.json")
    let detail = try JSONDecoder().decode(GameDetail.self, from: data)
    #expect(detail.id == 12345)
}
```

**方式 2：Bundle.module（仅限 SwiftPM test target）**

Swift Testing：
```swift
let url = try #require(Bundle.module.url(forResource: "game_detail_response", withExtension: "json"))
let data = try Data(contentsOf: url)
```

XCTest：
```swift
let url = try XCTUnwrap(Bundle.module.url(forResource: "game_detail_response", withExtension: "json"))
let data = try Data(contentsOf: url)
```

**不推荐的做法**：

- 在 `loadFixture()` 中用多个 `if-else` 回退不同路径（如 test Bundle → `#filePath` → 绝对路径），增加环境敏感性
- 在测试方法中硬编码绝对路径
- 依赖 `Bundle(for: type(of: self))` 而不验证资源是否存在

**CI 兼容性**：`#filePath` 方式不依赖 Bundle 资源拷贝，在本地 Xcode、`xcodebuild` CLI、CI 环境下行为一致，是最可靠的选择。

## Property-Based Testing — Swift Testing 参数化（轻量替代）

Swift 生态没有成熟的 property-based testing 库，但 Swift Testing 的 `@Test(arguments:)` 可作为轻量替代——用静态数据集覆盖多种输入，比单个 happy path 有效得多：

```swift
import Testing

@Suite("Clamp 属性验证")
struct ClampTests {

    static let values = Array(stride(from: -100, through: 200, by: 17))

    @Test("结果始终在 [min, max] 范围内", arguments: values)
    func clampStaysInRange(value: Int) {
        let result = clamp(value, min: 0, max: 100)
        #expect(result >= 0 && result <= 100,
                "clamp(\(value), 0, 100) = \(result)，超出范围")
    }

    static let roundTripInputs = [
        #"{"key":"value"}"#,
        #"{"nested":{"a":1}}"#,
        #"{}"#,
        #"{"list":[1,2,3]}"#,
    ]

    @Test("序列化往返一致性", arguments: roundTripInputs)
    func roundTrip(json: String) throws {
        let data = json.data(using: .utf8)!
        let parsed = try ConfigParser.parse(data)
        let reEncoded = try JSONEncoder().encode(parsed)
        let reParsed = try ConfigParser.parse(reEncoded)
        #expect(parsed == reParsed, "round-trip 不一致")
    }
}
```

如项目引入了 [SwiftCheck](https://github.com/typelift/SwiftCheck) 库，可使用真正的随机化属性测试：

```swift
import SwiftCheck
import XCTest

class ValidatorPropertyTests: XCTestCase {
    func testEmailRejectsNoAt() {
        property("不含 @ 的字符串不是合法邮箱") <- forAll { (s: String) in
            !s.contains("@") ==> !validateEmail(s)
        }
    }
}
```
