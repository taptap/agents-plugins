# Go 集成测试参考模板

## API 测试 — net/http/httptest

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

## API 测试 — testcontainers

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

## 数据库测试 — 事务回滚模式

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

## 服务间调用测试 — Mock 外部服务

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

## 中间件测试 — Auth 中间件

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

## gRPC 测试 — bufconn

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

## 消息队列 — Channel-Based 异步验证

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

## 定时任务测试

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
