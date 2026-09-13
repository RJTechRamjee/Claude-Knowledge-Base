# Out-of-Scope Exam Topics

A deliberate anti-scope list. These are real, current Claude/Anthropic topics — some of them (newer model families, prompt caching mechanics, streaming) are already partially documented elsewhere in this knowledge base for non-exam purposes — but the **Claude Certified Architect – Foundations** exam guide explicitly excludes them. Don't spend study time here; don't expect exam questions on them; and don't let newer live-API detail (e.g. from the `claude-api` skill) bleed into exam-scoped answers, since the exam targets `claude-sonnet-4-6` specifically (see §6 in [00-foundations-messages-api.md](00-foundations-messages-api.md)).

---

## 63. Out-of-Scope Topics Quick Reference

Verbatim from the exam guide's Appendix, Section 17:

| Topic | Note |
|---|---|
| Fine-tuning Claude models or training custom models | Not part of the Agent SDK / API / Claude Code / MCP surface tested |
| Claude API authentication, billing, or account management | Operational/account concerns, not architecture |
| Detailed implementation of specific programming languages or frameworks | Beyond what's needed for tool/schema configuration |
| Deploying or hosting MCP servers (infrastructure, networking, container orchestration) | The exam tests MCP *tool/resource design* and *client-side configuration*, not server hosting |
| Claude's internal architecture, training process, or model weights | Not testable from a practitioner's vantage point |
| Constitutional AI, RLHF, or safety training methodologies | Research/training topics, not deployment architecture |
| Embedding models or vector database implementation details | Out of scope even though relevant to some RAG systems |
| Computer use (browser automation, desktop interaction) | A real built-in tool (current type strings: `computer_20250124`, `computer_20251124`, `computer_toolset_20260801`), but not tested here |
| Vision/image analysis capabilities | Not tested, despite `image` being a real content-block type |
| Streaming API implementation or server-sent events | Not tested — the exam's tool-loop examples are all non-streaming |
| Rate limiting, quotas, or API pricing calculations | Operational, not architectural |
| OAuth, API key rotation, or authentication protocol details | Even though MCP `oauth`/`headersHelper` config is in scope (§44 in [02-tool-design-and-mcp-integration.md](02-tool-design-and-mcp-integration.md)), the underlying auth *protocol* mechanics are not |
| Specific cloud provider configurations (AWS, GCP, Azure) | Bedrock/Vertex/Foundry specifics are out of scope |
| Performance benchmarking or model comparison metrics | Not testable knowledge for this certification |
| Prompt caching implementation details (beyond knowing it exists) | You should know caching *exists* as a cost lever; breakpoint placement, invalidation mechanics, etc. are not tested |
| Token counting algorithms or tokenization specifics | Not tested |

### Why this matters for how you study

The exam's "In-Scope Topics" list (guide Appendix, Section 17) and the Technologies/Concepts list are both scoped tightly around: the Agent SDK's agentic loop / hooks / subagents, MCP tool and resource design, Claude Code's configuration surface (CLAUDE.md, rules, skills, commands, plan mode), `tool_use` + JSON schema structured output, the Message Batches API, and context/reliability patterns (escalation, error propagation, provenance). Live-API features that post-date or sit outside that scope — newer model families (Opus 5, Sonnet 5, Fable 5/5.1), fast mode, task budgets, compaction betas, context editing, Managed Agents, the Tool Runner helper, `inference_geo`, Workload Identity Federation — are real and current (see the `claude-api` skill for that surface) but are **not** exam content. If a practice question or this reference ever seems to reference one of them, treat that as scope drift to flag, not something to study for this specific certification.

---
