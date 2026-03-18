---
name: plugin-status
description: 检查插件配置状态。当用户说"检查配置"、"plugin status"、"插件状态"、"环境是否配好"时触发。
disable-model-invocation: true
---

# 插件配置状态检查

逐项检查以下配置，输出状态表格。

## 检查项

依次执行以下 bash 命令，收集结果：

```bash
# 1. Plugins 启用状态
echo "=== PLUGINS ==="
cat ~/.claude/settings.json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
plugins=d.get('enabledPlugins',{})
required=['spec@taptap-plugins','sync@taptap-plugins','git@taptap-plugins','quality@taptap-plugins']
for p in required:
    status='✅' if plugins.get(p) else '❌'
    print(f'{status} {p}')
deprecated=['ralph@taptap-plugins']
for p in deprecated:
    if plugins.get(p): print(f'⚠️  {p} (废弃，需清理)')
" 2>/dev/null || echo "❌ ~/.claude/settings.json 不存在"

# 2. Marketplace 配置
echo "=== MARKETPLACE ==="
cat ~/.claude/settings.json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
m=d.get('extraKnownMarketplaces',{})
if 'taptap-plugins' in m: print('✅ taptap-plugins marketplace')
else: print('❌ taptap-plugins marketplace 未配置到 \$HOME')
" 2>/dev/null

# 3. Hooks scripts（symlinks）
echo "=== HOOKS SCRIPTS ==="
for s in set-auto-update-plugins ensure-cli-tools ensure-statusline ensure-plugins ensure-tool-search ensure-lsp-tool ensure-lsp ensure-mcp statusline; do
  f=~/.claude/hooks/scripts/${s}.sh
  if [ -L "$f" ] && [ -e "$f" ]; then echo "✅ ${s}.sh → $(readlink "$f")"
  elif [ -f "$f" ]; then echo "⚠️  ${s}.sh（普通文件，非 symlink）"
  else echo "❌ ${s}.sh 缺失"
  fi
done

# 4. Agents skills（Codex 兼容）
echo "=== AGENTS SKILLS ==="
if [ -d ~/.agents/skills ]; then
  count=$(ls -d ~/.agents/skills/*/ 2>/dev/null | wc -l | tr -d ' ')
  echo "✅ ~/.agents/skills/（${count} 个 skills）"
  for s in git-flow code-reviewing fix-conflict grafana-dashboard-design; do
    [ -L ~/.agents/skills/$s ] && echo "  ✅ $s" || echo "  ❌ $s 缺失"
  done
else
  echo "❌ ~/.agents/skills/ 不存在"
fi

# 5. 插件版本检测
echo "=== PLUGIN VERSIONS ==="
python3 -c "
import json,os
km_path = os.path.expanduser('~/.claude/plugins/known_marketplaces.json')
if not os.path.exists(km_path):
    print('❌ known_marketplaces.json 不存在')
else:
    km = json.load(open(km_path))
    for name, info in km.items():
        loc = info.get('installLocation','')
        mp_path = os.path.join(loc, '.claude-plugin', 'marketplace.json')
        if os.path.exists(mp_path):
            mp = json.load(open(mp_path))
            ver = mp.get('metadata',{}).get('version','?')
            plugins = {p['name']: p['version'] for p in mp.get('plugins',[])}
            print(f'✅ {name} (marketplace v{ver})')
            for pname, pver in plugins.items():
                print(f'  - {pname}: v{pver}')
        else:
            print(f'➖ {name} (installLocation: {loc}, marketplace.json 不存在)')
" 2>/dev/null

# 5.5. Hooks scripts 版本一致性
echo "=== HOOKS VERSION CHECK ==="
# 检查任意一个 hook script 的 symlink 有效性
if [ -L ~/.claude/hooks/scripts/ensure-plugins.sh ]; then
  target=$(readlink ~/.claude/hooks/scripts/ensure-plugins.sh)
  if [ -e "$target" ]; then
    echo "✅ hooks scripts symlink 有效 → $target"
  else
    echo "❌ hooks scripts symlink 失效（目标不存在: $target）→ 需重启 Claude Code 触发 bootstrap"
  fi
else
  [ -f ~/.claude/hooks/scripts/ensure-plugins.sh ] && echo "⚠️  hooks scripts 是普通文件（非 symlink），可能是旧版本" || echo "❌ ensure-plugins.sh 缺失 → 需启动 Claude Code 触发 bootstrap"
fi

# 6. $HOME Symlinks 状态
echo "=== HOME SYMLINKS ==="
echo "--- ~/.claude/hooks/scripts/ ---"
total=0; valid=0; invalid=0; regular=0
for f in ~/.claude/hooks/scripts/*.sh; do
  [ -e "$f" ] || continue
  total=$((total+1))
  name=$(basename "$f")
  if [ -L "$f" ]; then
    if [ -e "$f" ]; then valid=$((valid+1))
    else invalid=$((invalid+1)); echo "  ❌ $name (symlink 失效 → $(readlink "$f"))"
    fi
  else regular=$((regular+1)); echo "  ⚠️  $name (普通文件，非 symlink)"
  fi
done
[ $invalid -eq 0 ] && [ $regular -eq 0 ] && echo "  ✅ ${valid}/${total} 全部有效 symlink" || echo "  总计: ${total} 文件, ${valid} 有效 symlink, ${invalid} 失效, ${regular} 普通文件"

echo "--- ~/.agents/skills/ ---"
if [ -d ~/.agents/skills ]; then
  total=0; valid=0; invalid=0
  for s in ~/.agents/skills/*/; do
    [ -d "$s" ] || continue
    total=$((total+1))
    name=$(basename "$s")
    if [ -L "${s%/}" ]; then
      if [ -e "${s%/}" ]; then valid=$((valid+1))
      else invalid=$((invalid+1)); echo "  ❌ $name (symlink 失效)"
      fi
    fi
  done
  [ $invalid -eq 0 ] && echo "  ✅ ${valid}/${total} 全部有效 symlink" || echo "  总计: ${total} skills, ${valid} 有效, ${invalid} 失效"
else
  echo "  ❌ ~/.agents/skills/ 不存在"
fi

# 7. MCP 配置
echo "=== MCP ==="
# Claude Code
python3 -c "
import json
d=json.load(open('$HOME/.claude.json'))
servers=d.get('mcpServers',{})
for name in ['context7','feishu-mcp','feishu-project-mcp']:
    status='✅' if name in servers else '➖'
    print(f'  {status} {name} (Claude Code)')
" 2>/dev/null || echo "  ❌ ~/.claude.json 不存在"
# Codex
if [ -f ~/.codex/config.toml ]; then
  for name in feishu-mcp feishu-project-mcp; do
    grep -q "\[mcp_servers.$name\]" ~/.codex/config.toml 2>/dev/null && echo "  ✅ $name (Codex)" || echo "  ➖ $name (Codex)"
  done
else
  echo "  ➖ ~/.codex/config.toml 不存在（Codex 未安装）"
fi

# 6. Repo 级配置
echo "=== REPO ==="
[ -f .claude/settings.json ] && echo "✅ .claude/settings.json" || echo "❌ .claude/settings.json 不存在"
[ -L CLAUDE.md ] && echo "✅ CLAUDE.md → $(readlink CLAUDE.md)" || ([ -f CLAUDE.md ] && echo "⚠️  CLAUDE.md（普通文件，非 symlink）" || echo "➖ CLAUDE.md 不存在")
[ -f AGENTS.md ] && echo "✅ AGENTS.md" || echo "➖ AGENTS.md 不存在"
[ -L .agents/skills ] && echo "✅ .agents/skills → $(readlink .agents/skills)" || echo "➖ .agents/skills 不存在"
[ -d .claude/hooks ] && echo "⚠️  .claude/hooks/（旧版 project hooks，可清理）" || echo "✅ 无 project hooks（已迁移到 \$HOME）"
```

## 输出格式

将上面的检查结果整理为表格：

```
📋 插件配置状态检查

$HOME 级：
  Plugins:     ✅ spec / ✅ sync / ✅ git / ✅ quality
  Marketplace: ✅ taptap-plugins
  Versions:    ✅ taptap-plugins (marketplace vX.Y.Z) — git vA.B.C / sync vD.E.F / ...
  Hooks:       ✅ 10/10 scripts（symlink，版本一致）
  Symlinks:
    ~/.claude/hooks/scripts/  ✅ N/N 全部有效 symlink
    ~/.agents/skills/         ✅ N/N 全部有效 symlink
  MCP:         ✅ context7 / ...

Repo 级：
  Settings:    ✅ .claude/settings.json
  AGENTS.md:   ✅ / CLAUDE.md: ✅ → AGENTS.md
  Skills:      ✅ .agents/skills → .claude/skills
  Hooks:       ✅ 无旧版 project hooks

问题：
  [列出所有 ❌ 和 ⚠️ 项，给出修复建议]
  - ❌ 项：给出具体修复命令
  - ⚠️ 项：说明风险和建议操作
  无问题则显示：✅ 所有配置正常！
```
