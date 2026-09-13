# Claude Knowledge Base

A personal, documentation-only reference for the Anthropic Claude API, the Claude Agent SDK, and Claude Code — built specifically to prepare for the **Claude Certified Architect – Foundations** exam (CCAR-F). There's nothing to build, test, or run here; it's all Markdown.

## Start here

| File | What it's for |
|---|---|
| **[CLAUDE.md](CLAUDE.md)** | How this repo is organized and maintained — read this first if you're adding content |
| **[anthropic_api_reference.md](anthropic_api_reference.md)** | The main index — exam blueprint weights, the 6 exam scenarios, weak-area focus list, and links into every section |
| **[reference/](reference/)** | The reference itself, one file per exam domain (see below) |
| **[EXAM_PREP_FULL.md](EXAM_PREP_FULL.md)** | Everything below, concatenated into one file — for offline reading or printing |
| **[mental_map.md](mental_map.md)** | Condensed ASCII cheat-sheet: an exam-domain map plus the general API/Claude Code structural map |
| **[claude_commands.md](claude_commands.md)** | Slash command reference for Claude Code |
| **[examples/sample-project/](examples/sample-project/)** | A worked example project showing CLAUDE.md, `.claude/rules/`, skills, agents, and hooks configured together |

## How the reference is organized

`reference/` mirrors the exam's own 5-domain blueprint, so studying by domain and studying by file are the same thing:

- `00-foundations-messages-api.md` — prerequisite Messages API mechanics (tool choice, stop reasons, the tool loop, etc.)
- `01-agentic-architecture-and-orchestration.md` — **Domain 1 (27%)**
- `02-tool-design-and-mcp-integration.md` — **Domain 2 (18%)**
- `03-claude-code-configuration-and-workflows.md` — **Domain 3 (20%)**
- `04-prompt-engineering-and-structured-output.md` — **Domain 4 (20%)**
- `05-context-management-and-reliability.md` — **Domain 5 (15%)**
- `06-out-of-scope.md` — topics the exam guide explicitly excludes

Every section is numbered globally (`## N. Title`) and the number never changes once assigned, even if the section moves to a different file. `anthropic_api_reference.md` tracks the next free number.

## Scope

Target model: `claude-sonnet-4-6`. Target SDKs: `anthropic` (Python) and `claude-agent-sdk` (Python). Reference current as of August 2026 — see [reference/06-out-of-scope.md](reference/06-out-of-scope.md) for what's deliberately *not* covered here even though it's real, current Claude/Anthropic functionality.
