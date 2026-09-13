# Domain 1 — Agentic Architecture & Orchestration

**Exam weight: 27%** — the largest domain. Covers Task Statements 1.1–1.7: agentic loop control flow, coordinator/subagent orchestration, subagent invocation & context passing, multi-step workflow enforcement/handoff, Agent SDK hooks, task decomposition strategy, and session state/resumption/forking.

**Running example used throughout:** *Scenario 1 — Customer Support Resolution Agent* (`get_customer`, `lookup_order`, `process_refund`, `escalate_to_human`; target 80%+ first-contact resolution) and *Scenario 3 — Multi-Agent Research System* (coordinator + `web-searcher`, `document-analyzer`, `synthesizer`, `report-writer` subagents).

---

## 40. Agentic Loop Anti-Patterns — What NOT to Check for Termination

**Task Statement 1.1.** The loop control flow itself is simple (§11 of [00-foundations](00-foundations-messages-api.md)): continue while `stop_reason == "tool_use"`, stop on `"end_turn"`. What the exam actually probes is which *wrong* signals candidates reach for instead.

### The three anti-patterns

| Anti-pattern | Why it's wrong | What to do instead |
|---|---|---|
| **Parsing assistant text for natural-language completion signals** (e.g. scanning for "I'm done" / "Here is the final answer") | Text is unstructured and unreliable — Claude can phrase completion arbitrarily; false positives/negatives both occur | Check `stop_reason == "end_turn"` — a structured, guaranteed field |
| **Using a fixed iteration cap (`maxTurns`) as the primary stop signal** | Terminates correctly-progressing work early, or lets truly stuck loops burn all turns before anyone notices | Use `stop_reason` as the primary signal; `maxTurns` is only a safety-net ceiling around it (§13) |
| **Checking for the presence of assistant text content as a completion indicator** | Claude can emit brief text *alongside* a `tool_use` block on the same turn (e.g. "Let me check that.") — text presence does not imply the turn is final | `stop_reason` is the only structurally reliable signal; text presence/absence is not |

```python
# ❌ Wrong — anti-pattern: text-content check
def is_done_wrong(response):
    return any(b.type == "text" and len(b.text) > 0 for b in response.content)

# ❌ Wrong — anti-pattern: iteration cap as the actual stop decision
def is_done_wrong2(turn_count):
    return turn_count >= 10   # stops "correct" work early, or masks a stuck loop for 10 turns

# ✅ Correct — the only structurally reliable signal
def is_done(response):
    return response.stop_reason == "end_turn"
```

### Model-driven vs. pre-configured decision trees

The exam distinguishes **model-driven decision-making** (Claude reasons about which tool to call next, given the current context) from a **pre-configured decision tree or fixed tool sequence** coded outside the model. The agentic loop pattern is model-driven by design: your code's job is to execute whatever tool Claude requests and feed the result back — not to pre-script which tool runs at step *N*. Hardcoding "always call `get_customer`, then always call `lookup_order`" defeats the purpose of an agentic loop and turns it into a scripted pipeline (see §38 for when a fixed pipeline is actually the right choice).

---

## 24. Multi-Agent Architecture — Hub-and-Spoke Pattern

**Task Statement 1.2.**

### What it is

```
User
  │
  ▼
Coordinator (hub)      ← owns: orchestration, retry/fallback, sequencing, final answer
  ├── web-searcher      (spoke) — searches, returns results, knows nothing else
  ├── document-analyzer (spoke) — analyzes documents, returns findings
  ├── synthesizer        (spoke) — combines findings, returns a draft
  └── report-writer      (spoke) — formats final cited report
```

The coordinator manages **all** inter-subagent communication, error handling, and information routing. Subagents never talk to each other directly — everything routes through the hub. This is Anthropic's documented default multi-agent pattern.

### Coordinator responsibilities
- Analyze query complexity and **dynamically decide which subagents to invoke** — not always the full pipeline (a simple factual query may only need `web-searcher`)
- Partition scope across subagents to minimize duplication (assign distinct subtopics/source types per agent, not the same broad query to all)
- Dispatch tasks, receive results (including errors), decide retry/fallback/synthesis
- Produce the final answer

