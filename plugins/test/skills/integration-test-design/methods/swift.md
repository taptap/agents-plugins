# Swift/iOS 集成测试参考模板

iOS 客户端的集成测试关注的不是 HTTP 服务端的 CRUD，而是**客户端内部多组件协作的完整链路**：路由导航、网络请求->业务处理、推送通知->路由跳转、跨模块数据流等。

## 路由导航集成测试

验证 URL -> 路由匹配 -> VC 实例化 -> 参数传递的完整链路：

```swift
import XCTest
@testable import MyApp
import TapRouter

final class DeepLinkIntegrationTests: XCTestCase {

    private var routerHelper: RouterTestHelper!

    override func setUp() {
        super.setUp()
        routerHelper = RouterTestHelper()
        routerHelper.install()
        RouterRegisterManager.registerRouter()
    }

    override func tearDown() {
        routerHelper.uninstall()
        super.tearDown()
    }

    func test_universalLink_convertsAndRoutes() {
        let webURL = URL(string: "https://www.example.com/item/12345")!

        let converted = LaunchRouterManager.convertToAppRoute(url: webURL)

        XCTAssertTrue(
            RouterBase.canOpen(url: converted.absoluteString),
            "转换后的 URL 应能被路由表匹配: \(converted)"
        )
    }

    func test_deepLink_routesToCorrectVC() {
        let url = URL(string: "myapp://item?id=12345")!

        RouterBase.open(url: url.absoluteString)

        let vc = routerHelper.assertLastVC(is: ItemDetailViewController.self)
        XCTAssertEqual(vc?.itemID, "12345")
    }

    func test_invalidURL_noRouteTriggered() {
        let url = URL(string: "myapp://nonexistent/path")!

        RouterBase.open(url: url.absoluteString)

        routerHelper.assertNoRouteTriggered()
    }
}
```

## 路由测试 Helper 模式

拦截路由调用，捕获目标 VC 和参数而不执行真实导航：

```swift
final class RouterTestHelper {

    struct CapturedRoute {
        let viewController: UIViewController
        let params: [String: Any]?
    }

    private(set) var capturedRoutes: [CapturedRoute] = []
    var lastCapturedVC: UIViewController? { capturedRoutes.last?.viewController }

    func install() {
        Router.routeInterceptor = { [weak self] vc, params in
            self?.capturedRoutes.append(CapturedRoute(viewController: vc, params: params))
            return true
        }
    }

    func uninstall() {
        Router.routeInterceptor = nil
        capturedRoutes.removeAll()
    }

    @discardableResult
    func assertLastVC<T: UIViewController>(
        is type: T.Type,
        file: StaticString = #filePath, line: UInt = #line
    ) -> T? {
        guard let vc = lastCapturedVC else {
            XCTFail("没有捕获到任何路由", file: file, line: line)
            return nil
        }
        guard let typed = vc as? T else {
            XCTFail("期望 \(T.self)，实际为 \(Swift.type(of: vc))", file: file, line: line)
            return nil
        }
        return typed
    }

    func assertNoRouteTriggered(file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertTrue(capturedRoutes.isEmpty,
                      "不应有路由被触发，但捕获到 \(capturedRoutes.count) 个",
                      file: file, line: line)
    }
}
```

### Helper 适用范围

`RouterTestHelper` 的拦截器安装在 `Router.route()` 上：

- 经过 `Router.route()` push/present 的 VC -> 会被捕获 -> 用 `assertLastVC(is:)` 断言
- 走自定义分派路径（如 ActionType 协议的 `makeAction()`）-> **不经过** `Router.route()` -> 不会被捕获
- 参数缺失/格式错误的降级处理 -> 视具体实现，可能不经过 `Router.route()` -> 用 `assertNoRouteTriggered()` 或跳过

使用 `assertLastVC(is:)` 前，确认被测场景的结果会经过 `Router.route()`。

```swift
// 确认经过 Router.route() 的场景 -> 正常断言
func test_deepLink_routesToCorrectVC() {
    let url = "taptap://taptap.cn/app?app_id=12345"
    RouterBase.open(url)
    let vc = routerHelper.assertLastVC(is: TapGameDetailViewController.self)
    XCTAssertEqual(vc?.appId, "12345")
}

// 确认不经过 Router.route() 的降级场景 -> 断言无导航
func test_userRoute_withoutUserId_triggersNoNavigation() {
    let url = "taptap://taptap.cn/user"
    RouterBase.open(url)
    routerHelper.assertNoRouteTriggered()
}
```

## 网络请求 Stub 集成测试

使用 URLProtocol 子类拦截网络请求，验证「请求发出 -> Stub 响应 -> 业务处理」完整链路：

