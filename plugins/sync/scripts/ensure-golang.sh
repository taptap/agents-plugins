#!/bin/bash
# ensure-golang.sh - 检测并安装 golang 和 mcp-grafana (macOS/Linux)
# 此脚本用于确保 mcp-grafana 运行环境就绪
# 
# 安装目录：
#   - Golang: $HOME/go-sdk/current (符号链接指向实际版本)
#   - mcp-grafana: $HOME/go/bin/mcp-grafana
#
# 使用方式：
#   bash ensure-golang.sh           # 只安装，不打印详细日志
#   bash ensure-golang.sh --verbose # 打印详细日志

set -e

# ========== 配置 ==========

GO_VERSION="1.25.6"  # 可以根据需要更新版本
GO_SDK_DIR="$HOME/go-sdk"
GO_BIN_DIR="$HOME/go/bin"
MCP_GRAFANA_REPO="github.com/grafana/mcp-grafana/cmd/mcp-grafana@latest"

# 日志配置
LOG_DIR="$HOME/.claude/plugins/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/ensure-golang-$(date +%Y-%m-%d).log"

# 详细模式
VERBOSE=false
if [[ "$1" == "--verbose" ]] || [[ "$1" == "-v" ]]; then
    VERBOSE=true
fi

# ========== 颜色定义 ==========

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ========== 日志函数 ==========

log_to_file() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

log_info() {
    local msg="[INFO] $1"
    echo -e "${GREEN}$msg${NC}"
    log_to_file "$msg"
}

log_warn() {
    local msg="[WARN] $1"
    echo -e "${YELLOW}$msg${NC}"
    log_to_file "$msg"
}

log_error() {
    local msg="[ERROR] $1"
    echo -e "${RED}$msg${NC}"
    log_to_file "$msg"
}

log_step() {
    local msg="[STEP] $1"
    echo -e "${BLUE}$msg${NC}"
    log_to_file "$msg"
}

log_detail() {
    if [[ "$VERBOSE" == "true" ]]; then
        local msg="  → $1"
        echo -e "${CYAN}$msg${NC}"
    fi
    log_to_file "[DETAIL] $1"
}

log_success() {
    local msg="✅ $1"
    echo -e "${GREEN}$msg${NC}"
    log_to_file "[SUCCESS] $1"
}

# ========== 辅助函数 ==========

check_command() {
    command -v "$1" &> /dev/null
}

detect_os() {
    local os
    os=$(uname -s | tr '[:upper:]' '[:lower:]')
    case "$os" in
        darwin) echo "darwin" ;;
        linux) echo "linux" ;;
        *) 
            log_error "不支持的操作系统: $os"
            exit 1
            ;;
    esac
}

detect_arch() {
    local arch
    arch=$(uname -m)
    case "$arch" in
        x86_64) echo "amd64" ;;
        amd64) echo "amd64" ;;
        arm64) echo "arm64" ;;
        aarch64) echo "arm64" ;;
        *)
            log_error "不支持的架构: $arch"
            exit 1
            ;;
    esac
}

detect_shell_rc() {
    # 检测当前 shell 并返回对应的 rc 文件
    local shell_name
    shell_name=$(basename "$SHELL")
    case "$shell_name" in
        zsh) echo "$HOME/.zshrc" ;;
        bash) echo "$HOME/.bashrc" ;;
        *)
            # 默认使用 .profile
            echo "$HOME/.profile"
            ;;
    esac
}

# ========== PATH 配置 ==========

configure_path() {
    local rc_file
    rc_file=$(detect_shell_rc)
    local path_export='export PATH="$HOME/go-sdk/current/bin:$HOME/go/bin:$PATH"'
    local marker="# Go SDK (added by ensure-golang.sh)"
    
    log_step "配置 PATH 环境变量"
    log_detail "Shell 配置文件: $rc_file"
    
    # 检查是否已配置
    if grep -q "go-sdk/current/bin" "$rc_file" 2>/dev/null; then
        log_info "PATH 已配置，跳过写入"
        log_detail "已存在配置: $(grep 'go-sdk/current/bin' "$rc_file")"
    else
        log_detail "添加 PATH 配置到 $rc_file"
        echo "" >> "$rc_file"
        echo "$marker" >> "$rc_file"
        echo "$path_export" >> "$rc_file"
        log_success "PATH 配置已写入 $rc_file"
    fi
    
    # 当前会话立即生效
    export PATH="$HOME/go-sdk/current/bin:$HOME/go/bin:$PATH"
    log_detail "当前会话 PATH 已更新"
}

