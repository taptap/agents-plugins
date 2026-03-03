#!/bin/bash
# ensure-lsp.sh - SessionStart hook: 静默检测并安装缺失的 LSP binary
# 读取项目 .claude/settings.json 中启用的 LSP 插件，自动安装对应 binary
# 后台执行，不阻塞 session 启动

set -e

# 日志配置
LOG_DIR="$HOME/.claude/plugins/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/ensure-lsp-$(date +%Y-%m-%d).log"
exec >> "$LOG_FILE" 2>&1
echo ""
echo "===== $(date '+%Y-%m-%d %H:%M:%S') ====="

has_command() {
  command -v "$1" >/dev/null 2>&1
}

SETTINGS_FILE=".claude/settings.json"

if [ ! -f "$SETTINGS_FILE" ]; then
  echo "⏭️  $SETTINGS_FILE 不存在，跳过 LSP 检查"
  exit 0
fi

# 提取启用的 LSP 插件列表
extract_lsp_plugins() {
  local file="$1"
  if has_command jq; then
    jq -r '.enabledPlugins // {} | to_entries[] | select(.key | endswith("-lsp@claude-plugins-official")) | select(.value == true) | .key' "$file" 2>/dev/null
  elif has_command python3; then
    python3 -c "
import json, sys
with open('$file') as f:
    d = json.load(f)
for k, v in d.get('enabledPlugins', {}).items():
    if k.endswith('-lsp@claude-plugins-official') and v is True:
        print(k)
" 2>/dev/null
  else
    echo ""
  fi
}

# LSP 插件 → binary 名 + 安装命令 映射
install_binary_for_plugin() {
  local plugin="$1"
  case "$plugin" in
    gopls-lsp@claude-plugins-official)
      if ! has_command gopls; then
        echo "📦 安装 gopls..."
        if has_command go; then
          go install golang.org/x/tools/gopls@latest 2>&1 && echo "✅ gopls 安装成功" || echo "⚠️  gopls 安装失败"
        else
          echo "⚠️  go 未安装，无法安装 gopls"
        fi
      else
        echo "✅ gopls 已存在"
      fi
      ;;
    typescript-lsp@claude-plugins-official)
      if ! has_command typescript-language-server; then
        echo "📦 安装 typescript-language-server..."
        if has_command npm; then
          npm install -g typescript-language-server typescript 2>&1 && echo "✅ typescript-language-server 安装成功" || echo "⚠️  安装失败"
        else
          echo "⚠️  npm 未安装，无法安装 typescript-language-server"
        fi
      else
        echo "✅ typescript-language-server 已存在"
      fi
      ;;
    pyright-lsp@claude-plugins-official)
      if ! has_command pyright-langserver; then
        echo "📦 安装 pyright..."
        if has_command npm; then
          npm install -g pyright 2>&1 && echo "✅ pyright 安装成功" || echo "⚠️  安装失败"
        elif has_command pip; then
          pip install pyright 2>&1 && echo "✅ pyright 安装成功" || echo "⚠️  安装失败"
        elif has_command pip3; then
          pip3 install pyright 2>&1 && echo "✅ pyright 安装成功" || echo "⚠️  安装失败"
        else
          echo "⚠️  npm/pip 均未安装，无法安装 pyright"
        fi
      else
        echo "✅ pyright-langserver 已存在"
      fi
      ;;
    rust-analyzer-lsp@claude-plugins-official)
      if ! has_command rust-analyzer; then
        echo "📦 安装 rust-analyzer..."
        if has_command rustup; then
          rustup component add rust-analyzer 2>&1 && echo "✅ rust-analyzer 安装成功" || echo "⚠️  安装失败"
        else
          echo "⚠️  rustup 未安装，无法安装 rust-analyzer"
        fi
      else
        echo "✅ rust-analyzer 已存在"
      fi
      ;;
    jdtls-lsp@claude-plugins-official)
      if ! has_command jdtls; then
        echo "⚠️  jdtls 未安装，请参考 https://github.com/eclipse-jdtls/eclipse.jdt.ls 手动安装"
      else
        echo "✅ jdtls 已存在"
      fi
      ;;
    kotlin-lsp@claude-plugins-official)
      if ! has_command kotlin-language-server; then
        echo "📦 安装 kotlin-language-server..."
        if has_command brew; then
          brew install kotlin-language-server 2>&1 && echo "✅ kotlin-language-server 安装成功" || echo "⚠️  安装失败"
        else
          echo "⚠️  brew 未安装，无法自动安装 kotlin-language-server"
        fi
      else
        echo "✅ kotlin-language-server 已存在"
      fi
      ;;
    swift-lsp@claude-plugins-official)
      if ! has_command sourcekit-lsp; then
        echo "⚠️  sourcekit-lsp 未安装，请安装 Xcode"
      else
        echo "✅ sourcekit-lsp 已存在"
      fi
      ;;
    clangd-lsp@claude-plugins-official)
      if ! has_command clangd; then
        echo "📦 安装 clangd..."
        if has_command brew; then
          brew install llvm 2>&1 && echo "✅ clangd 安装成功" || echo "⚠️  安装失败"
        else
          echo "⚠️  brew 未安装，无法自动安装 clangd"
        fi
      else
        echo "✅ clangd 已存在"
      fi
      ;;
    csharp-lsp@claude-plugins-official)
      if ! has_command csharp-ls; then
        echo "📦 安装 csharp-ls..."
        if has_command dotnet; then
          dotnet tool install -g csharp-ls 2>&1 && echo "✅ csharp-ls 安装成功" || echo "⚠️  安装失败"
        else
          echo "⚠️  dotnet 未安装，无法安装 csharp-ls"
        fi
      else
        echo "✅ csharp-ls 已存在"
      fi
      ;;
    php-lsp@claude-plugins-official)
      if ! has_command intelephense; then
        echo "📦 安装 intelephense..."
        if has_command npm; then
          npm install -g intelephense 2>&1 && echo "✅ intelephense 安装成功" || echo "⚠️  安装失败"
        else
          echo "⚠️  npm 未安装，无法安装 intelephense"
        fi
      else
        echo "✅ intelephense 已存在"
      fi
      ;;
    *)
      echo "⏭️  未知 LSP 插件: $plugin，跳过"
      ;;
  esac
}

# 主逻辑
LSP_PLUGINS=$(extract_lsp_plugins "$SETTINGS_FILE")

if [ -z "$LSP_PLUGINS" ]; then
  echo "⏭️  未检测到启用的 LSP 插件，跳过"
  exit 0
fi

echo "检测到启用的 LSP 插件:"
echo "$LSP_PLUGINS" | while read -r plugin; do
  [ -n "$plugin" ] && echo "  - $plugin"
done

echo ""
echo "$LSP_PLUGINS" | while read -r plugin; do
  [ -n "$plugin" ] && install_binary_for_plugin "$plugin"
done

echo ""
echo "===== LSP binary 检查完成 ====="
exit 0
