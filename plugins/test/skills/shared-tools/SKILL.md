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
| `fetch_feishu_doc.py` | 获取飞书文档完整内容（文字+图片） | `FEISHU_APP_ID`, `FEISHU_APP_SECRET` | `FEISHU_HOST`（默认 `https://open.feishu.cn`） |
| `gitlab_helper.py` | GitLab MR diff/详情/文件内容 | `GITLAB_URL`, `GITLAB_TOKEN` | `GITLAB_SSL_VERIFY`（默认开启，设 `false` 关闭） |
| `github_helper.py` | GitHub PR diff/详情/文件内容 | `GITHUB_TOKEN` | `GITHUB_URL`（默认 `https://api.github.com`） |
| `search_mrs.py` | 搜索 Story/Bug 关联的 GitLab MR | `GITLAB_URL`, `GITLAB_TOKEN`, `GITLAB_PROJECT_MAPPING` | `GITLAB_SSL_VERIFY` |
| `search_prs.py` | 搜索 Story/Bug 关联的 GitHub PR | `GITHUB_TOKEN`, `GITHUB_REPO_MAPPING` | `GITHUB_URL` |

## 飞书文档获取

```bash
FETCH=$SKILLS_ROOT/shared-tools/scripts/fetch_feishu_doc.py

# 从 URL 获取（自动识别 wiki/docx/docs 链接）
python3 $FETCH --url "https://xxx.feishu.cn/wiki/AbCdEfG" --output-dir . 2>fetch_meta.json

# 直接指定 document_id
python3 $FETCH --doc-id "AbCdEfG" --output-dir . 2>fetch_meta.json

# 仅获取文字，跳过图片下载
python3 $FETCH --url "..." --output-dir . --skip-images
```

**输出**：
- stdout: Markdown 格式文档内容（标题/段落/列表/表格/代码块/图片引用）
- stderr: JSON 元数据 `{"title": "...", "document_id": "...", "images": [...], "image_count": N}`

**图片处理**：图片自动下载到 `{output-dir}/images/`，AI 可通过 Read 工具查看。`--skip-images` 跳过图片下载。

## GitLab 辅助脚本

```bash
GITLAB=$SKILLS_ROOT/shared-tools/scripts/gitlab_helper.py

# MR diff
python3 $GITLAB mr-diff <project_path> <mr_iid>

# MR 详情
python3 $GITLAB mr-detail <project_path> <mr_iid>

# 文件内容
python3 $GITLAB file-content <project_path> <file_path> [--ref master]
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

通过 Figma MCP 获取设计稿数据。各 skill 中使用 `get_figma_data(url="<Figma链接>")` 表示此操作，实际执行时对应 Figma MCP 的 `get_design_context` 工具。

调用时需从 Figma URL 中解析 `fileKey` 和 `nodeId` 作为参数传入。URL 解析规则见 Figma MCP 的工具说明。

## 通用约定

- **禁止**使用 WebFetch 获取飞书文档（飞书需认证，WebFetch 无法通过）
- **禁止**使用 WebFetch 获取 Figma 设计稿（使用 Figma MCP `get_figma_data`）
- 脚本失败重试策略见 [CONVENTIONS.md](../../CONVENTIONS.md#脚本失败重试策略)
- `fetch_feishu_doc.py` 的 stderr 推荐重定向到 `2>fetch_meta.json`，捕获元数据供后续引用
