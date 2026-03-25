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
