# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

This is a **documentation-only knowledge base** — there is nothing to build, test, or run. It stores reusable reference material for the Anthropic Claude API and Python SDK, built specifically to prepare for the **Claude Certification exam**.

## Key Files

**[anthropic_api_reference.md](anthropic_api_reference.md)** is a slim **index** into the reference content — it lists every numbered section with a link into the file under `reference/` that actually holds it, plus the exam blueprint weights, the 6 exam scenarios, and a "focus areas" table pointing at the weakest-scoring task statements from the last practice attempt. The reference is organized to **mirror the exam's own 5-domain blueprint** (Claude Certified Architect – Foundations, CCAR-F), so studying by domain and studying by file are the same thing:

- `reference/00-foundations-messages-api.md` — prerequisite Messages API mechanics every domain assumes: tool choice, content blocks, stop reasons, built-in/local tools, models & pricing, request/response shape, the tool loop, `maxTurns`, API statelessness
- `reference/01-agentic-architecture-and-orchestration.md` — **Domain 1 (27%)**: agentic loop anti-patterns, hub-and-spoke, the `Task` tool & `AgentDefinition`, workflow enforcement/handoff, Agent SDK hooks, task decomposition, session management, `fork_session`
- `reference/02-tool-design-and-mcp-integration.md` — **Domain 2 (18%)**: tool description quality, structured MCP error responses, tool distribution across agents, MCP server scope/config/resources, built-in tool selection
- `reference/03-claude-code-configuration-and-workflows.md` — **Domain 3 (20%)**: choosing the right config mechanism (CLAUDE.md vs. rules vs. skills vs. hooks vs. permissions), slash commands/skills, path-scoped rules, permission modes, plan mode, iterative refinement, CI/CD integration
- `reference/04-prompt-engineering-and-structured-output.md` — **Domain 4 (20%)**: explicit criteria/false-positive reduction, XML tag structuring, few-shot prompting, `tool_use` + JSON schema enforcement, validation/retry/feedback loops, Message Batches API, multi-instance/multi-pass review
- `reference/05-context-management-and-reliability.md` — **Domain 5 (15%)**: long-session context preservation, escalation/ambiguity resolution, error propagation across multi-agent systems, human review/confidence calibration, information provenance
- `reference/06-out-of-scope.md` — topics the exam guide explicitly excludes (fine-tuning, billing/auth protocol details, cloud-provider specifics, computer use, vision, streaming, rate limits, benchmarking, prompt-caching/tokenization internals). Keep genuinely out-of-scope material here, not mixed into a domain file.

Section numbering is global and never renumbers — each section keeps its original number regardless of which file it lives in, even when a section is relocated to a different domain file during a restructure. The index in `anthropic_api_reference.md` tracks the next available number.

**[claude_commands.md](claude_commands.md)** is the slash commands reference — when/why/how for all built-in commands and skills, most important ones first.

**[mental_map.md](mental_map.md)** is the structural overview. It has two parts: an **Exam Domain Map** (condensed ASCII summary of all 5 domains, cross-referenced to `anthropic_api_reference.md` section numbers) and a **General API / Claude Code Structural Map** (the full API surface, including things outside exam scope). **Update the Exam Domain Map whenever a new exam-relevant concept is added to the reference**; only touch the general map for non-exam API/CLI facts.

Target model documented: `claude-sonnet-4-6`. Target SDKs: `anthropic` (Python) and `claude-agent-sdk` (Python). Reference marked current as of August 2026.

### Exam-Blueprint Alignment Rules

These layer on top of the Q&A workflow below — apply them whenever the conversation touches certification-exam content specifically (as opposed to general Claude/API questions unrelated to the exam):

1. **Tag new content with its Task Statement.** When adding a section that maps to a specific exam Task Statement (e.g. "Task Statement 2.2"), name it explicitly in the section's opening line, the way existing sections do. This is what makes the domain files double as a blueprint checklist.
2. **Scenario-fit code examples.** Code samples illustrating exam concepts should use one of the 6 established running scenarios (Customer Support Resolution Agent, Code Generation with Claude Code, Multi-Agent Research System, Developer Productivity, Claude Code for CI, Structured Data Extraction) and their established fixtures (tool names, subagent names, schemas — see each domain file's "Running example" line) rather than inventing new one-off scenarios, unless the question is about a 7th scenario not on this list.
3. **Out-of-scope routing.** If a question is about a real, current Claude/Anthropic feature that the exam guide's Appendix explicitly excludes (fine-tuning, billing, computer use, vision, streaming, prompt-caching internals, etc.), still answer it — accurately, using `claude-api`-skill-grade knowledge if useful — but file any reference-worthy notes in `reference/06-out-of-scope.md`, not into a domain file. Note the scope difference in the answer to the user.
4. **Verify before writing.** For Claude Agent SDK / Claude Code CLI specifics in particular (subagent config field names, hook signatures, CLI flags), don't write down a recalled pattern without checking it against current `code.claude.com/docs` — these surfaces have drifted before (e.g. the Agent SDK's `AgentDefinition`/`Task`/`fork_session` mechanics look similar to, but are distinct from, the CLI's filesystem-based `.claude/agents/*.md` subagent convention).

## Offline / Print Copy

**[EXAM_PREP_FULL.md](EXAM_PREP_FULL.md)** is a generated, consolidated single-file concatenation of `anthropic_api_reference.md` + every `reference/*.md` file (in domain order) + `mental_map.md` + `claude_commands.md` — for offline reading or printing (e.g. via VS Code's "Markdown PDF" export, or `pandoc EXAM_PREP_FULL.md -o EXAM_PREP_FULL.pdf`). It is a **build artifact, not a source file** — never hand-edit it directly; regenerate it after any change to the source files with:

```bash
{
  cat anthropic_api_reference.md
  for f in reference/00-foundations-messages-api.md reference/01-agentic-architecture-and-orchestration.md \
           reference/02-tool-design-and-mcp-integration.md reference/03-claude-code-configuration-and-workflows.md \
           reference/04-prompt-engineering-and-structured-output.md reference/05-context-management-and-reliability.md \
           reference/06-out-of-scope.md; do cat "$f"; done
  cat mental_map.md
  cat claude_commands.md
} > EXAM_PREP_FULL.md
```

Regenerate it as one of the last steps of any session that touches the reference — don't leave it stale.

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
