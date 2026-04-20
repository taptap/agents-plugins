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
  done
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

  tmp_root="$(new_tmpdir)"
  home_dir="${tmp_root}/home"
  clone_dir="${home_dir}/.agents/plugins/taptap-plugins"
  mkdir -p "${clone_dir}/plugins/git/.codex-plugin" "${home_dir}/.agents/plugins"
  git -C "$clone_dir" init >/dev/null 2>&1
  git -C "$clone_dir" remote add origin https://github.com/taptap/agents-plugins.git
  jq -n --arg version "0.1.14" '{
    name: "git",
    version: $version,
    description: "validator fixture"
  }' > "${clone_dir}/plugins/git/.codex-plugin/plugin.json"
  jq -n '{
    name: "local-plugins",
    interface: {
      displayName: "Local Plugins"
    },
    plugins: [
      {
        name: "removed",
        source: {
          source: "local",
          path: "./.agents/plugins/taptap-plugins/plugins/removed"
        },
        policy: {
          installation: "AVAILABLE",
          authentication: "ON_INSTALL"
        },
        category: "Productivity"
      },
      {
        name: "external",
        source: {
          source: "local",
          path: "./other/external"
        },
        policy: {
          installation: "AVAILABLE",
          authentication: "ON_INSTALL"
        },
        category: "Productivity"
      }
    ]
  }' > "${home_dir}/.agents/plugins/marketplace.json"

  if HOME="$home_dir" bash "${REPO_ROOT}/plugins/sync/scripts/ensure-codex-plugins.sh" >/dev/null 2>&1; then
    removed_exists=$(jq -r '[.plugins[] | select(.name == "removed")] | length' "${home_dir}/.agents/plugins/marketplace.json")
    external_exists=$(jq -r '[.plugins[] | select(.name == "external")] | length' "${home_dir}/.agents/plugins/marketplace.json")
    git_exists=$(jq -r '[.plugins[] | select(.name == "git")] | length' "${home_dir}/.agents/plugins/marketplace.json")
    if [[ "$removed_exists" == "0" && "$external_exists" == "1" && "$git_exists" == "1" ]]; then
      pass "ensure-codex-plugins.sh prunes stale managed entries and preserves foreign plugins"
    else
      fail "ensure-codex-plugins.sh did not prune stale managed entries correctly"
    fi
  else
    fail "ensure-codex-plugins.sh exited non-zero during stale managed entry test"
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
# N+1. testcase.schema.json 校验（schema 自身可用 + 接受/拒绝样本数据）
# ============================================================
echo "=== Check N+1: testcase.schema.json ==="

TESTCASE_SCHEMA="${REPO_ROOT}/plugins/test/contracts/testcase.schema.json"
if [[ ! -f "$TESTCASE_SCHEMA" ]]; then
  fail "testcase.schema.json not found at ${TESTCASE_SCHEMA}"
elif ! command -v python3 >/dev/null 2>&1; then
  echo "  SKIP: python3 not installed"
elif ! python3 -c 'import jsonschema' >/dev/null 2>&1; then
  echo "  SKIP: jsonschema not installed (pip install jsonschema)"
else
  if python3 - <<PYEOF >/tmp/schema-check.log 2>&1
import json, sys, jsonschema
schema = json.load(open("${TESTCASE_SCHEMA}"))
ok = [{"title": "登录成功", "priority": "P0",
       "preconditions": ["账号已注册"],
       "steps": [{"action": "输入凭证", "expected": "校验通过"}]}]
jsonschema.validate(ok, schema)
bad_samples = [
    ("priority enum", [{"title": "t", "priority": "P9", "preconditions": [],
                        "steps": [{"action": "a"}]}]),
    ("title 非空",    [{"title": "", "priority": "P0", "preconditions": [],
                        "steps": [{"action": "a"}]}]),
    ("禁止额外字段",  [{"title": "t", "priority": "P0", "preconditions": [],
                        "steps": [{"action": "a"}], "name": "x"}]),
    ("steps 非空",    [{"title": "t", "priority": "P0", "preconditions": [],
                        "steps": []}]),
]
for label, data in bad_samples:
    try:
        jsonschema.validate(data, schema)
        sys.exit(f"非法数据未被拒绝: {label}")
    except jsonschema.ValidationError:
        pass
print("ok")
PYEOF
  then
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
