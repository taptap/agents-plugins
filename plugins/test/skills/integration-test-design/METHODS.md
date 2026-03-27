# 集成测试方法论与参考模板

本文件提供语言无关的集成测试设计原则和各语言的参考代码模板。

**定位**：当项目中已有集成测试代码时，应优先从已有测试中学习框架、数据库策略和 Mock 方式（init 阶段完成）。本文件的模板仅在以下场景使用：
- 项目中完全没有已有集成测试（首次添加）
- 需要了解某种集成测试模式的通用写法（如 testcontainers、消息队列测试）

## API 测试

### Go — net/http/httptest

```go
func TestCreateUser(t *testing.T) {
	// Setup
	db := setupTestDB(t)
	defer cleanupTestDB(t, db)
	router := setupRouter(db)

	tests := []struct {
		name       string
		body       string
		wantStatus int
		wantBody   string
		setup      func()
	}{
		{
			name:       "create user successfully",
			body:       `{"name": "Alice", "email": "alice@example.com"}`,
			wantStatus: http.StatusCreated,
		},
		{
			name: "duplicate email",
			body: `{"name": "Bob", "email": "alice@example.com"}`,
			setup: func() {
				// 预先插入 alice@example.com
				db.Exec("INSERT INTO users (name, email) VALUES (?, ?)", "Alice", "alice@example.com")
			},
			wantStatus: http.StatusConflict,
		},
		{
			name:       "missing required field",
			body:       `{"name": ""}`,
			wantStatus: http.StatusBadRequest,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if tt.setup != nil {
				tt.setup()
			}
			defer db.Exec("DELETE FROM users")

			req := httptest.NewRequest(http.MethodPost, "/api/v1/users", strings.NewReader(tt.body))
			req.Header.Set("Content-Type", "application/json")
			w := httptest.NewRecorder()

			router.ServeHTTP(w, req)

			assert.Equal(t, tt.wantStatus, w.Code)
		})
	}
}
```

### Go — testcontainers

```go
func TestWithPostgres(t *testing.T) {
	ctx := context.Background()

	pg, err := postgres.Run(ctx,
		"postgres:16-alpine",
		postgres.WithDatabase("testdb"),
		postgres.WithUsername("test"),
		postgres.WithPassword("test"),
		testcontainers.WithWaitStrategy(
			wait.ForLog("database system is ready to accept connections").
				WithOccurrence(2).
				WithStartupTimeout(5*time.Second),
		),
	)
	require.NoError(t, err)
	defer pg.Terminate(ctx)

	connStr, err := pg.ConnectionString(ctx, "sslmode=disable")
	require.NoError(t, err)

	db, err := sql.Open("postgres", connStr)
	require.NoError(t, err)
	defer db.Close()

	// Run migrations
	runMigrations(db)

	// Run tests
	t.Run("create and get user", func(t *testing.T) {
		repo := NewUserRepo(db)
		user, err := repo.Create(ctx, "Alice", "alice@example.com")
		require.NoError(t, err)

		got, err := repo.GetByID(ctx, user.ID)
		require.NoError(t, err)
		assert.Equal(t, "Alice", got.Name)
	})
}
```

### Python — pytest + httpx

```python
import pytest
from httpx import AsyncClient
from myapp import create_app

@pytest.fixture
async def app():
    app = create_app(testing=True)
    yield app

@pytest.fixture
async def client(app):
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture(autouse=True)
async def clean_db(app):
    yield
    # Teardown: 清理测试数据
    async with app.db.acquire() as conn:
        await conn.execute("DELETE FROM users")

class TestCreateUser:
    async def test_create_success(self, client):
        resp = await client.post("/api/v1/users", json={
            "name": "Alice",
            "email": "alice@example.com",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data

    async def test_duplicate_email(self, client):
        # Setup
        await client.post("/api/v1/users", json={
            "name": "Alice", "email": "alice@example.com",
        })
        # Act
        resp = await client.post("/api/v1/users", json={
            "name": "Bob", "email": "alice@example.com",
        })
        assert resp.status_code == 409

    async def test_missing_field(self, client):
        resp = await client.post("/api/v1/users", json={"name": ""})
        assert resp.status_code == 400
```

### TypeScript — supertest

