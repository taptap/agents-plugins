#!/bin/bash
# detect-lsp.sh - 检测项目编程语言，输出应启用的 LSP plugin ID
# sync:basic Phase 0 调用，在项目根目录执行
# 输出格式: DETECTED_LSP=gopls-lsp@claude-plugins-official,typescript-lsp@claude-plugins-official
# 如果无匹配: DETECTED_LSP=none

PROJECT_ROOT="${1:-.}"
DETECTED=()

# Go: go.mod 或多个 .go 文件
if [ -f "$PROJECT_ROOT/go.mod" ] || [ "$(find "$PROJECT_ROOT" -maxdepth 2 -name '*.go' -type f 2>/dev/null | head -1)" ]; then
  DETECTED+=("gopls-lsp@claude-plugins-official")
fi

# TypeScript/JavaScript: tsconfig.json 或 package.json
if [ -f "$PROJECT_ROOT/tsconfig.json" ] || [ -f "$PROJECT_ROOT/package.json" ]; then
  DETECTED+=("typescript-lsp@claude-plugins-official")
fi

# Python: pyproject.toml / requirements.txt / setup.py
if [ -f "$PROJECT_ROOT/pyproject.toml" ] || [ -f "$PROJECT_ROOT/requirements.txt" ] || [ -f "$PROJECT_ROOT/setup.py" ]; then
  DETECTED+=("pyright-lsp@claude-plugins-official")
fi

# Rust: Cargo.toml
if [ -f "$PROJECT_ROOT/Cargo.toml" ]; then
  DETECTED+=("rust-analyzer-lsp@claude-plugins-official")
fi

# Java: pom.xml / build.gradle / build.gradle.kts
if [ -f "$PROJECT_ROOT/pom.xml" ] || [ -f "$PROJECT_ROOT/build.gradle" ] || [ -f "$PROJECT_ROOT/build.gradle.kts" ]; then
  DETECTED+=("jdtls-lsp@claude-plugins-official")
fi

# Kotlin: build.gradle(.kts) + *.kt 文件
if { [ -f "$PROJECT_ROOT/build.gradle" ] || [ -f "$PROJECT_ROOT/build.gradle.kts" ]; } && \
   [ "$(find "$PROJECT_ROOT" -maxdepth 3 -name '*.kt' -type f 2>/dev/null | head -1)" ]; then
  DETECTED+=("kotlin-lsp@claude-plugins-official")
fi

# Swift: Package.swift / *.xcodeproj
if [ -f "$PROJECT_ROOT/Package.swift" ] || [ "$(find "$PROJECT_ROOT" -maxdepth 1 -name '*.xcodeproj' -type d 2>/dev/null | head -1)" ]; then
  DETECTED+=("swift-lsp@claude-plugins-official")
fi

# C/C++: CMakeLists.txt / Makefile + *.c/*.cpp
if { [ -f "$PROJECT_ROOT/CMakeLists.txt" ] || [ -f "$PROJECT_ROOT/Makefile" ]; } && \
   [ "$(find "$PROJECT_ROOT" -maxdepth 3 \( -name '*.c' -o -name '*.cpp' -o -name '*.h' \) -type f 2>/dev/null | head -1)" ]; then
  DETECTED+=("clangd-lsp@claude-plugins-official")
fi

# C#: *.csproj / *.sln
if [ "$(find "$PROJECT_ROOT" -maxdepth 2 \( -name '*.csproj' -o -name '*.sln' \) -type f 2>/dev/null | head -1)" ]; then
  DETECTED+=("csharp-lsp@claude-plugins-official")
fi

# PHP: composer.json
if [ -f "$PROJECT_ROOT/composer.json" ]; then
  DETECTED+=("php-lsp@claude-plugins-official")
fi

# 输出结果
if [ ${#DETECTED[@]} -eq 0 ]; then
  echo "DETECTED_LSP=none"
else
  IFS=','
  echo "DETECTED_LSP=${DETECTED[*]}"
fi
