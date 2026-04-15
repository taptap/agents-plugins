# Changelog

## 0.1.33 — Add metersphere-sync, feedback skill, and Urhox binary analysis to test plugin

### Test Plugin (0.0.3)

- Added metersphere-sync skill for test plan management and case import with hierarchical module support
- Added qa-workflow orchestrator skill for end-to-end QA pipeline execution
- Added feedback skill: analyze Slack #taptap-feedback channel user feedback, classify issues, and create Feishu Bug tickets
- Added feedback skill knowledge base (10 reference docs: TapSDK, 实名, 下载安装, 评分, 配置, 内容发布, 注册登录, 青少年, 缺陷提交规范, 商店线产品分工)
- Added feedback skill Feishu API script for creating and updating Bug work items
- Added Urhox binary diff scope filtering to change-analysis phase 2.3
- Added Urhox binary impact analysis in change-analysis phase 3A
- Added test-case-generation sufficiency gate and iterative re-entry
- Added unified .env-based config for all Python scripts via python-dotenv
- Added requirement-clarification native AskUserQuestion tool calls
- Added phase execution guarantees and output validation for all multi-phase skills

### Marketplace

- Bumped version from 0.1.32 to 0.1.33
- Updated test plugin to version 0.0.3

## 0.1.32 — Add Codex plugin support and migrate marketplace repo name

### Sync Plugin (0.1.27)

- Added Codex plugin support with `.codex-plugin/` directory and manifest
- Added `codex-plugins-config` agent for configuring Codex plugins via standalone clone
- Added `ensure-codex-plugins.sh` and `update-codex-plugins.sh` scripts for Codex plugin auto-update
- Updated `/sync:hooks` command to include Codex hooks setup step (`.codex/hooks/` sync)
- Updated `/sync:basic` command to add Codex plugin standalone clone as Phase 1 step
- Updated `/sync:basic` and `/sync:lsp` project settings handling to migrate `taptap/claude-plugins-marketplace` to `taptap/agents-plugins` without overwriting custom repos
- Updated sync commands to prefer `${CLAUDE_PLUGIN_ROOT}` before installed marketplace/cache paths, so inline `--plugin-dir` development sessions resolve the current plugin source correctly
- Updated `ensure-plugins.sh` to migrate old marketplace repo name with robust jq-based detection
- Updated `set-auto-update-plugins.sh` to handle old repo name migration and add JSON validity check before parsing
- Updated `ensure-cli-tools.sh` to add shell-aware token setup hints (zsh/bash/fish)
- Simplified `hooks-config` agent to non-destructive project hooks check only; removed `permissionMode: acceptEdits`

### Git Plugin (0.1.15)

- Added `.codex-plugin/` manifest for Codex CLI compatibility

### Spec Plugin (0.1.6)

- Added `.codex-plugin/` manifest for Codex CLI compatibility

### Test Plugin (0.0.2)

- Added `.codex-plugin/` manifest for Codex CLI compatibility

### Marketplace

- Bumped version from 0.1.31 to 0.1.32
- Updated sync plugin to version 0.1.27
- Updated git plugin to version 0.1.15
- Updated spec plugin to version 0.1.6
- Updated test plugin to version 0.0.2

## 0.1.31 — Simplify sync workflow and remove Cursor-side distribution

### Sync Plugin (0.1.26)

- Removed Cursor-specific commands, templates, and snippet mirroring assets from the sync plugin
- Changed `/sync:basic` and related MCP commands to focus on Claude Code environment setup only
- Removed the `ensure-codex-skills.sh` SessionStart hook and stopped sync from maintaining `~/.agents/skills` for Codex
- Removed deprecated `sequential-thinking` MCP cleanup logic from mcp command, agent, and scripts
- Updated sync documentation, status checks, and helper skills to match the reduced Claude Code scope
- Cleaned up repo-local optional hook guidance after removing the bundled snippet sync pre-commit flow
- Added BASE subdirectory variable mapping documentation to `/sync:basic` command

### Marketplace

- Bumped version from 0.1.30 to 0.1.31
- Updated sync plugin to version 0.1.26

## 0.1.30 — Add QA workflow plugin with multi-agent test skills

### Test Plugin (0.0.1)

