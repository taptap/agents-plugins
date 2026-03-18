#!/bin/bash
# ensure-plugins.sh - 自动确保 enabledPlugins + extraKnownMarketplaces 完整
# SessionStart hook: 检查并合并到 ~/.claude/settings.json
# 后台执行，不阻塞 session 启动，配置在下次 session 生效

set -e

# 日志配置
LOG_DIR="$HOME/.claude/plugins/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/ensure-plugins-$(date +%Y-%m-%d).log"
exec >> "$LOG_FILE" 2>&1
echo ""
echo "===== $(date '+%Y-%m-%d %H:%M:%S') ====="

has_command() {
  command -v "$1" >/dev/null 2>&1
}

SETTINGS_FILE="$HOME/.claude/settings.json"

# 期望的插件列表
REQUIRED_PLUGINS=("spec@taptap-plugins" "sync@taptap-plugins" "git@taptap-plugins" "quality@taptap-plugins")

# 需要清理的废弃插件
DEPRECATED_PLUGINS=("ralph@taptap-plugins")

# 检查是否已有全部插件且无废弃插件
check_plugins_ok() {
  local file="$1"
  if [ ! -f "$file" ]; then
    return 1
  fi
  if has_command jq; then
    # 检查必要插件都存在
    for plugin in "${REQUIRED_PLUGINS[@]}"; do
      if ! jq -e ".enabledPlugins[\"$plugin\"]" "$file" >/dev/null 2>&1; then
        return 1
      fi
    done
    # 检查废弃插件不存在
    for plugin in "${DEPRECATED_PLUGINS[@]}"; do
      if jq -e ".enabledPlugins[\"$plugin\"]" "$file" >/dev/null 2>&1; then
        return 1
      fi
    done
    # 检查 extraKnownMarketplaces.taptap-plugins 存在
    if ! jq -e '.extraKnownMarketplaces["taptap-plugins"]' "$file" >/dev/null 2>&1; then
      return 1
    fi
    return 0
  fi
  if has_command python3; then
    python3 -c "
import json, sys
with open('$file') as f:
    d = json.load(f)
plugins = d.get('enabledPlugins', {})
marketplaces = d.get('extraKnownMarketplaces', {})
required = ['spec@taptap-plugins', 'sync@taptap-plugins', 'git@taptap-plugins', 'quality@taptap-plugins']
deprecated = ['ralph@taptap-plugins']
has_marketplace = 'taptap-plugins' in marketplaces
sys.exit(0 if all(k in plugins for k in required) and not any(k in plugins for k in deprecated) and has_marketplace else 1)
" 2>/dev/null
    return $?
  fi
  return 1
}

if check_plugins_ok "$SETTINGS_FILE"; then
  echo "✅ enabledPlugins 已包含全部插件且无废弃插件，跳过"
  exit 0
fi

echo "正在配置 enabledPlugins..."

# jq 优先
if has_command jq; then
  if [ -f "$SETTINGS_FILE" ]; then
    jq '(.enabledPlugins // {}) as $ep |
    .enabledPlugins = ($ep + {
      "spec@taptap-plugins": true,
      "sync@taptap-plugins": true,
      "git@taptap-plugins": true,
      "quality@taptap-plugins": true
    } | del(.["ralph@taptap-plugins"])) |
    .extraKnownMarketplaces = ((.extraKnownMarketplaces // {}) + {
      "taptap-plugins": {
        "source": {
          "source": "github",
          "repo": "taptap/claude-plugins-marketplace"
        }
      }
    })' "$SETTINGS_FILE" > "${SETTINGS_FILE}.tmp" \
      && mv "${SETTINGS_FILE}.tmp" "$SETTINGS_FILE"
  else
    mkdir -p "$(dirname "$SETTINGS_FILE")"
    echo '{"enabledPlugins": {"spec@taptap-plugins": true, "sync@taptap-plugins": true, "git@taptap-plugins": true, "quality@taptap-plugins": true}, "extraKnownMarketplaces": {"taptap-plugins": {"source": {"source": "github", "repo": "taptap/claude-plugins-marketplace"}}}}' \
      | jq '.' > "${SETTINGS_FILE}.tmp" \
      && mv "${SETTINGS_FILE}.tmp" "$SETTINGS_FILE"
  fi
  echo "✅ 已配置 enabledPlugins (jq)"
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

    plugins = data.get("enabledPlugins", {})
    if not isinstance(plugins, dict):
        plugins = {}

    plugins["spec@taptap-plugins"] = True
    plugins["sync@taptap-plugins"] = True
    plugins["git@taptap-plugins"] = True
    plugins["quality@taptap-plugins"] = True
    plugins.pop("ralph@taptap-plugins", None)  # 清理已废弃的插件
    data["enabledPlugins"] = plugins

    # 确保 extraKnownMarketplaces 包含 taptap-plugins
    marketplaces = data.get("extraKnownMarketplaces", {})
    if not isinstance(marketplaces, dict):
        marketplaces = {}
    if "taptap-plugins" not in marketplaces:
        marketplaces["taptap-plugins"] = {
            "source": {
                "source": "github",
                "repo": "taptap/claude-plugins-marketplace"
            }
        }
    data["extraKnownMarketplaces"] = marketplaces

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

    print("✅ 已配置 enabledPlugins + extraKnownMarketplaces (python3)")
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

echo "⚠️  未检测到 jq 或 python3，跳过 enabledPlugins 配置"
exit 0
