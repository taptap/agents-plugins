#!/bin/bash
# ensure-lsp-tool.sh - 自动确保 env.ENABLE_LSP_TOOL 已配置
# SessionStart hook: 检查并设置 ENABLE_LSP_TOOL 到 ~/.claude/settings.json
# 后台执行，不阻塞 session 启动，配置在下次 session 生效

set -e

# 日志配置
LOG_DIR="$HOME/.claude/plugins/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/ensure-lsp-tool-$(date +%Y-%m-%d).log"
exec >> "$LOG_FILE" 2>&1
echo ""
echo "===== $(date '+%Y-%m-%d %H:%M:%S') ====="

has_command() {
  command -v "$1" >/dev/null 2>&1
}

SETTINGS_FILE="$HOME/.claude/settings.json"

# 检查是否已有 ENABLE_LSP_TOOL
check_has_lsp_tool() {
  local file="$1"
  if [ ! -f "$file" ]; then
    return 1
  fi
  if has_command jq; then
    if jq -e '.env.ENABLE_LSP_TOOL' "$file" >/dev/null 2>&1; then
      local val
      val=$(jq -r '.env.ENABLE_LSP_TOOL' "$file" 2>/dev/null)
      echo "当前值: ENABLE_LSP_TOOL=$val"
      return 0
    fi
    return 1
  fi
  if has_command python3; then
    python3 -c "
import json, sys
with open('$file') as f:
    d = json.load(f)
env = d.get('env', {})
if 'ENABLE_LSP_TOOL' in env:
    print(f'当前值: ENABLE_LSP_TOOL={env[\"ENABLE_LSP_TOOL\"]}')
    sys.exit(0)
sys.exit(1)
" 2>/dev/null
    return $?
  fi
  return 1
}

if check_has_lsp_tool "$SETTINGS_FILE"; then
  echo "✅ ENABLE_LSP_TOOL 已配置，跳过"
  exit 0
fi

echo "正在配置 ENABLE_LSP_TOOL..."

# jq 优先
if has_command jq; then
  if [ -f "$SETTINGS_FILE" ]; then
    jq '.env = ((.env // {}) + {"ENABLE_LSP_TOOL": "1"})' \
      "$SETTINGS_FILE" > "${SETTINGS_FILE}.tmp" \
      && mv "${SETTINGS_FILE}.tmp" "$SETTINGS_FILE"
  else
    mkdir -p "$(dirname "$SETTINGS_FILE")"
    echo '{"env": {"ENABLE_LSP_TOOL": "1"}}' \
      | jq '.' > "${SETTINGS_FILE}.tmp" \
      && mv "${SETTINGS_FILE}.tmp" "$SETTINGS_FILE"
  fi
  echo "✅ 已配置 ENABLE_LSP_TOOL=1 (jq)"
  exit 0
fi

# python3 兜底
if has_command python3; then
  python3 - "$SETTINGS_FILE" <<'PY'
import json
import os
import sys

def main():
    path = sys.argv[1]
    data = {}

    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            print("⚠️  settings.json 解析失败，跳过")
            return 0

    if not isinstance(data, dict):
        print("⚠️  settings.json 顶层不是对象，跳过")
        return 0

    env = data.get("env", {})
    if not isinstance(env, dict):
        env = {}

    if "ENABLE_LSP_TOOL" in env:
        print(f"✅ ENABLE_LSP_TOOL 已配置: {env['ENABLE_LSP_TOOL']}，跳过")
        return 0

    env["ENABLE_LSP_TOOL"] = "1"
    data["env"] = env

    dir_path = os.path.dirname(path)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path)

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
        print("⚠️  settings.json 写入失败，跳过")
        return 0

    print("✅ 已配置 ENABLE_LSP_TOOL=1 (python3)")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("⚠️  执行异常，跳过")
        raise SystemExit(0)
PY
  exit 0
fi

echo "⚠️  未检测到 jq 或 python3，跳过 ENABLE_LSP_TOOL 配置"
exit 0