```typescript
import request from 'supertest'
import { createApp } from '../src/app'
import { setupTestDB, cleanupTestDB } from './helpers/db'

describe('POST /api/v1/users', () => {
  let app: Express
  let db: TestDB

  beforeAll(async () => {
    db = await setupTestDB()
    app = createApp(db)
  })

  afterEach(async () => {
    await db.query('DELETE FROM users')
  })

  afterAll(async () => {
    await cleanupTestDB(db)
  })

  it('should create user successfully', async () => {
    const res = await request(app)
      .post('/api/v1/users')
      .send({ name: 'Alice', email: 'alice@example.com' })
      .expect(201)

    expect(res.body).toHaveProperty('id')
  })

  it('should return 409 for duplicate email', async () => {
    await request(app)
      .post('/api/v1/users')
      .send({ name: 'Alice', email: 'alice@example.com' })

    await request(app)
      .post('/api/v1/users')
      .send({ name: 'Bob', email: 'alice@example.com' })
      .expect(409)
  })

  it('should return 400 for missing required field', async () => {
    await request(app)
      .post('/api/v1/users')
      .send({ name: '' })
      .expect(400)
  })
})
```

## 数据库测试

### Go — 事务回滚模式

```go
func TestUserRepo(t *testing.T) {
	db := setupTestDB(t)

	t.Run("create and find", func(t *testing.T) {
		tx, err := db.Begin()
		require.NoError(t, err)
		defer tx.Rollback() // 自动回滚，测试间隔离

		repo := NewUserRepo(tx)

		user, err := repo.Create(context.Background(), "Alice", "alice@example.com")
		require.NoError(t, err)
		assert.NotZero(t, user.ID)

		found, err := repo.FindByID(context.Background(), user.ID)
		require.NoError(t, err)
		assert.Equal(t, "Alice", found.Name)
	})

	t.Run("find nonexistent returns nil", func(t *testing.T) {
		tx, err := db.Begin()
		require.NoError(t, err)
		defer tx.Rollback()

		repo := NewUserRepo(tx)
		found, err := repo.FindByID(context.Background(), 99999)
		require.NoError(t, err)
		assert.Nil(t, found)
	})
}
```

### Python — pytest fixtures + 事务

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

@pytest.fixture
def db_session(engine):
    """每个测试在事务中执行，结束后自动回滚"""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()

def test_create_user(db_session):
    repo = UserRepo(db_session)
    user = repo.create("Alice", "alice@example.com")
    assert user.id is not None

    found = repo.find_by_id(user.id)
    assert found.name == "Alice"
```

## 服务间调用测试

### Go — Mock 外部服务

```go
func TestOrderService_CreateOrder(t *testing.T) {
	// Mock 支付服务
	paymentServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, http.MethodPost, r.Method)
		assert.Equal(t, "/api/v1/payments", r.URL.Path)

		var req PaymentRequest
		json.NewDecoder(r.Body).Decode(&req)
		assert.Greater(t, req.Amount, 0.0)

		w.WriteHeader(http.StatusOK)
		json.NewEncoder(w).Encode(PaymentResponse{
			TransactionID: "tx-123",
			Status:        "success",
		})
	}))
	defer paymentServer.Close()

	db := setupTestDB(t)
	svc := NewOrderService(db, paymentServer.URL)

	order, err := svc.CreateOrder(context.Background(), CreateOrderRequest{
		UserID:  1,
		Items:   []OrderItem{{ProductID: 1, Quantity: 2}},
		Amount:  99.99,
	})

	require.NoError(t, err)
	assert.Equal(t, "tx-123", order.TransactionID)
	assert.Equal(t, OrderStatusPaid, order.Status)

	// 验证数据库副作用
	var count int
	db.QueryRow("SELECT COUNT(*) FROM orders WHERE user_id = ?", 1).Scan(&count)
	assert.Equal(t, 1, count)
}
```

### Python — Mock 外部服务（responses）

```python
import responses
from myapp.order_service import OrderService

@responses.activate
def test_create_order(db_session):
    # Mock 支付服务
    responses.add(
        responses.POST,
        "https://payment.internal/api/v1/payments",
        json={"transaction_id": "tx-123", "status": "success"},
        status=200,
    )

    svc = OrderService(db=db_session, payment_url="https://payment.internal")
    order = svc.create_order(user_id=1, items=[{"product_id": 1, "qty": 2}], amount=99.99)

    assert order.transaction_id == "tx-123"
    assert order.status == "paid"

    # 验证数据库副作用
    count = db_session.query(Order).filter_by(user_id=1).count()
    assert count == 1
