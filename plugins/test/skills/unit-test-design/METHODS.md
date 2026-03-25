# 单元测试方法论与参考模板

本文件提供语言无关的测试设计原则和各语言的参考代码模板。

**定位**：当项目中已有测试代码时，应优先从已有测试中学习框架、Mock 方式和风格约定（init 阶段完成）。本文件的模板仅在以下场景使用：
- 项目中完全没有已有测试文件（全新项目）
- 项目已有测试使用了不熟悉的框架，需要对照参考
- 需要了解某个测试设计模式的通用写法（如 property-based testing）

## Go — testing + testify

### 表驱动测试（推荐模式）

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

### Mock 接口

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

### HTTP Mock

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

### 数据库 Mock（sqlmock）

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

## Python — pytest

### 参数化测试

```python
import pytest
from mymodule import parse_config

@pytest.mark.parametrize("input_data,expected,raises", [
    (b'{"key": "value"}', {"key": "value"}, None),
    (b'', None, ValueError),
    (None, None, TypeError),
    (b'{invalid', None, ValueError),
])
def test_parse_config(input_data, expected, raises):
    if raises:
        with pytest.raises(raises):
            parse_config(input_data)
    else:
        result = parse_config(input_data)
        assert result == expected
```

### Mock 依赖

```python
from unittest.mock import MagicMock, patch
from mymodule.service import UserService

def test_get_user():
    mock_repo = MagicMock()
    mock_repo.get_by_id.return_value = {"id": 1, "name": "Alice"}

    svc = UserService(repo=mock_repo)
    user = svc.get_user(1)

    assert user["name"] == "Alice"
    mock_repo.get_by_id.assert_called_once_with(1)
```

### HTTP Mock（responses）

```python
import responses
from mymodule import fetch_data

@responses.activate
def test_fetch_data():
    responses.add(
        responses.GET,
        "https://api.example.com/data",
        json={"result": "ok"},
        status=200,
    )

    result = fetch_data("https://api.example.com/data")
    assert result == {"result": "ok"}
```

### Fixture 与临时文件

```python
import pytest

@pytest.fixture
def config_file(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text("key: value\n")
    return config

def test_load_config(config_file):
    result = load_config(str(config_file))
    assert result["key"] == "value"
```

## TypeScript — vitest / jest

### describe/it 嵌套

```typescript
import { describe, it, expect } from 'vitest'
import { parseConfig } from './config'

describe('parseConfig', () => {
  it('should parse valid JSON', () => {
    const result = parseConfig('{"key": "value"}')
    expect(result).toEqual({ key: 'value' })
  })

  it('should throw on empty input', () => {
    expect(() => parseConfig('')).toThrow()
  })

  it('should throw on invalid JSON', () => {
    expect(() => parseConfig('{invalid')).toThrow()
  })
})
```

### Mock 模块

```typescript
import { describe, it, expect, vi } from 'vitest'
import { UserService } from './user-service'

vi.mock('./user-repo', () => ({
  UserRepo: vi.fn().mockImplementation(() => ({
    getById: vi.fn().mockResolvedValue({ id: 1, name: 'Alice' }),
  })),
}))

describe('UserService', () => {
  it('should get user by id', async () => {
    const svc = new UserService()
    const user = await svc.getUser(1)
    expect(user.name).toBe('Alice')
  })
})
```

### HTTP Mock（msw）

```typescript
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

const server = setupServer(
  http.get('/api/data', () => {
    return HttpResponse.json({ result: 'ok' })
  }),
)

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())

it('should fetch data', async () => {
  const result = await fetchData('/api/data')
  expect(result).toEqual({ result: 'ok' })
})
```

## Java — JUnit 5 + Mockito

### 参数化测试

```java
@ParameterizedTest
@MethodSource("parseConfigTestCases")
void testParseConfig(String input, Config expected, Class<? extends Exception> expectedException) {
    if (expectedException != null) {
        assertThrows(expectedException, () -> ConfigParser.parse(input));
    } else {
        Config result = ConfigParser.parse(input);
        assertEquals(expected, result);
    }
}

static Stream<Arguments> parseConfigTestCases() {
    return Stream.of(
        Arguments.of("{\"key\": \"value\"}", new Config("value"), null),
        Arguments.of("", null, ParseException.class),
        Arguments.of(null, null, NullPointerException.class)
    );
}
```

### Mock 依赖（Mockito）

```java
@ExtendWith(MockitoExtension.class)
class UserServiceTest {

    @Mock
    private UserRepository userRepo;

    @InjectMocks
    private UserService userService;

    @Test
    void shouldGetUserById() {
        when(userRepo.findById(1L)).thenReturn(Optional.of(new User(1L, "Alice")));

        User user = userService.getUser(1L);

        assertEquals("Alice", user.getName());
        verify(userRepo).findById(1L);
    }
}
```

## Kotlin — JUnit 5 + MockK

### Mock 依赖（MockK）

