#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MARKETPLACE_JSON="${REPO_ROOT}/.claude-plugin/marketplace.json"
EXIT_CODE=0

pass() { echo "  PASS: $1"; }
fail() { echo "  FAIL: $1" >&2; EXIT_CODE=1; }

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
# 4. gitignore 一致性
# ============================================================
echo "=== Check 4: gitignore consistency ==="

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
# 5. shellcheck
# ============================================================
echo "=== Check 5: shellcheck ==="

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
# Summary
# ============================================================
echo ""
if [[ $EXIT_CODE -eq 0 ]]; then
  echo "All checks passed."
else
  echo "Some checks failed. See FAIL entries above." >&2
fi

exit $EXIT_CODE