- Added QA workflow plugin with full test lifecycle skills
- Added test-case-generation skill with multi-agent review pipeline (dual reviewer + redundancy audit)
- Added unit-test-design skill with business-scenario-driven principles and language-specific methods (Go/Java/Kotlin/Python/Swift/TypeScript)
- Added integration-test-design skill with framework-specific methods
- Added verification-test-generation skill for code-level test generation with phase execution guarantees
- Added change-analysis skill with Android third-party interaction impact assessment
- Added requirement-clarification skill with structured Q&A cards and ask_question output format
- Added requirement-review skill with 12-dimension evaluation framework
- Added requirement-traceability skill with smoke-test mode, defect extraction, and P0 gate
- Added test-case-review skill with 4-dimension review protocol
- Added api-contract-validation skill with contract enforcement
- Added bug-fix-review and test-failure-analyzer skills
- Added ui-fidelity-check skill with Figma MCP tiered data fetching protocol
- Added shared-tools (fetch_feishu_doc.py, search_prs.py, search_mrs.py, gitlab_helper.py, github_helper.py, validate_contracts.py)
- Added output workspace convention for requirement-based artifact organization
- Added phase execution guarantees and output validation for all multi-phase skills

### Marketplace

- Bumped version from 0.1.29 to 0.1.30
- Added test plugin version 0.0.1
- Removed orphaned quality plugin entry (directory does not exist)

## 0.1.29 — Remove quality plugin, refine module-discovery scope, add feishu-bot-card skill

### Spec Plugin (0.1.5)

- Changed module-discovery skill from auto-execute to on-demand (only for repos that adopt the module-index workflow)

### Sync Plugin (0.1.25)

- Added feishu-bot-card skill for sending Feishu webhook card messages
- Removed quality plugin from enabled plugins list and added cleanup for retired plugins (quality, ralph)
- Removed Ralph loop status display from statusline
- Updated ensure-codex-skills.sh to only remove symlinks (not directories) for retired skills
- Updated ensure-plugins.sh to include skill-creator and clean retired plugins
- Fixed ensure-plugins.sh to also clean retired plugins from installed_plugins.json (prevents "plugin not found" errors after plugin removal)
- Added ensure-plugins.sh Step 3: auto-clean retired plugins from current project's settings.json and settings.local.json on SessionStart
- Fixed ensure-mcp.sh to skip context7 MCP config when context7 plugin is already installed (prevents duplicate MCP server conflict)

### Marketplace

- Removed quality plugin registration from marketplace
- Bumped version from 0.1.28 to 0.1.29
- Updated spec plugin to version 0.1.5
- Updated sync plugin to version 0.1.25

## 0.1.27 — Remove context7 from auto-install plugins

### Sync Plugin (0.1.23)

- Removed `context7@claude-plugins-official` from auto-install plugin list to avoid conflict with project-level `.mcp.json` context7 config

### Marketplace

- Bumped version from 0.1.26 to 0.1.27
- Updated sync plugin to version 0.1.23

## 0.1.26 — GitLab domain migration & Codex TUI statusline

### Git Plugin (0.1.13)

- Updated self-hosted GitLab domain from `git.gametaptap.com` to `git.tapsvc.com` across code-reviewing, git-remote-operations, and gitlab-operations docs

### Sync Plugin (0.1.22)

- Added Codex official TUI `status_line` sync to `~/.codex/config.toml` via `ensure-codex-statusline.sh`
- Updated codex-statusline agent and skill docs to include Codex TUI sync
- Updated self-hosted GitLab domain from `git.gametaptap.com` to `git.tapsvc.com` in git-cli-auth command

### Marketplace

- Bumped version from 0.1.25 to 0.1.26
- Updated git plugin to version 0.1.13
- Updated sync plugin to version 0.1.22

## 0.1.25 — Codex skills sync

### Sync Plugin (0.1.21)

- Added `ensure-codex-skills.sh` to sync plugin skills to `~/.agents/skills/` for Codex discovery
- Added manifest-based tracking (`~/.cache/codex-skills-sync/managed.txt`) to safely manage symlinks without touching user-created files
- Added migration logic to clean old hardlinks and symlinks from `~/.codex/skills/` and `~/.agents/skills/`
- Added `EXCLUDE_PLUGINS` and `EXCLUDE_SKILLS` config to skip unpublished plugins (e.g., ralph)
- Added marketplace filter (`INCLUDE_MARKETPLACE`) to only sync skills from our own marketplace
- Registered `ensure-codex-skills.sh` as SessionStart hook for automatic sync on session start

