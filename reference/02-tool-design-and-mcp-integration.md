# Domain 2 — Tool Design & MCP Integration

**Exam weight: 18%.** Covers Task Statements 2.1–2.5: tool interface design, structured MCP error responses, distributing tools across agents & `tool_choice`, integrating MCP servers into Claude Code, and selecting built-in tools (Read/Write/Edit/Bash/Grep/Glob) effectively.

**Running example used throughout:** *Scenario 1 — Customer Support Resolution Agent* (`get_customer` vs `lookup_order` disambiguation) and *Scenario 4 — Developer Productivity* (MCP server integration, built-in tool selection while exploring an unfamiliar codebase).

---

## 41. Tool Description Quality and Disambiguation

**Task Statement 2.1.**

### Descriptions are the primary selection mechanism

An LLM chooses which tool to call almost entirely from its `description` field (plus the surrounding system prompt). A minimal description — `"Retrieves customer information"` / `"Retrieves order details"` — gives the model no basis to differentiate two similarly-shaped tools, and misrouting follows: a query like *"check my order #12345"* gets routed to `get_customer` because nothing in either description says which tool owns order-shaped identifiers.

### The fix, in priority order

1. **Expand the descriptions first** — input formats it handles, example queries, edge cases, and explicit boundaries versus the similar tool. This is the correct **first step**: low effort, directly addresses the root cause (the model lacks disambiguating information), and requires no new infrastructure.
2. Only if descriptions alone don't resolve ambiguity, consider renaming for clarity or splitting an overloaded tool into purpose-specific ones (below) — higher-effort structural changes, not first-line fixes.

```python
# ❌ Before — indistinguishable to the model
{"name": "get_customer", "description": "Retrieves customer information"}
{"name": "lookup_order",  "description": "Retrieves order details"}

# ✅ After — explicit boundaries, formats, and disambiguation
{
    "name": "get_customer",
    "description": (
        "Look up a customer record by email or phone number ONLY. "
        "Returns customer_id, name, verification status. "
        "Do NOT use this for order-related queries (order numbers, shipment status) — "
        "use lookup_order for anything that includes an order number like '#12345'."
    ),
}
{
    "name": "lookup_order",
    "description": (
        "Look up an order by its order number (format: '#' followed by 4-6 digits, e.g. '#12345'). "
        "Returns order status, items, shipment tracking. "
        "Requires a verified customer_id from get_customer first — call get_customer before this "
        "if the customer has not yet been verified in this conversation."
    ),
}
```

### Why the other common fixes are wrong *as a first step*

| Alternative fix | Why it's the wrong first move |
|---|---|
| Few-shot examples showing correct routing | Adds token overhead on every request without fixing the underlying ambiguity in the tool contracts themselves |
| A routing layer that pre-parses input and pre-selects a tool by keyword | Over-engineered; bypasses the model's semantic understanding with brittle keyword matching |
| Consolidate both tools into one generic `lookup_entity` tool | A legitimate structural option (see below), but higher-effort than warranted when the root cause is simply thin descriptions |

### Splitting an overloaded tool (when descriptions alone can't fix it)

If a tool is *genuinely* trying to do two things (e.g. `analyze_document` doing extraction, summarization, *and* verification), splitting into purpose-specific tools with distinct input/output contracts removes the ambiguity structurally:

```python
# Before: one overloaded tool, ambiguous by design
{"name": "analyze_document", "description": "Analyzes a document"}

# After: three tools, each with a defined contract
{"name": "extract_data_points",        "description": "Extracts named fields (dates, amounts, parties) from a document into structured JSON."}
{"name": "summarize_content",          "description": "Produces a prose summary of a document's content."}
{"name": "verify_claim_against_source", "description": "Checks whether a specific claim is supported by a given document, returning true/false + citation."}
```

### System-prompt keyword sensitivity

Wording in the system prompt can create unintended tool associations independent of the tool descriptions themselves — e.g. a system prompt that repeatedly says "search for information" can bias the model toward a `web_search`-like tool even when a more specific tool is the correct choice. Review system-prompt wording for keyword overlap with tool names/descriptions when debugging unexpected tool selection.

