# Feedback 工作流程详细步骤

本文件包含 feedback skill 三个阶段的详细执行步骤、API 使用指南和工作流示例。

---

## 阶段 1：获取并分析反馈（自动执行）

### 触发方式

用户会用以下方式触发：

```markdown
分析 #taptap-feedback 频道的最新反馈
```

或

```markdown
分析 https://xindong.slack.com/archives/C01EB1KAE4B/p1769651933515359
```

### 执行步骤

1. **获取反馈消息**
   - 使用 Slack MCP 工具获取指定消息
   - 如果用户提供 Slack URL，提取 channel_id 和 message_ts
   - 提取关键信息：用户ID、设备、版本、订单号等

2. **识别问题类型**
   - 分析技术关键词
   - 判断业务模块
   - 识别责任端（iOS/Android/前端/后端）

3. **智能查询知识库**（关键步骤）

   **知识库路径**：`references/knowledge-base/` 目录

   **查询决策流程**：
   ```
   识别问题类型关键词
     ↓
   匹配知识库文件
     ↓
   如果匹配度 > 70% → 读取完整知识库
     ↓
   提取历史案例、对接人信息
   ```

4. **生成分析报告**
   - 基于 Slack 消息识别的变更
   - 结合知识库的历史案例
   - 标注置信度（✅ 已确认 / ⚠️ 推测 / ❓ 未知）

### Slack URL 解析说明

**从 Slack URL 提取参数**：
```
URL: https://xindong.slack.com/archives/C01EB1KAE4B/p1769651933515359
                                           ↓                  ↓
                                      channel_id        message_ts
提取:
  channel_id = C01EB1KAE4B
  message_ts = 1769651933.515359
```

**Slack 消息链接格式**：
- 原始 msg_id: `1770008570.481699`
- 链接格式: `https://xindong.slack.com/archives/C01EB1KAE4B/p1770008570481699`

---

## 阶段 2：输出分析报告