### Marketplace

- Bumped version from 0.1.24 to 0.1.25
- Updated sync plugin to version 0.1.21

## 0.1.24 — Codex statusline fixes

### Sync Plugin (0.1.20)

- Fixed context usage showing 100% by using `last_token_usage.input_tokens` instead of cumulative `total_token_usage.total_tokens`
- Fixed cross-instance context usage contamination by matching sessions via filename creation timestamp
- Fixed tmux normal mode statusline not showing due to `_is_iterm2` incorrectly returning true (inherited `TERM_PROGRAM`)
- Added `_is_tmux_cc()` to properly distinguish tmux -CC from normal tmux mode
- Fixed tmux -CC mode "Unrecognized command from tmux" error by wrapping SetUserVar with tmux passthrough
- Added `_iterm2_escape()` helper for automatic tmux passthrough wrapping
- Auto-configure `allow-passthrough on` in tmux.conf (prefers `.tmux.conf.local` for framework compatibility)
- Switched iTerm2 plist operations from direct file I/O to `defaults export/import` (cfprefsd) to prevent running iTerm2 from overwriting changes
- Added `cleanup_iterm2()` function for proper Status Bar removal
- Fixed zsh hooks update detection using shasum hash comparison instead of string equality
- Added `/clean-codex-statusline` skill for complete statusline cleanup

### Marketplace

- Bumped version from 0.1.23 to 0.1.24
- Updated sync plugin to version 0.1.20

## 0.1.23 — Codex compatibility

### Sync Plugin (0.1.19)

- Added codex-statusline skill with tmux and iTerm2 support (auto-detect terminal, display project/branch/model)
- Made Codex MCP configuration optional (`--with-codex` flag) in mcp-feishu and mcp-feishu-project skills to save Codex context window space
- Migrated hooks from project-level to $HOME-level (`~/.claude/hooks/`) for Codex $HOME workspace compatibility
- Added cleanup of legacy project-level hooks in hooks-config agent
- Removed sequential-thinking MCP from configuration and templates
- Added sequential-thinking cleanup step to mcp-config agent
- Simplified `/sync:mcp` command (context7 only)
- Added plugin-status skill for runtime plugin diagnostics
- Enhanced grafana-dashboard-design skill with expanded design specifications
- Enhanced mcp-feishu and mcp-feishu-project skills with improved configuration flow
- Expanded ensure-plugins.sh with additional plugin management logic

### Git Plugin (0.1.12)

- Added environment detection to auto-select review mode: Agent Team (Claude Code) or serial dual-perspective (Codex)
- Added Mode B: serial cross-validation review for Codex — calls Claude CLI for first pass, agent does second pass, then merges findings
- Added `.agents/skills/code-reviewing/` as fallback path for review checklist and rules ($HOME Codex compatibility)
- Refactored git-flow into three standalone skills: commit, commit-push, commit-push-pr

### Marketplace

- Added `.agents/` symlink and `AGENTS.md` for Codex workspace compatibility
- Fixed hooks.md frontmatter YAML indentation error
- Bumped version from 0.1.22 to 0.1.23
- Updated git plugin to version 0.1.12
- Updated sync plugin to version 0.1.19

## 0.1.21

### Git Plugin (0.1.10)

- Added project-level custom review rules support (review-rules.md with scope-based matching)
- Redesigned code review engine: Agent Team with debate phase (2 members review independently then cross-validate)
- Added review checklist loading with project customization support (shared with CI reviewer)
- Updated plugin description to reflect new review architecture

### Sync Plugin (0.1.17)

- Added review-rules template sync to skills-sync agent (copies review-rules.md if not exists)
- Added review-rules to `/sync:basic` output and override policy docs
- Added review-rules.md template to sync plugin skills directory

### Marketplace

- Bumped version from 0.1.20 to 0.1.21
- Updated git plugin to version 0.1.10
- Updated sync plugin to version 0.1.17
- Removed ralph plugin (still in development)

## 0.1.20

### Git Plugin (0.1.9)

- Added Pipeline Watch to commit-push command (monitors existing MR pipeline after push)
- Added Pipeline Watch foreground mode with MANDATORY marker to prevent AI skipping
- Added fix-conflict skill for automated branch merge conflict resolution
- Added auto-detection and assignment of claude reviewer when creating MR

