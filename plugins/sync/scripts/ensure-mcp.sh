#!/bin/bash
# ensure-mcp.sh - 自动配置 MCP 服务器 (context7) + 清理废弃 MCP
# SessionStart hook: 检查 ~/.claude.json 并添加缺失的 MCP 配置
# 后台执行，不阻塞 session 启动，配置在下次 session 生效

set -e

# 日志配置
LOG_DIR="$HOME/.claude/plugins/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/ensure-mcp-$(date +%Y-%m-%d).log"
exec >> "$LOG_FILE" 2>&1
echo ""
echo "===== $(date '+%Y-%m-%d %H:%M:%S') ====="

has_command() {
  command -v "$1" >/dev/null 2>&1
}

# 获取当前项目路径
get_project_path() {
  # 优先使用 PWD（会话启动时的工作目录）
  if [ -n "$PWD" ] && [ -d "$PWD" ]; then
    echo "$PWD"
    return 0
  fi

  # 回退到 git root
  if has_command git; then
    local git_root
    git_root=$(git rev-parse --show-toplevel 2>/dev/null)
    if [ -n "$git_root" ]; then
      echo "$git_root"
      return 0
    fi
  fi

  # 无法检测
  return 1
}

CLAUDE_JSON="$HOME/.claude.json"

# ========== jq 路径 ==========

# 同步项目 MCP 到 user scope（jq 版本）
sync_project_mcps_jq() {
  local project_path="$1"

  # 提取项目级 MCP 列表
  local project_mcps
  project_mcps=$(jq -r --arg path "$project_path" \
    '.projects[$path].mcpServers // {} | keys[]' \
    "$CLAUDE_JSON" 2>/dev/null)

  if [ -z "$project_mcps" ]; then
    echo "✅ 项目无 MCP 配置，跳过迁移"
    return 0
  fi

  # 同步每个 MCP
  local changed=false
  for mcp_name in $project_mcps; do
    # 跳过元数据键（_开头）
    if [[ "$mcp_name" =~ ^_ ]]; then
      continue
    fi

    # 检查顶层是否已存在
    if jq -e --arg name "$mcp_name" \
      '.mcpServers[$name]' "$CLAUDE_JSON" >/dev/null 2>&1; then
      continue
    fi

    # 复制到 user scope
    jq --arg path "$project_path" --arg name "$mcp_name" \
      '.mcpServers[$name] = .projects[$path].mcpServers[$name]' \
      "$CLAUDE_JSON" > "${CLAUDE_JSON}.tmp" && \
      mv "${CLAUDE_JSON}.tmp" "$CLAUDE_JSON"

    echo "✅ 已同步 $mcp_name 到 user scope"
    changed=true
  done

  if [ "$changed" = "true" ]; then
    echo "✅ MCP 迁移完成，下次会话生效"
  fi
}

ensure_mcp_jq() {
  local file="$1"
  local changed=false

  # 如果文件不存在，创建初始结构
  if [ ! -f "$file" ]; then
    echo '{"mcpServers":{}}' | jq '.' > "${file}.tmp" && mv "${file}.tmp" "$file"
    echo "✅ 创建 $file"
  fi

  # 确保 mcpServers 存在
  if ! jq -e '.mcpServers' "$file" >/dev/null 2>&1; then
    jq '. + {"mcpServers":{}}' "$file" > "${file}.tmp" && mv "${file}.tmp" "$file"
  fi

  # 检查并添加 context7
  if ! jq -e '.mcpServers.context7' "$file" >/dev/null 2>&1; then
    jq '.mcpServers.context7 = {"command":"npx","args":["-y","@upstash/context7-mcp"],"env":{}}' \
      "$file" > "${file}.tmp" && mv "${file}.tmp" "$file"
    echo "✅ 已添加 context7 MCP"
    changed=true
  else
    echo "✅ context7 已配置，跳过"
  fi

  # 清理已废弃的 sequential-thinking（如果存在）
  if jq -e '.mcpServers["sequential-thinking"]' "$file" >/dev/null 2>&1; then
    jq 'del(.mcpServers["sequential-thinking"])' \
      "$file" > "${file}.tmp" && mv "${file}.tmp" "$file"
    echo "🗑️ 已移除 sequential-thinking MCP（已废弃）"
    changed=true
  fi

  if [ "$changed" = "false" ]; then
    echo "✅ MCP 配置已完整，无需更新"
  fi

  # 新增：项目 MCP 迁移
  local project_path
  project_path=$(get_project_path)
  if [ -n "$project_path" ]; then
    echo ""
    echo "===== 检查项目 MCP 迁移 ====="
    sync_project_mcps_jq "$project_path"
  fi

  return 0
}