# ========== Golang 安装 ==========

install_golang() {
    local os arch
    os=$(detect_os)
    arch=$(detect_arch)
    local go_tarball="go${GO_VERSION}.${os}-${arch}.tar.gz"
    local download_url="https://go.dev/dl/${go_tarball}"
    local install_dir="$GO_SDK_DIR/go${GO_VERSION}"
    local current_link="$GO_SDK_DIR/current"
    
    log_step "安装 Golang $GO_VERSION"
    log_detail "操作系统: $os"
    log_detail "架构: $arch"
    log_detail "下载地址: $download_url"
    log_detail "安装目录: $install_dir"
    
    # 创建目录
    mkdir -p "$GO_SDK_DIR"
    log_detail "创建目录: $GO_SDK_DIR"
    
    # 下载
    log_info "正在下载 Golang $GO_VERSION..."
    log_detail "curl -fsSL $download_url -o /tmp/$go_tarball"
    
    if ! curl -fsSL "$download_url" -o "/tmp/$go_tarball"; then
        log_error "下载失败: $download_url"
        log_error "请检查网络连接或尝试手动下载"
        exit 1
    fi
    
    log_detail "下载完成: /tmp/$go_tarball"
    log_detail "文件大小: $(ls -lh /tmp/$go_tarball | awk '{print $5}')"
    
    # 解压
    log_info "正在解压..."
    log_detail "tar -xzf /tmp/$go_tarball -C $GO_SDK_DIR"
    
    # 如果目标目录已存在，先删除
    if [[ -d "$install_dir" ]]; then
        log_detail "删除旧版本目录: $install_dir"
        rm -rf "$install_dir"
    fi
    
    tar -xzf "/tmp/$go_tarball" -C "$GO_SDK_DIR"
    
    # 重命名为带版本号的目录
    if [[ -d "$GO_SDK_DIR/go" ]]; then
        mv "$GO_SDK_DIR/go" "$install_dir"
        log_detail "重命名: $GO_SDK_DIR/go -> $install_dir"
    fi
    
    # 创建符号链接
    log_detail "创建符号链接: $current_link -> go${GO_VERSION}"
    rm -f "$current_link"
    ln -s "go${GO_VERSION}" "$current_link"
    
    # 清理临时文件
    rm -f "/tmp/$go_tarball"
    log_detail "清理临时文件: /tmp/$go_tarball"
    
    # 配置 PATH
    configure_path
    
    # 验证安装
    log_info "验证 Golang 安装..."
    local go_version_output
    go_version_output=$("$current_link/bin/go" version 2>&1)
    log_success "Golang 安装成功: $go_version_output"
    
    return 0
}

# ========== mcp-grafana 安装 ==========

install_mcp_grafana() {
    log_step "安装 mcp-grafana"
    log_detail "安装源: $MCP_GRAFANA_REPO"
    log_detail "安装目录: $GO_BIN_DIR"
    
    # 确保 go 命令可用
    if ! check_command go; then
        log_error "go 命令不可用，请先安装 Golang"
        exit 1
    fi
    
    log_detail "Go 版本: $(go version)"
    
    # 创建目录
    mkdir -p "$GO_BIN_DIR"
    
    # 执行安装
    log_info "正在安装 mcp-grafana (可能需要几分钟)..."
    log_detail "GOBIN=$GO_BIN_DIR go install $MCP_GRAFANA_REPO"
    
    if GOBIN="$GO_BIN_DIR" go install "$MCP_GRAFANA_REPO" 2>&1 | tee -a "$LOG_FILE"; then
        log_success "mcp-grafana 安装成功"
    else
        log_error "mcp-grafana 安装失败"
        log_error "请查看日志文件: $LOG_FILE"
        exit 1
    fi
    
    # 验证安装
    if [[ -f "$GO_BIN_DIR/mcp-grafana" ]]; then
        log_detail "二进制文件: $GO_BIN_DIR/mcp-grafana"
        log_detail "文件大小: $(ls -lh "$GO_BIN_DIR/mcp-grafana" | awk '{print $5}')"
        
        # 尝试获取版本
        local version_output
        version_output=$("$GO_BIN_DIR/mcp-grafana" --version 2>&1 || echo "版本信息不可用")
        log_detail "版本信息: $version_output"
    else
        log_error "安装后未找到 mcp-grafana 二进制文件"
        exit 1
    fi
    
    return 0
}