### The narrow-decomposition failure mode (exam sample question)

If the coordinator decomposes "impact of AI on creative industries" into only `["AI in digital art", "AI in graphic design", "AI in photography"]`, every subagent can execute flawlessly and the *system* still fails — music, writing, and film are silently missing from the report. Each subagent worked correctly within its assigned scope; the root cause is upstream, in the coordinator's task decomposition, not in any spoke. This is the single most exam-tested failure mode in this domain: **when subagents each report success but a system output has a coverage gap, check the coordinator's decomposition logs before blaming any subagent.**

### Iterative refinement loops

The coordinator should evaluate the synthesis output for gaps, re-delegate to search/analysis subagents with *targeted* follow-up queries, and re-invoke synthesis — rather than treating a single decomposition pass as final.

```python
draft = synthesize(findings)
gaps = coordinator_evaluate_coverage(draft, original_topic)   # e.g. "no coverage of music/writing/film"
while gaps:
    targeted_findings = [invoke_subagent("web-searcher", f"AI impact on {gap}") for gap in gaps]
    findings.extend(targeted_findings)
    draft = synthesize(findings)
    gaps = coordinator_evaluate_coverage(draft, original_topic)
```

### Parallel subagent execution

Emit multiple subagent invocations **in a single coordinator response/turn**, not across separate sequential turns, to get real latency improvement:

```python
# Coordinator emits both Task-tool calls in the same turn → run concurrently
# (see §36 for the Task tool / AgentDefinition mechanics)
results = await asyncio.gather(
    invoke_subagent("web-searcher", "AI impact on the music industry"),
    invoke_subagent("document-analyzer", uploaded_papers),
)
```

### Error handling — coordinator owns retry/fallback, never each spoke

| Situation | What the subagent reports | What the coordinator does |
|---|---|---|
| Transient failure, **resolved internally** by the subagent (e.g. a DB reconnect succeeds on retry #3) | ✅ Success only — no retry history, no partial-result flag | Nothing extra — treats it as a normal success |
| Unrecoverable failure (timeout exhausted, hard error) | Structured error context: failure type, attempted query, partial results, alternatives tried | Retry the subagent / invoke a fallback / proceed with partial results and annotate the gap |

```python
results, errors = {}, {}
for name, result in subagent_outputs.items():
    if result.is_error:
        errors[name] = result.error_context           # capture what failed and why
    else:
        results[name] = result.content                 # keep completed work

report = synthesize(results)
for name, ctx in errors.items():
    report.add_coverage_gap(name, reason=ctx)           # annotate, don't fabricate, don't abort
```

Do **not** put retry/fallback *decision* logic inside each subagent — that duplicates logic across every spoke and breaks the centralized control that is the defining benefit of hub-and-spoke. (Full detail on structured error propagation: §59, "Error Propagation Strategies Across Multi-Agent Systems", in [05-context-management-and-reliability.md](05-context-management-and-reliability.md).)

### Pattern comparison (other topologies, for contrast)

| Pattern | Central coordinator? | Best for |
|---|---|---|
| **Hub-and-Spoke** | ✅ Yes | General orchestration — Anthropic's default |
| Hierarchical (tree) | ✅ Multi-level | Very large, structured tasks with natural sub-domains |
| MapReduce / parallel fan-out | ✅ Yes | Same task across many data chunks |
| Sequential Pipeline | ❌ No | Linear, ordered, predictable workflows (see §38) |
| Peer-to-Peer / Mesh | ❌ No | Rarely used — hard to debug, context isolation breaks down |
| Adversarial / Debate | ✅ Judge | Red-teaming, verification |

---

## 36. Subagent Spawning — the `Task`/`Agent` Tool and `AgentDefinition` (Agent SDK)

**Task Statement 1.3.** *Verified against `code.claude.com/docs/en/agent-sdk`, including a second independent verification pass.*

### The `Task` tool (exam terminology) — now named `Agent` in current tooling

The exam guide's own language for this Task Statement is explicit: *"The Task tool as the mechanism for spawning subagents, and the requirement that allowedTools must include 'Task' for a coordinator to invoke subagents."* Answer exam questions using that framing — `"Task"` is the name to recognize.

**Current-product accuracy note (the tool has since been renamed):** in the coordinator's `tool_use` blocks, the current Claude Code / Agent SDK tool for spawning subagents is named **`Agent`**, not `Task` — current code examples register `"Agent"` in `allowed_tools`/`allowedTools`. `Task` is the *legacy* name (Claude Code versions before v2.1.63 used it in `tool_use` blocks, and it still appears as the tool's name in the `system:init` tools list for backward compatibility). Also, listing the tool in `allowed_tools` is not a strict prerequisite the way this reference previously stated — `allowed_tools` governs *auto-approval* (skipping a permission prompt), and the subagent-spawning tool (`Agent`/`Task`) is documented as one of the tools that runs without asking even when not explicitly listed. Treat "allowedTools must include Task" as the exam's expected knowledge point, and "Agent, not a hard allowlist requirement" as the current-tooling reality if you're building against the SDK today.

