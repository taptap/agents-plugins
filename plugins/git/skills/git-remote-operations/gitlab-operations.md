# GitLab CLI (glab) 参考手册

使用 `glab` 进行 GitLab 操作的命令参考。

> **自托管 GitLab 实例说明**：glab 在 git 仓库内执行时，会自动从 `git remote` URL 检测 GitLab 实例地址（如 `git.gametaptap.com`），无需手动指定主机。如果在仓库外操作或需要指定其他仓库，可使用 `-R/--repo` 参数：
>
> ```bash
> # 在仓库内：glab 自动检测主机，直接使用即可
> glab mr view 123
> glab mr list
>
> # 在仓库外或指定其他仓库：使用 --repo
> glab mr view 123 --repo group/project
> ```

## 认证

```bash
# 检查认证状态
glab auth status

# 登录 gitlab.com
glab auth login

# 登录自托管实例
glab auth login --host git.gametaptap.com

# 使用 token 登录
glab auth login --host git.gametaptap.com --token YOUR_TOKEN
```

## Merge Request 操作

### 创建 MR

```bash
glab mr create \
  --title "title" \
  --description "description" \
  --source-branch feature-branch \
  --target-branch master \
  --assignee @me \
  --yes
```

**选项：**
- `--title`：MR 标题
- `--description`：MR 描述（多行使用 HEREDOC）
- `--source-branch`：源分支（默认为当前分支）
- `--target-branch`：目标分支（默认为 main/master）
- `--assignee`：指派给用户（@me 表示自己）
- `--draft` / `--wip`：标记为草稿
- `--remove-source-branch`：合并后自动删除源分支
- `--squash`：启用 squash 合并
- `--yes`：跳过确认提示

### 列出 MR

```bash
# 列出已开启的 MR
glab mr list

# 列出所有 MR
glab mr list --state all

# 列出指派给我的 MR
glab mr list --assignee @me

# 按源分支列出（JSON 输出）
glab mr list --source-branch=$(git branch --show-current) --output json
```

### 查看 MR

```bash
# 查看 MR 详情
glab mr view 123

# 在浏览器中查看
glab mr view 123 --web
```

### 更新 MR

```bash
# 更新标题
glab mr update 123 --title "new title"

# 更新描述
glab mr update 123 --description "new description"

# 添加指派人
glab mr update 123 --assignee username

# 标记为就绪（取消草稿）
glab mr update 123 --ready
```

### 合并 MR

```bash
# 合并
glab mr merge 123

# Squash 合并
glab mr merge 123 --squash

# 合并并删除源分支
glab mr merge 123 --remove-source-branch

# 流水线通过后合并
glab mr merge 123 --when-pipeline-succeeds
```

### 关闭/重新打开 MR

```bash
glab mr close 123
glab mr reopen 123
```

## Issue 操作

### 创建 Issue

```bash
glab issue create \
  --title "Issue title" \
  --description "Description"
```

### 列出 Issue

```bash
# 列出已开启的 Issue
glab issue list

# 列出所有 Issue
glab issue list --state all

# 列出指派给我的 Issue
glab issue list --assignee @me
```

### 查看 Issue

```bash
glab issue view 456
glab issue view 456 --web
```

### 关闭/重新打开 Issue

```bash
glab issue close 456
glab issue reopen 456
```

## 流水线操作

### 查看流水线

```bash
# 列出当前分支的流水线
glab pipeline list

# 查看指定流水线
glab pipeline view 789

# 查看 CI 状态
glab pipeline ci status
```

### 触发流水线

```bash
# 为当前分支触发
glab pipeline run

# 为指定分支触发
glab pipeline run --branch feature-branch
```

### 重试/取消流水线

```bash
glab pipeline retry 789
glab pipeline cancel 789
```

## 仓库操作

### 克隆

```bash
glab repo clone group/project
glab repo clone group/project --host git.gametaptap.com
```

### 查看

```bash
glab repo view
glab repo view --web
```

## HEREDOC 多行内容示例

```bash
glab mr create \
  --title "feat: add feature" \
  --description "$(cat <<'EOF'
## Summary
- Change 1
- Change 2

## Test Plan
- [ ] Tests pass
EOF
)" \
  --target-branch master \
  --yes
```

## 参考

- [glab 官方文档](https://gitlab.com/gitlab-org/cli)
