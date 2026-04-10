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
REQUIRED_PLUGINS=("spec@taptap-plugins" "sync@taptap-plugins" "git@taptap-plugins" "skill-creator@claude-plugins-official")

# 需要清理的退役插件
DEPRECATED_PLUGINS=("ralph@taptap-plugins" "quality@taptap-plugins")
EXPECTED_MARKETPLACE_REPO="taptap/claude-plugins-marketplace"

# ========== Step 1: 确保 enabledPlugins 完整 ==========

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
    # 检查 extraKnownMarketplaces.taptap-plugins 存在且 repo 正确
    if ! jq -e ".extraKnownMarketplaces[\"taptap-plugins\"].source.repo == \"$EXPECTED_MARKETPLACE_REPO\"" "$file" >/dev/null 2>&1; then
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
required = ['spec@taptap-plugins', 'sync@taptap-plugins', 'git@taptap-plugins', 'skill-creator@claude-plugins-official']
deprecated = ['ralph@taptap-plugins', 'quality@taptap-plugins']
has_marketplace = marketplaces.get('taptap-plugins', {}).get('source', {}).get('repo') == 'taptap/claude-plugins-marketplace'
sys.exit(0 if all(k in plugins for k in required) and not any(k in plugins for k in deprecated) and has_marketplace else 1)
" 2>/dev/null
    return $?
  fi
  return 1
}

if check_plugins_ok "$SETTINGS_FILE"; then
  echo "✅ enabledPlugins 已包含全部插件且无废弃插件，跳过"
else
  echo "正在配置 enabledPlugins..."

  # jq 优先
  if has_command jq; then
    if [ -f "$SETTINGS_FILE" ]; then
      jq '(.enabledPlugins // {}) as $ep |
      .enabledPlugins = ($ep + {
        "spec@taptap-plugins": true,
        "sync@taptap-plugins": true,
        "git@taptap-plugins": true,
        "skill-creator@claude-plugins-official": true
      } | del(.["ralph@taptap-plugins"]) | del(.["quality@taptap-plugins"])) |
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
      echo '{"enabledPlugins": {"spec@taptap-plugins": true, "sync@taptap-plugins": true, "git@taptap-plugins": true, "skill-creator@claude-plugins-official": true}, "extraKnownMarketplaces": {"taptap-plugins": {"source": {"source": "github", "repo": "taptap/claude-plugins-marketplace"}}}}' \
        | jq '.' > "${SETTINGS_FILE}.tmp" \
        && mv "${SETTINGS_FILE}.tmp" "$SETTINGS_FILE"
    fi
    echo "✅ 已配置 enabledPlugins (jq)"

  # python3 兜底
  elif has_command python3; then
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
    plugins["skill-creator@claude-plugins-official"] = True
    plugins.pop("ralph@taptap-plugins", None)   # 清理已废弃的插件
    plugins.pop("quality@taptap-plugins", None)  # 已废弃，由 code-reviewing skill 替代
    data["enabledPlugins"] = plugins

    # 确保 extraKnownMarketplaces 包含 taptap-plugins 且 repo 指向最新仓库名
    marketplaces = data.get("extraKnownMarketplaces", {})
    if not isinstance(marketplaces, dict):
        marketplaces = {}
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

  else
    echo "⚠️  未检测到 jq 或 python3，跳过 enabledPlugins 配置"
  fi
fi

# ========== Step 2: 清理 installed_plugins.json 中的退役插件 ==========

INSTALLED_FILE="$HOME/.claude/plugins/installed_plugins.json"
if [ -f "$INSTALLED_FILE" ]; then
  # installed_plugins.json v2 结构: {"version": 2, "plugins": {...}}
  # 需要在 .plugins 下查找和删除
  needs_clean=false
  for plugin in "${DEPRECATED_PLUGINS[@]}"; do
    if has_command jq; then
      if jq -e ".plugins[\"$plugin\"]" "$INSTALLED_FILE" >/dev/null 2>&1; then
        needs_clean=true
        break
      fi
    elif has_command python3; then
      if python3 -c "import json; d=json.load(open('$INSTALLED_FILE')); exit(0 if '$plugin' in d.get('plugins', d) else 1)" 2>/dev/null; then
        needs_clean=true
        break
      fi
    fi
  done

  if $needs_clean; then
    if has_command jq; then
      jq_filter="."
      for plugin in "${DEPRECATED_PLUGINS[@]}"; do
        jq_filter="$jq_filter | del(.plugins[\"$plugin\"])"
      done
      jq "$jq_filter" "$INSTALLED_FILE" > "${INSTALLED_FILE}.tmp" \
        && mv "${INSTALLED_FILE}.tmp" "$INSTALLED_FILE"
      echo "✅ 已清理 installed_plugins.json 中的退役插件"
    elif has_command python3; then
      python3 -c "
import json, os
path = '$INSTALLED_FILE'
with open(path) as f:
    d = json.load(f)
plugins = d.get('plugins', d)
deprecated = [p.strip() for p in '${DEPRECATED_PLUGINS[*]}'.split()]
changed = False
for p in deprecated:
    if p in plugins:
        del plugins[p]
        changed = True
if changed:
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write('\n')
    os.replace(tmp, path)
    print('✅ 已清理 installed_plugins.json 中的退役插件')
"
    fi
  else
    echo "✅ installed_plugins.json 无退役插件，跳过"
  fi
fi

# ========== Step 3: 清理当前项目的 settings 中的退役插件 ==========
# SessionStart hook 的工作目录是当前项目目录

for settings_file in ".claude/settings.json" ".claude/settings.local.json"; do
  if [ -f "$settings_file" ]; then
    needs_project_clean=false
    for plugin in "${DEPRECATED_PLUGINS[@]}"; do
      if has_command jq; then
        if jq -e ".enabledPlugins[\"$plugin\"]" "$settings_file" >/dev/null 2>&1; then
          needs_project_clean=true
          break
        fi
      elif has_command python3; then
        if python3 -c "import json; d=json.load(open('$settings_file')); exit(0 if '$plugin' in d.get('enabledPlugins',{}) else 1)" 2>/dev/null; then
          needs_project_clean=true
          break
        fi
      fi
    done

    if $needs_project_clean; then
      if has_command jq; then
        jq_filter=".enabledPlugins"
        for plugin in "${DEPRECATED_PLUGINS[@]}"; do
          jq_filter="$jq_filter | del(.[\"$plugin\"])"
        done
        jq ".enabledPlugins = ($jq_filter)" "$settings_file" > "${settings_file}.tmp" \
          && mv "${settings_file}.tmp" "$settings_file"
        echo "✅ 已清理 $settings_file 中的退役插件"
      elif has_command python3; then
        python3 -c "
import json, os
path = '$settings_file'
with open(path) as f:
    d = json.load(f)
plugins = d.get('enabledPlugins', {})
deprecated = [p.strip() for p in '${DEPRECATED_PLUGINS[*]}'.split()]
changed = False
for p in deprecated:
    if p in plugins:
        del plugins[p]
        changed = True
if changed:
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write('\n')
    os.replace(tmp, path)
    print('✅ 已清理 $settings_file 中的退役插件')
"
      fi
    fi
  fi
done
