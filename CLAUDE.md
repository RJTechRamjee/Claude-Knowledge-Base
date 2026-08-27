# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

This is a **documentation-only knowledge base** — there is nothing to build, test, or run. It stores reusable reference material for the Anthropic Claude API and Python SDK.

## Key Files

**[anthropic_api_reference.md](anthropic_api_reference.md)** is the primary reference — numbered sections, grows freely without renumbering.

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

## Updating the Reference from Q&A Sessions

This repo doubles as a living reference — whenever a conversation yields new or clarified knowledge about the Anthropic API, update `anthropic_api_reference.md` immediately after answering. Apply these rules:

**What to capture**
- Any API behavior, parameter, or pattern not already covered in the document
- Corrections to existing entries (wrong defaults, outdated type strings, missing edge cases)
- Clarifications that required looking something up or reasoning carefully — if it wasn't obvious, it belongs here
- New code patterns or idioms (streaming, prompt caching, multi-agent, MCP tool definitions, etc.)

**Where to put it**
- If it fits an existing section, add it there (new sub-heading or bullet)
- If it is a distinct topic, add a new numbered section before section 12 (Quick Mental Map) and update the mental map accordingly
- Keep the mental map in sync — it is the document's index

**How to write it**
- Use the same style: numbered top-level sections, fenced code blocks with language tags (`python`, `bash`), comparison tables for multiple options
- One concrete code snippet is worth more than a paragraph of prose
- Note any versioned type strings (e.g. `bash_20250124`) when they appear — they change between API versions

**Model and SDK scope**
The document currently targets `claude-sonnet-4-6` and the Python `anthropic` SDK. If a question introduces a different model or SDK language, note that scope difference inline (e.g., `# Node.js SDK`) rather than silently mixing conventions.

## Style Reference

Section structure in `anthropic_api_reference.md`:
- `##` for numbered top-level sections
- `###` for named variants within a section
- Fenced code blocks with `python` or `bash` tags
- Comparison tables with `|` syntax, header row, separator row, then data rows
- Section separator: `---`