```kotlin
class UserServiceTest {

    private val userRepo = mockk<UserRepository>()
    private val svc = UserService(userRepo)

    @Test
    fun `should get user by id`() {
        every { userRepo.findById(1L) } returns User(1L, "Alice")

        val user = svc.getUser(1L)

        assertEquals("Alice", user.name)
        verify { userRepo.findById(1L) }
    }
}
```

## Swift — XCTest

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

## Property-Based Testing（属性测试）

对纯函数、转换器、校验器等无副作用的代码，property-based testing 比固定样例更有效——它用随机输入验证不变量，而非只检查几个 AI 选定的值。

### Go — rapid

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

### Python — hypothesis

```python
from hypothesis import given, strategies as st, assume
import json

@given(st.dictionaries(st.text(min_size=1), st.integers()))
def test_parse_config_round_trip(data):
    """属性：序列化→反序列化应得到相同结果"""
    encoded = json.dumps(data).encode()
    result = parse_config(encoded)
    assert result == data

@given(st.text())
def test_validate_email_rejects_no_at(text):
    """属性：不含 @ 的字符串一定不是合法邮箱"""
    assume("@" not in text)
    assert validate_email(text) is False

@given(st.integers(min_value=-1000, max_value=1000))
def test_clamp_stays_in_range(value):
    """属性：clamp 的结果一定在 [min, max] 范围内"""
    result = clamp(value, 0, 100)
    assert 0 <= result <= 100
```

### TypeScript — fast-check

```typescript
import fc from 'fast-check'

test('parseConfig round-trip', () => {
  fc.assert(
    fc.property(
      fc.record({ key: fc.string(), value: fc.integer() }),
      (original) => {
        const encoded = JSON.stringify(original)
        const parsed = parseConfig(encoded)
        expect(parsed).toEqual(original)
      }
    )
  )
})

test('validateEmail rejects strings without @', () => {
  fc.assert(
    fc.property(
      fc.string().filter(s => !s.includes('@')),
      (input) => {
        expect(validateEmail(input)).toBe(false)
      }
    )
  )
})
```

### 何时使用 Property-Based Testing

| 场景 | 属性示例 |
| --- | --- |
| 序列化/反序列化 | `decode(encode(x)) == x` |
| 校验器 | 不合法输入一定被拒绝 |
| 排序/过滤 | 输出是输入的子集且有序 |
| 数学运算 | `add(a, b) == add(b, a)`，`abs(x) >= 0` |
| 幂等操作 | `f(f(x)) == f(x)` |
| 范围约束 | `clamp(x, min, max)` 的结果在 `[min, max]` 内 |

## 弱断言 vs 强断言

AI 生成测试时容易使用过弱的断言，导致测试永远通过。以下对比说明如何加强断言质量。

### Go 示例

```go
// 弱断言 — 只检查没有 error，实现返回空对象也能过
func TestGetUser_Weak(t *testing.T) {
	user, err := svc.GetUser(ctx, 1)
	assert.NoError(t, err)
	assert.NotNil(t, user)           // 弱：不验证内容
}

// 强断言 — 验证返回值的关键字段
func TestGetUser_Strong(t *testing.T) {
	user, err := svc.GetUser(ctx, 1)
	assert.NoError(t, err)
	assert.Equal(t, int64(1), user.ID)
	assert.Equal(t, "alice@example.com", user.Email)
	assert.False(t, user.CreatedAt.IsZero(), "CreatedAt should be set")
}

// 弱断言 — 任何 error 都能过
func TestGetUser_NotFound_Weak(t *testing.T) {
	_, err := svc.GetUser(ctx, 99999)
	assert.Error(t, err)             // 弱：网络错误也能过
}

// 强断言 — 验证具体的错误类型
func TestGetUser_NotFound_Strong(t *testing.T) {
	_, err := svc.GetUser(ctx, 99999)
	assert.ErrorIs(t, err, ErrNotFound)
}
```

### Python 示例

```python
# 弱断言
def test_parse_weak():
    result = parse_config(b'{"key": "value"}')
    assert result is not None           # 弱：空 dict 也是 not None
    assert len(result) > 0              # 弱：不验证具体内容

# 强断言
def test_parse_strong():
    result = parse_config(b'{"key": "value"}')
    assert result["key"] == "value"     # 强：验证具体字段和值
    assert "key" in result              # 强：验证结构
```

## 通用原则

### 测试命名

| 语言 | 命名规则 | 示例 |
| --- | --- | --- |
| Go | `Test{Function}_{Scenario}_{Expected}` | `TestParseConfig_EmptyInput_ReturnsError` |
| Python | `test_{function}_{scenario}` | `test_parse_config_empty_input_raises` |
| TypeScript | describe + it 描述 | `it('should throw on empty input')` |
| Java | `should{Expected}When{Scenario}` | `shouldThrowWhenInputIsEmpty` |
| Kotlin | 反引号描述 | `` `should throw when input is empty` `` |
| Swift | `test{Function}{Scenario}` | `testParseConfigEmptyInput` |

### 测试用例覆盖矩阵

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