```python
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition

options = ClaudeAgentOptions(
    allowed_tools=["Agent", "Read", "Grep"],   # current tool name; "Task" is the exam/legacy name for the same mechanism
    agents={
        "web-searcher": AgentDefinition(
            description="Searches the web for a given subtopic and returns dated, sourced findings.",
            prompt="You are a web-research subagent. Search only for the assigned subtopic. "
                   "Return each finding as {claim, evidence_excerpt, source_url, published_date}.",
            tools=["WebSearch"],
        ),
        "document-analyzer": AgentDefinition(
            description="Analyzes uploaded documents for claims relevant to the research topic.",
            prompt="Extract claims with excerpt, document name, page/section, and any stated date.",
            tools=["Read", "Grep"],
        ),
    },
)

async for message in query(prompt="Research the impact of AI on creative industries", options=options):
    ...
```

### `AgentDefinition` fields

| Field | Required? | Purpose |
|---|---|---|
| `description` | ✅ | What this subagent does — the coordinator model uses this to decide *when* to invoke it |
| `prompt` | ✅ | The subagent's system prompt / instructions |
| `tools` | optional | Restricts this subagent to a named subset (see §43, "Distributing Tools Appropriately Across Agents", in [02-tool-design-and-mcp-integration.md](02-tool-design-and-mcp-integration.md)) |
| `model` | optional | Override the model for this subagent (e.g. a cheaper model for a narrow task) |
| `disallowedTools` / `skills` / `mcpServers` / `maxTurns` / `permissionMode` | optional | Further scoping per subagent type |

### Subagents do not automatically inherit parent context

A subagent invoked via `Agent` (called `Task` in the exam guide and in older tooling) starts with an **isolated context** — it does not automatically receive the coordinator's conversation history or the outputs of other subagents. Anything a subagent needs must be **explicitly included in its prompt/task description**:

```python
# ❌ Wrong — assumes the synthesis subagent can see prior subagents' raw output
Agent(agent="synthesizer", prompt="Now synthesize the findings.")

# ✅ Correct — findings are explicitly embedded in the prompt
Agent(
    agent="synthesizer",
    prompt=(
        "Synthesize the following findings into a cited report.\n\n"
        f"Web search findings:\n{json.dumps(web_findings, indent=2)}\n\n"
        f"Document analysis findings:\n{json.dumps(doc_findings, indent=2)}"
    ),
)
```

### Structured data over prose — preserving attribution across the handoff

Pass findings as structured objects (claim, evidence excerpt, source URL/document name, page number, date) rather than freeform prose summaries, so the receiving subagent can preserve attribution instead of re-deriving or losing it:

```python
finding = {
    "claim": "Generative tools reduced average concept-art turnaround by ~40%.",
    "evidence_excerpt": "...average time-to-first-draft fell from 6 days to 3.5...",
    "source_url": "https://example.org/report-2026",
    "published_date": "2026-02-14",
}
```

### Fork-based session management for divergent exploration

See §37, "`fork_session` — Branching a Session (Agent SDK)", below — a related but distinct mechanism for branching a *session* (not spawning a subagent) from a shared baseline.

---

## 39. Multi-Step Workflows — Enforcement and Handoff Patterns