# ========== 主逻辑 ==========

main() {
    echo ""
    echo "=========================================="
    echo "  Golang & mcp-grafana 环境检测与安装"
    echo "=========================================="
    echo ""
    
    log_to_file "===== 开始执行 $(date '+%Y-%m-%d %H:%M:%S') ====="
    log_detail "日志文件: $LOG_FILE"
    log_detail "详细模式: $VERBOSE"
    
    local need_go_install=false
    local need_mcp_install=false
    
    # ===== 检查 Golang =====
    log_step "检查 Golang 环境"
    
    if check_command go; then
        local go_version
        go_version=$(go version 2>&1)
        log_success "Golang 已安装: $go_version"
        log_detail "Go 路径: $(which go)"
    else
        # 检查是否已安装但未在 PATH 中
        if [[ -x "$GO_SDK_DIR/current/bin/go" ]]; then
            log_warn "Golang 已安装但不在 PATH 中"
            configure_path
            log_success "PATH 已配置，Golang 可用"
        else
            log_warn "Golang 未安装"
            need_go_install=true
        fi
    fi
    
    # ===== 安装 Golang（如果需要）=====
    if [[ "$need_go_install" == "true" ]]; then
        install_golang
    fi
    
    echo ""
    
    # ===== 检查 mcp-grafana =====
    log_step "检查 mcp-grafana"
    
    if check_command mcp-grafana; then
        log_success "mcp-grafana 已安装"
        log_detail "路径: $(which mcp-grafana)"
    else
        # 检查是否已安装但未在 PATH 中
        if [[ -x "$GO_BIN_DIR/mcp-grafana" ]]; then
            log_warn "mcp-grafana 已安装但不在 PATH 中"
            configure_path
            log_success "PATH 已配置，mcp-grafana 可用"
        else
            log_warn "mcp-grafana 未安装"
            need_mcp_install=true
        fi
    fi
    
    # ===== 安装 mcp-grafana（如果需要）=====
    if [[ "$need_mcp_install" == "true" ]]; then
        install_mcp_grafana
    fi
    
    echo ""
    
    # ===== 最终状态报告 =====
    echo "=========================================="
    echo "  环境状态报告"
    echo "=========================================="
    echo ""
    
    # Golang 状态
    if check_command go; then
        echo -e "${GREEN}✅ Golang${NC}"
        echo "   版本: $(go version | awk '{print $3}')"
        echo "   路径: $(which go)"
    else
        echo -e "${RED}❌ Golang 不可用${NC}"
    fi
    
    echo ""
    
    # mcp-grafana 状态
    if check_command mcp-grafana || [[ -x "$GO_BIN_DIR/mcp-grafana" ]]; then
        echo -e "${GREEN}✅ mcp-grafana${NC}"
        local mcp_path
        mcp_path=$(which mcp-grafana 2>/dev/null || echo "$GO_BIN_DIR/mcp-grafana")
        echo "   路径: $mcp_path"
    else
        echo -e "${RED}❌ mcp-grafana 不可用${NC}"
    fi
    
    echo ""
    
    # PATH 状态
    local rc_file
    rc_file=$(detect_shell_rc)
    if grep -q "go-sdk/current/bin" "$rc_file" 2>/dev/null; then
        echo -e "${GREEN}✅ PATH 已配置${NC}"
        echo "   配置文件: $rc_file"
    else
        echo -e "${YELLOW}⚠️  PATH 未持久化${NC}"
        echo "   请手动添加到 $rc_file:"
        echo '   export PATH="$HOME/go-sdk/current/bin:$HOME/go/bin:$PATH"'
    fi
    
    echo ""
    echo "📋 日志文件: $LOG_FILE"
    echo ""
    
    log_to_file "===== 执行完成 $(date '+%Y-%m-%d %H:%M:%S') ====="
    
    return 0
}

# ========== 执行 ==========

main "$@"
