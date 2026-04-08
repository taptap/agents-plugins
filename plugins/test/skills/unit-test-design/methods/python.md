# Python 单元测试参考模板

Python — pytest

## 参数化测试

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

## Mock 依赖

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

## HTTP Mock（responses）

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

## Fixture 与临时文件

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

## Property-Based Testing — hypothesis

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

## 弱断言 vs 强断言

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