**Task Statement 1.4.**

### Programmatic enforcement vs. prompt-based guidance

| | Prompt-based guidance | Programmatic enforcement |
|---|---|---|
| Mechanism | System-prompt instruction ("always verify identity first") | A hook or gate that blocks the tool call outright |
| Compliance | Probabilistic — has a non-zero failure rate | Deterministic — cannot be bypassed |
| Use when | Ordering preference, non-critical | Financial/compliance-critical ordering (e.g. identity verification before any refund) |

Exam sample: an agent that skips `get_customer` in 12% of cases and calls `lookup_order` on a stated name alone, occasionally misidentifying accounts. The fix is **not** a stronger system-prompt instruction or few-shot examples — both are prompt-based and leave a non-zero failure rate on a case with financial consequences. The fix is a **programmatic prerequisite gate** (implemented as a `PreToolUse` hook — see §21) that blocks `lookup_order`/`process_refund` until `get_customer` has returned a verified customer ID in this turn's context.

```python
# .claude/settings.json — PreToolUse hook enforcing verification order
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "lookup_order|process_refund",
        "hooks": [{"type": "command", "command": "python3 scripts/require_verified_customer.py"}]
      }
    ]
  }
}
```

`require_verified_customer.py` checks whether a verified `customer_id` already exists in this session's state (e.g. written by a prior successful `get_customer` call) and exits non-zero (deny) if not — see §21 for the exact hook return-shape mechanics.

### Decomposing multi-concern requests

A single customer message can carry multiple distinct issues (e.g. "my order #4821 never arrived, *and* I was double-charged"). Decompose into distinct items, investigate each **in parallel** using shared context, then synthesize one unified resolution — rather than resolving the first-mentioned issue and dropping the second, or running them as two disconnected turns that lose shared context (e.g. the same verified `customer_id`).

### Structured handoff summaries for human escalation

A human agent picking up an escalation typically has **no access to the conversation transcript**. The handoff must be self-contained:

```python
handoff = {
    "customer_id": "CUST-88213",
    "root_cause": "Refund policy is silent on competitor price-matching; customer requests a match to a competitor's current lower price.",
    "amount_in_question": 42.50,
    "attempted_resolution": "Offered standard 10% loyalty discount; customer declined, reiterated price-match request.",
    "recommended_action": "Escalate to pricing team — policy gap, not a customer-service judgment call.",
}
escalate_to_human(**handoff)
```

Compare with §58, "Escalation Triggers and Ambiguity Resolution", in [05-context-management-and-reliability.md](05-context-management-and-reliability.md) for *when* to escalate — this section covers *what* to hand off once the decision is made.

---

## 21. Agent SDK / Claude Code Hooks — Tool Call Interception and Data Normalization

**Task Statement 1.5.** Hooks are the mechanism for **deterministic** guarantees where a system prompt instruction would only be **probabilistic**.

### Hook types

| Hook | Runs | Can block? | Use for |
|---|---|---|---|
| `PreToolUse` | Before the tool executes | ✅ Yes — set a deny decision | Enforcing preconditions, blocking policy-violating calls |
| `PostToolUse` | After the tool executes | ❌ No — tool already ran | Normalizing heterogeneous result data, logging, side effects |
| `Notification` | On status/notification events | ❌ No | Alerting |
| `Stop` | When Claude finishes a turn | ❌ No | Summaries, notifications |

A `Notification` hook cannot enforce ordering: the tool **executes before** the notification fires, so a warning logged in a `Notification` hook means the refund already ran. Only `PreToolUse` can prevent execution.

### `PreToolUse` — blocking a policy-violating action (Scenario 1: refund threshold)

```python
def pre_tool_hook(tool_name, tool_input):
    if tool_name == "process_refund":
        amount = tool_input["amount"]
        if isinstance(amount, str):
            amount = float(amount.replace("$", "").replace(",", ""))   # normalize + enforce together

        if amount > 500:
            return {"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionReason": f"${amount} exceeds the $500 auto-approval threshold",
            }}
            # caller/coordinator should redirect this case to escalate_to_human

        return {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "updatedInput": {**tool_input, "amount": amount},
        }}
```