### Sync Plugin (0.1.16)

- Added review-checklist sync to skills-sync agent (skip if already exists)
- Fixed Claude Skills override policy docs in basic.md (review-checklist preserves custom version)
- Fixed missing execute permissions on 4 hook scripts
- Added Pipeline Watch to Cursor git-commit-push template
- Added MANDATORY marker to pipeline watcher in Cursor git-commit-push-pr template

### Marketplace

- Bumped version from 0.1.19 to 0.1.20
- Updated git plugin to version 0.1.9
- Updated sync plugin to version 0.1.16

## 0.1.19

### Sync Plugin (0.1.15)

- Added `/sync:lsp` command (detect project language + install LSP binary + enable plugins, with --check and --install modes)
- Added LSP binary immediate installation to `/sync:basic` Phase 2.2 (no longer deferred to next session)
- Added LSP documentation to README (commands table, config file locations, new member scenario)
- Added code review step with `--skip-code-review` to Cursor template commands (git-commit-push, git-commit-push-pr)
- Fixed MR template agent overwriting existing project templates (merged check+copy into atomic bash command)
- Updated hooks-config agent to sync 9 scripts (added ensure-lsp-tool.sh, ensure-lsp.sh)
- Updated hooks.json to include LSP tool and LSP binary hooks in SessionStart chain
- Updated ensure-plugins.sh to include ralph plugin
- Updated statusline.sh and ensure-golang.sh improvements

### Git Plugin (0.1.8)

- Added automatic code review step (before pusu) to commit-push and commit-push-pr commands with Agent Team + Codex dual-engine
- Added `--skip-code-review` parameter to skip code review
- Added `code-reviewing` skill (MR review + local review, 5-dimension checklist)
- Added `git-remote-operations` skill (GitHub/GitLab platform auto-detection, PR/MR/Issue/Pipeline management)
- Added GitHub PR support to commit-push-pr (gh CLI alongside glab)
- Added Pipeline/CI monitoring after MR/PR creation (auto-poll + failure analysis + auto-fix for lint/test)
- Changed commit-push-pr to support both GitLab and GitHub platforms
- Updated git-flow snippets (branch creation, commit execution)

### Quality Plugin (0.0.4)

- Moved `code-reviewing` skill from quality plugin to git plugin (centralized review flow)
- Removed SKILL.md, confidence-scoring.md, review-dimensions.md from quality/skills/code-reviewing/

### Marketplace

- Bumped version from 0.1.18 to 0.1.19
- Updated sync plugin to version 0.1.15
- Updated git plugin to version 0.1.8
- Updated quality plugin to version 0.0.4

## 0.1.18

### Git Plugin (0.1.7)

- Fixed missing `allowed-tools` entries for `printenv`, `echo`, `grep` in commit/commit-push/commit-push-pr commands
- Fixed missing `head`, `python3`, `cat` entries in commit-push-pr command
- Changed `GIT_ALLOW_NO_TICKET` context from `echo "$VAR"` to `printenv` for proper permission handling

### Sync Plugin (0.1.14)

- Fixed missing `allowed-tools` entries across 10 command files (git-cli-auth, mcp, hooks, cursor, statusline, basic, mcp-grafana, mcp-feishu-project, and cursor-templates)
- Added missing `printenv`, `head`, `pwd`, `cp`, `ls`, `sort`, `tail`, `echo`, `wc`, `claude`, `bash`, `mv`, `tr`, `grep`, `cat` entries where needed
- Changed `GIT_ALLOW_NO_TICKET` context in cursor-templates from `echo "$VAR"` to `printenv`

### Quality Plugin (0.0.3)

- Fixed missing `allowed-tools` entries for `mkdir`, `echo`, `date` in review command

### Spec Plugin (0.1.4)

- Fixed missing `allowed-tools` entry for `pwd` in spec command

### Marketplace

- Bumped version from 0.1.17 to 0.1.18
- Updated git plugin to version 0.1.7
- Updated sync plugin to version 0.1.14
- Updated quality plugin to version 0.0.3
- Updated spec plugin to version 0.1.4

## 0.1.17

### Git Plugin (0.1.6)

