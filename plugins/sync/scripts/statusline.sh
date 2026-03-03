#!/bin/bash
# statusline.sh - Claude Code 状态栏脚本
# 布局：模型名 | 仓库+分支+worktree | Context 进度 | 版本号

set -e

# 颜色定义
RESET='\033[0m'
BOLD_MAGENTA='\033[1;35m'  # 模型名（亮紫色）
CYAN='\033[0;36m'          # 项目名、worktree
BOLD_BLUE='\033[1;34m'     # git:( and )
RED='\033[0;31m'           # 分支名
GRAY='\033[0;90m'          # 分隔符、版本号

# 进度条颜色
BAR_GREEN='\033[0;32m'
BAR_YELLOW='\033[1;33m'
BAR_RED='\033[0;31m'

# 阈值配置
CONTEXT_GREEN_MAX=60
CONTEXT_YELLOW_MAX=80

# 获取进度条颜色
get_bar_color() {
    local pct="$1"
    [ "$pct" -lt "$CONTEXT_GREEN_MAX" ] && echo "$BAR_GREEN" && return
    [ "$pct" -lt "$CONTEXT_YELLOW_MAX" ] && echo "$BAR_YELLOW" && return
    echo "$BAR_RED"
}

# 生成进度条（block style）
make_bar() {
    local pct="$1" width=10
    local filled=$((pct * width / 100))
    local empty=$((width - filled))
    local bar=""
    for ((i=0; i<filled; i++)); do bar+="█"; done
    for ((i=0; i<empty; i++)); do bar+="░"; done
    echo "$bar"
}

# 检测 worktree
get_worktree() {
    local cwd="$1"
    [ -f "$cwd/.git" ] || return 1
    local git_dir
    git_dir=$(git -C "$cwd" rev-parse --git-dir 2>/dev/null)
    [[ "$git_dir" == *"/worktrees/"* ]] && basename "$git_dir" || return 1
}

# 主逻辑
main() {
    local input
    input=$(cat)

    # 解析 JSON
    local model cwd project_dir
    model=$(echo "$input" | jq -r '.model.display_name // "Unknown"')
    cwd=$(echo "$input" | jq -r '.workspace.current_dir // "."')
    project_dir=$(echo "$input" | jq -r '.workspace.project_dir // "."')
    local pct_raw version
    pct_raw=$(echo "$input" | jq -r '.context_window.used_percentage // "null"')
    version=$(echo "$input" | jq -r '.version // "unknown"')
    local pct=""
    if [[ "$pct_raw" == "null" || -z "$pct_raw" ]]; then
        pct="--"
    else
        pct=$(echo "$pct_raw" | cut -d'.' -f1)
        [[ "$pct" =~ ^[0-9]+$ ]] || pct="--"
    fi

    # 提取信息
    local project branch
    project=$(basename "$project_dir")
    branch=$(git -C "$cwd" branch --show-current 2>/dev/null)
    local worktree
    worktree=$(get_worktree "$cwd" 2>/dev/null || echo "")
    local bar_color="$GRAY"
    local bar="░░░░░░░░░░"
    if [[ "$pct" != "--" ]]; then
        bar_color=$(get_bar_color "$pct")
        bar=$(make_bar "$pct")
    fi

    # 构建输出：模型名 | 仓库+分支+worktree | 进度条 | 版本
    local out="${BOLD_MAGENTA}[${model}]${RESET}"
    out+=" ${GRAY}|${RESET}"
    out+=" ${CYAN}${project}${RESET}"
    [ -n "$branch" ] && out+=" ${BOLD_BLUE}git:(${RED}${branch}${BOLD_BLUE})${RESET}"
    [ -n "$worktree" ] && out+=" ${CYAN}wt:${worktree}${RESET}"
    out+=" ${GRAY}|${RESET}"
    out+=" ${bar_color}${bar}${RESET} ${pct}%"
    out+=" ${GRAY}|${RESET}"
    out+=" ${GRAY}v${version}${RESET}"

    echo -e "$out"

    # Ralph loop 状态（第二行，仅循环活跃时显示）
    local ralph_file="${cwd}/.claude/ralph-loop.local.md"
    if [ -f "$ralph_file" ]; then
        local r_iter r_max r_promise r_prompt
        r_iter=$(sed -n 's/^iteration: *//p' "$ralph_file" 2>/dev/null)
        r_max=$(sed -n 's/^max_iterations: *//p' "$ralph_file" 2>/dev/null)
        r_promise=$(sed -n 's/^completion_promise: *//p' "$ralph_file" 2>/dev/null | sed 's/^"\(.*\)"$/\1/')
        r_prompt=$(awk '/^---$/{i++; next} i>=2{print; exit}' "$ralph_file" 2>/dev/null)

        if [ -n "$r_iter" ]; then
            local iter_str
            if [ "$r_max" -gt 0 ] 2>/dev/null; then
                iter_str="${r_iter}/${r_max}"
            else
                iter_str="${r_iter}"
            fi

            local ralph_line="${BAR_YELLOW}🔄 Ralph ${iter_str}${RESET}"
            [ -n "$r_promise" ] && [ "$r_promise" != "null" ] && ralph_line+=" ${GRAY}promise:${r_promise}${RESET}"
            [ -n "$r_prompt" ] && ralph_line+=" ${GRAY}| ${r_prompt:0:40}${RESET}"

            echo -e "$ralph_line"
        fi
    fi
}

main
