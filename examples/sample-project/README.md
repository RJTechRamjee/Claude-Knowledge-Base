# sample-project (reference example)

This folder is not a real app — it's a worked example of every recognized
`.claude/` file type, for the list documented in
[section 22 of ../../anthropic_api_reference.md](../../anthropic_api_reference.md#22-claude-code-rules--claude-rules-and-path-scoped-loading).

| File | Demonstrates |
|---|---|
| `CLAUDE.md` | Project instructions, loaded every session |
| `.claude/rules/general-style.md` | Rule with no `paths:` field — unconditional load |
| `.claude/rules/api-conventions.md` | Rule with `paths:` field — conditional per-file load |
| `.claude/skills/deploy-checklist/SKILL.md` | Skill package, invoked as `/deploy-checklist` |
| `.claude/agents/code-reviewer.md` | Subagent definition with isolated context |
| `.claude/agent-memory/code-reviewer/notes.md` | Persistent memory storage for a project-scoped subagent |
| `.claude/output-styles/concise.md` | Custom system-prompt section changing response tone |
| `.claude/settings.json` | Committed permissions + hooks config |
| `.claude/settings.local.json` | Personal per-project overrides (normally gitignored) |
| `.claude/.mcp.json` | Team-shared MCP server config |
| `.claude/.worktreeinclude` | Gitignored file carried into new worktrees |