- Added `GIT_ALLOW_NO_TICKET` environment variable support for per-repo no-ticket configuration
- Added env var context line to all three commands (commit, commit-push, commit-push-pr)
- Changed no-ticket behavior: AI is now strictly prohibited from auto-inferring or filling `#no-ticket`
- Changed section 0 in commit format spec to enforce explicit user selection via AskUserQuestion
- Changed step 3 in task ID extraction to conditionally show no-ticket option based on env var
- Changed docs/style/chore type examples from `#no-ticket` to `#TAP-xxxxx` to avoid implying AI auto-use
- Added step 0 (config check) to SKILL.md execution flow

### Sync Plugin (0.1.13)

- Mirrored Git Plugin no-ticket configuration changes to cursor-templates
- Added `GIT_ALLOW_NO_TICKET` env var context to Cursor command templates
- Updated cursor-templates git-flow.mdc with repo-level config section and no-ticket rules
- Changed cursor-templates snippets (02-extract-task-id.md, 03-commit-format.md) to match git plugin

### Marketplace

- Bumped version from 0.1.16 to 0.1.17
- Updated git plugin to version 0.1.6
- Updated sync plugin to version 0.1.13

## 0.1.16

### Sync Plugin (0.1.12)

- Refactored `/sync:basic` command to use parallel agent architecture (Phase 0 path resolution + 6 named subagents)
- Reduced command execution from ~550 lines to ~150 lines (Phase 0: ≤2 Bash calls)
- Added 4 new helper scripts: `ensure-mcp.sh`, `ensure-plugins.sh`, `ensure-statusline.sh`, `ensure-tool-search.sh`
- Added `agents/` directory with 6 specialized subagents for parallel execution
- Updated `/sync:hooks` command with improved error handling and path resolution
- Updated `/sync:mcp-feishu` command with enhanced configuration logic
- Updated `/sync:mcp-feishu-project` command with streamlined setup process
- Updated `/sync:mcp-grafana` command with better validation and error messages
- Updated hooks.json configuration structure
- Updated mcp-feishu and mcp-feishu-project skill definitions

### Marketplace

- Bumped version from 0.1.15 to 0.1.16
- Updated sync plugin to version 0.1.12

## 0.1.15

### Sync Plugin (0.1.11)

- Added `/sync:statusline` command for configuring Claude Code custom status line (project/branch/context/model/worktree)
- Added MCP lazy-loading configuration to `/sync:basic` (ENABLE_TOOL_SEARCH=auto:1)
- Added Stage 6 to `/sync:basic`: Status Line configuration (copy script + update settings.json)
- Added TapTap Plugins auto-enable to `/sync:basic` (spec/sync/git/quality)
- Changed MCP config (context7 + sequential-thinking) target from project-level (`.mcp.json` / `.cursor/mcp.json`) to user-level (`~/.claude.json` / `~/.cursor/mcp.json`) for cross-project reuse
- Changed Spec Skills sync to `--with-spec` optional parameter in `/sync:basic` (not synced by default)
- Changed ensure-cli-tools.sh to run silently in background (non-blocking session startup, no terminal output)
- Changed hooks.json ensure-cli-tools to async background execution
- Cleaned up statusline.sh debug output
- Updated grafana-dashboard-design skill description

### Marketplace

- Bumped version from 0.1.14 to 0.1.15
- Updated sync plugin to version 0.1.11

## 0.1.14

### Sync Plugin (0.1.10)

- Added `/sync:mcp-feishu-project` command for configuring Feishu Project MCP (project.feishu.cn)
- Added `mcp-feishu-project` skill that auto-triggers when user provides Feishu Project MCP URL

### Marketplace

- Bumped version from 0.1.13 to 0.1.14
- Updated sync plugin to version 0.1.10

## 0.1.13

### Git Plugin (0.1.5)

- Added security restrictions: prohibited `glab mr approve` and `glab mr merge` (MR approval/merge must be manual)
- Added security restrictions: prohibited `git push --force` and variants
- Refined `allowed-tools` for push commands (removed wildcard `git push:*`, explicitly listed safe push variants)
- Added `glab` related allowed-tools (`glab mr create`, `glab auth status`, `which glab`)

### Sync Plugin (0.1.9)

- Added `/sync:mcp-grafana <username> <password>` command for Grafana MCP configuration
- Auto-installs Golang and mcp-grafana if not present
- Configures to both Claude Code and Cursor simultaneously
- Added `--dev` parameter for `/sync:basic` to prioritize cache path (for plugin developers)
- Added Stage 5: Sync Claude Skills (`grafana-dashboard-design`) to `.claude/skills/`
- Added `sync-mcp-grafana.md` Cursor command template
- Updated commit format to match git plugin (dual signature lines)