报告格式模板见 [TEMPLATES.md](TEMPLATES.md#分析报告格式)。

> 此阶段仅分析，**不创建 Bug 单**，**不发送 Slack 消息**

---

## 阶段 3：用户确认与操作（需人工确认）

### 3.1 创建飞书 Bug（可选）

**触发命令**：
```markdown
创建飞书 Bug
```

**执行动作**：
1. **使用 Python API 脚本创建 Bug**（一次性设置所有字段，包括标题、描述、业务线、报告人、经办人等）
2. **从脚本返回中获取缺陷 ID**：脚本会返回 `work_item_id`，用于后续链接和操作
3. **添加技术分析评论**（可选）
4. **在 Slack 原消息下回复**：Bug 单已创建 + 详情页链接（`https://project.feishu.cn/pojq34/issue/detail/{work_item_id}`）

**创建工单前必须二次确认（关键检查项）**：

在执行 `feishu_api.py create` 命令前，**必须检查以下字段的一致性**：

| 检查项 | 确认内容 | 常见错误 |
|--------|---------|---------|
| **业务线** | `--business` 参数值必须与分析报告中的业务线一致 | 知识库写"基础产品 (SDK)"，但飞书系统只接受"TapSDK" |
| **经办人** | `--operator` 参数值必须在 USER_MAP 中存在 | 用户名拼写错误或未配置映射 |
| **报告人** | `--reporter` 参数值必须在 USER_MAP 中存在 | 同上 |

**飞书系统支持的业务线枚举值**（必须使用以下值之一）：
> `商店` / `社区` / `iOS` / `小游戏` / `启动器` / `PC` / `TapSDK` / `账号价值` / `服务端基建` / `前端基建` / `风控内审` / `测试基建` / `设计基建`

**注意**：知识库中的描述（如"基础产品 (SDK)"）与飞书系统枚举值可能不一致，必须使用飞书系统支持的枚举值。

**创建前自检流程**：
```
1. 检查 --business 值是否在枚举列表中
2. 检查 --operator 和 --reporter 是否在 USER_MAP 中
3. 确认 Slack 回复中的业务线与 --business 参数一致
4. 如果有警告信息（如"业务线不在可选列表中"），必须修正后重新执行
```

### 3.2 直接回复用户（可选）

**触发命令**：
```markdown
回复消息：[你的回复内容]
```

**执行动作**：
- 在 Slack 原消息下发送指定的回复内容

---

## feishu_api.py 使用指南

脚本位置：`plugins/test/skills/feedback/scripts/feishu_api.py`

### 创建 Bug

```bash
python3 plugins/test/skills/feedback/scripts/feishu_api.py create \
  --name "{Bug标题}" \
  --priority {P0/P1/P2/P3} \
  --severity {致命/严重/一般/轻微} \
  --bug_classification {iOS/Android/FE/Server} \
  --issue_stage {线上阶段/灰度阶段/回归测试等} \
  --description "{描述内容}" \
  --business "{业务线名称}" \
  --reporter {报告人用户名} \
  --operator {经办人用户名}
```

**创建 Bug 示例**：
```bash
python3 plugins/test/skills/feedback/scripts/feishu_api.py create \
  --name "[线上][游戏详情页] Android端抽卡分析绑定B站账号失败" \
  --priority P2 \
  --severity 一般 \
  --bug_classification Android \
  --issue_stage 线上阶段 \
  --description "## 问题描述\n用户反馈..." \
  --business "商店" \
  --reporter jinshichen \
  --operator chenhao
```

**脚本返回格式**：
```
✅ Bug 创建成功!
🔗 https://project.feishu.cn/pojq34/issue/detail/6796230012
📋 Work Item ID: 6796230012
```

### 更新 Bug

```bash
# 更新描述
python3 plugins/test/skills/feedback/scripts/feishu_api.py update -w {work_item_id} \
  -d "## 问题描述\n用户反馈..."

# 更新业务线（使用业务线名称，自动转换为 ID）
python3 plugins/test/skills/feedback/scripts/feishu_api.py update -w {work_item_id} \
  -b "商店"

# 更新经办人（使用用户名，自动转换为 user_key）
python3 plugins/test/skills/feedback/scripts/feishu_api.py update -w {work_item_id} \
  -o chenhao

# 一次性更新描述、业务线、经办人
python3 plugins/test/skills/feedback/scripts/feishu_api.py update -w {work_item_id} \
  -d "## 问题描述\n..." \
  -b "商店" \
  -o chenhao
```

### 添加评论

```bash
python3 plugins/test/skills/feedback/scripts/feishu_api.py comment -w {work_item_id} \
  -c "## 技术分析

Bug判断
这是社区核心互动功能缺陷...

可能原因:
1. 接口参数校验问题
2. 前端未正确传参

建议验证:
- 检查接口文档
- 查看前端调用代码"
```

### 查询 Bug 详情

```bash
python3 plugins/test/skills/feedback/scripts/feishu_api.py get -w {work_item_id}
```

### 加载用户映射缓存

```bash
python3 plugins/test/skills/feedback/scripts/feishu_api.py load-cache
```

### 支持的参数

| 参数 | 说明 | 可选值 |
|------|------|--------|
| `--name` / `-n` | Bug 标题（必填） | 自定义文本 |
| `--priority` / `-p` | 优先级 | `P0` / `P1` / `P2` / `P3` |
| `--severity` | 严重程度 | `致命` / `严重` / `一般` / `轻微` |
| `--bug_classification` | Bug端分类 | `iOS` / `Android` / `FE` / `Server` |
| `--issue_stage` | 发现阶段 | `UI/UE/PM内部LR` / `UI/UE/PM验收` / `冒烟测试` / `新功能测试` / `回归测试` / `灰度阶段` / `线上阶段` |
| `--description` / `-d` | 描述内容（Markdown 格式） | 自定义文本 |
| `--business` / `-b` | 业务线名称 | `商店` / `社区` / `iOS` / `小游戏` / `启动器` / `PC` / `TapSDK` |
| `--reporter` / `-r` | 报告人用户名 | `jinshichen` / `zhangtao` / `wangweidong` 等 |
| `--operator` / `-o` | 经办人用户名 | `chenhao` / `chenyihao` / `liufeng` 等 |

### 支持的更新字段

| 参数 | 说明 | 可选值 |
|------|------|--------|
| `--description` / `-d` | 描述内容（Markdown 格式） | 自定义文本 |
| `--business` / `-b` | 业务线名称 | `商店` / `社区` / `iOS` / `小游戏` / `启动器` / `PC` / `TapSDK` |
| `--reporter` / `-r` | 报告人用户名 | `jinshichen` / `zhangtao` / `wangweidong` 等 |
| `--operator` / `-o` | 经办人用户名 | `chenhao` / `chenyihao` / `liufeng` 等 |

### 注意事项

- 脚本内置默认凭证，无需额外配置环境变量
- 支持的业务线：`商店`, `社区`, `iOS`, `小游戏`, `启动器`, `PC`, `TapSDK`
- **用户映射机制**：
  - **优先使用动态缓存**：首次使用时运行 `load-cache` 命令加载项目成员映射（支持邮箱和姓名匹配）
  - **回退到静态映射**：如果缓存未加载或未找到，使用内置的 `USER_MAP` 静态映射
  - **自动加载**：在更新或创建操作时，如果需要用户映射且缓存未加载，会自动尝试加载

---

## 完整工作流（Python API）

1. **Python API 创建 Bug（一次性设置所有字段）**：
   ```bash
   python3 plugins/test/skills/feedback/scripts/feishu_api.py create \
     --name "[线上][功能模块] 问题描述" \
     --priority P2 \
     --severity 一般 \
     --bug_classification Android \
     --issue_stage 线上阶段 \
     --description "## 问题描述\n{问题简述}\n\n## 复现步骤\n1. {步骤1}\n2. {步骤2}\n\n## 环境信息\n设备: {设备}\n版本: {版本}\n用户ID: {用户ID}\n\n## 相关链接\n工单: {工单链接}\nSlack: {Slack链接}" \
     --business "商店" \
     --reporter jinshichen \
     --operator chenhao
   ```
   
   **脚本返回**：`work_item_id`（如 `6796230012`）

2. **添加技术分析评论**（可选）：
   ```bash
   python3 plugins/test/skills/feedback/scripts/feishu_api.py comment \
     -w {work_item_id} \
     -c "## 技术分析

Bug判断
{Bug判断内容}

错误信息: {错误信息}

可能原因:
1. {原因1}
2. {原因2}

建议验证:
- {验证步骤1}
- {验证步骤2}"
   ```

3. **Slack 回复完整信息**（模板见 [TEMPLATES.md](TEMPLATES.md#slack-回复模板bug)）

---

## 示例对话

**用户**：
```
分析 https://xindong.slack.com/archives/C01EB1KAE4B/p1769651933515359
```

**AI 执行流程**：
1. 从 URL 提取 channel_id 和 message_ts
2. 调用 `slack_read_thread` 获取消息及线程回复
3. 提取关键信息（用户ID、设备、版本等）
4. 识别问题类型关键词
5. **判断是否需要查询知识库**
   - 识别到"动态显示异常" → 可能属于社区问题
   - 识别到"group_id必填" → 代码bug，不在知识库覆盖范围
   - **决策**：不查询知识库
6. 检查线程回复，发现已有处理信息
7. 生成分析报告
8. 输出报告，等待用户下一步指令
