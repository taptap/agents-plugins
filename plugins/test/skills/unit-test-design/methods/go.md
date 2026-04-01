# Go 单元测试参考模板

Go — testing + testify

## 表驱动测试（推荐模式）

```go
func TestParseConfig(t *testing.T) {
	tests := []struct {
		name    string
		input   []byte
		want    *Config
		wantErr bool
	}{
		{
			name:  "valid JSON",
			input: []byte(`{"key": "value"}`),
			want:  &Config{Key: "value"},
			// 防护：如果实现返回空 Config 而非解析结果，此用例会失败
		},
		{
			name:    "empty input",
			input:   []byte{},
			wantErr: true,
			// 防护：如果实现遗漏空输入校验（返回零值 Config），此用例会失败
		},
		{
			name:    "nil input",
			input:   nil,
			wantErr: true,
			// 防护：如果实现对 nil 直接 json.Unmarshal 导致 panic，此用例会捕获
		},
		{
			name:    "invalid JSON",
			input:   []byte(`{invalid`),
			wantErr: true,
			// 防护：如果实现吞掉 json 解析错误返回空 Config，此用例会失败
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := ParseConfig(tt.input)
			if tt.wantErr {
				assert.Error(t, err)
				return
			}
			assert.NoError(t, err)
			assert.Equal(t, tt.want, got)
		})
	}
}
```

## Mock 接口

```go
// 源码定义接口
type UserRepository interface {
	GetByID(ctx context.Context, id int64) (*User, error)
}

// 测试中 Mock
type mockUserRepo struct {
	mock.Mock
}

func (m *mockUserRepo) GetByID(ctx context.Context, id int64) (*User, error) {
	args := m.Called(ctx, id)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*User), args.Error(1)
}

func TestUserService_GetUser(t *testing.T) {
	repo := new(mockUserRepo)
	repo.On("GetByID", mock.Anything, int64(1)).Return(&User{ID: 1, Name: "Alice"}, nil)

	svc := NewUserService(repo)
	user, err := svc.GetUser(context.Background(), 1)

	assert.NoError(t, err)
	assert.Equal(t, "Alice", user.Name)
	repo.AssertExpectations(t)
}
```

## HTTP Mock

```go
func TestFetchData(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assert.Equal(t, "/api/data", r.URL.Path)
		w.WriteHeader(http.StatusOK)
		w.Write([]byte(`{"result": "ok"}`))
	}))
	defer server.Close()

	result, err := FetchData(server.URL)
	assert.NoError(t, err)
	assert.Equal(t, "ok", result)
}
```

## 数据库 Mock（sqlmock）

```go
func TestGetUser(t *testing.T) {
	db, mock, err := sqlmock.New()
	require.NoError(t, err)
	defer db.Close()

	rows := sqlmock.NewRows([]string{"id", "name"}).AddRow(1, "Alice")
	mock.ExpectQuery("SELECT id, name FROM users WHERE id = ?").
		WithArgs(1).
		WillReturnRows(rows)

	user, err := GetUser(db, 1)
	assert.NoError(t, err)
	assert.Equal(t, "Alice", user.Name)
	assert.NoError(t, mock.ExpectationsWereMet())
}
```

## Property-Based Testing — rapid

```go
import "pgregory.net/rapid"

func TestParseConfig_RoundTrip(t *testing.T) {
	// 属性：任何合法 Config 序列化后再反序列化应得到相同结果
	rapid.Check(t, func(t *rapid.T) {
		original := &Config{
			Key:   rapid.String().Draw(t, "key"),
			Value: rapid.IntRange(0, 10000).Draw(t, "value"),
		}
		data, err := json.Marshal(original)
		if err != nil {
			t.Fatal(err)
		}
		parsed, err := ParseConfig(data)
		if err != nil {
			t.Fatal(err)
		}
		if parsed.Key != original.Key || parsed.Value != original.Value {
			t.Fatalf("round-trip failed: got %+v, want %+v", parsed, original)
		}
	})
}

func TestValidateEmail(t *testing.T) {
	// 属性：合法邮箱必须包含 @ 且 @ 后有 .
	rapid.Check(t, func(t *rapid.T) {
		// 生成随机字符串，验证校验器行为一致
		input := rapid.String().Draw(t, "email")
		result := ValidateEmail(input)

		hasAt := strings.Contains(input, "@")
		parts := strings.SplitN(input, "@", 2)
		hasDot := hasAt && len(parts) == 2 && strings.Contains(parts[1], ".")

		if result && !hasDot {
			t.Fatalf("ValidateEmail(%q) returned true but input has no valid domain", input)
		}
	})
}
```

## 弱断言 vs 强断言

```go
// 弱断言 -- 只检查没有 error，实现返回空对象也能过
func TestGetUser_Weak(t *testing.T) {
	user, err := svc.GetUser(ctx, 1)
	assert.NoError(t, err)
	assert.NotNil(t, user)           // 弱：不验证内容
}

// 强断言 -- 验证返回值的关键字段
func TestGetUser_Strong(t *testing.T) {
	user, err := svc.GetUser(ctx, 1)
	assert.NoError(t, err)
	assert.Equal(t, int64(1), user.ID)
	assert.Equal(t, "alice@example.com", user.Email)
	assert.False(t, user.CreatedAt.IsZero(), "CreatedAt should be set")
}

// 弱断言 -- 任何 error 都能过
func TestGetUser_NotFound_Weak(t *testing.T) {
	_, err := svc.GetUser(ctx, 99999)
	assert.Error(t, err)             // 弱：网络错误也能过
}

// 强断言 -- 验证具体的错误类型
func TestGetUser_NotFound_Strong(t *testing.T) {
	_, err := svc.GetUser(ctx, 99999)
	assert.ErrorIs(t, err, ErrNotFound)
}
```