### Marketplace

- Bumped version from 0.1.12 to 0.1.13
- Updated git plugin to version 0.1.5
- Updated sync plugin to version 0.1.9

## 0.1.12

### Sync Plugin (0.1.8)

- Refactored Spec Skills sync: removed single index file `sync-claude-plugin.mdc`, now generates independent `.mdc` rule files
- Added `doc-auto-sync.mdc` - auto-sync module docs when AI modifies code (alwaysApply: true)
- Added `module-discovery.mdc` - must read module index before development (alwaysApply: true)
- Added `generate-module-map.mdc` - prompt for generating module index (alwaysApply: false)
- Filters out skills marked as "测试中" (testing): `implementing-from-task`, `merging-parallel-work`
- Auto-deletes old `sync-claude-plugin.mdc` file for backward compatibility
- Updated `/sync:basic` command to include Spec Skills sync stage

### Marketplace

- Bumped version from 0.1.11 to 0.1.12
- Updated sync plugin to version 0.1.8

## 0.1.10

### Sync Plugin (0.1.6)

- Refactored hooks architecture to use project-relative paths (`.claude/hooks/scripts/`) instead of plugin-root-relative paths
- Added `set-auto-update-plugins.sh` script to enable automatic marketplace plugin updates
- Added `sync-git-flow-snippets.sh` script for automated git-flow documentation synchronization
- Added pre-commit git hook (`.githooks/pre-commit`) for automatic snippet syncing when git-flow docs change
- Enhanced `ensure-cli-tools.sh` with detailed logging showing installation and configuration status
- Updated `hooks.json` to use project-relative script paths for better portability across team environments
- Removed Windows support: deleted `ensure-cli-tools.ps1` (macOS/Linux only)
- Removed `reload-plugins.sh` (replaced by `set-auto-update-plugins.sh`)

### Git Plugin (0.1.4)

