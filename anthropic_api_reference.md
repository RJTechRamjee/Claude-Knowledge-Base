# Anthropic API – Reusable Reference

> Model: `claude-sonnet-4-6` | SDK: `anthropic` (Python)

This file is now an **index** into the reference content, which has been split by topic under [`reference/`](reference/) for manageability. Each numbered section below links directly to its full write-up in the file that owns it. Follow a link to read the actual content — nothing has been duplicated here.

---

## Contents

**Next available section number: 36** — when adding a new section, use this number and bump it here.

### Messages API Core — [reference/01-messages-api-core.md](reference/01-messages-api-core.md)
Tool choice; content block types; stop reasons; built-in tools; local tool definitions; current models/pricing; message roles; request parameters; response fields.

1. [Tool Choice](reference/01-messages-api-core.md#1-tool-choice)
2. [Content Block Types](reference/01-messages-api-core.md#2-content-block-types)
3. [Stop Reasons](reference/01-messages-api-core.md#3-stop-reasons)
4. [Built-in (Standard) Tools](reference/01-messages-api-core.md#4-built-in-standard-tools)
5. [Local Tool Definition](reference/01-messages-api-core.md#5-local-tool-definition)
6. [Current Models and Pricing](reference/01-messages-api-core.md#6-current-models-and-pricing)
8. [Message Roles](reference/01-messages-api-core.md#8-message-roles)
9. [Top-level Request Parameters](reference/01-messages-api-core.md#9-top-level-request-parameters)
10. [Response Object Fields](reference/01-messages-api-core.md#10-response-object-fields)

### Tool Use and Sessions — [reference/02-tool-use-and-sessions.md](reference/02-tool-use-and-sessions.md)
Session resumption; the multi-turn tool loop; maxTurns; structured output edge cases; the Message Batches API.

7. [Session Resumption — The API Is Stateless](reference/02-tool-use-and-sessions.md#7-session-resumption-the-api-is-stateless)
11. [Multi-turn Tool Loop Pattern](reference/02-tool-use-and-sessions.md#11-multi-turn-tool-loop-pattern)
13. [maxTurns](reference/02-tool-use-and-sessions.md#13-maxturns)
15. [Structured Output — Handling Missing Data in Tool Schemas](reference/02-tool-use-and-sessions.md#15-structured-output-handling-missing-data-in-tool-schemas)
30. [Message Batches API: Fire-and-Forget Model and Tool-Use Limitation](reference/02-tool-use-and-sessions.md#30-message-batches-api-fire-and-forget-model-and-tool-use-limitation)

### Claude Code Configuration — [reference/03-claude-code-config.md](reference/03-claude-code-config.md)
CLI session management; path-scoped rules and symlinks; permission modes; `.claude/rules/`; tool selection (Bash vs. Read/Glob/Grep).

12. [Session Management (Claude Code CLI)](reference/03-claude-code-config.md#12-session-management-claude-code-cli)
18. [Path-Scoped Rules and Symlinks in Claude Code](reference/03-claude-code-config.md#18-path-scoped-rules-and-symlinks-in-claude-code)
20. [Claude Code Permission Modes](reference/03-claude-code-config.md#20-claude-code-permission-modes)
22. [Claude Code Rules — `.claude/rules/` and Path-Scoped Loading](reference/03-claude-code-config.md#22-claude-code-rules-clauderules-and-path-scoped-loading)
23. [Claude Code Tool Selection — Bash vs. Read / Glob / Grep](reference/03-claude-code-config.md#23-claude-code-tool-selection-bash-vs-read-glob-grep)
32. [Blocking Bash in CI Pipelines — `--disallowedTools`](reference/03-claude-code-config.md#32-blocking-bash-in-non-interactive--ci-pipelines----disallowedtools)
33. [Piped Stdin Size Limit — 10 MB Cap](reference/03-claude-code-config.md#33-piped-stdin-size-limit-in-claude-code--10-mb-cap)
34. [`claudeMdExcludes` — Filtering CLAUDE.md Loading in Monorepos](reference/03-claude-code-config.md#34-claudemdexcludes--filtering-claudemd-loading-in-monorepos)
35. [CLAUDE.md `@path` Import Syntax — Triggering vs. Suppressing Imports](reference/03-claude-code-config.md#35-claudemd-path-import-syntax-triggering-vs-suppressing-imports)

### Claude Code Skills and Hooks — [reference/04-claude-code-skills-and-hooks.md](reference/04-claude-code-skills-and-hooks.md)
Skills scope and resolution; hooks (hook types, blocking vs. observational, enforcement patterns).

16. [Claude Code Skills – Scope and Resolution](reference/04-claude-code-skills-and-hooks.md#16-claude-code-skills-scope-and-resolution)
21. [Claude Code Hooks — Hook Types and Enforcement](reference/04-claude-code-skills-and-hooks.md#21-claude-code-hooks-hook-types-and-enforcement)

### Multi-Agent Architecture and Context — [reference/05-multi-agent-and-context.md](reference/05-multi-agent-and-context.md)
Multi-instance review; long-session context management; XML tag prompt structuring; hub-and-spoke multi-agent architecture; agent escalation design; prompt specificity tradeoffs.

14. [Multi-Instance Review Architecture](reference/05-multi-agent-and-context.md#14-multi-instance-review-architecture)
17. [Context Window Management in Long Sessions](reference/05-multi-agent-and-context.md#17-context-window-management-in-long-sessions)
19. [Prompt Structuring — XML Tags for Category Isolation](reference/05-multi-agent-and-context.md#19-prompt-structuring-xml-tags-for-category-isolation)
24. [Multi-Agent Architecture — Hub-and-Spoke Pattern](reference/05-multi-agent-and-context.md#24-multi-agent-architecture-hub-and-spoke-pattern)
25. [Agent Escalation Design — Self-Reported Confidence Scores](reference/05-multi-agent-and-context.md#25-agent-escalation-design-self-reported-confidence-scores)
31. [Prompt Specificity and False Positives vs. False Negatives](reference/05-multi-agent-and-context.md#31-prompt-specificity-and-false-positives-vs-false-negatives)

### MCP (Model Context Protocol) — [reference/06-mcp.md](reference/06-mcp.md)
MCP resources and @ mention syntax; `.mcp.json` environment variable expansion; server authentication; scope precedence for duplicate server names.

26. [MCP Server Resources: @ Mention Reference Syntax](reference/06-mcp.md#26-mcp-server-resources-mention-reference-syntax)
27. [MCP Config: Environment Variable Expansion in `.mcp.json`](reference/06-mcp.md#27-mcp-config-environment-variable-expansion-in-mcpjson)
28. [MCP Server Authentication: `headers` vs `headersHelper` vs `oauth`](reference/06-mcp.md#28-mcp-server-authentication-headers-vs-headershelper-vs-oauth)
29. [MCP Server Config: Scope Precedence for Duplicate Server Names](reference/06-mcp.md#29-mcp-server-config-scope-precedence-for-duplicate-server-names)
