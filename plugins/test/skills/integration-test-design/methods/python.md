# Python 集成测试参考模板

## API 测试 — pytest + httpx

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

## 数据库测试 — pytest fixtures + 事务

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

## 服务间调用测试 — Mock 外部服务（responses）

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

## 消息队列 / 异步操作 — asyncio 异步测试

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
