---
name: feishu-bot-card
description: 通过飞书自定义机器人 Webhook 发送消息卡片时触发。覆盖卡片 JSON 构建、lark_md 与 markdown 元素的区别、表格渲染、签名生成、OSS 文件下载链接等常见场景。当用户提到飞书机器人、webhook 卡片、飞书群通知、lark_md、飞书卡片表格、飞书 bot 推送时使用此 skill。
---

# 飞书自定义机器人卡片开发

通过 Webhook 发送飞书卡片消息的完整指南。重点解决实际开发中的常见陷阱。

## 核心概念

飞书自定义机器人通过 Webhook URL 接收 JSON，支持两种消息类型：
- **text** — 纯文本
- **interactive** — 消息卡片（推荐，支持富文本、表格、按钮等）

## 卡片 JSON 结构

### 必须使用 Schema 2.0

飞书卡片有 v1 和 v2 两个版本。**v2 (schema 2.0)** 支持 `markdown` 元素（含表格），v1 不支持。这是最常见的踩坑点。

```json
{
  "msg_type": "interactive",
  "card": {
    "schema": "2.0",
    "header": {
      "template": "blue",
      "title": {
        "tag": "plain_text",
        "content": "卡片标题"
      }
    },
    "body": {
      "elements": [
        {
          "tag": "markdown",
          "content": "markdown 内容，支持表格"
        }
      ]
    }
  }
}
```

关键区别：
- **v1**: elements 直接在 card 下，用 `"tag": "div"` + `"text": {"tag": "lark_md"}`
- **v2**: elements 在 `card.body` 下，用 `"tag": "markdown"` 直接渲染

### lark_md vs markdown 元素

| 特性 | lark_md (v1) | markdown (v2) |
|------|-------------|---------------|
| 表格 | 不支持 | 支持 |
| 加粗/斜体 | 支持 | 支持 |
| 链接 | 支持 | 支持 |
| 代码块 | 不支持 | 支持 |
| 标题 | 不支持 | 支持 |
| @人 | 支持 | 支持 |

如果需要表格，必须用 schema 2.0 + markdown 元素。

### 表格语法

```json
{
  "tag": "markdown",
  "content": "| Agent | 抽检数 | 正确数 | 一致率 |\n|-------|--------|--------|--------|\n| Agent 1 | 300 | 285 | 95.0% |\n| **总计** | **500** | **471** | **94.2%** |"
}
```

限制：单个 markdown 组件最多 4 个表格，每个表格超过 5 行数据后分页展示。

## Webhook 签名

飞书 Webhook 支持可选的签名验证。签名算法：

```go
// timestamp + "\n" + secret 作为签名字符串
stringToSign := fmt.Sprintf("%d\n%s", timestamp, secret)
h := hmac.New(sha256.New, []byte(stringToSign))
signature := base64.StdEncoding.EncodeToString(h.Sum(nil))
```

请求体需要带上 `timestamp` 和 `sign` 字段：
```json
{
  "timestamp": "1774256169",
  "sign": "base64签名",
  "msg_type": "interactive",
  "card": { ... }
}
```

secret 为空时不签名，直接发送即可。

## 完整的 Go 实现模式

### 卡片构建（推荐 schema 2.0）

```go
func buildCardMessage(title, content string) map[string]any {
    elements := make([]map[string]any, 0)

    if content != "" {
        elements = append(elements, map[string]any{
            "tag":     "markdown",
            "content": content,
        })
    }

    return map[string]any{
        "schema": "2.0",
        "header": map[string]any{
            "template": "blue",
            "title": map[string]any{
                "tag":     "plain_text",
                "content": title,
            },
        },
        "body": map[string]any{
            "elements": elements,
        },
    }
}
```

### 发送请求

```go
requestBody := map[string]any{
    "timestamp": fmt.Sprintf("%d", time.Now().Unix()),
    "sign":      generateSign(timestamp, secret),
    "msg_type":  "interactive",
    "card":      buildCardMessage(title, content),
}
jsonData, _ := json.Marshal(requestBody)
resp, err := http.Post(webhookURL, "application/json",
    bytes.NewBuffer(jsonData))
```

## 附件下载：OSS 签名 URL

飞书卡片不支持直接附件上传，常见方案是将文件上传到 OSS 并在卡片中提供下载链接。

如果 OSS bucket 是私有的（AccessDenied），必须生成带签名的临时 URL：

```go
// 错误：直接拼 URL，私有 bucket 会 403
url := fmt.Sprintf("https://%s.%s/%s", bucket, endpoint, key)

// 正确：用 SDK 生成签名 URL
signedURL, err := bucket.SignURL(objectKey, oss.HTTPGet, 7*24*3600)
// 7*24*3600 = 7 天有效期（秒）
```

在卡片中展示：
```go
content := fmt.Sprintf("[CSV 明细下载（7 天有效）](%s)", signedURL)
```

## CSV 生成最佳实践

生成 CSV 供下载时注意：

```go
// 1. 写入 UTF-8 BOM，确保 Excel 正确识别中文
f.Write([]byte{0xEF, 0xBB, 0xBF})

// 2. 使用 csv.Writer
w := csv.NewWriter(f)
w.Write(header)
for _, row := range rows {
    w.Write(row)
}
w.Flush()

// 3. 上传后清理临时文件
defer os.Remove(filePath)
```

## 常见错误清单

| 错误 | 原因 | 解决 |
|------|------|------|
| 表格显示为纯文本 | 用了 lark_md 或 v1 schema | 改用 schema 2.0 + `"tag": "markdown"` |
| OSS 文件 403 | bucket 私有，URL 无签名 | 用 `bucket.SignURL()` 生成临时 URL |
| 卡片底部多余文字 | Extra/note 字段有值 | 不需要时不传 Extra |
| 签名校验失败 | timestamp 与服务器时间差 >1h | 确保使用当前时间戳 |
| CSV 中文乱码 | 缺少 UTF-8 BOM | 文件开头写入 `0xEF, 0xBB, 0xBF` |

## 参考文档

- [飞书卡片概述](https://open.feishu.cn/document/uAjLw4CM/ukzMukzMukzM/feishu-cards/feishu-card-overview)
- [富文本 Markdown 组件](https://open.feishu.cn/document/uAjLw4CM/ukzMukzMukzM/feishu-cards/card-json-v2-components/content-components/rich-text)
- [自定义机器人 FAQ](https://open.feishu.cn/document/faq/bot)
