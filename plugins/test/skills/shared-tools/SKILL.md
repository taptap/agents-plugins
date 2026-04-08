---
name: shared-tools
description: >
  数据获取共享脚本集合：飞书文档获取、GitLab MR/文件、GitHub PR/文件、MR/PR 搜索。
  默认由其他 skill 间接引用。
---

# 共享工具集

## Quick Start

- Skill 类型：共享工具型
- 适用场景：其他 skill 在数据获取阶段需要调用共享脚本
- 使用边界：优先由核心 skill 引用；直接使用仅限调试或独立数据获取

## 工具清单

| 脚本 | 功能 | 必填环境变量 | 可选环境变量 |
| --- | --- | --- | --- |
| `fetch_feishu_doc.py` | 获取飞书文档完整内容（文字+图片） | `FEISHU_APP_ID`, `FEISHU_APP_SECRET` | `FEISHU_BASE_URL`（默认 `https://open.feishu.cn`，别名 `FEISHU_HOST`） |
| `gitlab_helper.py` | GitLab MR diff/详情/文件内容 | `GITLAB_URL`, `GITLAB_TOKEN` | `GITLAB_SSL_VERIFY`（默认开启，设 `false` 关闭） |
| `github_helper.py` | GitHub PR diff/详情/文件内容 | `GITHUB_TOKEN` | `GITHUB_URL`（默认 `https://api.github.com`） |
| `search_mrs.py` | 搜索 Story/Bug 关联的 GitLab MR | `GITLAB_URL`, `GITLAB_TOKEN`, `GITLAB_PROJECT_MAPPING` | `GITLAB_SSL_VERIFY` |
| `search_prs.py` | 搜索 Story/Bug 关联的 GitHub PR | `GITHUB_TOKEN`, `GITHUB_REPO_MAPPING` | `GITHUB_URL` |

## 飞书文档获取

```bash
FETCH=$SKILLS_ROOT/shared-tools/scripts/fetch_feishu_doc.py

# 从 URL 获取（自动识别 wiki/docx/docs 链接）
python3 $FETCH --url "https://xxx.feishu.cn/wiki/AbCdEfG" --output-dir . 2>tmp.log

# 直接指定 document_id
python3 $FETCH --doc-id "AbCdEfG" --output-dir . 2>tmp.log

# 仅获取文字，跳过图片下载
python3 $FETCH --url "..." --output-dir . --skip-images
```

**输出**：
- stdout: Markdown 格式文档内容（标题/段落/列表/表格/代码块/图片引用）
- stderr: 混合输出进度日志（以 `[LOG]` 开头）和 JSON 元数据（最后一行）。消费元数据时取最后一行：`2>tmp.log && tail -1 tmp.log > fetch_meta.json`

**图片处理**：图片自动下载到 `{output-dir}/images/`，AI 可通过 Read 工具查看。`--skip-images` 跳过图片下载。

## GitLab 辅助脚本

```bash
GITLAB=$SKILLS_ROOT/shared-tools/scripts/gitlab_helper.py

# MR diff
python3 $GITLAB mr-diff <project_path> <mr_iid>

# MR 详情
python3 $GITLAB mr-detail <project_path> <mr_iid>

# 文件内容
python3 $GITLAB file-content <project_path> <file_path> [--ref main]
```

## GitHub 辅助脚本

```bash
GITHUB=$SKILLS_ROOT/shared-tools/scripts/github_helper.py

# PR diff
python3 $GITHUB pr-diff <owner/repo> <pr_number>

# PR 详情
python3 $GITHUB pr-detail <owner/repo> <pr_number>

# 文件内容
python3 $GITHUB file-content <owner/repo> <file_path> [--ref main]
```

## MR/PR 搜索脚本

```bash
# 搜索 Story/Bug 关联的 GitLab MR
python3 $SKILLS_ROOT/shared-tools/scripts/search_mrs.py <story_id>

# 搜索 Story/Bug 关联的 GitHub PR
python3 $SKILLS_ROOT/shared-tools/scripts/search_prs.py <work_item_id>
```

输出 JSON 到 stdout，包含关联的已合并+进行中 MR/PR 列表。

**映射配置**：搜索脚本通过环境变量配置项目/仓库映射：

- `GITLAB_PROJECT_MAPPING`：JSON 格式，key 为平台名，value 为 GitLab 项目 ID（int）或 ID 列表。示例：`{"server": 2103, "android": 4252, "mini_game": [4191, 4218]}`
- `GITHUB_REPO_MAPPING`：JSON 格式，key 为平台名，value 为 GitHub repo（`owner/repo`）或列表。示例：`{"server": ["org/repo-a"], "web": "org/repo-b"}`

## Figma 设计稿获取

通过 Figma MCP 分级获取设计稿数据。**禁止直接对页面级节点调用 get_design_context**。

### 别名映射

各 skill 中使用的简写与实际 MCP 工具的对应关系：

