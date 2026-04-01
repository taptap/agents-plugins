# TypeScript 集成测试参考模板

## API 测试 — supertest

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