# ========== python3 兜底 ==========

ensure_mcp_python() {
  local file="$1"
  python3 - "$file" <<'PY'
import json
import os
import sys
import subprocess

MCP_SERVERS = {
    "context7": {
        "command": "npx",
        "args": ["-y", "@upstash/context7-mcp"],
        "env": {}
    }
}

DEPRECATED_SERVERS = ["sequential-thinking"]

def get_project_path():
    """获取当前项目路径"""
    # 优先使用 PWD
    pwd = os.environ.get('PWD')
    if pwd and os.path.isdir(pwd):
        return pwd

    # 回退到 git root
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass

    return None

def sync_project_mcps(data, project_path):
    """同步项目级 MCP 到 user scope"""
    # 确保 mcpServers 存在
    if "mcpServers" not in data:
        data["mcpServers"] = {}

    # 获取项目级 MCP 配置
    projects = data.get("projects", {})
    project_config = projects.get(project_path, {})
    project_mcps = project_config.get("mcpServers", {})

    if not project_mcps:
        print("✅ 项目无 MCP 配置，跳过迁移")
        return False

    # 同步每个 MCP
    changed = False
    for mcp_name, mcp_config in project_mcps.items():
        # 跳过元数据键
        if mcp_name.startswith("_"):
            continue

        # 检查是否已存在
        if mcp_name in data["mcpServers"]:
            continue

        # 复制到 user scope
        data["mcpServers"][mcp_name] = mcp_config
        print(f"✅ 已同步 {mcp_name} 到 user scope")
        changed = True

    if changed:
        print("✅ MCP 迁移完成，下次会话生效")

    return changed

def main():
    path = sys.argv[1]
    data = {}

    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read().strip()
                if raw:
                    data = json.loads(raw)
        except Exception:
            print("⚠️  claude.json 解析失败，跳过")
            return 0

    if not isinstance(data, dict):
        print("⚠️  claude.json 顶层不是对象，跳过")
        return 0

    if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
        data["mcpServers"] = {}

    changed = False
    for name, config in MCP_SERVERS.items():
        if name not in data["mcpServers"]:
            data["mcpServers"][name] = config
            print(f"✅ 已添加 {name} MCP")
            changed = True
        else:
            print(f"✅ {name} 已配置，跳过")

    # 清理废弃 MCP
    for name in DEPRECATED_SERVERS:
        if name in data["mcpServers"]:
            del data["mcpServers"][name]
            print(f"🗑️ 已移除 {name} MCP（已废弃）")
            changed = True

    if not changed:
        print("✅ MCP 配置已完整，无需更新")

    # 新增：项目 MCP 迁移
    project_path = get_project_path()
    if project_path:
        print("")
        print("===== 检查项目 MCP 迁移 =====")
        project_changed = sync_project_mcps(data, project_path)
        if project_changed:
            changed = True

    if not changed:
        return 0

    tmp_path = f"{path}.tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path, path)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        print("⚠️  claude.json 写入失败，跳过")
        return 0

    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("⚠️  执行异常，跳过")
        raise SystemExit(0)
PY
}

# ========== 主逻辑 ==========

if has_command jq; then
  ensure_mcp_jq "$CLAUDE_JSON"
  exit 0
fi

if has_command python3; then
  ensure_mcp_python "$CLAUDE_JSON"
  exit 0
fi

echo "⚠️  未检测到 jq 或 python3，跳过 MCP 配置"
exit 0