```

## 中间件测试

### Go — Auth 中间件

```go
func TestAuthMiddleware(t *testing.T) {
	handler := AuthMiddleware(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		userID := r.Context().Value("user_id").(int64)
		w.WriteHeader(http.StatusOK)
		fmt.Fprintf(w, "user:%d", userID)
	}))

	tests := []struct {
		name       string
		token      string
		wantStatus int
	}{
		{
			name:       "valid token",
			token:      generateTestToken(1),
			wantStatus: http.StatusOK,
		},
		{
			name:       "missing token",
			token:      "",
			wantStatus: http.StatusUnauthorized,
		},
		{
			name:       "expired token",
			token:      generateExpiredToken(1),
			wantStatus: http.StatusUnauthorized,
		},
		{
			name:       "invalid token",
			token:      "invalid-token",
			wantStatus: http.StatusUnauthorized,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, "/", nil)
			if tt.token != "" {
				req.Header.Set("Authorization", "Bearer "+tt.token)
			}
			w := httptest.NewRecorder()
			handler.ServeHTTP(w, req)
			assert.Equal(t, tt.wantStatus, w.Code)
		})
	}
}
```

## gRPC 测试

### Go — gRPC 服务测试

```go
func TestUserService_GetUser(t *testing.T) {
	// 启动 gRPC 测试服务器
	lis := bufconn.Listen(1024 * 1024)
	srv := grpc.NewServer()
	pb.RegisterUserServiceServer(srv, NewUserServiceServer(setupTestDB(t)))
	go srv.Serve(lis)
	defer srv.Stop()

	// 建立客户端连接
	conn, err := grpc.DialContext(context.Background(), "bufnet",
		grpc.WithContextDialer(func(ctx context.Context, _ string) (net.Conn, error) {
			return lis.DialContext(ctx)
		}),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	require.NoError(t, err)
	defer conn.Close()

	client := pb.NewUserServiceClient(conn)

	t.Run("get existing user", func(t *testing.T) {
		resp, err := client.GetUser(context.Background(), &pb.GetUserRequest{Id: 1})
		require.NoError(t, err)
		assert.Equal(t, "Alice", resp.Name)
	})

	t.Run("get nonexistent user", func(t *testing.T) {
		_, err := client.GetUser(context.Background(), &pb.GetUserRequest{Id: 99999})
		assert.Equal(t, codes.NotFound, status.Code(err))
	})
}
```

## 消息队列 / 异步操作测试

### Go — Channel-Based 异步验证

```go
func TestOrderService_SendNotification(t *testing.T) {
	// 用 channel 捕获异步发送的消息
	msgChan := make(chan NotificationMsg, 10)
	mockQueue := &MockMessageQueue{
		PublishFunc: func(msg NotificationMsg) error {
			msgChan <- msg
			return nil
		},
	}

	db := setupTestDB(t)
	svc := NewOrderService(db, mockQueue)

	// 触发业务操作（会异步发送通知）
	order, err := svc.CreateOrder(context.Background(), CreateOrderRequest{
		UserID: 1, Amount: 99.99,
	})
	require.NoError(t, err)

	// 验证异步消息（带超时）
	select {
	case msg := <-msgChan:
		assert.Equal(t, "order_created", msg.Type)
		assert.Equal(t, order.ID, msg.OrderID)
		assert.Equal(t, int64(1), msg.UserID)
	case <-time.After(5 * time.Second):
		t.Fatal("timeout waiting for notification message")
	}
}
```

### Python — asyncio 异步测试

```python
import asyncio
import pytest

@pytest.fixture
def mock_queue():
    """捕获异步发布的消息"""
    messages = []

    class MockQueue:
        async def publish(self, msg):
            messages.append(msg)

    return MockQueue(), messages

@pytest.mark.asyncio
async def test_order_notification(db_session, mock_queue):
    queue, messages = mock_queue
    svc = OrderService(db=db_session, queue=queue)

    order = await svc.create_order(user_id=1, amount=99.99)

    # 等待异步任务完成
    await asyncio.sleep(0.1)

    assert len(messages) == 1
    assert messages[0]["type"] == "order_created"
    assert messages[0]["order_id"] == order.id
```

### Go — 定时任务测试

```go
func TestScheduler_ProcessExpiredOrders(t *testing.T) {
	db := setupTestDB(t)

	// 插入一条已过期的订单
	_, err := db.Exec(
		"INSERT INTO orders (id, status, expires_at) VALUES (?, ?, ?)",
		1, "pending", time.Now().Add(-1*time.Hour),
	)
	require.NoError(t, err)

	// 执行定时任务
	scheduler := NewOrderScheduler(db)
	processed, err := scheduler.ProcessExpiredOrders(context.Background())

	require.NoError(t, err)
	assert.Equal(t, 1, processed)

	// 验证订单状态已更新
	var status string
	db.QueryRow("SELECT status FROM orders WHERE id = ?", 1).Scan(&status)
	assert.Equal(t, "cancelled", status)
}
```

## Swift/iOS — 客户端集成测试

iOS 客户端的集成测试关注的不是 HTTP 服务端的 CRUD，而是**客户端内部多组件协作的完整链路**：路由导航、网络请求→业务处理、推送通知→路由跳转、跨模块数据流等。

### 路由导航集成测试

验证 URL → 路由匹配 → VC 实例化 → 参数传递的完整链路：

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

### 路由测试 Helper 模式

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

#### Helper 适用范围

`RouterTestHelper` 的拦截器安装在 `Router.route()` 上：

- 经过 `Router.route()` push/present 的 VC → 会被捕获 → 用 `assertLastVC(is:)` 断言
- 走自定义分派路径（如 ActionType 协议的 `makeAction()`）→ **不经过** `Router.route()` → 不会被捕获
- 参数缺失/格式错误的降级处理 → 视具体实现，可能不经过 `Router.route()` → 用 `assertNoRouteTriggered()` 或跳过

使用 `assertLastVC(is:)` 前，确认被测场景的结果会经过 `Router.route()`。

```swift
// 确认经过 Router.route() 的场景 → 正常断言
func test_deepLink_routesToCorrectVC() {
    let url = "taptap://taptap.cn/app?app_id=12345"
    RouterBase.open(url)
    let vc = routerHelper.assertLastVC(is: TapGameDetailViewController.self)
    XCTAssertEqual(vc?.appId, "12345")
}

// 确认不经过 Router.route() 的降级场景 → 断言无导航
func test_userRoute_withoutUserId_triggersNoNavigation() {
    let url = "taptap://taptap.cn/user"
    RouterBase.open(url)
    routerHelper.assertNoRouteTriggered()
}
```

### 网络请求 Stub 集成测试

使用 URLProtocol 子类拦截网络请求，验证「请求发出 → Stub 响应 → 业务处理」完整链路：

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

### 通知处理集成测试

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

### Combine Publisher 集成测试

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

### RxSwift 集成测试

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

### iOS 集成测试弱断言 vs 强断言

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

### iOS 测试场景覆盖矩阵

| 维度 | 场景 | 断言要求 | 优先级 |
| --- | --- | --- | --- |
| 路由正向 | 合法 URL → 正确 VC + 参数 | VC 类型 + 参数值 + 初始状态 | P0 |
| 路由异常 | 非法 URL / 未注册路由 | 无路由触发 + 无崩溃 | P0 |
| 网络正向 | Stub 成功响应 → 数据正确解析 | 请求参数 + 响应解析 + UI 状态 | P0 |
| 网络异常 | 超时/断网/401/500 | 错误提示 + 降级行为（如重试、登出） | P1 |
| 通知正向 | 通知触发 → 正确响应 | 通知 userInfo 消费 + 副作用（路由/刷新） | P1 |
| 登录门控 | 未登录访问需登录功能 | 拦截到登录页 + 登录后恢复原路由 | P1 |
| 跨模块 | 模块 A 事件 → 模块 B 响应 | 事件发出 + 接收方状态变更 | P2 |

## 通用原则

### 测试数据策略

| 策略 | 说明 | 适用场景 |
| --- | --- | --- |
| 内联构造 | 直接在测试中硬编码数据 | 简单场景，数据量小 |
| Factory 函数 | 封装数据构造逻辑，支持覆盖默认值 | 多个测试共享相似数据 |
| Fixture 文件 | 从 JSON/YAML 文件加载 | 复杂数据结构、大量数据 |
| Builder 模式 | 链式调用构造复杂对象 | 对象属性多、组合多 |

### Factory 函数示例（Go）

```go
func NewTestUser(overrides ...func(*User)) *User {
	u := &User{
		Name:  "DefaultUser",
		Email: "default@example.com",
		Role:  "member",
	}
	for _, fn := range overrides {
		fn(u)
	}
	return u
}

// 使用
user := NewTestUser(func(u *User) {
	u.Name = "Admin"
	u.Role = "admin"
})
```

## 弱断言 vs 强断言

集成测试中最常见的质量问题是断言太浅。以下对比说明如何加强。

### API 测试断言

```go
// 弱：只检查状态码，实现返回空 body 也能过
func TestCreateUser_Weak(t *testing.T) {
	resp := doPost(t, "/api/v1/users", `{"name": "Alice", "email": "a@b.com"}`)
	assert.Equal(t, 201, resp.StatusCode)
}

// 强：验证响应体 + 数据库副作用
func TestCreateUser_Strong(t *testing.T) {
	resp := doPost(t, "/api/v1/users", `{"name": "Alice", "email": "a@b.com"}`)
	assert.Equal(t, 201, resp.StatusCode)

	// 验证响应体
	var body map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&body)
	userID := body["id"].(float64)
	assert.Greater(t, userID, float64(0))

	// 验证数据库副作用（不只信任 API 返回）
	var dbUser User
	err := db.QueryRow("SELECT name, email FROM users WHERE id = ?", int64(userID)).
		Scan(&dbUser.Name, &dbUser.Email)
	assert.NoError(t, err)
	assert.Equal(t, "Alice", dbUser.Name)
	assert.Equal(t, "a@b.com", dbUser.Email)
}
```

### 错误场景断言

```go
// 弱：任何 4xx 都能过
func TestCreateUser_DuplicateEmail_Weak(t *testing.T) {
	doPost(t, "/api/v1/users", `{"name": "Alice", "email": "a@b.com"}`)
	resp := doPost(t, "/api/v1/users", `{"name": "Bob", "email": "a@b.com"}`)
	assert.Equal(t, 409, resp.StatusCode)
}

