# TypeScript 单元测试参考模板

TypeScript — vitest / jest

## describe/it 嵌套

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

## Mock 模块

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

## HTTP Mock（msw）

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

## Property-Based Testing — fast-check

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