Return shape: a `hookSpecificOutput` object with `hookEventName`, `permissionDecision` (`"allow"` / `"deny"` / `"ask"` — there is no `"defer"`), an optional `permissionReason`, and — only on `PreToolUse` — an optional `updatedInput` to rewrite the tool call before it runs.

**Rule:** if a normalize step and an enforce step must see each other's output, put them in **one** hook — `updatedInput` from one `PreToolUse` hook does **not** propagate to a second `PreToolUse` hook; each hook receives the *original* input.

### `PostToolUse` — normalizing heterogeneous MCP tool output (Scenario 1 / 3)

Different backend tools return dates as Unix timestamps, ISO 8601 strings, or numeric status codes inconsistently. A `PostToolUse` hook normalizes this **before** the model reasons over it, so the model never has to hold multiple date formats in its head:

```python
def post_tool_hook(tool_name, tool_output):
    if tool_name == "lookup_order":
        tool_output["order_date"] = normalize_to_iso8601(tool_output["order_date"])
        tool_output["status"] = STATUS_CODE_MAP.get(tool_output["status_code"], "unknown")
    return tool_output
```

### Multiple `PreToolUse` hooks on the same event — most-restrictive wins

```
deny > ask > allow > {} (abstain)
```

If an identity-verification hook returns `deny` and a fraud-score hook returns `allow` for the same call, the call is **blocked** — `deny` from any hook overrides `allow` from every other hook. (There is no `defer` decision value — only `allow`/`deny`/`ask`.)

### Deterministic (hooks) vs. probabilistic (prompt) — the decision rule

| Requirement | Use |
|---|---|
| "Always verify identity before a refund, no exceptions" | `PreToolUse` hook (hard gate) |
| "Prefer a friendly tone" | System prompt (guidance is fine — no compliance stakes) |
| "Never approve a refund over $500 without a human" | `PreToolUse` hook (financial/compliance-critical) |
| "Generally try get_customer before lookup_order" | Prompt/few-shot *if* the cost of an occasional miss is low; a hook if it isn't (see §39) |

> See §46/§47, "Choosing the Right Claude Code Configuration Mechanism" / "Enforcement Layer vs. Guidance Layer", in [03-claude-code-configuration-and-workflows.md](03-claude-code-configuration-and-workflows.md) for the broader decision framework across CLAUDE.md / rules / skills / hooks / permissions — one of the most heavily tested distinctions in Domain 3, and the same "deterministic vs. probabilistic" logic drives both.

---

## 38. Task Decomposition Strategies for Complex Workflows

**Task Statement 1.6.**

### Fixed pipeline (prompt chaining) vs. dynamic adaptive decomposition

| | Fixed pipeline (prompt chaining) | Dynamic adaptive decomposition |
|---|---|---|
| Subtasks | Predetermined, sequential, known in advance | Generated based on what is discovered at each step |
| Best for | Predictable, multi-aspect reviews (e.g. "analyze each file, then run a cross-file pass") | Open-ended investigation where scope isn't knowable upfront |
| Failure mode if misapplied | Using a fixed pipeline for open-ended work misses discoveries the plan didn't anticipate | Using full dynamic decomposition for a predictable review adds needless coordination overhead |

### Prompt chaining example — large code review (Scenario 5: CI)

```
Step 1: for each changed file → local analysis pass (bugs, style, missing tests, in isolation)
Step 2: one cross-file integration pass → data flow between files, contradictory findings, duplicated logic
```

Splitting this way avoids **attention dilution**: a single pass across 14 changed files produces inconsistent depth (detailed feedback for some files, superficial for others) and can flag the same pattern as a problem in one file while approving it in another. Per-file passes give consistent depth; the separate integration pass is where cross-file issues belong — merging both concerns into one pass is what caused the dilution in the first place.

### Dynamic decomposition example — open-ended task (Scenario 4: dev productivity)

"Add comprehensive tests to a legacy codebase" cannot be decomposed upfront — you don't yet know which modules are undertested or which are highest-risk. The adaptive approach:

```python
structure = explore_agent.map_codebase_structure()          # phase 1: what exists
high_impact = explore_agent.identify_high_impact_areas(structure)  # phase 2: what matters, informed by phase 1
plan = build_prioritized_test_plan(high_impact)              # phase 3: adapts as dependencies are discovered
```

Each phase's subtasks are generated from the *previous* phase's findings — not fixed at the start. This is the same principle as §24's narrow-decomposition failure: a plan fixed too early (before discovery) systematically under-covers the true scope.

### Decision rule

- Scope and steps are **knowable in advance**, and depth/consistency matter more than adaptability → **prompt chaining**
- Scope is **discovered as you go**, and a fixed plan would systematically miss things → **dynamic decomposition**

---

## 12. Session Management (Claude Code CLI and Agent SDK)

**Task Statement 1.7 (part 1).**

### Named sessions

```bash
claude --name "migration-task"      # start a named session
/rename "migration-task"            # rename during a session
claude --resume "migration-task"    # resume by name
claude --resume                     # no argument → interactive picker
```

### Resuming by explicit `session_id` — the CI/parallel-job pattern

When multiple `claude -p` invocations run concurrently (e.g. parallel CI jobs reviewing different PRs — Scenario 5), `--continue` is unreliable because it attaches to the *most recent* session by timestamp, which may belong to a different concurrent job. Capture `session_id` from the first call's JSON output and pass it explicitly:

```bash
RESPONSE=$(git diff origin/main | claude -p 'review this PR for bugs' --output-format json)
SESSION_ID=$(echo "$RESPONSE" | jq -r '.session_id')
claude -p 'what is the most critical issue you found?' --resume "$SESSION_ID"
```

### Informing a resumed session about file changes

When resuming a session after the underlying code has changed, tell the agent explicitly which files changed rather than assuming it will re-detect drift — stale tool results (a file read before the edit) otherwise silently persist in context. For targeted re-analysis: `claude --resume "session-name" "Files auth.py and db/pool.py changed since we last spoke — re-check just those against your earlier findings."`

### Resume vs. fresh session with an injected summary

| Situation | Use |
|---|---|
| Prior context is still mostly valid, just continuing the same investigation | `--resume` |
| Prior tool results are now stale (files changed, external state moved on) | Start fresh, inject a **structured summary** of what's still true, rather than resuming and hoping the model reconciles stale reads itself |

---

## 37. `fork_session` — Branching a Session (Agent SDK)

**Task Statement 1.7 (part 2).** *Verified against `code.claude.com/docs/en/agent-sdk/sessions`.*

`fork_session` (Python) / `forkSession` (TypeScript) is an option passed alongside `resume` to `query()`. It creates a **new, independent session** that starts as a copy of the resumed session's history — giving it its own new session ID — rather than continuing to mutate the original session:

```python
from claude_agent_sdk import query, ClaudeAgentOptions

# Baseline: shared codebase analysis already happened in session `baseline_id`

# Branch A — explore a REST-based refactor
async for msg in query(
    prompt="Refactor this using a REST API layered architecture.",
    options=ClaudeAgentOptions(resume=baseline_id, fork_session=True),
):
    ...

# Branch B — explore an event-driven refactor, from the SAME baseline, independently
async for msg in query(
    prompt="Refactor this using an event-driven architecture instead.",
    options=ClaudeAgentOptions(resume=baseline_id, fork_session=True),
):
    ...
```

Both branches see the same shared analysis baseline but diverge independently from that point — exploring Branch A does not affect Branch B, and neither mutates the original `baseline_id` session. This is the correct mechanism for "compare two approaches from the same starting analysis" (e.g. two testing strategies, two refactoring directions), as distinct from `--resume` (continues the *same* session in place) and from spawning a `Task` subagent (isolated context, not a branch of *this* conversation's history).

| Mechanism | Continues same session? | New independent session created? | Shares prior history? |
|---|---|---|---|
| `--resume` / `resume=` (no fork) | ✅ Yes, in place | ❌ No | ✅ Yes — same session |
| `resume=` + `fork_session=True` | ❌ No | ✅ Yes | ✅ Yes — copied at fork point, then diverges |
| `Task` subagent spawn (§36) | N/A — not a session concept | N/A | ❌ No — isolated context, explicit prompt only |

---
