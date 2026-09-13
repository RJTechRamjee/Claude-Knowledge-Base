# Claude Certified Architect – Foundations: Exam Reference

> Exam: **Claude Certified Architect – Foundations** (CCAR-F), guide effective July 2026 · Target model: `claude-sonnet-4-6` · Target SDKs: `anthropic` (Python) and `claude-agent-sdk` (Python) · Reference current as of August 2026.

This file is an **index** into the reference content — it lists every numbered section with a link into the file under [`reference/`](reference/) that actually holds it. The reference is organized to mirror the **exam's own 5-domain blueprint** (plus a foundations file and an out-of-scope file), so studying by domain and studying by file are the same thing.

> Links below point to the **file**, not a page-internal anchor — section numbers are prominent headings, so `Ctrl+F` (or your editor's outline view) for `## N.` gets you there reliably even where GitHub's auto-generated anchors are unpredictable (backticks, em-dashes, and slashes in a heading all affect the anchor differently).

---

## Exam Blueprint at a Glance

| Domain | Weight | File |
|---|---|---|
| 1. Agentic Architecture & Orchestration | 27% | [reference/01-agentic-architecture-and-orchestration.md](reference/01-agentic-architecture-and-orchestration.md) |
| 2. Tool Design & MCP Integration | 18% | [reference/02-tool-design-and-mcp-integration.md](reference/02-tool-design-and-mcp-integration.md) |
| 3. Claude Code Configuration & Workflows | 20% | [reference/03-claude-code-configuration-and-workflows.md](reference/03-claude-code-configuration-and-workflows.md) |
| 4. Prompt Engineering & Structured Output | 20% | [reference/04-prompt-engineering-and-structured-output.md](reference/04-prompt-engineering-and-structured-output.md) |
| 5. Context Management & Reliability | 15% | [reference/05-context-management-and-reliability.md](reference/05-context-management-and-reliability.md) |

Plus: [reference/00-foundations-messages-api.md](reference/00-foundations-messages-api.md) (prerequisite API mechanics every domain assumes) and [reference/06-out-of-scope.md](reference/06-out-of-scope.md) (explicitly excluded topics — don't study these for this exam).

## The 6 Exam Scenarios

The exam draws **4 of these 6** scenarios per sitting. This reference builds running code examples against **all 6**, since which 4 you draw is random:

1. **Customer Support Resolution Agent** — `get_customer`/`lookup_order`/`process_refund`/`escalate_to_human`, 80%+ first-contact resolution target
2. **Code Generation with Claude Code** — custom slash commands, CLAUDE.md, plan mode vs. direct execution
3. **Multi-Agent Research System** — coordinator + web-search/document-analysis/synthesis/report subagents
4. **Developer Productivity with Claude** — built-in tools (Read/Write/Bash/Grep/Glob) + MCP servers on unfamiliar codebases
5. **Claude Code for Continuous Integration** — automated PR review, test generation, false-positive minimization
6. **Structured Data Extraction** — JSON schema validation, edge-case handling, downstream integration

## Focus Areas (from the last practice-exam score report)

These task statements scored 0%–50% and got extra depth/worked examples in this pass — if short on time, review these sections first (**§** = section number; find it with `Ctrl+F "## N."` in the linked file):

| Task Statement | Section(s) | File |
|---|---|---|
| 3.1 — Enforcement (hooks/permissions) vs. CLAUDE.md placement | §46, §47 | [03-claude-code-configuration-and-workflows.md](reference/03-claude-code-configuration-and-workflows.md) |
| 3.1 — Choosing CLAUDE.md vs. rules vs. skills vs. hooks vs. permissions | §46 | [03-claude-code-configuration-and-workflows.md](reference/03-claude-code-configuration-and-workflows.md) |
| 1.5 — `PostToolUse` hooks enforcing code quality independent of instruction-following | §48 | [03-claude-code-configuration-and-workflows.md](reference/03-claude-code-configuration-and-workflows.md) |
| 5.2 — Escalation: honor explicit request vs. autonomous resolution | §58 | [05-context-management-and-reliability.md](reference/05-context-management-and-reliability.md) |
| 4.4 — Feedback-loop metadata (`detected_pattern`) improving prompts/schemas over time | §56 | [04-prompt-engineering-and-structured-output.md](reference/04-prompt-engineering-and-structured-output.md) |
| 2.2 — Structured, type-specific MCP tool error responses | §42 | [02-tool-design-and-mcp-integration.md](reference/02-tool-design-and-mcp-integration.md) |
| 1.6 — Adaptive task decomposition vs. fixed sequences | §38 | [01-agentic-architecture-and-orchestration.md](reference/01-agentic-architecture-and-orchestration.md) |
| 1.1 — `stop_reason` loop termination anti-patterns | §40 | [01-agentic-architecture-and-orchestration.md](reference/01-agentic-architecture-and-orchestration.md) |
| 3.5 — Iterative refinement (examples, targeted feedback, batching) | §50 | [03-claude-code-configuration-and-workflows.md](reference/03-claude-code-configuration-and-workflows.md) |
| 2.5 — Systematic Grep/Glob/Read exploration under context constraints | §45 | [02-tool-design-and-mcp-integration.md](reference/02-tool-design-and-mcp-integration.md) |
| 2.4 — MCP server scope: project (team) vs. user (personal/experimental) | §44 | [02-tool-design-and-mcp-integration.md](reference/02-tool-design-and-mcp-integration.md) |
| 5.2 — Self-reported confidence / sentiment are unreliable escalation proxies | §25 | [05-context-management-and-reliability.md](reference/05-context-management-and-reliability.md) |
| 5.5 — Confidence/characteristic-based review routing vs. random sampling | §61 | [05-context-management-and-reliability.md](reference/05-context-management-and-reliability.md) |
| 2.1 — Tool description disambiguation for semantically similar tools | §41 | [02-tool-design-and-mcp-integration.md](reference/02-tool-design-and-mcp-integration.md) |

---

## Contents

**Next available section number: 64** — when adding a new section, use this number and bump it here. (Numbers 52, 53, and 57 are intentionally retired/unused — see notes below; gaps in the sequence are expected and fine.)

### Foundations — Messages API Core Mechanics — [reference/00-foundations-messages-api.md](reference/00-foundations-messages-api.md)
Prerequisite building blocks assumed by every domain: tool choice, content blocks, stop reasons, built-in/local tools, models & pricing, message roles, request/response shape, the multi-turn tool loop, `maxTurns`, and API statelessness.

- 1. Tool Choice
- 2. Content Block Types
- 3. Stop Reasons
- 4. Built-in (Standard) Tools
- 5. Local Tool Definition
- 6. Current Models and Pricing
- 7. Session Resumption — The API Is Stateless
- 8. Message Roles
- 9. Top-level Request Parameters
- 10. Response Object Fields
- 11. Multi-turn Tool Loop Pattern
- 13. `maxTurns`

### Domain 1: Agentic Architecture & Orchestration (27%) — [reference/01-agentic-architecture-and-orchestration.md](reference/01-agentic-architecture-and-orchestration.md)
Agentic loop anti-patterns, hub-and-spoke orchestration, the `Task`/`Agent` tool & `AgentDefinition`, multi-step workflow enforcement/handoff, Agent SDK hooks, task decomposition strategy, session management, and `fork_session`.

- 12. Session Management (Claude Code CLI and Agent SDK)
- 21. Agent SDK / Claude Code Hooks — Tool Call Interception and Data Normalization
- 24. Multi-Agent Architecture — Hub-and-Spoke Pattern
- 36. Subagent Spawning — the `Task`/`Agent` Tool and `AgentDefinition`
- 37. `fork_session` — Branching a Session (Agent SDK)
- 38. Task Decomposition Strategies for Complex Workflows
- 39. Multi-Step Workflows — Enforcement and Handoff Patterns
- 40. Agentic Loop Anti-Patterns — What NOT to Check for Termination

### Domain 2: Tool Design & MCP Integration (18%) — [reference/02-tool-design-and-mcp-integration.md](reference/02-tool-design-and-mcp-integration.md)
Tool description quality & disambiguation, structured MCP error responses, distributing tools across agents, MCP server scope/config/resources, and systematic use of built-in tools.

- 23. Built-in Tool Selection — Bash vs. Read/Glob/Grep, and Edit vs. Write
- 26. MCP Server Resources: @ Mention Reference Syntax *(covered within §44)*
- 27. MCP Config: Environment Variable Expansion in `.mcp.json` *(covered within §44)*
- 28. MCP Server Authentication *(covered within §44)*
- 29. MCP Server Config: Scope Precedence for Duplicate Server Names *(covered within §44)*
- 41. Tool Description Quality and Disambiguation
- 42. Structured Error Responses for MCP Tools
- 43. Distributing Tools Appropriately Across Agents
- 44. Configuring MCP Servers at the Correct Scope
- 45. Systematic Codebase Exploration — Grep, Glob, Read Together

### Domain 3: Claude Code Configuration & Workflows (20%) — [reference/03-claude-code-configuration-and-workflows.md](reference/03-claude-code-configuration-and-workflows.md)
Choosing the right configuration mechanism, enforcement vs. guidance, `PostToolUse` quality gates, slash commands & skills, path-scoped rules, permission modes, CLI supporting mechanics, plan mode, iterative refinement, and CI/CD integration.

- 16. Custom Slash Commands and Skills — Scope and Configuration
- 18. Path-Scoped Rules and Symlinks in Claude Code
- 20. Claude Code Permission Modes
- 22. `.claude/rules/` and Path-Scoped Loading (incl. `/memory`)
- 32. Blocking Bash in CI — `--disallowedTools`
- 33. Piped Stdin Size Limit in Claude Code — 10 MB Cap
- 34. `claudeMdExcludes` — Personal Monorepo Filtering
- 35. CLAUDE.md `@path` Import Syntax
- 46. Choosing the Right Claude Code Configuration Mechanism
- 47. Enforcement Layer vs. Guidance Layer — the Deterministic/Probabilistic Split
- 48. `PostToolUse` Hooks for Automatic Code-Quality Enforcement
- 49. Plan Mode vs. Direct Execution
- 50. Iterative Refinement Techniques
- 51. Integrating Claude Code into CI/CD Pipelines

*(§52 is unused — reserved slot from an earlier draft, never assigned.)*

### Domain 4: Prompt Engineering & Structured Output (20%) — [reference/04-prompt-engineering-and-structured-output.md](reference/04-prompt-engineering-and-structured-output.md)
Explicit criteria & false-positive reduction, XML tag structuring, few-shot prompting, `tool_use` + JSON schema enforcement, validation/retry/feedback loops, the Message Batches API, and multi-instance/multi-pass review.

- 14. Multi-Instance and Multi-Pass Review Architectures *(includes the former "multi-pass" content once drafted separately as §57 — folded in; §57 is retired)*
- 15. Structured Output — Handling Missing Data in Tool Schemas *(covered within §55)*
- 19. Prompt Structuring — XML Tags for Category Isolation
- 30. Message Batches API and Batch Processing Strategy
- 31. Explicit Criteria to Improve Precision and Reduce False Positives *(§53 folded in — retired, same task statement)*
- 54. Few-Shot Prompting for Output Consistency
- 55. Enforcing Structured Output with `tool_use` and JSON Schemas
- 56. Validation, Retry, and Feedback Loops for Extraction Quality

### Domain 5: Context Management & Reliability (15%) — [reference/05-context-management-and-reliability.md](reference/05-context-management-and-reliability.md)
Long-session context preservation, large-codebase exploration, escalation/ambiguity resolution, error propagation across multi-agent systems, human review/confidence calibration, and information provenance in multi-source synthesis.

- 17. Managing Conversation Context to Preserve Critical Information
- 25. Agent Escalation Design — Self-Reported Confidence, in Detail
- 58. Escalation Triggers and Ambiguity Resolution
- 59. Error Propagation Strategies Across Multi-Agent Systems
- 60. Context Management in Large Codebase Exploration
- 61. Human Review Workflows and Confidence Calibration
- 62. Information Provenance and Uncertainty in Multi-Source Synthesis

### Out-of-Scope Exam Topics — [reference/06-out-of-scope.md](reference/06-out-of-scope.md)
Fine-tuning, billing/auth protocol details, cloud-provider specifics, computer use, vision, streaming, rate limits, benchmarking, prompt-caching/tokenization internals, and other topics the exam guide explicitly excludes.

- 63. Out-of-Scope Topics Quick Reference
