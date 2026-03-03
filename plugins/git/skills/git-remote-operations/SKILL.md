---
name: git-remote-operations
description: 创建和管理 PR/MR、Issue 和 CI/CD 工作流/流水线。支持 GitHub、GitLab 和 git.gametaptap.com，自动检测平台并使用 gh（GitHub）或 glab（GitLab）CLI。当用户提及 git.gametaptap.com URL、创建/管理 PR/MR、处理 Issue、检查流水线状态或执行任何 Git 远程平台操作时触发。
---

# Git 远程平台操作

本 Skill 提供 GitHub 和 GitLab 的统一操作接口。

## 工作流程

### 步骤 1：检测平台

```bash
git remote get-url origin
```

| URL 模式 | 平台 | CLI 工具 |
|----------|------|----------|
| `github.com` | GitHub | `gh` |
| `gitlab.com` 或 `git.gametaptap.com` | GitLab | `glab` |

### 步骤 2：加载平台操作指南

使用 Read tool 加载对应的 CLI 指南：

| 平台 | 指南文件 |
|------|----------|
| GitHub | [github-operations.md](github-operations.md) |
| GitLab | [gitlab-operations.md](gitlab-operations.md) |

### 步骤 2.5：MR/PR 操作引导

当用户仅提供 MR/PR URL（未明确指定操作）时，获取并展示 MR/PR 基本信息后，使用 `AskUserQuestion` 询问下一步：

选项（根据 MR/PR 状态动态调整）：
- "进行代码审查（推荐）" — 触发 code-reviewing skill
- "查看代码变更 (diff)"
- "查看/回复评论"
- "合并 MR/PR"（仅 open 状态时显示）

当用户选择"进行代码审查"时，触发 `code-reviewing` skill，不要自行审查。

### 步骤 3：执行操作

按照加载的指南执行 CLI 命令。

## 故障排查

### CLI 未找到

检查 CLI 是否已安装：

```bash
which gh    # GitHub
which glab  # GitLab
```

如未找到 CLI，询问用户并引导安装：

- GitHub CLI: https://cli.github.com/
- GitLab CLI: https://gitlab.com/gitlab-org/cli

### 认证错误

```bash
gh auth login                              # GitHub
glab auth login --host git.gametaptap.com  # GitLab（自托管）
```

### 权限不足

验证对仓库的写入权限。

## 触发场景

本 Skill 在以下场景激活：
- 创建/管理 PR 或 MR
- 处理 GitHub/GitLab Issue
- 检查 CI/CD 流水线/工作流状态
- 合并 PR/MR
- 任何 Git 远程平台操作
