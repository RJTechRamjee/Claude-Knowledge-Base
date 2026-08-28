# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

This is a **documentation-only knowledge base** — there is nothing to build, test, or run. It stores reusable reference material for the Anthropic Claude API and Python SDK, built specifically to prepare for the **Claude Certification exam**.

## Key Files

**[anthropic_api_reference.md](anthropic_api_reference.md)** is now a slim **index** into the reference content — it lists every numbered section with a link into the file under `reference/` that actually holds it. The reference itself is split by topic across six files so no single file grows unbounded:

- `reference/01-messages-api-core.md` — Messages API core (tool choice, content blocks, stop reasons, built-in/local tools, models & pricing, message roles, request params, response fields)
- `reference/02-tool-use-and-sessions.md` — Session resumption, multi-turn tool loop, maxTurns, structured output edge cases, Message Batches API
- `reference/03-claude-code-config.md` — CLI session management, path-scoped rules/symlinks, permission modes, `.claude/rules/`, tool selection (Bash vs. Read/Glob/Grep)
- `reference/04-claude-code-skills-and-hooks.md` — Skills scope/resolution, hooks (types, blocking vs. observational)
- `reference/05-multi-agent-and-context.md` — Multi-instance review, context window management, XML tag prompt structuring, hub-and-spoke multi-agent architecture, agent escalation design, prompt specificity tradeoffs
- `reference/06-mcp.md` — MCP resources/@ mentions, `.mcp.json` env var expansion, server authentication, scope precedence

Section numbering is global and never renumbers — each section keeps its original number regardless of which file it lives in. The index in `anthropic_api_reference.md` tracks the next available number.

**[claude_commands.md](claude_commands.md)** is the slash commands reference — when/why/how for all built-in commands and skills, most important ones first.

**[mental_map.md](mental_map.md)** is the structural overview (ASCII tree of the full API + patterns). Kept separate so adding sections to the reference never forces a renumber. **Update this file whenever a new concept is added to the reference.** It covers:

- Tool choice modes (`auto`, `any`, `tool`, `none`) and local tool definition schema
- Content block types (`text`, `tool_use`, `tool_result`, `image`, `document`) and stop reasons
- Built-in tools (`web_search`, `bash`, `str_replace_editor`, `computer`) vs. local tools
- Full `client.messages.create()` parameter reference and response object fields
- Multi-turn tool loop pattern (complete Python example)
- Claude Code CLI session management (`--name`, `--resume`, `/rename`)
- `maxTurns` behavior and configuration (CLI and API)
- Quick mental map (ASCII tree of the full API structure)

Target model documented: `claude-sonnet-4-6`. Target SDK: `anthropic` (Python). Reference marked current as of August 2026.

## Certification Study Workflow

The primary use pattern is **exam question review**: the user shares a certification quiz question (usually as a screenshot), asks follow-up questions about it, and wants two things in every interaction:

1. **Explain the concept** — answer the question clearly, correct any misconceptions the user raises, and give enough context to understand *why* the correct answer is right and the wrong answers are wrong.
2. **Add it to the reference** — update the appropriate `reference/*.md` file (and the index in `anthropic_api_reference.md`) with the new knowledge immediately after explaining it.

Always do both, in that order. Do not skip the explanation in favour of just editing the file.

## Updating the Reference from Q&A Sessions

This repo doubles as a living reference — whenever a conversation yields new or clarified knowledge about the Anthropic Claude API, update the reference immediately after answering. Apply these rules:

**What to capture**
- Any API behavior, parameter, or pattern not already covered in the document
- Corrections to existing entries (wrong defaults, outdated type strings, missing edge cases)
- Clarifications that required looking something up or reasoning carefully — if it wasn't obvious, it belongs here
- New code patterns or idioms (streaming, prompt caching, multi-agent, MCP tool definitions, etc.)

**Where to put it**
- If it fits an existing section, add it there (new sub-heading or bullet), in whichever `reference/*.md` file currently holds that section
- If it is a distinct topic, pick the `reference/*.md` file matching the topic (or create a new one if none fit), append the section there using the next available number from the index in `anthropic_api_reference.md`, and update that index
- Keep the index in `anthropic_api_reference.md` in sync — it is the document's map to every section across all `reference/*.md` files, and it tracks the next available section number

**How to write it**
- Use the same style: numbered top-level sections (`## N. Title`), fenced code blocks with language tags (`python`, `bash`), comparison tables for multiple options
- One concrete code snippet is worth more than a paragraph of prose
- Note any versioned type strings (e.g. `bash_20250124`) when they appear — they change between API versions

**Model and SDK scope**
The document currently targets `claude-sonnet-4-6` and the Python `anthropic` SDK. If a question introduces a different model or SDK language, note that scope difference inline (e.g., `# Node.js SDK`) rather than silently mixing conventions.

## Style Reference

Section structure in each `reference/*.md` file:
- Each file opens with a `#` title describing its scope, a one-line description, then `---`
- `##` for numbered top-level sections (`## N. Title`) — numbers are global across all `reference/*.md` files and never renumbered
- `###` for named variants within a section
- Fenced code blocks with `python` or `bash` tags
- Comparison tables with `|` syntax, header row, separator row, then data rows
- Section separator: `---`

`anthropic_api_reference.md` itself contains no section bodies — only the index/TOC linking into `reference/*.md`.
