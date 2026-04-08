# API 契约校验产物模板

## api_contract_report.json

最终产物，包含完整的校验结果。

```json
{
  "overall_consistency": "consistent | inconsistent | partial | N/A",
  "checked_endpoints": 5,
  "issues_found": 2,
  "frontend_source": {
    "type": "mr | pr | diff_file | diff_text",
    "ref": "MR 链接 / 文件路径 / null"
  },
  "backend_source": {
    "type": "mr | pr | diff_file | diff_text | openapi_spec | none",
    "ref": "MR 链接 / 文件路径 / null"
  },
  "endpoints": [
    {
      "path": "/api/v2/user/profile",
      "method": "POST",
      "status": "consistent | inconsistent",
      "frontend_file": "TapNetworkPath.swift:42",
      "backend_file": "user_router.go:18",
      "issues": []
    },
    {
      "path": "/api/v2/games",
      "method": "GET",
      "status": "inconsistent",
      "frontend_file": "GameService.swift:27",
      "backend_file": "game_handler.go:55",
      "issues": [
        {
          "type": "field_mismatch | type_mismatch | path_mismatch | missing_field | missing_param | extra_field | breaking_change | naming_style",
          "severity": "high | medium | low",
          "description": "前端期望 `game_title: String`，后端提供 `title: String`",
          "frontend_expects": "game_title: String",
          "backend_provides": "title: String",
          "frontend_location": "GameModel.swift:12",
          "backend_location": "game_serializer.go:8",
          "is_breaking": false,
          "confidence": 0.9
        }
      ]
    }
  ],
  "degradation": {
    "is_degraded": false,
    "reason": null,
    "missing_sources": []
  },
  "metadata": {
    "skill": "api-contract-validation",
    "version": "1.0",
    "generated_at": "2026-03-27T10:00:00Z",
    "naming_normalization": "camelCase → snake_case"
  }
}
```

### 字段说明

#### 顶层字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `overall_consistency` | string | 整体一致性状态 |
| `checked_endpoints` | number | 被检查的端点总数 |
| `issues_found` | number | 发现的问题总数 |
| `frontend_source` | object | 前端变更来源信息 |
| `backend_source` | object | 后端变更来源信息 |
| `endpoints` | array | 逐端点的检查结果 |
| `degradation` | object | 降级信息（如有） |
| `metadata` | object | 报告元数据 |

#### endpoints[].issues[].type 枚举

| type | 说明 |
| --- | --- |
| `field_mismatch` | 字段名不匹配（非命名风格差异） |
| `type_mismatch` | 字段类型不匹配 |
| `path_mismatch` | 路径或 HTTP 方法不匹配 |
| `missing_field` | 前端期望的字段后端不提供 |
| `missing_param` | 后端必填参数前端未传 |
| `extra_field` | 前端声明了后端不存在的冗余字段 |
| `breaking_change` | 不向后兼容的变更 |
| `naming_style` | 仅命名风格差异（信息级别） |

#### endpoints[].issues[].severity 枚举

| severity | 说明 | 典型场景 |
| --- | --- | --- |
| `high` | 会导致运行时错误 | 类型不匹配、必填字段缺失、路径错误 |
| `medium` | 可能丢失数据或功能异常 | 后端新增字段前端未处理、枚举值变更 |
| `low` | 信息级别，不影响功能 | 命名风格差异、冗余可选字段 |

## contract_checklist.md（中间文件）

```markdown
# 契约检查清单

## 前端 API 文件

| 文件 | 分类 | 涉及端点 |
| --- | --- | --- |
| TapNetworkPath.swift | 路径定义 | /api/v2/user, /api/v2/games |
| UserModel.swift | 响应模型 | /api/v2/user |
| GameService.swift | 网络调用 | /api/v2/games |

## 后端 API 文件

| 文件 | 分类 | 涉及端点 |
| --- | --- | --- |
| user_router.go | 路由定义 | /api/v2/user |
| game_handler.go | Handler | /api/v2/games |
| game_serializer.go | 响应结构 | /api/v2/games |

## 端点列表

| 端点 | 方法 | 前端文件 | 后端文件 |
| --- | --- | --- | --- |
| /api/v2/user/profile | POST | UserModel.swift, TapNetworkPath.swift | user_router.go |
| /api/v2/games | GET | GameService.swift, TapNetworkPath.swift | game_handler.go |
```

## contract_analysis.md（中间文件）

```markdown
# 契约分析记录

## POST /api/v2/user/profile

### 前端签名
- 路径：`TapNetworkPath.userProfile` → `/api/v2/user/profile`
- 请求参数：`nickname: String (required)`, `avatar: String (optional)`
- 响应模型：`UserProfile { id: Int, nickname: String, avatar_url: String? }`

### 后端签名
- 路由：`POST /api/v2/user/profile`
- 请求参数：`nickname: string (required)`, `avatar: string (optional)`
- 响应：`{ id: int, nickname: string, avatar_url: string | null }`

### 对比结果
- ✅ 路径一致
- ✅ 请求参数一致
- ✅ 响应字段一致
- 状态：**consistent**

---

## GET /api/v2/games

### 前端签名
- 路径：`TapNetworkPath.gameList` → `/api/v2/games`
- 请求参数：`page: Int (required)`
- 响应模型：`GameList { items: [Game], total: Int }`
  - `Game { id: Int, game_title: String, rating: Double }`

### 后端签名
- 路由：`GET /api/v2/games`
- 请求参数：`page: int (required)`, `sort_by: string (optional)`
- 响应：`{ items: [{ id: int, title: string, rating: float }], total: int }`

### 对比结果
- ✅ 路径一致
- ⚠️ 后端新增可选参数 `sort_by`，前端未传递 → **medium**
- ❌ 字段名不匹配：前端 `game_title` vs 后端 `title` → **high**
- 状态：**inconsistent**
```