---

## 42. Structured Error Responses for MCP Tools

**Task Statement 2.2.**

### The `isError` flag

MCP tool results carry a boolean `isError` flag distinguishing success from failure at the protocol level. A uniform, generic error string (`"Operation failed"`) on every failure gives the agent no basis for a recovery decision — it cannot tell a retryable timeout from a permanent policy violation from a permission problem.

### Error categories and structured metadata

| Category | Example | `isRetryable` | Agent's correct response |
|---|---|---|---|
| **Transient** | Timeout, service temporarily unavailable | `true` | Retry (possibly with backoff) |
| **Validation** | Malformed input (bad date format, missing field) | `true` (after correcting input) | Correct the input and retry |
| **Business** | Refund exceeds policy threshold | `false` | Explain to the user / route to an alternative workflow — retrying changes nothing |
| **Permission** | Agent lacks scope for this action | `false` | Escalate to a human or a higher-privilege path — retrying changes nothing |

```python
# Structured MCP error result — every field is actionable, not just human-readable
{
    "isError": True,
    "errorCategory": "business",
    "isRetryable": False,
    "message": "Refund amount $650 exceeds the $500 auto-approval threshold for this account tier.",
    "suggestedNextAction": "escalate_to_human",
}
```

### Why this matters for agent behavior

Without `errorCategory`/`isRetryable`, an agent facing any failure has two bad defaults: retry blindly (wastes calls on a business-rule rejection that will never succeed) or give up immediately (abandons a transient failure that would have succeeded on retry). Structured metadata lets the agent's own reasoning make the correct choice per failure type.

### Access failures vs. valid empty results

A tool call that **fails** (timeout, connection error) is not the same as a tool call that **succeeds with no matches** (a valid, successful query that legitimately found nothing). Conflating the two — e.g. returning an empty list for both — hides a real failure behind what looks like a normal "no results" case. Distinguish them explicitly:

```python
# Access failure — needs a retry/fallback decision
{"isError": True, "errorCategory": "transient", "isRetryable": True, "message": "Order service timed out after 3 attempts."}

# Valid empty result — success, nothing to retry
{"isError": False, "results": [], "message": "Query succeeded; no orders found for this customer."}
```

### Local recovery before escalation (subagent context)

A subagent should attempt local recovery for transient failures itself (e.g. retry a flaky connection 2–3 times) and only propagate to the coordinator the errors it **cannot** resolve — along with what was attempted and any partial results obtained. Reporting a resolved transient failure upward as if it were still a problem, or reporting it with `is_error: true` retry history attached, misrepresents a task that actually succeeded. See §59, "Error Propagation Strategies Across Multi-Agent Systems", in [05-context-management-and-reliability.md](05-context-management-and-reliability.md) for the coordinator-side handling of what a subagent does escalate.

---

## 43. Distributing Tools Appropriately Across Agents

**Task Statement 2.3.**

### Too many tools degrades selection reliability

Giving one agent access to 18 tools instead of 4–5 increases decision complexity and measurably degrades tool-selection accuracy — even when each individual tool description is well written. The fix is architectural, not prompt-level: **scope each agent to only the tools its role needs.**

```python
# ❌ One agent, every tool — degrades reliability
support_agent_tools = [get_customer, lookup_order, process_refund, escalate_to_human,
                        web_search, send_email, update_inventory, generate_invoice,
                        void_transaction, apply_credit, ... ]  # 18 tools

# ✅ Scoped per role (Scenario 1)
support_agent_tools = [get_customer, lookup_order, process_refund, escalate_to_human]  # 4 tools
```

Agents given tools outside their specialization tend to misuse them — e.g. a `synthesizer` subagent (Scenario 3) given web-search access will sometimes attempt its own searches instead of relying on the `web-searcher` subagent's findings, duplicating work and bypassing the coordinator's routing.

### Scoped cross-role tools for high-frequency needs

When a subagent needs *some* capability outside its core role frequently enough that always routing through the coordinator adds meaningful latency, give it a narrow, purpose-built tool for that specific need — not full access to the other role's tools:

```python
# synthesizer needs to fact-check simple claims often (85% of cases are simple lookups)
# Give it ONE scoped tool, not the full web-searcher toolset:
{"name": "verify_fact", "description": "Checks a single factual claim (date, name, statistic) against a quick web lookup. For deep research, this is NOT a substitute for the web-searcher subagent."}
```

Route the remaining 15% (deeper investigation) through the coordinator → `web-searcher`, as before. This is least-privilege applied to the common case, without over-provisioning the subagent for the rare case.

### `tool_choice` as an access-scoping mechanism per turn

Beyond which tools an agent *has*, `tool_choice` controls which of them can fire *on a given turn* — see §1, "Tool Choice", in [00-foundations-messages-api.md](00-foundations-messages-api.md) for the full `auto`/`any`/`tool`/`none` reference. Forcing a specific tool (`{"type": "tool", "name": "extract_metadata"}`) is the mechanism for enforcing a pipeline's first step; `"any"` guarantees some tool fires when a plain-text fallback is unacceptable (Domain 4 territory).

---

## 44. Configuring MCP Servers at the Correct Scope

**Task Statement 2.4.**

### Project-level vs. user-level — choosing where a server config lives

| Scope | File | Use for | Shared with team? |
|---|---|---|---|
| **Project** | `.mcp.json` at repo root | Servers the whole team needs — shared backend tools, a company Jira/GitHub MCP server | ✅ Yes — committed to version control |
| **User** | `~/.claude.json` (user-level config) | Personal or experimental servers — a server you're evaluating, a personal productivity integration | ❌ No — stays on your machine |

The decision rule is **who else needs it, and is it stable enough to commit**: a server every teammate must have to work in this repo → project scope; a server that's yours alone, or still being evaluated → user scope. Configuring a stable, shared tool at user scope means new team members silently lack it; configuring an experimental/personal server at project scope pushes half-finished or personal config onto every teammate.

```jsonc
// .mcp.json (project root, committed) — shared team tooling
{
  "mcpServers": {
    "jira": {
      "command": "npx",
      "args": ["-y", "@company/jira-mcp-server"],
      "env": { "JIRA_API_TOKEN": "${JIRA_API_TOKEN}" }   // env var expansion — no secret committed
    }
  }
}
```

```jsonc
// ~/.claude.json (user-level, not committed) — personal/experimental
{
  "mcpServers": {
    "my-experimental-notes-server": {
      "command": "node", "args": ["/Users/me/dev/notes-mcp/index.js"]
    }
  }
}
```

### Both scopes are discovered and available simultaneously

Tools from every configured MCP server — project *and* user scope — are discovered at connection time and available to the agent in the same session; the agent doesn't need to explicitly "switch on" either scope.

### Scope precedence for duplicate server names

When the **same server name** is defined at more than one scope, Claude Code does not merge fields — it uses the entire definition from the single **highest-precedence** scope:

```
managed (org-provided)  >  local  >  project  >  user  >  plugin-provided  >  claude.ai connectors
```

A developer's personal **local**-scoped override of a shared **project**-scoped `analytics` server wins — local always outranks project, regardless of which one is version-controlled. This is expected, resolved-automatically behavior, not a configuration error. (`managedMcpServers` is an org-provided tier that outranks even `local`, available in newer Claude Code versions — not the exam's focus, but good to know it exists if you see it in current tooling.)

### Environment variable expansion in `.mcp.json`

```jsonc
{"args": ["--region", "${API_REGION:-us-east-1}"], "env": {"API_KEY": "${MY_API_KEY}"}}
```

`${VAR:-default}` falls back to the literal default if `VAR` is unset. A bare `${VAR}` with no default, left unset, does **not** silently blank out — Claude Code emits a missing-variable warning and loads the server using the **literal, unexpanded** `${VAR}` text, which will typically fail downstream (e.g. as a bad argument or credential) rather than failing at config-parse time. This mechanic is config-wide — it works identically in `command`, `args`, `env`, `url`, and `headers` — which is what lets one `.mcp.json` be committed and shared while still tolerating machine-specific values, as long as a sensible default is supplied for anything optional.