| Skill 简写 | MCP 工具 | 用途 | 预期体量 |
|---|---|---|---|
| `figma_metadata(url)` | `mcp__figma__get_metadata` | 结构探测，获取节点树（ID/类型/名称/尺寸） | 10-50KB |
| `figma_context(url, nodeId)` | `mcp__figma__get_design_context` | 单节点设计详情（代码+元数据） | 50-200KB |
| `figma_screenshot(url, nodeId)` | `mcp__figma__get_screenshot` | 节点截图 | 图片 |
| `figma_extract(url, script)` | `mcp__figma__use_figma` | 自定义 JS 提取特定数据 | <10KB |

### 标准调用流程

1. **解析 URL**：从 Figma URL 提取 `fileKey` 和 `nodeId`（规则见工具 description）
2. **结构探测**：`figma_metadata(url)` — 获取目标节点下的结构树
3. **识别目标**：从 metadata XML 中找到需要详情的子节点 ID
4. **按需获取**：对每个目标子节点调用 `figma_context(url, nodeId)`，始终传 `excludeScreenshot=true`
5. **精准补充**：需要视觉对照时单独 `figma_screenshot`；需要特定字段时用 `figma_extract`

### 参数要求

- `get_design_context` 默认传 `excludeScreenshot=true`（减少 30-60% 数据量）
- `get_design_context` 默认传 `disableCodeConnect=true`（workflow 场景不需要 Code Connect）
- `search_design_system` 用短关键词分多次查询，不要一次传复合查询
- `use_figma` 脚本必须用 `return` 返回数据，控制返回量在 10KB 以内

### use_figma 脚本模板

当需要从设计稿中提取特定数据（Level 3）时，使用以下模板，将 `TARGET_NODE_ID` 替换为实际节点 ID：

**文本内容提取**（适用于需求评审、用例生成）：
```javascript
const texts = [];
function collectText(node) {
  if (node.type === 'TEXT') {
    texts.push({ id: node.id, name: node.name, content: node.characters });
  }
  if ('children' in node) {
    for (const child of node.children) collectText(child);
  }
}
collectText(figma.currentPage.findOne(n => n.id === 'TARGET_NODE_ID'));
return JSON.stringify(texts);
```

**组件结构提取**（适用于设计稿分析）：
```javascript
const MAX_DEPTH = 3;
function collectComponents(node, depth) {
  if (depth > MAX_DEPTH) return null;
  const info = { id: node.id, name: node.name, type: node.type };
  if (node.type === 'INSTANCE') {
    info.mainComponent = node.mainComponent?.name;
  }
  if ('children' in node && depth < MAX_DEPTH) {
    info.children = node.children
      .filter(c => ['FRAME', 'COMPONENT', 'INSTANCE', 'COMPONENT_SET'].includes(c.type))
      .map(c => collectComponents(c, depth + 1))
      .filter(Boolean);
  }
  return info;
}
const target = figma.currentPage.findOne(n => n.id === 'TARGET_NODE_ID');
return JSON.stringify(collectComponents(target, 0));
```

**交互状态提取**（适用于用例生成、冒烟测试）：
```javascript
const interactives = [];
function collect(node) {
  if (['INSTANCE', 'COMPONENT'].includes(node.type)) {
    const props = node.componentProperties || {};
    if (Object.keys(props).length > 0) {
      interactives.push({
        id: node.id, name: node.name, type: node.type,
        properties: Object.fromEntries(
          Object.entries(props).map(([k, v]) => [k, { type: v.type, value: v.value }])
        ),
      });
    }
  }
  if ('children' in node) node.children.forEach(collect);
}
collect(figma.currentPage.findOne(n => n.id === 'TARGET_NODE_ID'));
return JSON.stringify(interactives);
```

**布局与间距提取**（适用于 UI 还原度检查）：
```javascript
function collectLayout(node, depth) {
  if (depth > 2) return null;
  const info = { id: node.id, name: node.name, type: node.type };
  if ('layoutMode' in node && node.layoutMode !== 'NONE') {
    info.layout = {
      mode: node.layoutMode, gap: node.itemSpacing,
      padding: { top: node.paddingTop, right: node.paddingRight,
                 bottom: node.paddingBottom, left: node.paddingLeft },
      sizing: { primary: node.primaryAxisSizingMode,
                counter: node.counterAxisSizingMode },
    };
  }
  info.size = { w: Math.round(node.width), h: Math.round(node.height) };
  if ('children' in node && depth < 2) {
    info.children = node.children.map(c => collectLayout(c, depth + 1)).filter(Boolean);
  }
  return info;
}
const target = figma.currentPage.findOne(n => n.id === 'TARGET_NODE_ID');
return JSON.stringify(collectLayout(target, 0));
```

## 通用约定

- **禁止**使用 WebFetch 获取飞书文档（飞书需认证，WebFetch 无法通过）
- **禁止**使用 WebFetch 获取 Figma 设计稿（使用 Figma MCP 分级获取协议）
- 脚本失败重试策略见 [CONVENTIONS.md](../../CONVENTIONS.md#脚本失败重试策略)
- `fetch_feishu_doc.py` 的 stderr 包含进度日志和 JSON 元数据（最后一行），消费元数据时取 stderr 最后一行