```swift
final class UserProfileIntegrationTests: XCTestCase {

    override func setUp() {
        super.setUp()
        StubURLProtocol.register()
    }

    override func tearDown() {
        StubURLProtocol.unregister()
        super.tearDown()
    }

    func test_fetchProfile_success_updatesViewModel() async throws {
        StubURLProtocol.requestHandler = { request in
            XCTAssertEqual(request.url?.path, "/api/v1/user/profile")
            XCTAssertNotNil(request.value(forHTTPHeaderField: "Authorization"))

            let response = HTTPURLResponse(url: request.url!, statusCode: 200,
                                           httpVersion: nil, headerFields: nil)!
            let body = #"{"id":1,"name":"Alice","level":"vip"}"#.data(using: .utf8)
            return (response, body)
        }

        let viewModel = UserProfileViewModel()
        await viewModel.loadProfile()

        XCTAssertEqual(viewModel.userName, "Alice")
        XCTAssertEqual(viewModel.userLevel, "vip")
        XCTAssertFalse(viewModel.isLoading)
        XCTAssertNil(viewModel.errorMessage)
    }

    func test_fetchProfile_networkError_showsError() async {
        StubURLProtocol.requestHandler = { _ in
            throw URLError(.notConnectedToInternet)
        }

        let viewModel = UserProfileViewModel()
        await viewModel.loadProfile()

        XCTAssertNotNil(viewModel.errorMessage)
        XCTAssertTrue(viewModel.errorMessage!.contains("网络"))
    }

    func test_fetchProfile_401_triggersLogout() async {
        StubURLProtocol.requestHandler = { request in
            let response = HTTPURLResponse(url: request.url!, statusCode: 401,
                                           httpVersion: nil, headerFields: nil)!
            return (response, nil)
        }

        let viewModel = UserProfileViewModel()
        await viewModel.loadProfile()

        XCTAssertTrue(AccountManager.shared.isLoggedOut)
    }
}
```

## 通知处理集成测试

验证推送/本地通知从接收到路由跳转的完整链路：

```swift
final class LoginNotificationTests: XCTestCase {

    private var routerHelper: RouterTestHelper!
    private var notificationHelper: NotificationTestHelper!

    override func setUp() {
        super.setUp()
        routerHelper = RouterTestHelper()
        routerHelper.install()
        notificationHelper = NotificationTestHelper()
    }

    override func tearDown() {
        routerHelper.uninstall()
        notificationHelper.removeAll()
        super.tearDown()
    }

    func test_loginSuccess_refreshesHomePage() {
        notificationHelper.post(name: .userDidLogin, userInfo: ["userId": "12345"])

        let expectation = expectation(description: "Home page refreshed")
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            XCTAssertTrue(HomePageManager.shared.didRefresh)
            expectation.fulfill()
        }
        waitForExpectations(timeout: 2)
    }

    func test_logoutNotification_routesToLoginPage() {
        notificationHelper.post(name: .userDidLogout)

        let expectation = expectation(description: "Route to login")
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            self.routerHelper.assertLastVC(is: LoginViewController.self)
            expectation.fulfill()
        }
        waitForExpectations(timeout: 2)
    }
}
```

## Combine Publisher 集成测试

使用 XCTestCase 扩展等待 Combine publisher 发出值：

```swift
import Combine
import XCTest

extension XCTestCase {
    func awaitPublisher<T, E: Error>(
        _ publisher: AnyPublisher<T, E>,
        timeout: TimeInterval = 2
    ) throws -> T {
        var result: Result<T, Error>?
        let expectation = expectation(description: "Awaiting publisher")

        let cancellable = publisher.first().sink(
            receiveCompletion: { completion in
                if case .failure(let error) = completion { result = .failure(error) }
                expectation.fulfill()
            },
            receiveValue: { value in result = .success(value) }
        )

        waitForExpectations(timeout: timeout)
        cancellable.cancel()

        switch result {
        case .success(let value): return value
        case .failure(let error): throw error
        case .none:
            XCTFail("Publisher did not emit within \(timeout)s")
            throw URLError(.timedOut)
        }
    }
}

final class SearchIntegrationTests: XCTestCase {

    override func setUp() {
        super.setUp()
        StubURLProtocol.register()
    }

    override func tearDown() {
        StubURLProtocol.unregister()
        super.tearDown()
    }

    func test_searchQuery_emitsResults() throws {
        StubURLProtocol.requestHandler = { request in
            XCTAssertTrue(request.url!.query!.contains("q=swift"))
            let response = HTTPURLResponse(url: request.url!, statusCode: 200,
                                           httpVersion: nil, headerFields: nil)!
            let body = #"{"items":[{"id":1,"title":"Swift Guide"}]}"#.data(using: .utf8)
            return (response, body)
        }

        let viewModel = SearchViewModel()
        viewModel.search(query: "swift")

        let results = try awaitPublisher(
            viewModel.$searchResults.dropFirst().eraseToAnyPublisher()
        )
        XCTAssertEqual(results.count, 1)
        XCTAssertEqual(results.first?.title, "Swift Guide")
    }
}
```