### MCP resources — reducing exploratory tool calls

MCP servers expose **resources** (readable content catalogs — issue summaries, documentation hierarchies, database schemas) distinct from **tools** (callable actions). Referencing a resource inline with `@server:protocol://path` gives the agent visibility into available data without needing a preliminary "list what's available" tool call:

```
@docs:file://api/authentication
```

### Prefer existing community servers for standard integrations

For standard integrations (Jira, GitHub, Slack), prefer an existing, maintained community MCP server over building a custom one — reserve custom server development for genuinely team-specific workflows that no general-purpose server covers.

---

## 45. Systematic Codebase Exploration — Grep, Glob, Read Together

**Task Statement 2.5.**

### Building understanding incrementally, not exhaustively

The efficient pattern for exploring an unfamiliar codebase (Scenario 4) is: **Grep to find entry points → Read to follow imports and trace flows → repeat, narrowing** — not reading every file upfront. Reading the entire codebase before answering any question burns context on files that turn out to be irrelevant to the actual task, and it does not scale as the codebase grows.

```python
# Step 1 — Grep to locate the concept, not read everything
Grep(pattern="class OrderService", type="py")          # → finds definition location

# Step 2 — Read only the file(s) Grep pointed at
Read(file_path="src/services/order/OrderService.py")   # → follow imports/inheritance from here

# Step 3 — Grep again for the next concept surfaced by Step 2 (e.g. a base class), Read that
Grep(pattern="class TransactionalBase", type="py")
Read(file_path="src/services/base/TransactionalBase.py")
```

### Choosing the right tool for the question

| Goal | Right tool | Wrong tool (and why) |
|---|---|---|
| Find files by name/extension pattern | **Glob** (`**/*.test.tsx`) | `Grep` — searches content, not paths; misses files whose content never contains the search term |
| Search file **contents** for a symbol, error message, or import | **Grep** | `Glob` — cannot see inside files |
| Trace a function's usage across wrapper modules | **Grep** for each exported name, after identifying all export names first | Guessing one name and missing re-exports |
| Read a specific file fully | **Read** | `Bash(cat ...)` — unnecessary shell overhead |
| Run a test suite and see pass/fail + stack trace | **Bash** | `Read`/`Glob`/`Grep` — none of them execute anything |

### Managing context window constraints while exploring

Incremental exploration (above) is itself a context-management technique — reading only what each step's findings point to keeps far less irrelevant content in the window than an upfront full-repo read. For sessions long enough that this still isn't sufficient (multi-hour codebase exploration), combine with the scratchpad-file and subagent-delegation patterns in §60, "Context Management in Large Codebase Exploration", in [05-context-management-and-reliability.md](05-context-management-and-reliability.md).

---

## 23. Built-in Tool Selection — Bash vs. Read / Glob / Grep, and Edit vs. Write

**Task Statement 2.5 (continued).** The rule: **static file operations use dedicated tools; execution and live output require Bash.**

| Goal | Correct tool | Wrong tool (and why it fails) |
|---|---|---|
| Run a test suite and capture a stack trace | **Bash** | `Read` reads config, not live output; `Glob` finds files, not pass/fail status |
| Find files by name pattern | **Glob** | `Bash(find …)` works but is slower and less integrated |
| Search file contents for a symbol | **Grep** | `Bash(grep …)` works but bypasses the optimized tool |
| Read a specific file's contents | **Read** | `Bash(cat …)` — unnecessary overhead |
| Run any terminal command (build, lint, deploy, git) | **Bash** | No substitute — only Bash executes commands |

### `Edit` vs. `Write`

| Scenario | Right tool |
|---|---|
| Fix a single function name in a file | **`Edit`** (targeted, unique-text match) |
| Reformat indentation across a 900-line file | **`Write`** (after `Read`) — hundreds of fragile per-line `Edit` calls is the wrong approach |
| `Edit` fails because the anchor text isn't unique | Fall back to **`Read` + `Write`** — read the full file, transform in memory, write it back whole |

```python
content = Read(file_path="generated_output.py")
reformatted = reindent(content)
Write(file_path="generated_output.py", content=reformatted)
```

---
