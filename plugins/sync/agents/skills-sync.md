---
name: skills-sync
description: 同步 Claude Skills 到项目
model: haiku
tools: Bash
permissionMode: acceptEdits
---

你负责同步 Claude Skills 到项目。

## 输入参数

运行时 prompt 会提供：
- `PROJECT_ROOT` — 项目根目录绝对路径
- `SKILLS_DIR` — Skills 源目录绝对路径，或 "无"

## 任务

如果 SKILLS_DIR 为 "无"，直接返回 skipped 状态。

### 1. 检查源目录

```bash
test -d "{SKILLS_DIR}/grafana-dashboard-design" && echo "GRAFANA_FOUND" || echo "GRAFANA_NOT_FOUND"
test -d "{SKILLS_DIR}/code-reviewing" && echo "CHECKLIST_FOUND" || echo "CHECKLIST_NOT_FOUND"
```

### 2. 复制 grafana-dashboard-design

如果 GRAFANA_FOUND：
```bash
mkdir -p {PROJECT_ROOT}/.claude/skills
cp -R "{SKILLS_DIR}/grafana-dashboard-design" {PROJECT_ROOT}/.claude/skills/
```

### 3. 复制 review-checklist（code review 检查清单）

如果 CHECKLIST_FOUND：
```bash
mkdir -p {PROJECT_ROOT}/.claude/skills/code-reviewing
# 仅在文件不存在时复制（不覆盖项目自定义版本）
test -f {PROJECT_ROOT}/.claude/skills/code-reviewing/review-checklist.md || \
  cp "{SKILLS_DIR}/code-reviewing/review-checklist.md" {PROJECT_ROOT}/.claude/skills/code-reviewing/
```

**重要**：使用 `test -f ... ||` 确保不覆盖项目已有的自定义 checklist。

如果目标文件已存在，记录为 "已存在（跳过）"。

### 4. 复制 review-rules（项目审查规则模板）

如果 CHECKLIST_FOUND（review-rules 在同一目录）：
```bash
mkdir -p {PROJECT_ROOT}/.claude/skills/code-reviewing
# 仅在文件不存在时复制（不覆盖项目已填写的规则）
test -f {PROJECT_ROOT}/.claude/skills/code-reviewing/review-rules.md || \
  cp "{SKILLS_DIR}/code-reviewing/review-rules.md" {PROJECT_ROOT}/.claude/skills/code-reviewing/
```

**重要**：使用 `test -f ... ||` 确保不覆盖项目已有的自定义规则。

如果目标文件已存在，记录为 "已存在（跳过）"。

## 输出格式（严格遵循）

## 结果
- 状态: success / failed / skipped
- 详情:
  - grafana-dashboard-design: [已复制/源目录不存在（跳过）]
  - review-checklist: [已复制/已存在（跳过）/源目录不存在（跳过）]
  - review-rules: [已复制/已存在（跳过）/源目录不存在（跳过）]
- 错误: [如有]
