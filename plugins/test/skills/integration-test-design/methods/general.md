# 通用集成测试原则

本文件提供语言无关的集成测试设计原则，适用于所有技术栈。

## 测试数据策略

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

## 测试场景覆盖矩阵

对每个 API 接口，至少覆盖以下维度：

| 维度 | 场景 | 断言要求 | 优先级 |
| --- | --- | --- | --- |
| 正向 | 合法请求 -> 成功响应 | 状态码 + 响应体关键字段 + DB 副作用 | P0 |
| 参数验证 | 缺失/非法字段 -> 400 | 状态码 + 错误消息含字段名 | P0 |
| 认证授权 | 未认证 -> 401，无权限 -> 403 | 状态码 + 确认操作未执行 | P1 |
| 业务规则 | 违反唯一性/状态约束 -> 409/422 | 状态码 + 错误消息 + DB 未被污染 | P1 |
| 不存在 | 资源不存在 -> 404 | 状态码 + 错误消息 | P1 |
| 反例 | 不应成功的操作确实被拒绝 | 确认 DB 无变更 | P1 |
| 幂等性 | 重复请求结果一致 | 两次响应相同 + DB 不重复 | P2 |
| 并发 | 竞态条件处理 | 只有一个成功 + 无脏数据 | P2 |