// 强：验证错误内容 + 确认数据库未被污染
func TestCreateUser_DuplicateEmail_Strong(t *testing.T) {
	doPost(t, "/api/v1/users", `{"name": "Alice", "email": "a@b.com"}`)
	resp := doPost(t, "/api/v1/users", `{"name": "Bob", "email": "a@b.com"}`)
	assert.Equal(t, 409, resp.StatusCode)

	// 验证错误消息有意义
	var errBody map[string]string
	json.NewDecoder(resp.Body).Decode(&errBody)
	assert.Contains(t, errBody["message"], "email")

	// 确认第二个用户未入库
	var count int
	db.QueryRow("SELECT COUNT(*) FROM users WHERE email = ?", "a@b.com").Scan(&count)
	assert.Equal(t, 1, count) // 仍然只有第一个
}
```

### 删除操作断言

```python
# 弱：只检查状态码
def test_delete_user_weak(client):
    resp = client.delete("/api/v1/users/1")
    assert resp.status_code == 204

# 强：验证数据库中确实不存在了
def test_delete_user_strong(client, db_session):
    # Setup
    user = create_test_user(db_session, name="Alice")

    resp = client.delete(f"/api/v1/users/{user.id}")
    assert resp.status_code == 204

    # 验证 DB 副作用
    found = db_session.query(User).filter_by(id=user.id).first()
    assert found is None  # 硬删除
    # 或者对于软删除：
    # assert found.deleted_at is not None
```

### 测试场景覆盖矩阵

对每个 API 接口，至少覆盖以下维度：

| 维度 | 场景 | 断言要求 | 优先级 |
| --- | --- | --- | --- |
| 正向 | 合法请求 → 成功响应 | 状态码 + 响应体关键字段 + DB 副作用 | P0 |
| 参数验证 | 缺失/非法字段 → 400 | 状态码 + 错误消息含字段名 | P0 |
| 认证授权 | 未认证 → 401，无权限 → 403 | 状态码 + 确认操作未执行 | P1 |
| 业务规则 | 违反唯一性/状态约束 → 409/422 | 状态码 + 错误消息 + DB 未被污染 | P1 |
| 不存在 | 资源不存在 → 404 | 状态码 + 错误消息 | P1 |
| 反例 | 不应成功的操作确实被拒绝 | 确认 DB 无变更 | P1 |
| 幂等性 | 重复请求结果一致 | 两次响应相同 + DB 不重复 | P2 |
| 并发 | 竞态条件处理 | 只有一个成功 + 无脏数据 | P2 |
