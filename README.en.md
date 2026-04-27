English | [中文](./README.md)

# TapTap Agents Plugins

A plugin marketplace maintained by the TapTap team, offering workflow automation for AI development tools.

## Team Configuration

For team projects, you can configure `.claude/settings.json` in the project root directory. Claude Code will automatically install plugins without manual installation commands.

### 1. Configure Settings

Run the following command in the project root directory:

```bash
mkdir -p .claude && echo '{
  "extraKnownMarketplaces": {
    "taptap-plugins": {
      "source": {
        "source": "github",
        "repo": "taptap/agents-plugins"
      }
    }
  },
  "enabledPlugins": {
    "spec@taptap-plugins": true,
    "sync@taptap-plugins": true,
    "git@taptap-plugins": true
  }
}' > .claude/settings.json
```

**Optional: Per-repo Git plugin configuration**

You can configure Git plugin behavior via the `env` field in `.claude/settings.json`:

| Variable | Default | Description |
|----------|---------|-------------|
| `GIT_ALLOW_NO_TICKET` | `"true"` | Whether to allow no-ticket commits, set to `"false"` to disable |

Example (disable no-ticket, require task ID):

```json
{
  "env": {
    "GIT_ALLOW_NO_TICKET": "false"
  },
  "enabledPlugins": { ... }
}
```

### 2. Run /sync

One-click configuration for MCP, auto-update, and development environment templates:

```bash
# Run in Claude Code
/sync:basic

# After configuration, restart Claude Code to use
```

**Included features:**

- ✅ Configure context7 MCP (automatically fetch latest documentation)
- ✅ Enable plugin auto-reload + CLI tool detection (restart session after modifications to take effect)
- ✅ Sync GitLab Merge Request default template
- ✅ Support GitHub Pull Request template

### 3. Verify Installation

```bash
# View installed plugins
/plugin

# View available commands
/help
```

## Plugin List


| Plugin  | Version | Description                                                                                          |
| ------- | ------- | ---------------------------------------------------------------------------------------------------- |
| spec    | 0.1.8   | Spec-Driven Development workflow plugin                                                              |
| git     | 0.1.16  | Git workflow automation plugin (commit/push/MR + dual-mode code review + remote platform ops)        |
| sync    | 0.1.30  | Dev environment config sync plugin (MCP + LSP + Hooks + Claude Skills)                               |
| test    | 0.0.8   | QA workflow plugin (requirement clarification/test case generation/change analysis/traceability/code-level test generation) |


See the README.md in each plugin directory for detailed documentation.

**Version History**: See [CHANGELOG.md](./CHANGELOG.md) for release notes.

## Daily Usage

### Git Workflow (Recommended)

For development scenarios that require creating MRs:

```bash
# 1. Provide a task link to automatically create branch, commit, push, and create MR
/git:commit-push-pr https://xindong.atlassian.net/browse/TAP-12345

# Or provide a Feishu task link
/git:commit-push-pr https://project.feishu.cn/pojq34/story/detail/12345
```

**Command execution flow:**

- Automatically extract Task ID from task link
- **Smart branch prefix detection**: Analyzes `git diff` content to automatically choose the appropriate prefix
  - `docs/`: Only documentation files modified
  - `test/`: Only test files modified
  - `fix/`: Contains bug fix keywords
  - `feat/`: New features or files added
  - `refactor/`: Code refactoring
  - `perf/`: Performance optimization
  - `chore/`: Configuration or maintenance tasks
- If on main/master branch, will prompt for branch description and create a feature branch (e.g., `feat/TAP-12345-description`)
- Analyzes code changes and generates commit messages following conventions
- Pushes code and automatically creates Merge Request / Pull Request

**Platform Support:**


| Platform | CLI Tool | Template Path                                    |
| -------- | -------- | ------------------------------------------------ |
| GitLab   | `glab`   | `.gitlab/merge_request_templates/default.md`     |
| GitHub   | `gh`     | `.github/PULL_REQUEST_TEMPLATE.md`               |


> 💡 The command automatically detects the repository type and available CLI tools, choosing the appropriate method to create MR/PR.

**CLI Tool Configuration:** Use the `/sync:git-cli-auth` command to detect and configure authentication

```bash
# Configure git CLI Token
/sync:git-cli-auth

# Or use the original commands
gh auth login        # GitHub
glab auth login      # GitLab
```

### Quick Commit & Push

The Git plugin provides three commit modes, choose based on your needs:

**1. Commit Only (Local Development)**

```bash
# Use when: You need multiple commits, not ready to push yet
/git:commit
```