## RxSwift 集成测试

使用 RxTest / RxBlocking 测试 RxSwift 数据流：

```swift
import RxSwift
import RxTest
import RxBlocking
import XCTest

final class FeedViewModelRxTests: XCTestCase {

    var disposeBag: DisposeBag!
    var scheduler: TestScheduler!

    override func setUp() {
        super.setUp()
        disposeBag = DisposeBag()
        scheduler = TestScheduler(initialClock: 0)
        StubURLProtocol.register()
    }

    override func tearDown() {
        StubURLProtocol.unregister()
        disposeBag = nil
        super.tearDown()
    }

    func test_loadFeed_emitsItems() throws {
        StubURLProtocol.requestHandler = { _ in
            let response = HTTPURLResponse(url: URL(string: "https://api.example.com")!,
                                           statusCode: 200, httpVersion: nil, headerFields: nil)!
            let body = #"{"items":[{"id":1},{"id":2}]}"#.data(using: .utf8)
            return (response, body)
        }

        let viewModel = FeedViewModel()
        viewModel.loadFeed()

        let items = try viewModel.feedItems
            .toBlocking(timeout: 3)
            .first()

        XCTAssertEqual(items?.count, 2)
    }

    func test_loadFeed_error_showsAlert() {
        StubURLProtocol.requestHandler = { _ in throw URLError(.timedOut) }

        let observer = scheduler.createObserver(String.self)
        let viewModel = FeedViewModel()
        viewModel.errorMessage
            .bind(to: observer)
            .disposed(by: disposeBag)

        viewModel.loadFeed()

        scheduler.advanceTo(1)
        XCTAssertFalse(observer.events.isEmpty)
    }
}
```

## 弱断言 vs 强断言

```swift
// 弱：只检查路由是否被触发
func test_deepLink_weak() {
    RouterBase.open(url: "myapp://item?id=123")
    XCTAssertNotNil(routerHelper.lastCapturedVC)  // 弱：不验证 VC 类型和参数
}

// 强：验证 VC 类型 + 参数 + 状态
func test_deepLink_strong() {
    RouterBase.open(url: "myapp://item?id=123")
    let vc = routerHelper.assertLastVC(is: ItemDetailViewController.self)
    XCTAssertEqual(vc?.itemID, "123")          // 验证参数传递
    XCTAssertEqual(vc?.displayMode, .detail)    // 验证初始状态
}

// 弱：只检查请求发出了
func test_networkCall_weak() async {
    StubURLProtocol.requestHandler = { _ in /*...*/ }
    await viewModel.loadData()
    XCTAssertFalse(viewModel.isLoading)  // 弱：不验证数据是否正确处理
}

// 强：验证请求参数 + 响应处理 + UI 状态
func test_networkCall_strong() async {
    StubURLProtocol.requestHandler = { request in
        XCTAssertEqual(request.httpMethod, "GET")                    // 验证请求方法
        XCTAssertEqual(request.url?.path, "/api/v1/items")          // 验证路径
        XCTAssertNotNil(request.value(forHTTPHeaderField: "Authorization")) // 验证认证
        // ... return stubbed response
    }
    await viewModel.loadData()
    XCTAssertEqual(viewModel.items.count, 2)                        // 验证数据解析
    XCTAssertEqual(viewModel.items.first?.title, "Expected Title")  // 验证具体字段
    XCTAssertFalse(viewModel.isLoading)                             // 验证 UI 状态
    XCTAssertNil(viewModel.errorMessage)                            // 验证无错误
}
```

## 测试场景覆盖矩阵

| 维度 | 场景 | 断言要求 | 优先级 |
| --- | --- | --- | --- |
| 路由正向 | 合法 URL -> 正确 VC + 参数 | VC 类型 + 参数值 + 初始状态 | P0 |
| 路由异常 | 非法 URL / 未注册路由 | 无路由触发 + 无崩溃 | P0 |
| 网络正向 | Stub 成功响应 -> 数据正确解析 | 请求参数 + 响应解析 + UI 状态 | P0 |
| 网络异常 | 超时/断网/401/500 | 错误提示 + 降级行为（如重试、登出） | P1 |
| 通知正向 | 通知触发 -> 正确响应 | 通知 userInfo 消费 + 副作用（路由/刷新） | P1 |
| 登录门控 | 未登录访问需登录功能 | 拦截到登录页 + 登录后恢复原路由 | P1 |
| 跨模块 | 模块 A 事件 -> 模块 B 响应 | 事件发出 + 接收方状态变更 | P2 |
