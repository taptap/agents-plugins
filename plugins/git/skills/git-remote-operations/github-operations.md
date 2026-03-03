# GitHub CLI (gh) 参考手册

使用 `gh` 进行 GitHub 操作的命令参考。

## 认证

```bash
# 检查认证状态
gh auth status

# 登录（交互式）
gh auth login

# 使用 token 登录
gh auth login --with-token < token.txt
```

## Pull Request 操作

### 创建 PR

```bash
gh pr create \
  --title "title" \
  --body "description" \
  --base main \
  --head feature-branch \
  --assignee @me
```

**选项：**
- `--title`：PR 标题
- `--body`：PR 描述（多行使用 HEREDOC）
- `--base`：基础/目标分支（默认为仓库默认分支）
- `--head`：源分支（默认为当前分支）
- `--assignee`：指派给用户（@me 表示自己）
- `--reviewer`：请求审查者
- `--draft`：标记为草稿
- `--web`：创建后在浏览器中打开

### 列出 PR

```bash
# 列出已开启的 PR
gh pr list

# 列出所有 PR
gh pr list --state all

# 列出指派给我的 PR
gh pr list --assignee @me

# 按作者列出 PR
gh pr list --author username
```

### 查看 PR

```bash
# 查看 PR 详情
gh pr view 123

# 在浏览器中查看
gh pr view 123 --web

# 查看 diff
gh pr diff 123

# 查看检查/状态
gh pr checks 123
```

### 更新 PR

```bash
# 更新标题
gh pr edit 123 --title "new title"

# 更新描述
gh pr edit 123 --body "new description"

# 添加指派人/审查者
gh pr edit 123 --add-assignee username
gh pr edit 123 --add-reviewer username

# 标记为就绪（取消草稿）
gh pr ready 123
```

### 合并 PR

```bash
# 合并（默认 merge commit）
gh pr merge 123

# Squash 合并
gh pr merge 123 --squash

# Rebase 合并
gh pr merge 123 --rebase

# 合并并删除分支
gh pr merge 123 --delete-branch

# 检查通过后自动合并
gh pr merge 123 --auto --squash
```

### 关闭/重新打开 PR

```bash
gh pr close 123
gh pr reopen 123
```

### 审查 PR

```bash
# 批准
gh pr review 123 --approve

# 请求修改
gh pr review 123 --request-changes --body "Please fix X"

# 评论
gh pr review 123 --comment --body "Looks good!"
```

### 检出 PR

```bash
gh pr checkout 123
```

## Issue 操作

### 创建 Issue

```bash
gh issue create \
  --title "Issue title" \
  --body "Description" \
  --assignee @me
```

### 列出 Issue

```bash
# 列出已开启的 Issue
gh issue list

# 列出所有 Issue
gh issue list --state all

# 列出指派给我的 Issue
gh issue list --assignee @me

# 按标签列出
gh issue list --label bug
```

### 查看 Issue

```bash
gh issue view 456
gh issue view 456 --web
```

### 关闭/重新打开 Issue

```bash
gh issue close 456
gh issue close 456 --reason "completed"
gh issue close 456 --reason "not planned"
gh issue reopen 456
```

### 评论 Issue

```bash
gh issue comment 456 --body "Comment text"
```

## Workflow/Actions 操作

### 查看运行记录

```bash
# 列出工作流运行记录
gh run list

# 列出指定工作流的运行记录
gh run list --workflow=ci.yml

# 查看运行详情
gh run view 789

# 查看运行日志
gh run view 789 --log
```

### 触发工作流

```bash
# 手动触发
gh workflow run ci.yml

# 带参数触发
gh workflow run ci.yml -f environment=production
```

### 重跑/取消

```bash
gh run rerun 789
gh run cancel 789
```

### 监视运行

```bash
gh run watch 789
```

## 仓库操作

### 克隆

```bash
gh repo clone owner/repo
gh repo clone owner/repo target-dir
```

### 查看

```bash
gh repo view
gh repo view owner/repo
gh repo view --web
```

### Fork

```bash
gh repo fork
gh repo fork owner/repo --clone
```

## Release 操作

### 列出/查看 Release

```bash
gh release list
gh release view v1.0.0
```

### 创建 Release

```bash
gh release create v1.0.0 --title "Version 1.0.0" --notes "Release notes"
gh release create v1.0.0 --notes "Notes" dist/*.zip  # 附带资源文件
gh release create v1.0.0 --draft --notes "Draft release"
```

### 下载资源文件

```bash
gh release download          # 最新 release
gh release download v1.0.0   # 指定 release
```

## HEREDOC 多行内容示例

```bash
gh pr create \
  --title "feat: add feature" \
  --body "$(cat <<'EOF'
## Summary
- Change 1
- Change 2

## Test Plan
- [ ] Tests pass
EOF
)" \
  --base main
```

## 参考

- [gh CLI 官方文档](https://cli.github.com/manual/)