**2. Commit and Push (Backup to Remote)**

```bash
# Use when: Feature complete, need to backup to remote, but no MR needed
/git:commit-push
```

**3. Commit, Push, and Create MR (Full Workflow)**

```bash
# Use when: Feature complete, create merge request immediately
/git:commit-push-pr https://xindong.atlassian.net/browse/TAP-12345
```

**Notes**:

- All commands automatically extract Task ID from branch name
- On main/master branch, a feature branch will be created automatically
- `/git:commit-push-pr` supports smart branch prefix detection

### Spec-Driven Development

> ⚠️ **Warning**: This feature is under development and not recommended for use yet

Generate technical specifications and execute development from requirement documents:

```bash
# Generate a complete technical specification and execution plan based on task requirements
/spec https://xindong.atlassian.net/browse/TAP-12345
```

#### Module Discovery

AI reads the module index on demand for repositories that adopt the module-index workflow, quickly understanding the project structure:


| Path                                    | Description                                                                           |
| --------------------------------------- | ------------------------------------------------------------------------------------- |
| `tap-agents/tap-agents-configs.md`      | Project configuration file (project type, name, business module directory, class suffixes, file extensions) |
| `tap-agents/prompts/module-map.md`      | Module index (P0/P1/P2 priority classification + keyword lookup table)                |
| `tap-agents/prompts/modules/[module].md`| Detailed documentation for each module                                                |


**Workflow:**

1. First determine whether the repository actually uses the `tap-agents` module index workflow and treats it as the module discovery entry point
2. Only for module-location tasks, check whether `module-map.md` exists
3. If it is missing and the user explicitly wants this workflow, ask whether it should be generated
4. Read the module index and use its keywords for quick code navigation

#### Documentation Auto-Sync

AI **automatically maintains** module documentation when modifying code:


| Trigger Scenario  | AI Behavior                                                        |
| ----------------- | ------------------------------------------------------------------ |
| New module added  | Creates `modules/[module].md` + updates `module-map.md`            |
| Module modified   | Checks and updates corresponding documentation                    |
| Documentation missing | Automatically creates documentation (enforced)                 |
| Documentation outdated | Trusts code, automatically updates documentation              |


**Configuration (defined in `tap-agents/tap-agents-configs.md`):**

- `「Project Type」`: iOS / Android / Web / Backend, etc.
- `「Project Name」`: Project name
- `「Business Module Directory」`: Main business code directory (e.g., `TapTap`, `src/modules`)
- `「Main Class Suffix」`: Suffixes for identifying main classes (e.g., `ViewController`, `Service`)
- `「File Extension」`: Code file extensions (e.g., `.swift`, `.kt`, `.go`)

### Code Review

Use the Git plugin's built-in review flow to inspect local changes or MR/PRs:

```bash
# Review current workspace or branch changes
/git:code-reviewing

# Review a specific Merge Request / Pull Request
/git:code-reviewing https://gitlab.example.com/group/project/-/merge_requests/123

# Review a specific commit or branch
/git:code-reviewing HEAD~1
```

**Highlights:**

- **Dual-engine review**: Claude Agent Team + Codex cross-checking
- **Local and MR modes**: Works with uncommitted changes, commits, branches, and MR/PR URLs
- **Project-aware rules**: Loads repo review checklist and review rules automatically
- **Risk-first output**: Reports blockers first, then residual risks and verification gaps

### Development Environment Sync

```bash
# One-click environment setup (recommended for new team members)
/sync:basic

# Or configure each item separately
/sync:mcp            # Configure context7 MCP
/sync:hooks          # Enable plugin auto-reload

# Configure Feishu Docs MCP (optional)
/sync:mcp-feishu https://open.feishu.cn/mcp/stream/mcp_xxxxx

# Configure Feishu Project MCP (optional)
/sync:mcp-feishu-project https://project.feishu.cn/mcp_server/v1?mcpKey=xxx&projectKey=yyy&userKey=zzz

# Configure Grafana MCP (optional, auto-installs Golang and mcp-grafana)
/sync:mcp-grafana <username> <password>
```

**Feature Details:**

- **MCP Servers**: Automatically fetch latest documentation for GitHub libraries (context7)
- **Auto-Reload**: Restart session after plugin modifications to take effect, no manual reinstallation needed

## Update Plugins

```bash
# Update a specific plugin
/plugin update spec@taptap-plugins

# Or reinstall
/plugin uninstall spec@taptap-plugins
/plugin install spec@taptap-plugins
```

## Feedback

Please submit issues on [GitHub Issues](https://github.com/taptap/agents-plugins/issues).
