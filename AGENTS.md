# 插件开发规范

## Git 提交规范

- Commit message、MR/PR title 和 description 必须使用**纯英文**
- 不需要携带工单 ID（no-ticket），本仓库不关联任务系统
- 执行 `/git:commit-push-pr` 时无需询问工单，但每一步（分支创建、commit、review、push、MR 创建）都需要让用户确认后再执行

## 版本管理（必须遵守）

详见 [版本管理规则](.claude/rules/versioning.md)

### 开发中
每次修改插件文件后，必须升级 patch 版本

### 发布前
执行 `/prepare-release` 完成发布准备（版本重置 + CHANGELOG + README 更新）

## 调试

执行 `/clear-cache` 清理本地插件缓存
