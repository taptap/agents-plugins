#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MARKETPLACE_JSON="${REPO_ROOT}/.claude-plugin/marketplace.json"
EXIT_CODE=0

pass() { echo "  PASS: $1"; }
fail() { echo "  FAIL: $1" >&2; EXIT_CODE=1; }

TEMP_DIRS=()

new_tmpdir() {
  local dir
  dir="$(mktemp -d)"
  TEMP_DIRS+=("$dir")
  printf '%s\n' "$dir"
}

cleanup() {
  if [[ ${#TEMP_DIRS[@]} -gt 0 ]]; then
    rm -rf "${TEMP_DIRS[@]}"
  fi
}

trap cleanup EXIT

# ============================================================
# 1. claude plugin validate（对 marketplace 中注册的每个插件）
# ============================================================
echo "=== Check 1: claude plugin validate ==="

if command -v claude >/dev/null 2>&1; then
  plugin_names=$(jq -r '.plugins[].name' "$MARKETPLACE_JSON")
  for name in $plugin_names; do
    plugin_dir="${REPO_ROOT}/plugins/${name}"
    if [[ ! -d "$plugin_dir" ]]; then
      fail "[${name}] plugin directory not found: ${plugin_dir}"
      continue
    fi
    if claude plugin validate "$plugin_dir" >/dev/null 2>&1; then
      pass "[${name}] claude plugin validate"
    else
      fail "[${name}] claude plugin validate failed"
      claude plugin validate "$plugin_dir" 2>&1 | sed 's/^/    /' || true
    fi
  done
else
  echo "  SKIP: claude CLI not installed, skipping plugin validate"
fi

# ============================================================
# 2. 版本一致性（plugin.json ↔ marketplace.json）
# ============================================================
echo "=== Check 2: Version consistency ==="

plugin_count=$(jq '.plugins | length' "$MARKETPLACE_JSON")
for i in $(seq 0 $((plugin_count - 1))); do
  name=$(jq -r ".plugins[$i].name" "$MARKETPLACE_JSON")
  mp_version=$(jq -r ".plugins[$i].version" "$MARKETPLACE_JSON")
  plugin_json="${REPO_ROOT}/plugins/${name}/.claude-plugin/plugin.json"

  if [[ ! -f "$plugin_json" ]]; then
    fail "[${name}] plugin.json not found: ${plugin_json}"
    continue
  fi

  pj_version=$(jq -r '.version' "$plugin_json")

  if [[ "$mp_version" == "$pj_version" ]]; then
    pass "[${name}] version=${pj_version}"
  else
    fail "[${name}] marketplace=${mp_version} != plugin.json=${pj_version}"
  fi

  # name 一致性
  pj_name=$(jq -r '.name' "$plugin_json")
  if [[ "$name" != "$pj_name" ]]; then
    fail "[${name}] marketplace name '${name}' != plugin.json name '${pj_name}'"
  fi
done

# ============================================================
# 3. marketplace.json schema
# ============================================================
echo "=== Check 3: marketplace.json schema ==="

# metadata 必填字段
for field in version description pluginRoot; do
  val=$(jq -r ".metadata.${field} // empty" "$MARKETPLACE_JSON")
  if [[ -n "$val" ]]; then
    pass "metadata.${field} exists"
  else
    fail "metadata.${field} missing"
  fi
done

# semver 格式
meta_version=$(jq -r '.metadata.version' "$MARKETPLACE_JSON")
if [[ "$meta_version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  pass "metadata.version semver format: ${meta_version}"
else
  fail "metadata.version not semver: ${meta_version}"
fi

# plugins[] 条目必填字段
for i in $(seq 0 $((plugin_count - 1))); do
  name=$(jq -r ".plugins[$i].name" "$MARKETPLACE_JSON")
  for field in name source description version; do
    val=$(jq -r ".plugins[$i].${field} // empty" "$MARKETPLACE_JSON")
    if [[ -z "$val" ]]; then
      fail "[${name}] plugins[${i}].${field} missing"
    fi
  done
  # author.name
  author=$(jq -r ".plugins[$i].author.name // empty" "$MARKETPLACE_JSON")
  if [[ -z "$author" ]]; then
    fail "[${name}] plugins[${i}].author.name missing"
  fi
done
if [[ $EXIT_CODE -eq 0 ]]; then
  pass "all marketplace plugin entries complete"
fi

# ============================================================
# 4. Codex plugin.json 一致性
# ============================================================
echo "=== Check 4: Codex plugin.json consistency ==="

for i in $(seq 0 $((plugin_count - 1))); do
  name=$(jq -r ".plugins[$i].name" "$MARKETPLACE_JSON")
  mp_version=$(jq -r ".plugins[$i].version" "$MARKETPLACE_JSON")
  codex_json="${REPO_ROOT}/plugins/${name}/.codex-plugin/plugin.json"

  if [[ ! -f "$codex_json" ]]; then
    fail "[${name}] missing .codex-plugin/plugin.json for marketplace plugin"
    continue
  fi

  codex_version=$(jq -r '.version' "$codex_json")
  if [[ "$mp_version" == "$codex_version" ]]; then
    pass "[${name}] marketplace-codex version=${codex_version}"
  else
    fail "[${name}] marketplace=${mp_version} != codex plugin.json=${codex_version}"
  fi
done

shopt -s nullglob
codex_manifests=("${REPO_ROOT}"/plugins/*/.codex-plugin/plugin.json)
shopt -u nullglob

if [[ ${#codex_manifests[@]} -eq 0 ]]; then
  fail "no .codex-plugin/plugin.json found under plugins/"
else
  for codex_json in "${codex_manifests[@]}"; do
    plugin_dir="$(basename "$(dirname "$(dirname "$codex_json")")")"
    codex_name=$(jq -r '.name' "$codex_json")
    codex_version=$(jq -r '.version' "$codex_json")
    plugin_json="${REPO_ROOT}/plugins/${plugin_dir}/.claude-plugin/plugin.json"
    mp_version=$(jq -r --arg name "$plugin_dir" '.plugins[]? | select(.name == $name) | .version' "$MARKETPLACE_JSON")

    if [[ "$codex_name" != "$plugin_dir" ]]; then
      fail "[${plugin_dir}] codex plugin.json name '${codex_name}' != directory name '${plugin_dir}'"
    fi

    if [[ -f "$plugin_json" ]]; then
      claude_version=$(jq -r '.version' "$plugin_json")
      if [[ "$claude_version" == "$codex_version" ]]; then
        pass "[${plugin_dir}] codex version=${codex_version}"
      else
        fail "[${plugin_dir}] claude plugin.json=${claude_version} != codex plugin.json=${codex_version}"
      fi
    else
      pass "[${plugin_dir}] codex-only plugin manifest"
    fi

    if [[ -z "$mp_version" ]]; then
      pass "[${plugin_dir}] not in .claude-plugin/marketplace.json (allowed for Codex-only plugins)"
    fi

    # interface 段 schema 校验：必含 displayName / category / capabilities
    iface_display=$(jq -r '.interface.displayName // empty' "$codex_json")
    iface_category=$(jq -r '.interface.category // empty' "$codex_json")
    iface_caps=$(jq -r '.interface.capabilities // empty | type' "$codex_json")
    if [[ -n "$iface_display" && -n "$iface_category" && "$iface_caps" == "array" ]]; then
      pass "[${plugin_dir}] codex plugin.json has interface.{displayName, category, capabilities}"
    else
      fail "[${plugin_dir}] codex plugin.json missing interface fields (displayName='$iface_display' category='$iface_category' capabilities=$iface_caps)"
    fi
  done
fi

# .agents/plugins/marketplace.json 校验（Codex 端 marketplace 入口）
codex_marketplace="${REPO_ROOT}/.agents/plugins/marketplace.json"
if [[ -f "$codex_marketplace" ]]; then
  cm_name=$(jq -r '.name // empty' "$codex_marketplace")
  cm_display=$(jq -r '.interface.displayName // empty' "$codex_marketplace")
  if [[ "$cm_name" == "taptap-plugins" && -n "$cm_display" ]]; then
    pass ".agents/plugins/marketplace.json has name=taptap-plugins and interface.displayName"
  else
    fail ".agents/plugins/marketplace.json invalid: name='$cm_name' displayName='$cm_display'"
  fi

  # 列表中的每个 plugin 都应在 plugins/<name>/.codex-plugin/plugin.json 存在
  cm_plugin_count=$(jq -r '.plugins | length' "$codex_marketplace")
  for j in $(seq 0 $((cm_plugin_count - 1))); do
    cm_plugin_name=$(jq -r ".plugins[$j].name" "$codex_marketplace")
    cm_plugin_path=$(jq -r ".plugins[$j].source.path" "$codex_marketplace")
    target="${REPO_ROOT}/${cm_plugin_path#./}/.codex-plugin/plugin.json"
    if [[ -f "$target" ]]; then
      pass "[${cm_plugin_name}] .agents/plugins/marketplace.json source.path → ${cm_plugin_path} exists"
    else
      fail "[${cm_plugin_name}] .agents/plugins/marketplace.json source.path → ${cm_plugin_path} missing manifest at ${target}"
    fi
  done
else
  fail ".agents/plugins/marketplace.json missing (required for Codex marketplace add)"
fi

# ============================================================
# 5. gitignore 一致性
# ============================================================
echo "=== Check 5: gitignore consistency ==="

for i in $(seq 0 $((plugin_count - 1))); do
  name=$(jq -r ".plugins[$i].name" "$MARKETPLACE_JSON")
  plugin_dir="plugins/${name}"
  if git -C "$REPO_ROOT" check-ignore -q "$plugin_dir" 2>/dev/null; then
    fail "[${name}] registered in marketplace.json but gitignored"
  fi
done
if [[ $EXIT_CODE -eq 0 ]]; then
  pass "no gitignored plugins in marketplace.json"
fi

# ============================================================
# 6. shellcheck
# ============================================================
echo "=== Check 6: shellcheck ==="

if command -v shellcheck >/dev/null 2>&1; then
  sh_files=()
  while IFS= read -r -d '' f; do
    sh_files+=("$f")
  done < <(find "$REPO_ROOT" -name '*.sh' -not -path '*/node_modules/*' -print0)

  # .githooks 下的文件（无 .sh 后缀但有 shebang）
  for hook_file in "$REPO_ROOT"/.githooks/*; do
    [[ -f "$hook_file" ]] || continue
    [[ "$(basename "$hook_file")" == "README.md" ]] && continue
    head -1 "$hook_file" | grep -q '^#!/.*bash' && sh_files+=("$hook_file")
  done

  if [[ ${#sh_files[@]} -eq 0 ]]; then
    pass "no shell scripts found"
  else
    sc_failed=0
    for f in "${sh_files[@]}"; do
      rel="${f#"$REPO_ROOT"/}"
      if shellcheck -S warning "$f" >/dev/null 2>&1; then
        pass "${rel}"
      else
        fail "${rel}"
        shellcheck -S warning "$f" 2>&1 | head -20 | sed 's/^/    /' || true
        sc_failed=1
      fi
    done
    if [[ $sc_failed -eq 0 ]]; then
      pass "all shell scripts pass shellcheck"
    fi
  fi
else
  echo "  SKIP: shellcheck not installed"
fi

# ============================================================
# 7. sync runtime edge cases
# ============================================================
echo "=== Check 7: sync runtime edge cases ==="

if command -v python3 >/dev/null 2>&1; then
  HOOK_BOOTSTRAP_CMD=$(jq -r '.hooks.SessionStart[0].hooks[0].command' "${REPO_ROOT}/plugins/sync/hooks/hooks.json")

  if [[ -z "$HOOK_BOOTSTRAP_CMD" || "$HOOK_BOOTSTRAP_CMD" == "null" ]]; then
    fail "sync home hook bootstrap command missing"
  else
    pass "sync home hook bootstrap command exists"
  fi

  if [[ "$HOOK_BOOTSTRAP_CMD" == *'for loc in $('* ]]; then
    fail "sync home hook bootstrap still uses whitespace-splitting for-loop"
  else
    pass "sync home hook bootstrap avoids whitespace-splitting for-loop"
  fi

  tmp_root="$(new_tmpdir)"
  home_dir="${tmp_root}/home"
  good_install="${tmp_root}/good"
  bad_install="${tmp_root}/bad"
  mkdir -p "${home_dir}/.claude/plugins" "${good_install}/plugins/sync/scripts" "${bad_install}/plugins/sync/scripts"
  printf '#!/bin/bash\nexit 0\n' > "${good_install}/plugins/sync/scripts/ensure-codex-plugins.sh"
  printf '#!/bin/bash\nexit 0\n' > "${bad_install}/plugins/sync/scripts/ensure-codex-plugins.sh"
  chmod +x "${good_install}/plugins/sync/scripts/ensure-codex-plugins.sh" "${bad_install}/plugins/sync/scripts/ensure-codex-plugins.sh"
  jq -n \
    --arg bad "$bad_install" \
    --arg good "$good_install" \
    '{"other-marketplace":{"installLocation":$bad},"taptap-plugins":{"installLocation":$good}}' > "${home_dir}/.claude/plugins/known_marketplaces.json"

  if HOME="$home_dir" bash -c "$HOOK_BOOTSTRAP_CMD" >/dev/null 2>&1; then
    target=$(readlink "${home_dir}/.claude/hooks/scripts/ensure-codex-plugins.sh" 2>/dev/null || true)
    if [[ "$target" == "${good_install}/plugins/sync/scripts/ensure-codex-plugins.sh" ]]; then
      pass "sync home hook bootstrap only uses taptap-plugins installLocation"
    else
      fail "sync home hook bootstrap linked scripts from the wrong marketplace"
    fi
  else
    fail "sync home hook bootstrap failed when multiple marketplaces are present"
  fi

  tmp_root="$(new_tmpdir)"
  home_dir="${tmp_root}/home"
  mkdir -p "${home_dir}/.claude/hooks/scripts" "${home_dir}/.claude/plugins"
  ln -sf "${REPO_ROOT}/plugins/sync/scripts/ensure-plugins.sh" "${home_dir}/.claude/hooks/scripts/ensure-plugins.sh"
  jq -n --arg install "$REPO_ROOT" '{"taptap-plugins":{"installLocation":$install}}' > "${home_dir}/.claude/plugins/known_marketplaces.json"

  if HOME="$home_dir" bash -c "$HOOK_BOOTSTRAP_CMD" >/dev/null 2>&1; then
    if [[ -L "${home_dir}/.claude/hooks/scripts/ensure-codex-plugins.sh" ]]; then
      pass "sync home hook bootstrap backfills newly added scripts"
    else
      fail "sync home hook bootstrap did not backfill ensure-codex-plugins.sh"
    fi
  else
    fail "sync home hook bootstrap command failed during backfill test"
  fi

  tmp_root="$(new_tmpdir)"
  home_dir="${tmp_root}/home"
  install_parent="${tmp_root}/install roots"
  spaced_install="${install_parent}/agents plugins repo"
  mkdir -p "${home_dir}/.claude/plugins" "$install_parent"
  ln -s "$REPO_ROOT" "$spaced_install"
  jq -n --arg install "$spaced_install" '{"taptap-plugins":{"installLocation":$install}}' > "${home_dir}/.claude/plugins/known_marketplaces.json"

  if HOME="$home_dir" bash -c "$HOOK_BOOTSTRAP_CMD" >/dev/null 2>&1; then
    if [[ -L "${home_dir}/.claude/hooks/scripts/ensure-codex-plugins.sh" ]]; then
      pass "sync home hook bootstrap handles installLocation with spaces"
    else
      fail "sync home hook bootstrap missed scripts when installLocation contains spaces"
    fi
  else
    fail "sync home hook bootstrap failed when installLocation contains spaces"
  fi

  tmp_root="$(new_tmpdir)"
  home_dir="${tmp_root}/home"
  mkdir -p "${home_dir}/.claude"
  printf '{bad json\n' > "${home_dir}/.claude/settings.json"

  if HOME="$home_dir" bash "${REPO_ROOT}/plugins/sync/scripts/ensure-plugins.sh" >/dev/null 2>&1; then
    shopt -s nullglob
    ensure_logs=("${home_dir}"/.claude/plugins/logs/ensure-plugins-*.log)
    shopt -u nullglob
    if [[ ${#ensure_logs[@]} -eq 0 ]]; then
      fail "ensure-plugins.sh did not produce a log file during invalid settings test"
    elif grep -q 'settings.json 更新失败' "${ensure_logs[0]}" && ! grep -q '已配置 enabledPlugins (jq)' "${ensure_logs[0]}"; then
      pass "ensure-plugins.sh does not report jq success after settings.json parse failure"
    else
      fail "ensure-plugins.sh still reports jq success after settings.json parse failure"
    fi
  else
    fail "ensure-plugins.sh exited non-zero during invalid settings test"
  fi

  tmp_root="$(new_tmpdir)"
  home_dir="${tmp_root}/home"
  mkdir -p "${home_dir}/.claude"
  jq -n '{
    "enabledPlugins": {},
    "extraKnownMarketplaces": {
      "taptap-plugins": {
        "source": {
          "source": "github",
          "repo": "myfork/agents-plugins"
        }
      }
    }
  }' > "${home_dir}/.claude/settings.json"

  if HOME="$home_dir" bash "${REPO_ROOT}/plugins/sync/scripts/ensure-plugins.sh" >/dev/null 2>&1; then
    current_repo=$(jq -r '.extraKnownMarketplaces["taptap-plugins"].source.repo' "${home_dir}/.claude/settings.json")
    spec_enabled=$(jq -r '.enabledPlugins["spec@taptap-plugins"]' "${home_dir}/.claude/settings.json")
    sync_enabled=$(jq -r '.enabledPlugins["sync@taptap-plugins"]' "${home_dir}/.claude/settings.json")
    git_enabled=$(jq -r '.enabledPlugins["git@taptap-plugins"]' "${home_dir}/.claude/settings.json")
    if [[ "$current_repo" == "myfork/agents-plugins" && "$spec_enabled" == "true" && "$sync_enabled" == "true" && "$git_enabled" == "true" ]]; then
      pass "ensure-plugins.sh preserves custom marketplace repo while enabling required plugins"
    else
      fail "ensure-plugins.sh overwrote custom marketplace repo or missed required plugins"
    fi
  else
    fail "ensure-plugins.sh exited non-zero during custom repo preservation test"
  fi

  tmp_root="$(new_tmpdir)"
  home_dir="${tmp_root}/home"
  mkdir -p "${home_dir}/.claude/plugins"
  jq -n '{
    "taptap-plugins": {
      "source": {
        "source": "github",
        "repo": "myfork/agents-plugins"
      },
      "autoUpdate": false
    }
  }' > "${home_dir}/.claude/plugins/known_marketplaces.json"

  if HOME="$home_dir" bash "${REPO_ROOT}/plugins/sync/scripts/set-auto-update-plugins.sh" >/dev/null 2>&1; then
    current_repo=$(jq -r '."taptap-plugins".source.repo' "${home_dir}/.claude/plugins/known_marketplaces.json")
    current_auto_update=$(jq -r '."taptap-plugins".autoUpdate' "${home_dir}/.claude/plugins/known_marketplaces.json")
    if [[ "$current_repo" == "myfork/agents-plugins" && "$current_auto_update" == "true" ]]; then
      pass "set-auto-update-plugins.sh preserves custom repo while enabling autoUpdate"
    else
      fail "set-auto-update-plugins.sh overwrote custom repo or missed autoUpdate"
    fi
  else
    fail "set-auto-update-plugins.sh exited non-zero during custom repo test"
  fi

  create_fake_codex_plugin() {
    local plugin_root="$1"
    local plugin_name="$2"
    local plugin_version="$3"

    mkdir -p "${plugin_root}/.codex-plugin"
    cat > "${plugin_root}/.codex-plugin/plugin.json" <<EOF
{
  "name": "${plugin_name}",
  "version": "${plugin_version}",
  "description": "test plugin",
  "author": {
    "name": "TapTap AI Team"
  },
  "interface": {
    "displayName": "${plugin_name}",
    "category": "Productivity",
    "capabilities": [
      "Read",
      "Write"
    ]
  }
}
EOF
    printf '%s\n' "${plugin_name}" > "${plugin_root}/README.md"
  }

  create_fake_codex_marketplace_clone() {
    local target_home="$1"
    local install_source_type="$2"
    local install_source="$3"
    local origin_url="${4:-$install_source}"
    local clone_dir="${target_home}/.codex/.tmp/marketplaces/taptap-plugins"

    mkdir -p "${clone_dir}/.agents/plugins" "${clone_dir}/.git"

    cat > "${clone_dir}/.codex-marketplace-install.json" <<EOF
{
  "source_type": "${install_source_type}",
  "source": "${install_source}",
  "ref_name": null,
  "sparse_paths": [],
  "revision": "test-revision"
}
EOF

    cat > "${clone_dir}/.git/config" <<EOF
[remote "origin"]
	url = ${origin_url}
	fetch = +refs/heads/*:refs/remotes/origin/*
EOF

    cat > "${clone_dir}/.agents/plugins/marketplace.json" <<'EOF'
{
  "name": "taptap-plugins",
  "plugins": [
    {
      "name": "git",
      "source": {
        "source": "local",
        "path": "./plugins/git"
      },
      "policy": {
        "installation": "INSTALLED_BY_DEFAULT"
      }
    },
    {
      "name": "sync",
      "source": {
        "source": "local",
        "path": "./plugins/sync"
      },
      "policy": {
        "installation": "INSTALLED_BY_DEFAULT"
      }
    },
    {
      "name": "spec",
      "source": {
        "source": "local",
        "path": "./plugins/spec"
      },
      "policy": {
        "installation": "AVAILABLE"
      }
    },
    {
      "name": "test",
      "source": {
        "source": "local",
        "path": "./plugins/test"
      },
      "policy": {
        "installation": "AVAILABLE"
      }
    }
  ]
}
EOF

    create_fake_codex_plugin "${clone_dir}/plugins/git" "git" "1.0.0"
    create_fake_codex_plugin "${clone_dir}/plugins/sync" "sync" "2.0.0"
    create_fake_codex_plugin "${clone_dir}/plugins/spec" "spec" "3.0.0"
    create_fake_codex_plugin "${clone_dir}/plugins/test" "test" "4.0.0"
  }

  write_codex_shim_adds_remote_clone() {
    local bin_dir="$1"
    local shim_log="$2"
    local sleep_seconds="${3:-0}"
    local command_mode="${4:-both}"

    cat > "${bin_dir}/codex" <<EOF
#!/usr/bin/env bash
echo "\$@" >> "${shim_log}"
mode="${command_mode}"
supports_plugin=0
supports_legacy=0
case "\${mode}" in
  both)
    supports_plugin=1
    supports_legacy=1
    ;;
  plugin_only)
    supports_plugin=1
    ;;
  legacy_only)
    supports_legacy=1
    ;;
esac

if [[ "\$1" == "plugin" && "\$2" == "marketplace" && "\$3" == "add" && "\$4" == "--help" ]]; then
  [[ "\${supports_plugin}" == "1" ]] && exit 0 || exit 2
fi

if [[ "\$1" == "marketplace" && "\$2" == "add" && "\$3" == "--help" ]]; then
  [[ "\${supports_legacy}" == "1" ]] && exit 0 || exit 2
fi

if [[ "\$1" == "plugin" && "\$2" == "marketplace" && "\$3" == "remove" && "\$4" == "--help" ]]; then
  [[ "\${supports_plugin}" == "1" ]] && exit 0 || exit 2
fi

if [[ "\$1" == "marketplace" && "\$2" == "remove" && "\$3" == "--help" ]]; then
  [[ "\${supports_legacy}" == "1" ]] && exit 0 || exit 2
fi

if [[ "\$1" == "plugin" && "\$2" == "marketplace" && "\$3" == "remove" && "\$4" == "taptap-plugins" ]]; then
  rm -rf "\$HOME/.codex/.tmp/marketplaces/taptap-plugins"
  rm -rf "\$HOME/.codex/plugins/cache/taptap-plugins"
  exit 0
fi

if [[ "\$1" == "marketplace" && "\$2" == "remove" && "\$3" == "taptap-plugins" ]]; then
  rm -rf "\$HOME/.codex/.tmp/marketplaces/taptap-plugins"
  rm -rf "\$HOME/.codex/plugins/cache/taptap-plugins"
  exit 0
fi

if [[ "\$1" == "plugin" && "\$2" == "marketplace" && "\$3" == "add" && "\$4" == "taptap/agents-plugins" && "\${supports_plugin}" == "1" ]]; then
  sleep "${sleep_seconds}"
  clone_dir="\$HOME/.codex/.tmp/marketplaces/taptap-plugins"
  mkdir -p "\${clone_dir}/.agents/plugins" "\${clone_dir}/.git"
  cat > "\${clone_dir}/.codex-marketplace-install.json" <<'JSON'
{
  "source_type": "git",
  "source": "https://github.com/taptap/agents-plugins.git",
  "ref_name": null,
  "sparse_paths": [],
  "revision": "shim-revision"
}
JSON
  cat > "\${clone_dir}/.git/config" <<'GIT'
[remote "origin"]
	url = https://github.com/taptap/agents-plugins.git
	fetch = +refs/heads/*:refs/remotes/origin/*
GIT
  cat > "\${clone_dir}/.agents/plugins/marketplace.json" <<'MARKETPLACE'
{
  "name": "taptap-plugins",
  "plugins": [
    {
      "name": "git",
      "source": {
        "source": "local",
        "path": "./plugins/git"
      },
      "policy": {
        "installation": "INSTALLED_BY_DEFAULT"
      }
    },
    {
      "name": "sync",
      "source": {
        "source": "local",
        "path": "./plugins/sync"
      },
      "policy": {
        "installation": "INSTALLED_BY_DEFAULT"
      }
    },
    {
      "name": "spec",
      "source": {
        "source": "local",
        "path": "./plugins/spec"
      },
      "policy": {
        "installation": "AVAILABLE"
      }
    },
    {
      "name": "test",
      "source": {
        "source": "local",
        "path": "./plugins/test"
      },
      "policy": {
        "installation": "AVAILABLE"
      }
    }
  ]
}
MARKETPLACE
  for entry in "git 1.0.0" "sync 2.0.0" "spec 3.0.0" "test 4.0.0"; do
    set -- \$entry
    mkdir -p "\${clone_dir}/plugins/\$1/.codex-plugin"
    cat > "\${clone_dir}/plugins/\$1/.codex-plugin/plugin.json" <<JSON
{
  "name": "\$1",
  "version": "\$2",
  "description": "test plugin",
  "author": {
    "name": "TapTap AI Team"
  },
  "interface": {
    "displayName": "\$1",
    "category": "Productivity",
    "capabilities": [
      "Read",
      "Write"
    ]
  }
}
JSON
    printf '%s\n' "\$1" > "\${clone_dir}/plugins/\$1/README.md"
  done
  exit 0
fi

if [[ "\$1" == "marketplace" && "\$2" == "add" && "\$3" == "taptap/agents-plugins" && "\${supports_legacy}" == "1" ]]; then
  sleep "${sleep_seconds}"
  clone_dir="\$HOME/.codex/.tmp/marketplaces/taptap-plugins"
  mkdir -p "\${clone_dir}/.agents/plugins" "\${clone_dir}/.git"
  cat > "\${clone_dir}/.codex-marketplace-install.json" <<'JSON'
{
  "source_type": "git",
  "source": "https://github.com/taptap/agents-plugins.git",
  "ref_name": null,
  "sparse_paths": [],
  "revision": "shim-revision"
}
JSON
  cat > "\${clone_dir}/.git/config" <<'GIT'
[remote "origin"]
	url = https://github.com/taptap/agents-plugins.git
	fetch = +refs/heads/*:refs/remotes/origin/*
GIT
  cat > "\${clone_dir}/.agents/plugins/marketplace.json" <<'MARKETPLACE'
{
  "name": "taptap-plugins",
  "plugins": [
    {
      "name": "git",
      "source": {
        "source": "local",
        "path": "./plugins/git"
      },
      "policy": {
        "installation": "INSTALLED_BY_DEFAULT"
      }
    },
    {
      "name": "sync",
      "source": {
        "source": "local",
        "path": "./plugins/sync"
      },
      "policy": {
        "installation": "INSTALLED_BY_DEFAULT"
      }
    },
    {
      "name": "spec",
      "source": {
        "source": "local",
        "path": "./plugins/spec"
      },
      "policy": {
        "installation": "AVAILABLE"
      }
    },
    {
      "name": "test",
      "source": {
        "source": "local",
        "path": "./plugins/test"
      },
      "policy": {
        "installation": "AVAILABLE"
      }
    }
  ]
}
MARKETPLACE
  for entry in "git 1.0.0" "sync 2.0.0" "spec 3.0.0" "test 4.0.0"; do
    set -- \$entry
    mkdir -p "\${clone_dir}/plugins/\$1/.codex-plugin"
    cat > "\${clone_dir}/plugins/\$1/.codex-plugin/plugin.json" <<JSON
{
  "name": "\$1",
  "version": "\$2",
  "description": "test plugin",
  "author": {
    "name": "TapTap AI Team"
  },
  "interface": {
    "displayName": "\$1",
    "category": "Productivity",
    "capabilities": [
      "Read",
      "Write"
    ]
  }
}
JSON
    printf '%s\n' "\$1" > "\${clone_dir}/plugins/\$1/README.md"
  done
fi
exit 0
EOF
    chmod +x "${bin_dir}/codex"
  }

  python3_dir="$(dirname "$(command -v python3)")"

  # Test A: 远端 install metadata 存在时，不依赖 config block，也不重复调用 marketplace add
  tmp_root="$(new_tmpdir)"
  home_dir="${tmp_root}/home"
  project_dir="${tmp_root}/project"
  bin_dir="${tmp_root}/bin"
  shim_log="${tmp_root}/codex-shim.log"
  user_cfg="${home_dir}/.codex/config.toml"
  git_cache_manifest="${home_dir}/.codex/plugins/cache/taptap-plugins/git/1.0.0/.codex-plugin/plugin.json"
  sync_cache_manifest="${home_dir}/.codex/plugins/cache/taptap-plugins/sync/2.0.0/.codex-plugin/plugin.json"

  mkdir -p "${home_dir}/.codex" "${project_dir}" "${bin_dir}"
  : > "${shim_log}"
  : > "${user_cfg}"

  cat > "${bin_dir}/codex" <<EOF
#!/usr/bin/env bash
echo "\$@" >> "${shim_log}"
exit 0
EOF
  chmod +x "${bin_dir}/codex"

  create_fake_codex_marketplace_clone "${home_dir}" "git" "https://github.com/taptap/agents-plugins.git"
  git -C "${project_dir}" init >/dev/null 2>&1

  if (cd "${project_dir}" && PATH="${bin_dir}:${python3_dir}:/usr/bin:/bin" HOME="${home_dir}" bash "${REPO_ROOT}/plugins/sync/scripts/ensure-codex-plugins.sh" >/dev/null 2>&1); then
    if [[ ! -s "${shim_log}" ]] \
      && grep -q '^\[plugins\."git@taptap-plugins"\]$' "${user_cfg}" \
      && grep -q '^\[plugins\."sync@taptap-plugins"\]$' "${user_cfg}" \
      && [[ -f "${git_cache_manifest}" && -f "${sync_cache_manifest}" ]]
    then
      pass "ensure-codex-plugins.sh trusts remote install metadata and installs default plugins without marketplace add"
    else
      fail "ensure-codex-plugins.sh did not honor remote install metadata correctly (shim log: $(cat "${shim_log}" 2>/dev/null), user_cfg: $(cat "${user_cfg}" 2>/dev/null))"
    fi
  else
    fail "ensure-codex-plugins.sh exited non-zero during remote metadata test"
  fi

  # Test B: 旧本地源会迁移到远端源，并清理过期 marketplace config block
  tmp_root="$(new_tmpdir)"
  home_dir="${tmp_root}/home"
  project_dir="${tmp_root}/project"
  bin_dir="${tmp_root}/bin"
  shim_log="${tmp_root}/codex-shim.log"
  local_source="${tmp_root}/legacy-marketplace"
  user_cfg="${home_dir}/.codex/config.toml"

  mkdir -p "${home_dir}/.codex" "${project_dir}/.codex" "${bin_dir}" "${local_source}"
  : > "${shim_log}"

  write_codex_shim_adds_remote_clone "${bin_dir}" "${shim_log}" "0" "plugin_only"
  create_fake_codex_marketplace_clone "${home_dir}" "local" "${local_source}"

  printf '[marketplaces.taptap-plugins]\nsource_type = "local"\nsource = "%s"\n' "${local_source}" > "${user_cfg}"
  printf '[plugins."git@taptap-plugins"]\nenabled = true\n\n[plugins."sync@taptap-plugins"]\nenabled = true\n' \
    > "${project_dir}/.codex/config.toml"

  git -C "${project_dir}" init >/dev/null 2>&1

  if (cd "${project_dir}" && PATH="${bin_dir}:${python3_dir}:/usr/bin:/bin" HOME="${home_dir}" bash "${REPO_ROOT}/plugins/sync/scripts/ensure-codex-plugins.sh" >/dev/null 2>&1); then
    add_count=$(grep -Ec '^(plugin )?marketplace add taptap/agents-plugins$' "${shim_log}" || true)
    install_file="${home_dir}/.codex/.tmp/marketplaces/taptap-plugins/.codex-marketplace-install.json"
    if [[ "${add_count}" == "1" ]] \
      && grep -q '"source": "https://github.com/taptap/agents-plugins.git"' "${install_file}" \
      && ! grep -q '^\[marketplaces\.taptap-plugins\]$' "${user_cfg}" \
      && [[ -f "${home_dir}/.codex/plugins/cache/taptap-plugins/git/1.0.0/.codex-plugin/plugin.json" ]] \
      && [[ -f "${home_dir}/.codex/plugins/cache/taptap-plugins/sync/2.0.0/.codex-plugin/plugin.json" ]]
    then
      pass "ensure-codex-plugins.sh migrates legacy local marketplace state to the remote GitHub source"
    else
      fail "ensure-codex-plugins.sh did not finish remote migration (add_count=${add_count}, user_cfg: $(cat "${user_cfg}" 2>/dev/null), shim log: $(cat "${shim_log}" 2>/dev/null))"
    fi
  else
    fail "ensure-codex-plugins.sh exited non-zero during local-source migration test"
  fi

  # Test B2: 新版 codex CLI 不支持旧路径时，脚本使用 codex plugin marketplace add
  tmp_root="$(new_tmpdir)"
  home_dir="${tmp_root}/home"
  project_dir="${tmp_root}/project"
  bin_dir="${tmp_root}/bin"
  shim_log="${tmp_root}/codex-shim.log"

  mkdir -p "${home_dir}/.codex" "${project_dir}" "${bin_dir}"
  : > "${home_dir}/.codex/config.toml"
  : > "${shim_log}"

  write_codex_shim_adds_remote_clone "${bin_dir}" "${shim_log}" "0" "plugin_only"
  git -C "${project_dir}" init >/dev/null 2>&1

  if (cd "${project_dir}" && PATH="${bin_dir}:${python3_dir}:/usr/bin:/bin" HOME="${home_dir}" bash "${REPO_ROOT}/plugins/sync/scripts/ensure-codex-plugins.sh" >/dev/null 2>&1); then
    if grep -q '^plugin marketplace add taptap/agents-plugins$' "${shim_log}" \
      && ! grep -q '^marketplace add taptap/agents-plugins$' "${shim_log}" \
      && [[ -f "${home_dir}/.codex/.tmp/marketplaces/taptap-plugins/.codex-marketplace-install.json" ]]
    then
      pass "ensure-codex-plugins.sh prefers codex plugin marketplace add on newer Codex CLI versions"
    else
      fail "ensure-codex-plugins.sh did not use codex plugin marketplace add on newer CLI (shim log: $(cat "${shim_log}" 2>/dev/null))"
    fi
  else
    fail "ensure-codex-plugins.sh exited non-zero during plugin-marketplace command test"
  fi

  # Test B3: 旧版 codex CLI 仅支持 codex marketplace add 时仍可回退
  tmp_root="$(new_tmpdir)"
  home_dir="${tmp_root}/home"
  project_dir="${tmp_root}/project"
  bin_dir="${tmp_root}/bin"
  shim_log="${tmp_root}/codex-shim.log"

  mkdir -p "${home_dir}/.codex" "${project_dir}" "${bin_dir}"
  : > "${home_dir}/.codex/config.toml"
  : > "${shim_log}"

  write_codex_shim_adds_remote_clone "${bin_dir}" "${shim_log}" "0" "legacy_only"
  git -C "${project_dir}" init >/dev/null 2>&1

  if (cd "${project_dir}" && PATH="${bin_dir}:${python3_dir}:/usr/bin:/bin" HOME="${home_dir}" bash "${REPO_ROOT}/plugins/sync/scripts/ensure-codex-plugins.sh" >/dev/null 2>&1); then
    if grep -q '^marketplace add taptap/agents-plugins$' "${shim_log}" \
      && ! grep -q '^plugin marketplace add taptap/agents-plugins$' "${shim_log}" \
      && [[ -f "${home_dir}/.codex/.tmp/marketplaces/taptap-plugins/.codex-marketplace-install.json" ]]
    then
      pass "ensure-codex-plugins.sh falls back to codex marketplace add on legacy Codex CLI versions"
    else
      fail "ensure-codex-plugins.sh did not fall back to legacy marketplace add (shim log: $(cat "${shim_log}" 2>/dev/null))"
    fi
  else
    fail "ensure-codex-plugins.sh exited non-zero during legacy-marketplace command test"
  fi

  # Test C: 显式 enabled = false 必须保留，不被项目声明或默认安装覆盖
  tmp_root="$(new_tmpdir)"
  home_dir="${tmp_root}/home"
  project_dir="${tmp_root}/project"
  bin_dir="${tmp_root}/bin"
  shim_log="${tmp_root}/codex-shim.log"
  user_cfg="${home_dir}/.codex/config.toml"

  mkdir -p "${home_dir}/.codex" "${project_dir}/.codex" "${bin_dir}"
  : > "${shim_log}"

  cat > "${bin_dir}/codex" <<EOF
#!/usr/bin/env bash
echo "\$@" >> "${shim_log}"
exit 0
EOF
  chmod +x "${bin_dir}/codex"

  create_fake_codex_marketplace_clone "${home_dir}" "git" "https://github.com/taptap/agents-plugins.git"
  printf '[plugins."git@taptap-plugins"]\nenabled = false\n' > "${user_cfg}"
  printf '[plugins."git@taptap-plugins"]\nenabled = true\n\n[plugins."sync@taptap-plugins"]\nenabled = true\n' \
    > "${project_dir}/.codex/config.toml"

  git -C "${project_dir}" init >/dev/null 2>&1

  if (cd "${project_dir}" && PATH="${bin_dir}:${python3_dir}:/usr/bin:/bin" HOME="${home_dir}" bash "${REPO_ROOT}/plugins/sync/scripts/ensure-codex-plugins.sh" >/dev/null 2>&1); then
    if [[ ! -s "${shim_log}" ]] \
      && grep -A1 '^\[plugins\."git@taptap-plugins"\]$' "${user_cfg}" | grep -q '^enabled = false$' \
      && grep -A1 '^\[plugins\."sync@taptap-plugins"\]$' "${user_cfg}" | grep -q '^enabled = true$' \
      && [[ ! -e "${home_dir}/.codex/plugins/cache/taptap-plugins/git/1.0.0/.codex-plugin/plugin.json" ]] \
      && [[ -f "${home_dir}/.codex/plugins/cache/taptap-plugins/sync/2.0.0/.codex-plugin/plugin.json" ]]
    then
      pass "ensure-codex-plugins.sh preserves explicit user opt-outs while installing other enabled plugins"
    else
      fail "ensure-codex-plugins.sh overwrote enabled=false or installed a disabled plugin (user_cfg: $(cat "${user_cfg}" 2>/dev/null))"
    fi
  else
    fail "ensure-codex-plugins.sh exited non-zero during enabled=false preservation test"
  fi

  # Test D: codex CLI 缺失时仍优雅退出，并继续镜像项目 plugin enablement
  tmp_root="$(new_tmpdir)"
  home_dir="${tmp_root}/home"
  project_dir="${tmp_root}/project"
  user_cfg="${home_dir}/.codex/config.toml"

  mkdir -p "${home_dir}/.codex" "${project_dir}/.codex"
  : > "${user_cfg}"
  printf '[plugins."git@taptap-plugins"]\nenabled = true\n' > "${project_dir}/.codex/config.toml"
  git -C "${project_dir}" init >/dev/null 2>&1

  if (cd "${project_dir}" && PATH="${python3_dir}:/usr/bin:/bin" HOME="${home_dir}" bash "${REPO_ROOT}/plugins/sync/scripts/ensure-codex-plugins.sh" >/dev/null 2>&1); then
    if grep -q '^\[plugins\."git@taptap-plugins"\]$' "${user_cfg}" && grep -q '^enabled = true$' "${user_cfg}"; then
      pass "ensure-codex-plugins.sh exits 0 gracefully without codex while still mirroring project plugin state"
    else
      fail "ensure-codex-plugins.sh skipped project mirror when codex CLI was missing (user_cfg: $(cat "${user_cfg}" 2>/dev/null))"
    fi
  else
    fail "ensure-codex-plugins.sh did not exit 0 when codex CLI missing"
  fi

  # Test E: 并发 SessionStart 只允许一个进程执行 marketplace add
  tmp_root="$(new_tmpdir)"
  home_dir="${tmp_root}/home"
  project_dir="${tmp_root}/project"
  bin_dir="${tmp_root}/bin"
  shim_log="${tmp_root}/codex-shim.log"

  mkdir -p "${home_dir}/.codex" "${project_dir}" "${bin_dir}"
  : > "${home_dir}/.codex/config.toml"
  : > "${shim_log}"

  write_codex_shim_adds_remote_clone "${bin_dir}" "${shim_log}" "1" "plugin_only"
  git -C "${project_dir}" init >/dev/null 2>&1

  run_failed=0
  pids=()
  for _ in 1 2 3; do
    (
      cd "${project_dir}" \
        && PATH="${bin_dir}:${python3_dir}:/usr/bin:/bin" HOME="${home_dir}" \
          bash "${REPO_ROOT}/plugins/sync/scripts/ensure-codex-plugins.sh" >/dev/null 2>&1
    ) &
    pids+=("$!")
  done

  for pid in "${pids[@]}"; do
    if ! wait "${pid}"; then
      run_failed=1
    fi
  done

  if [[ "${run_failed}" != "0" ]]; then
    fail "ensure-codex-plugins.sh exited non-zero during concurrent invocation test"
  else
    add_count=$(grep -Ec '^(plugin )?marketplace add taptap/agents-plugins$' "${shim_log}" || true)
    if [[ "${add_count}" == "1" ]] \
      && [[ -f "${home_dir}/.codex/.tmp/marketplaces/taptap-plugins/.codex-marketplace-install.json" ]]
    then
      pass "ensure-codex-plugins.sh serializes concurrent SessionStart runs with a single marketplace add"
    else
      fail "ensure-codex-plugins.sh did not serialize concurrent marketplace registration (add_count=${add_count}, shim log: $(cat "${shim_log}" 2>/dev/null))"
    fi
  fi
else
  echo "  SKIP: python3 not installed, skipping sync runtime edge cases"
fi

# ============================================================
# 8. release skills detect untracked plugin files
# ============================================================
echo "=== Check 8: release skills detect untracked plugin files ==="

for file in \
  "${REPO_ROOT}/.claude/skills/prepare-release/SKILL.md" \
  "${REPO_ROOT}/.claude/skills/reset-version/SKILL.md"
do
  rel="${file#"$REPO_ROOT"/}"
  if grep -q 'git ls-files --others --exclude-standard -- plugins/' "$file"; then
    pass "${rel} checks untracked plugin files"
  else
    fail "${rel} does not mention untracked plugin file detection"
  fi
done

if grep -q '新增的未跟踪插件文件也算该插件有修改' "${REPO_ROOT}/.claude/rules/versioning.md"; then
  pass ".claude/rules/versioning.md documents untracked plugin file versioning"
else
  fail ".claude/rules/versioning.md does not mention untracked plugin files"
fi

# ============================================================
# 9. sync commands prefer CLAUDE_PLUGIN_ROOT
# ============================================================
echo "=== Check 9: sync commands prefer CLAUDE_PLUGIN_ROOT ==="

for file in \
  "${REPO_ROOT}/plugins/sync/commands/basic.md" \
  "${REPO_ROOT}/plugins/sync/commands/hooks.md" \
  "${REPO_ROOT}/plugins/sync/commands/statusline.md" \
  "${REPO_ROOT}/plugins/sync/commands/lsp.md" \
  "${REPO_ROOT}/plugins/sync/commands/mcp-grafana.md" \
  "${REPO_ROOT}/plugins/sync/skills/codex-statusline/SKILL.md"
do
  rel="${file#"$REPO_ROOT"/}"
  if grep -q 'CLAUDE_PLUGIN_ROOT' "$file"; then
    pass "${rel} documents CLAUDE_PLUGIN_ROOT source resolution"
  else
    fail "${rel} does not document CLAUDE_PLUGIN_ROOT source resolution"
  fi
done

for file in \
  "${REPO_ROOT}/plugins/sync/commands/basic.md" \
  "${REPO_ROOT}/plugins/sync/commands/hooks.md"
do
  rel="${file#"$REPO_ROOT"/}"
  if grep -q 'agents-plugins()' "$file" || grep -q 'zshrc' "$file"; then
    fail "${rel} still contains local wrapper / shell rc assumptions"
  else
    pass "${rel} avoids local wrapper / shell rc assumptions"
  fi
done

if grep -q 'Codex 插件独立 clone' "${REPO_ROOT}/plugins/sync/commands/basic.md"; then
  fail "plugins/sync/commands/basic.md still documents deprecated Codex clone wording"
else
  pass "plugins/sync/commands/basic.md documents Codex marketplace/plugin config without clone wording"
fi

if grep -q '必须把当前 sync 源目录里的 project hooks scripts 重新覆盖到项目内' "${REPO_ROOT}/plugins/sync/commands/basic.md" \
  && grep -q '.codex/hooks/scripts/ensure-codex-plugins.sh' "${REPO_ROOT}/plugins/sync/commands/basic.md"
then
  pass "plugins/sync/commands/basic.md documents overwriting existing project hook scripts during reruns"
else
  fail "plugins/sync/commands/basic.md does not require reruns to overwrite existing project hook scripts"
fi

literal_tilde='~'
deprecated_codex_distribution="${literal_tilde}/.agents/plugins"

for file in \
  "${REPO_ROOT}/plugins/sync/README.md" \
  "${REPO_ROOT}/plugins/sync/agents/codex-plugins-config.md" \
  "${REPO_ROOT}/plugins/sync/commands/hooks.md"
do
  rel="${file#"$REPO_ROOT"/}"
  if grep -Fq -- "${deprecated_codex_distribution}" "$file"; then
    fail "${rel} still documents deprecated ~/.agents/plugins Codex distribution"
  else
    pass "${rel} avoids deprecated ~/.agents/plugins Codex distribution wording"
  fi
done

if grep -q '.codex/hooks/scripts/ensure-codex-plugins.sh .*>/dev/null 2>&1 &' "${REPO_ROOT}/plugins/sync/commands/hooks.md"; then
  fail "plugins/sync/commands/hooks.md still documents the Codex startup hook as backgrounded"
else
  pass "plugins/sync/commands/hooks.md documents the Codex startup hook as synchronous"
fi

hooks_command="${REPO_ROOT}/plugins/sync/commands/hooks.md"
if grep -q '这些复制是\*\*覆盖式刷新\*\*' "${hooks_command}" \
  && grep -q '必须覆盖已存在的 `.codex/hooks/scripts/ensure-codex-plugins.sh`' "${hooks_command}"
then
  pass "plugins/sync/commands/hooks.md requires overwriting existing project hook scripts"
else
  fail "plugins/sync/commands/hooks.md does not require overwriting existing project hook scripts"
fi

background_codex_home_hook='ensure-codex-plugins.sh >/dev/null 2>&1 &'
if grep -Fq -- "${background_codex_home_hook}" "${REPO_ROOT}/plugins/sync/hooks/hooks.json"; then
  fail "plugins/sync/hooks/hooks.json still backgrounds ensure-codex-plugins.sh"
else
  pass "plugins/sync/hooks/hooks.json runs ensure-codex-plugins.sh synchronously"
fi

hooks_agent="${REPO_ROOT}/plugins/sync/agents/hooks-config.md"
if grep -Eq 'mkdir -p ~/\.(claude/hooks|claude/hooks/scripts)|~/.claude/hooks/scripts|~/.claude/hooks/hooks\.json' "${hooks_agent}"; then
  fail "plugins/sync/agents/hooks-config.md still writes Claude hooks under HOME"
else
  pass "plugins/sync/agents/hooks-config.md avoids HOME-level Claude hooks writes"
fi

if grep -q '{PROJECT_ROOT}/.claude/hooks/scripts' "${hooks_agent}" \
  && grep -q '{PROJECT_ROOT}/.codex/hooks/scripts' "${hooks_agent}" \
  && grep -Fq -- "不要写入 \`${literal_tilde}/.claude/hooks/\`" "${hooks_agent}"
then
  pass "plugins/sync/agents/hooks-config.md documents project-level Claude/Codex hook sync"
else
  fail "plugins/sync/agents/hooks-config.md does not fully document project-level hook sync"
fi

if grep -q '复制必须是\*\*覆盖式刷新\*\*' "${hooks_agent}" \
  && grep -q '不允许因为文件已存在而跳过复制' "${hooks_agent}" \
  && grep -q '.codex/hooks/scripts/ensure-codex-plugins.sh' "${hooks_agent}"
then
  pass "plugins/sync/agents/hooks-config.md requires overwriting existing project hook scripts"
else
  fail "plugins/sync/agents/hooks-config.md does not require overwriting existing project hook scripts"
fi

codex_agent="${REPO_ROOT}/plugins/sync/agents/codex-plugins-config.md"
if grep -q '复制必须是\*\*覆盖式刷新\*\*' "${codex_agent}" \
  && grep -q '不允许因为目标文件存在而跳过' "${codex_agent}" \
  && grep -q '让 `/sync:basic` / `/sync:hooks` 能把最新 marketplace 自愈逻辑同步到下游项目' "${codex_agent}"
then
  pass "plugins/sync/agents/codex-plugins-config.md requires overwriting existing Codex hook scripts"
else
  fail "plugins/sync/agents/codex-plugins-config.md does not require overwriting existing Codex hook scripts"
fi

if grep -q 'detect_shell_name' "${REPO_ROOT}/plugins/sync/scripts/ensure-cli-tools.sh" \
  && grep -q '.bashrc' "${REPO_ROOT}/plugins/sync/scripts/ensure-cli-tools.sh" \
  && grep -q 'set -Ux GH_TOKEN' "${REPO_ROOT}/plugins/sync/scripts/ensure-cli-tools.sh"
then
  pass "plugins/sync/scripts/ensure-cli-tools.sh provides multi-shell token setup hints"
else
  fail "plugins/sync/scripts/ensure-cli-tools.sh does not provide multi-shell token setup hints"
fi

for file in \
  "${REPO_ROOT}/plugins/sync/commands/basic.md" \
  "${REPO_ROOT}/plugins/sync/commands/lsp.md"
do
  rel="${file#"$REPO_ROOT"/}"
  if grep -q 'taptap/claude-plugins-marketplace' "$file" \
    && grep -q 'taptap/agents-plugins' "$file" \
    && grep -q '保留不动' "$file"
  then
    pass "${rel} documents project settings repo migration without overwriting custom repos"
  else
    fail "${rel} does not fully document project settings repo migration"
  fi
done

# ============================================================
# N. Contract bridge check（producer 端 contract.yaml 自检 + 与消费方对账）
# ============================================================
echo "=== Check N: Contract bridge ==="

BRIDGE_SCRIPT="${REPO_ROOT}/scripts/contract-bridge-check.py"
if [[ ! -f "$BRIDGE_SCRIPT" ]]; then
  fail "contract-bridge-check.py not found at ${BRIDGE_SCRIPT}"
elif ! command -v python3 >/dev/null 2>&1; then
  echo "  SKIP: python3 not installed"
elif ! python3 -c 'import yaml' >/dev/null 2>&1; then
  echo "  SKIP: PyYAML not installed (pip install pyyaml)"
else
  # marketplace 单仓 CI 用 lenient：找不到 ai-case consumer 就只校验 contract.yaml 自身合规
  if python3 "$BRIDGE_SCRIPT" --lenient >/tmp/bridge-check.log 2>&1; then
    pass "contract bridge check"
  else
    fail "contract bridge check"
    sed 's/^/    /' /tmp/bridge-check.log
  fi
fi

# ============================================================
# N+1. testcase.schema.json 校验（委托给 tests/check-schemas.sh）
# ============================================================
echo "=== Check N+1: testcase.schema.json ==="

CHECK_SCHEMAS="${REPO_ROOT}/tests/check-schemas.sh"
if [[ ! -f "$CHECK_SCHEMAS" ]]; then
  fail "check-schemas.sh not found at ${CHECK_SCHEMAS}"
elif ! command -v python3 >/dev/null 2>&1; then
  echo "  SKIP: python3 not installed"
elif ! python3 -c 'import jsonschema' >/dev/null 2>&1; then
  echo "  SKIP: jsonschema not installed (pip install jsonschema)"
else
  if bash "$CHECK_SCHEMAS" >/tmp/schema-check.log 2>&1; then
    pass "testcase.schema.json valid + rejects 4 invalid patterns"
  else
    fail "testcase.schema.json validation"
    sed 's/^/    /' /tmp/schema-check.log
  fi
fi

# ============================================================
# Summary
# ============================================================
echo ""
if [[ $EXIT_CODE -eq 0 ]]; then
  echo "All checks passed."
else
  echo "Some checks failed. See FAIL entries above." >&2
fi

exit $EXIT_CODE
