# >>> codex-statusline BEGIN >>>
# Codex statusline hooks for tmux + iTerm2
# Managed by sync plugin — do not edit manually

codex_status_state_key() {
  if [[ -n "${TMUX_PANE:-}" ]]; then
    print -r -- "$TMUX_PANE"
    return 0
  fi
  tty 2>/dev/null | tr '/ ' '__'
}

codex_status_active_file() {
  local state_key="${1:-}"
  [[ -n "$state_key" ]] || return 1
  print -r -- "$HOME/.cache/codex-status/${state_key}.active"
}

# 检测是否在 iTerm2 环境（包括 tmux -CC 模式）
_is_iterm2() {
  [[ "${TERM_PROGRAM:-}" == "iTerm.app" || -n "${ITERM_SESSION_ID:-}" ]] && return 0
  # tmux -CC 模式：client_control_mode=1 表示 iTerm2 tmux 集成
  [[ -n "${TMUX:-}" ]] && [[ "$(tmux display-message -p '#{client_control_mode}' 2>/dev/null)" == "1" ]] && return 0
  return 1
}

# iTerm2: 通过 SetUserVar 写入 status bar 数据（底部）
codex_iterm2_set_user_var() {
  _is_iterm2 || return 0
  local val="${1:-}"
  local encoded
  encoded="$(printf '%s' "$val" | base64 | tr -d '\r\n')"
  printf '\033]1337;SetUserVar=%s=%s\a' "codex_status" "$encoded" > /dev/tty 2>/dev/null
}

# 后台轮询更新 iTerm2 status bar（codex 运行期间）
codex_iterm2_watch() {
  _is_iterm2 || return 0
  local sk="$1" wd="$2" pid="$3"
  local active_file="$HOME/.cache/codex-status/${sk}.active"
  local tty_dev
  tty_dev="$(tty 2>/dev/null)" || return 0
  [[ -w "$tty_dev" ]] || return 0
  (
    (
      sleep 3
      while [[ -f "$active_file" ]]; do
        st="$("$HOME/.local/bin/codex-status" --plain --state-key="$sk" "$wd" "codex" "" "$pid" 2>/dev/null)" || true
        if [[ -n "$st" ]]; then
          encoded="$(printf '%s' "$st" | base64 | tr -d '\r\n')"
          printf '\033]1337;SetUserVar=%s=%s\a' "codex_status" "$encoded" > "$tty_dev" 2>/dev/null
        fi
        sleep 5
      done
      printf '\033]1337;SetUserVar=%s=%s\a' "codex_status" "" > "$tty_dev" 2>/dev/null
    ) &
  ) 2>/dev/null
}

# 首次自动配置 iTerm2 Status Bar（团队新机器零配置）
codex_iterm2_auto_setup() {
  _is_iterm2 || return 0
  local marker="$HOME/.cache/codex-status/.iterm2_configured"
  [[ -f "$marker" ]] && return 0
  mkdir -p "$HOME/.cache/codex-status"
  "$HOME/.local/bin/codex-status" --setup-iterm2 2>/dev/null && touch "$marker"
}

# tmux 普通模式（非 -CC）的 status-left
codex_tmux_apply_status() {
  [[ -n "$TMUX" ]] || return 0
  # tmux -CC 模式下不设 status-left（用 iTerm2 Status Bar 代替）
  _is_iterm2 && return 0
  command -v tmux >/dev/null 2>&1 || return 0
  tmux set -g status-left '#[fg=#1f2335,bg=#7aa2f7,bold] TMUX #[default] #(~/.local/bin/codex-status --state-key="#{pane_id}" "#{pane_current_path}" "#{pane_current_command}" "#{pane_title}" "#{pane_pid}")' >/dev/null 2>&1
  tmux set -g window-status-format '' >/dev/null 2>&1
  tmux set -g window-status-current-format '' >/dev/null 2>&1
  tmux set -g status-right '' >/dev/null 2>&1
}

codex_status_cleanup() {
  local state_key
  state_key="$(codex_status_state_key)"
  [[ -n "$state_key" ]] || return 0
  "$HOME/.local/bin/codex-status" --clear-active="$state_key" >/dev/null 2>&1 || true
  codex_iterm2_set_user_var ""
}

autoload -Uz add-zsh-hook
add-zsh-hook precmd codex_status_cleanup

codex_status_preexec() {
  local cmd="${1-}"
  [[ -n "$cmd" ]] || return 0
  case "$cmd" in
    codex|codex\ * )
      local state_key
      state_key="$(codex_status_state_key)"
      [[ -n "$state_key" ]] || return 0
      "$HOME/.local/bin/codex-status" --set-active="$state_key" "$PWD" >/dev/null 2>&1 || true
      codex_tmux_apply_status
      codex_iterm2_watch "$state_key" "$PWD" "$$"
      ;;
  esac
}
add-zsh-hook preexec codex_status_preexec

codex_tmux_apply_status
codex_iterm2_auto_setup
# <<< codex-statusline END <<<