- Modularized git-flow documentation into reusable snippets (6 files) for better maintainability
- Added support for Feishu task link extraction with automatic ID conversion
- Added support for Jira link extraction (`/browse/TAP-xxxxx` pattern)
- Enhanced task ID extraction with three-priority strategy: branch name → user input → user query
- Added mandatory second confirmation for commits without task ID (#no-ticket)
- Improved MR creation with Python-based template merging support
- Deleted monolithic `command-procedures.md` (replaced by modular snippets)

### Marketplace

- Bumped version from 0.1.9 to 0.1.10
- Updated git plugin to version 0.1.4
- Updated sync plugin to version 0.1.6

## 0.1.9

### Sync Plugin (0.1.5)

- `/sync:basic` now syncs the GitLab Merge Request default template
- Added SessionStart CLI tool checks for `gh`/`glab`, with scripts for macOS/Linux (`ensure-cli-tools.sh`) and Windows (`ensure-cli-tools.ps1`)
- Added `/sync:git-cli-auth` to detect gh/glab and configure GitHub/GitLab tokens

### Git Plugin (0.1.3)

- Refactored execution logic into reusable snippets (default branch detection, task ID extraction, branch creation, commit execution, etc.) to reduce duplication across command docs
- Tightened commit rules: title must include Chinese description; `Co-Authored-By` must be placed at the end of the body
- `commit-push-pr` can generate MR descriptions from templates (compatible with `.gitlab/merge_request_templates/default.md` and `Default.md`)

### Marketplace

- Bumped version from 0.1.8 to 0.1.9
- Updated git plugin to version 0.1.3
- Updated sync plugin to version 0.1.5

## 0.1.8

### Sync Plugin (0.1.4)

- Added `sync-claude-plugin.mdc` generation in `/sync:basic` command
- Syncs Claude Plugin Skills index to `.cursor/rules/sync-claude-plugin.mdc`
- Automatically extracts `name` and `description` from SKILL.md files
- Filters out skills marked as "测试中" (testing)
- Updated coverage strategy documentation (MCP/Hooks: skip if exists, Cursor: always overwrite)

### Spec Plugin (0.1.3)

- No functional changes, version bump for marketplace sync

### Marketplace

- Bumped version from 0.1.7 to 0.1.8
- Updated Sync plugin to version 0.1.4
- Updated Spec plugin to version 0.1.3

## 0.1.7

### Spec Plugin (0.1.2)

- Improved README with complete skills documentation
- Added `module-discovery` skill documentation (auto-read module index, keyword-based module location)
- Added `doc-auto-sync` skill documentation (layered doc system, auto-sync rules, check scripts)
- Updated `merging-parallel-work` skill documentation (worktree workflow, conflict resolution, merge report)
- Clarified trigger conditions and use cases for each skill

### Marketplace

- Bumped version from 0.1.6 to 0.1.7
- Updated Spec plugin to version 0.1.2

## 0.1.6

### Spec Plugin (0.1.1)

- Added `module-discovery` skill for AI to auto-read `module-map.md` at session start
- Added `generate-module-map.md` prompt for generating module index
- Updated `doc-auto-sync` prerequisite steps with project type and name config items

### Marketplace

- Bumped version from 0.1.5 to 0.1.6
- Updated Spec plugin to version 0.1.1

## 0.1.5

### Git Plugin (0.1.2)

- Removed support for TP- and TDS- task ID prefixes
- Simplified to support only TAP- prefix for task IDs
- Updated all documentation, commands, and regex patterns to reflect single prefix support
- Updated task ID extraction logic across all files

### Quality Plugin (0.0.2)

- Removed hardcoded absolute paths from developer's local environment
- Updated project standards file detection to use relative paths 
- Updated language-checks references to use plugin-relative paths
- Updated agent definitions path to use relative path 
- Fixed issue-comment template resource links to use correct relative paths
- Improved portability and generalization for public release

### Marketplace

- Bumped version from 0.1.4 to 0.1.5
- Updated git plugin to version 0.1.2
- Updated quality plugin to version 0.0.2

## 0.1.4

### Quality Plugin (0.0.1)

- Added AI-driven code review plugin with 9 parallel agents
- Added multi-language support (Go/Java/Python/Kotlin/Swift/TypeScript)
- Added four-dimensional review: bug detection, code quality, security analysis, performance analysis
- Added confidence scoring mechanism with redundancy confirmation (threshold: 80)
- Added intelligent project standards checking (CLAUDE.md/CONTRIBUTING.md auto-detection)
- Added `/review` command for automated code review workflow

### Sync Plugin (0.1.4)

- Improved `sync-from-zeus.sh` to auto-discover all plugins instead of hardcoding plugin names
- Removed warnings for non-existent plugins by using dynamic plugin directory scanning

### Marketplace

- Bumped version from 0.1.3 to 0.1.4
- Added quality plugin to marketplace registry

## 0.1.3

### Git Plugin (0.1.1)

- Added `/git:commit-push` command for commit and push workflow without creating MR
- Added `command-procedures.md` as shared logic layer for all commands and skills to reference
- Added intelligent branch prefix detection for `/git:commit-push-pr` (analyzes git diff to determine feat-, fix-, docs-, etc.)
- Added three-tier task ID extraction strategy (branch name → user input → ask user)
- Improved commit message format with bilingual support (English + Chinese sections)
- Improved README.md with architecture diagrams, command comparison table, and detailed workflow documentation
- Improved all command documentation to reference shared logic layer instead of duplicating procedures
- Changed commit signature format to use `Generated-By` and `Co-Authored-By` with proper spacing

### Sync Plugin (0.1.3)

- Added `cursor-templates/` directory with pre-formatted Cursor-compatible templates
- Added direct template copying approach (no runtime conversion needed)
- Improved `/sync:basic` to directly overwrite files without checking existence or conflicts
- Improved `/sync:cursor` to use three-tier template lookup and direct overwrite strategy
- Improved sync workflow to use single source of truth for Cursor format
- Changed conflict handling from interactive prompts to direct overwrite for team consistency
- Removed backup file creation (simplified sync process)

### Documentation

- Improved installation and usage instructions in root README.md
- Added detailed architecture documentation for Git plugin workflow
- Added best practices for template maintenance and customization

## 0.1.2

- Added Sync plugin with MCP and Cursor IDE synchronization features
- Improved Git plugin documentation

## 0.1.1

- Improved sync script with enhanced reliability
- Updated documentation

## 0.1.0

- Initial release with Git and Sync plugins
- Added Git workflow automation (commit, push, merge request creation)
- Added project configuration synchronization
