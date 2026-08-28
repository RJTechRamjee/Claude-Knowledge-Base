# Multi-Agent Architecture and Context Management

Multi-instance review, long-session context window management, XML tag prompt structuring, hub-and-spoke multi-agent architecture, agent escalation design, and prompt specificity tradeoffs.

---

## 14. Multi-Instance Review Architecture

### Why self-review misses issues (anchoring bias)
When the same Claude instance that generates code is asked to review it within the same conversation, it is anchored to its own prior reasoning — it tends to justify decisions rather than question them. A fresh instance has no attachment to those decisions and reviews the output as a stranger would.

### How "spawning" works
The Anthropic API is **stateless** — each `messages.create()` call is independent. "Spawning a second instance" simply means making a new API call with a clean `messages[]` array containing only the artifact to review, not the generation conversation history.

```python
import anthropic
client = anthropic.Anthropic()

# Instance 1 — Generator
gen_response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2000,
    system="You are a senior developer. Write clean, efficient code.",
    messages=[
        {"role": "user", "content": "Write a Python function to parse JWT tokens"}
    ]
)
generated_code = next(b.text for b in gen_response.content if b.type == "text")

# Instance 2 — Fresh reviewer (no history from Instance 1)
review_response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1000,
    system="You are a security-focused code reviewer. Find bugs and vulnerabilities.",
    messages=[
        {"role": "user", "content": f"Review this code for bugs:\n\n{generated_code}"}
    ]
)
```

### What "independent" means in practice
```
Instance 1 (Generator)            Instance 2 (Reviewer)
──────────────────────            ─────────────────────
Knows: full design reasoning      Knows: only the output code
Bias:  anchored to own choices    Bias:  none — reviews as a stranger
Result: justifies its decisions   Result: questions everything
```

### Ineffective alternatives
| Approach | Why it fails |
|---|---|
| Same instance self-reviews in same session | Anchored to prior reasoning; justifies rather than critiques |
| Same instance reviews twice in a row | Still anchored — repetition does not remove context |
| Stricter self-review system prompt | Marginally better but anchoring bias persists |
| Larger thinking budget on self-review | More reasoning, but reasoning is still biased toward original decisions |

### In Claude Code (Agent tool)
Spawning a subagent creates a fresh instance with no parent conversation history — the same independence guarantee:
```python
Agent({
    "prompt": f"Review this code for bugs:\n\n{generated_code}"
    # No parent context passed → truly independent review
})
```

### Achieving multi-instance review in Claude Code (VS Code) without the API

Three approaches, no API calls needed:

| Approach | How | Independence |
|---|---|---|
| Ask Claude to use a subagent | Prompt: "use a separate independent agent to review this" | ✅ Fresh instance, Agent tool handles it |
| New chat window | Generate in Chat 1 → copy output → open new chat → paste for review | ✅ Fresh instance, zero shared context |
| `/code-review` skill | Type `/code-review` after generation | ✅ Separate review pass |

**Subagent prompt example (stays in same conversation):**
```
Write a JWT parser function. Then spawn a separate independent agent —
with no access to our conversation — to review it fresh for bugs and security issues.
```
Claude Code invokes the Agent tool internally; the reviewer subagent receives only the code, not the generation reasoning.

**New chat is the simplest guarantee:** A new VS Code chat window = a completely stateless instance. No prompt engineering needed — independence is structural.

### Foreground subagent error handling — partial output behavior (v2.1.199+)
If a rate limit, overload, or server error cuts off a **foreground** subagent that has already produced text output, the Agent tool returns that partial output with a note that the subagent didn't finish. The coordinator receives the incomplete analysis and an explicit status so it can decide on follow-up actions.

If the subagent produced **no text output** (only tool calls) before the error, it instead fails with: `'Agent terminated early due to an API error'`.

| Subagent state at error | Agent tool result |
|---|---|
| Already produced text output | Partial text + note that subagent didn't finish |
| Only tool calls, no text output | `'Agent terminated early due to an API error'` |

This behavior requires Claude Code **v2.1.199 or later**.

### Generator-authored summaries break reviewer independence (token-saving anti-pattern)
Passing a generator-written summary to the reviewer instead of the raw diff is a common token-saving optimization that defeats the purpose of independent review.

**Why it fails:** The generator's summary frames its decisions in a self-justifying way. The reviewer then evaluates that framing — anchored to the generator's account — rather than forming an independent judgment from the raw artifact.

```
Token-saving shortcut (BAD):
  Generator writes → summary of changes → Reviewer reads summary
                                            ↑
                              Reviewer is anchored to generator's framing.
                              Independence is lost.

Correct approach:
  Generator writes → raw diff / output → Reviewer reads raw artifact
                                          ↑
                              Reviewer forms judgment from scratch.
                              Independence is preserved.
```

**What NOT to do if tokens are a concern:** Replace the raw artifact with a summary. Instead, truncate the raw artifact — cut lines, limit to changed hunks, etc. A truncated raw diff preserves independence; a summary never does.

**Why extended-thinking trace access is NOT required:** Independent reviewers don't need (and shouldn't have) the generator's thinking trace. Lacking that trace is what makes them effective — they can't be anchored to the generator's reasoning chain.

| Input to reviewer | Independence | Finding quality |
|---|---|---|
| Raw diff / raw output | ✅ Full | ✅ Unbiased |
| Truncated raw diff | ✅ Preserved | Slightly limited scope |
| Generator-authored summary | ❌ Lost (anchored to framing) | Degraded — evaluates the account, not the code |
| Generator's extended thinking trace | ❌ Lost | Worst — adopts generator's entire reasoning chain |

---

## 17. Context Window Management in Long Sessions

### The context eviction problem

The context window is finite. In long sessions exploring large codebases, **early conversation content gets compressed or evicted** as the window fills. Claude does not "remember" facts from earlier turns once they fall outside the active context — it may hallucinate plausible-sounding replacements.

```
Hour 1: Claude reads code → "OrderService extends TransactionalBase"  ← in context
Hour 4: Early turns compressed → Claude says "extends standard base controller" ← hallucinated
```

This is not a model quality problem. It is a context capacity problem.

### What does NOT fix it

| Attempted fix | Why it fails |
|---|---|
| Increase `max_tokens` | Controls output length only — not how much input context Claude can hold |
| Switch to a larger model mid-session | Larger parameter count ≠ restoring already-evicted conversation history |
| Re-read entire repo on each question | Prohibitively expensive; re-evicts other context |

### Correct pattern: scratchpad file as external memory

Have Claude write concrete findings to a file as it discovers them. The file persists on disk — outside the context window — and can be read back into context at any point.

```
# Instruction in system prompt or early user message:
"As you explore the codebase, record all concrete findings (class names,
inheritance chains, key behaviors) to findings.md. Consult findings.md
before answering any question about previously explored code."
```

```markdown
<!-- findings.md — grows throughout the session -->
## OrderService
- Extends: TransactionalBase (custom, NOT a standard base controller)
- Retry mechanism: exponential backoff with jitter, defined in TransactionalBase.retry()
- Located: src/services/order/OrderService.java:12

## PaymentGateway
- Implements: GatewayInterface, LoggableInterface
- ...
```

Claude reads `findings.md` before answering → facts survive context compression → consistent, accurate answers across a multi-hour session.

### General rule: externalize findings that must survive context compression

Any fact that needs to be reliably accessible later in a long session should be written to a file. Context is volatile; files are not.

### Lost-in-the-middle problem — aggregated multi-agent documents

LLMs attend most strongly to content at the **beginning and end** of a long input. Content buried in the middle of a large aggregated document is systematically under-attended, regardless of its importance. This causes findings from middle sections to be dropped or underweighted in synthesis steps.

**Symptom:** a synthesis step omits a finding that was present in the third of five sections of a long combined document.

**Root cause:** positional bias, not model quality. The model processed the content but did not weight it equally because of its position.

**Correct fix — key-findings summary at top + explicit section headings:**

```markdown
## Key Findings Summary
- Market sizing: TAM $4.2B, growing 12% YoY
- Competitor pricing: median $120/seat, range $80–$200
- **Regulatory risk: GDPR Article 22 requires human review for automated decisions** ← surfaced early
- Customer sentiment: NPS 42, churn driven by onboarding friction
- Distribution channels: direct sales 68%, partner 32%

---

## 1. Market Sizing
[full detail...]

## 2. Competitor Pricing
[full detail...]

## 3. Regulatory Risk
[full detail...]
...
```

The summary at the top ensures all critical findings are seen in the high-attention zone, regardless of where they sit in the body. Explicit headings give the model structural anchors to attend to each section.

**Why other approaches fail:**

| Approach | Why it fails |
|---|---|
| Split into two shorter docs (no summary/headings) | Reduces length but middle-drop-off can still occur within each half |
| Instruct synthesis step to re-read document twice | Doesn't fix positional bias structurally; adds latency |
| Reorder sections so important finding is last | Treats one symptom, not the cause; ordering may change in future runs |

---

## 19. Prompt Structuring — XML Tags for Category Isolation

When a prompt defines multiple distinct categories (each with its own criteria, rules, and examples), **uniquely named XML tags** create unambiguous boundaries that prevent cross-contamination.

### Why XML tags work

Claude is trained to respect XML tag boundaries as semantic containers. A named tag makes the scope of each block explicit — Claude applies criteria inside `<security_criteria>` only to security, and criteria inside `<correctness_criteria>` only to correctness.

```xml
<security_criteria>
  Flag: hardcoded secrets, SQL injection, missing auth checks.
  Severity: any confirmed vulnerability = critical.
  Example: `query = "SELECT * WHERE id=" + user_input` → critical.
</security_criteria>

<correctness_criteria>
  Flag: off-by-one errors, null dereferences, wrong return types.
  Severity: crash-inducing = high; wrong output = medium.
  Example: loop index starts at 1 on a 0-indexed array → high.
</correctness_criteria>

<style_criteria>
  Flag: inconsistent naming, missing docstrings, lines > 120 chars.
  Severity: all style issues = low.
</style_criteria>
```

### Why other approaches fail

| Approach | Problem |
|---|---|
| Continuous prose | No structural boundary — Claude may blend criteria across categories |
| Single bullet list, no headers | Bullet order implies grouping, but is ambiguous; Claude may mix criteria |
| Repeat full criteria in each section | Inflates prompt size; contradictions possible if copies drift |

### General rule
Use XML tags whenever a prompt has multiple **independent** sections that must not bleed into each other: criteria categories, evaluation dimensions, persona constraints, step-by-step instructions. The tag name itself signals the scope.

```xml
<!-- Good: named tags = unambiguous scope -->
<security_criteria> ... </security_criteria>
<correctness_criteria> ... </correctness_criteria>

<!-- Weaker: generic tags lose meaning with multiple instances -->
<criteria> ... </criteria>
<criteria> ... </criteria>
```

---

## 24. Multi-Agent Architecture — Hub-and-Spoke Pattern

### What it is

A multi-agent topology where one **coordinator (hub)** orchestrates multiple **specialist subagents (spokes)**. Each spoke has an isolated context and does one focused job; all cross-cutting decisions flow through the hub.

```
User
  │
  ▼
Coordinator (hub)      ← owns: orchestration, retry/fallback, sequencing, final answer
  ├── Web-search subagent   (spoke) — searches, returns results, knows nothing else
  ├── Code-review subagent  (spoke) — reviews code, returns findings, knows nothing else
  └── Data-fetch subagent   (spoke) — fetches data, returns payload, knows nothing else
```

### Coordinator responsibilities
- Dispatch tasks to the right subagent
- Receive results (including errors) from subagents
- Decide whether to retry, fall back, or synthesize partial results
- Produce the final answer to the user

### Subagent responsibilities
- Execute one focused task
- Report results **or errors** back to the coordinator
- No awareness of other subagents or overall task state

### Error handling — coordinator owns retry/fallback

When a subagent hits a transient error (e.g. network failure during web search), the subagent reports it and stops. The coordinator decides what to do next:

| Option | When to use |
|---|---|
| Retry the same subagent | Transient/recoverable errors |
| Invoke a fallback subagent | Persistent failure, alternative source available |
| Proceed without that result | Error is non-critical, partial result is acceptable |
| Abort and surface the error | Error is critical, task cannot continue |

**Do NOT** put retry logic inside each subagent — that duplicates logic across spokes and breaks the centralized control that is the defining benefit of hub-and-spoke.

### Partial results — preserve completed work on subagent failure

When one subagent in a parallel batch fails with an unrecoverable error, the coordinator should **synthesize from the completed results and annotate the gap** — not abort the entire pipeline.

**Correct pattern:**
```python
results = {}
errors = {}

for agent_name, result in subagent_outputs.items():
    if result.is_error:
        errors[agent_name] = result.error_context   # capture what failed and why
    else:
        results[agent_name] = result.content        # keep completed work

# Synthesize what we have; surface the gap honestly
report = synthesize(results)
for agent_name, ctx in errors.items():
    report.add_coverage_gap(agent_name, reason=ctx)  # annotate, don't fabricate
```

**Why each alternative is wrong:**

| Approach | Why it fails |
|---|---|
| Re-run all five subagents | Wastes four completed results; adds latency and cost for no gain |
| Abort the entire pipeline | Discards useful work; one connection error says nothing about the other four results |
| Fabricate content to fill the gap | Silently corrupts the report; downstream readers cannot distinguish real from invented |
| Synthesize partial + annotate gap | ✅ Maximally useful and honest |

**The principle:** completed subagent work has value even when the batch is incomplete. Aborting on any single failure treats partial results as worthless — almost never true in research or data-gathering pipelines. The coordinator's job is to make the most of what it has and be transparent about what it couldn't get.

### What subagents should report — transient vs unrecoverable failures

The rule: **subagents report the final outcome, not the retry history.**

| Situation | What the subagent reports to coordinator |
|---|---|
| Transient error, **resolved autonomously** | ✅ **Success** — coordinator doesn't need the retry history |
| Unrecoverable error, subagent **cannot continue** | ✅ **Error context** — coordinator decides retry/fallback |

**Transient failure resolved locally → report success only:**

If a subagent retries a step internally (e.g. a DB connection reset that succeeds on the third attempt), the task completed. The coordinator receives a success summary — not an error, not partial results, not retry detail. Surfacing resolved transient failures to the coordinator adds noise without value.

**Unrecoverable failure → report error context:**

If the subagent exhausts retries or hits a non-transient failure, it reports the error so the coordinator can decide: retry the subagent, invoke a fallback, or proceed without that result.

**Common wrong responses to a resolved transient failure:**

| Wrong response | Why it fails |
|---|---|
| Report partial results (omit the step that initially failed) | Factually wrong — the step succeeded; reporting it as missing misrepresents the outcome |
| Escalate and ask coordinator for new credentials | Wrong diagnosis — transient connection resets ≠ expired credentials |
| Report `is_error: true` with retry detail | The task succeeded; `is_error` is for actual failures, not resolved retries |

### Why not put error handling in the subagent?

Subagents operate with isolated contexts and are not designed for cross-cutting decisions. Delegating recovery to each subagent:
- Duplicates error-handling logic across every spoke
- Makes retry/fallback behaviour inconsistent
- Undermines the coordinator's ability to make globally informed decisions (e.g. "I already have enough data from other spokes — don't retry")

### Variants and competing patterns

**Hierarchical (Tree)** — hub-and-spoke at multiple levels. The top coordinator has sub-coordinators, each managing their own spokes. Use when a task has natural sub-domains too large for one coordinator.
```
Top Coordinator
  ├── Research Coordinator → [Web-search agent, Database agent]
  └── Writing Coordinator  → [Draft agent, Edit agent]
```

**Parallel Fan-out / MapReduce** — coordinator splits a task into N identical chunks, dispatches all in parallel, merges results. Spokes run the *same* task on different data (not different specialisms).
```
Coordinator → [chunk1, chunk2, chunk3] → all run in parallel → merge
```

**Sequential Pipeline** — no central coordinator; each agent's output feeds the next.
```
Extract → Summarise → Translate → Format
```
Good for linear document workflows. Weakness: one failure breaks the entire chain with no retry point.

**Peer-to-Peer / Mesh** — agents invoke each other directly; no hub. Flexible but hard to debug; context isolation breaks down quickly. Rarely used in LLM systems.

**Blackboard** — all agents share a common workspace (file, database, or memory store). Each reads state, does work, and writes back. Good for collaborative document assembly; risk of concurrent write conflicts.

**Adversarial / Debate** — two agents with opposing roles argue to a conclusion; a judge decides. Used for red-teaming, verification, and hallucination reduction.
```
Generator → Critic → Judge → final answer
```

### Pattern comparison

| Pattern | Central coordinator? | Parallelism | Best for |
|---|---|---|---|
| Hub-and-Spoke | ✅ Yes | ✅ Yes | General orchestration |
| Hierarchical | ✅ Multi-level | ✅ Yes | Very large, structured tasks |
| MapReduce | ✅ Yes | ✅ Maximum | Same task, many data chunks |
| Sequential Pipeline | ❌ No | ❌ No | Linear, ordered workflows |
| Peer-to-Peer | ❌ No | ✅ Yes | Ad-hoc collaboration |
| Blackboard | ❌ Shared state | ✅ Partial | Collaborative document building |
| Adversarial | ✅ Judge | ❌ Sequential | Verification, red-teaming |

Hub-and-spoke is Anthropic's recommended default because the coordinator gives a single place to put retry logic, fallback decisions, and result synthesis — which sequential and peer-to-peer scatter, and blackboard makes implicit.

### Key facts
- Hub-and-spoke is Anthropic's documented pattern for multi-agent orchestration in Claude Code
- The coordinator is the single point of control; subagents are stateless workers
- All inter-subagent communication routes through the coordinator — spokes never talk to each other directly
- See also: [[foreground-subagent-error-handling]] (section 14) for how the Agent tool surfaces partial output on errors

---

---

## 25. Agent Escalation Design — Self-Reported Confidence Scores

### Self-reported confidence scores are unreliable complexity proxies

When an agent generates a confidence score for its own answer (e.g. "45% confident"), that score reflects the model's *internal uncertainty estimate*, not the actual difficulty or ambiguity of the case. These two things can diverge significantly:

| Situation | Self-reported confidence | Actual case complexity |
|---|---|---|
| Clear evidence, familiar phrasing | High | Low — resolve directly |
| Clear evidence, unfamiliar phrasing | **Low** | **Low — still resolve directly** |
| Genuinely ambiguous evidence | Low | High — may warrant escalation |
| Model uncertainty about its own training | Low | Low — evidence is the ground truth |

A low confidence score should **not** automatically trigger escalation. The correct signal is the **quality of the supporting evidence**, not the score.

### Correct escalation criteria

Escalate when:
- The retrieved documentation or account data is **genuinely ambiguous or contradictory**
- The case involves **policy exceptions** requiring human judgement
- The stakes are high and the evidence does not clearly support a single answer

Do **not** escalate when:
- Supporting evidence clearly and unambiguously supports the answer, regardless of the confidence score
- The score is low due to unfamiliar phrasing or domain drift — check the evidence first

### Why numeric thresholds are wrong

Setting a rule like "escalate if confidence < 50%" treats the score as objective truth. It will:
- Over-escalate easy cases where evidence is clear but phrasing is unusual
- Under-escalate hard cases where evidence is weak but phrasing happens to match training data

### Key facts
- Self-reported confidence scores are unreliable proxies for actual case complexity
- The decision to escalate should be driven by evidence quality, not confidence score magnitude
- No category of question (e.g. billing proration) is automatically exempt from or guaranteed to trigger confidence-based escalation — the evidence is what matters
- Build escalation logic around structured evidence fields (source reliability, contradictions found, policy match) rather than raw confidence numbers

---

## 31. Prompt Specificity and False Positives vs. False Negatives

### The tradeoff
Broad, open-ended criteria ("flag anything that looks like a security risk") and narrow, checkable criteria ("flag code that concatenates user input into a SQL string") trade off in opposite directions:

| Criteria style | False positives | False negatives |
|---|---|---|
| Broad / open-ended judgment | **High** — flags superficially risky but benign code | Low — casts a wide net across categories |
| Narrow / specific and checkable | **Low** — only matches when the condition is objectively true | High — misses issues outside the named categories |

These are opposite failure modes. A prompt that reduces one *increases* the other — there is no free lunch. Choose based on which failure mode is costlier for the use case (e.g., a lint-style gate that blocks CI should minimize false positives; a first-pass triage that a human reviews after should minimize false negatives).

### Why specificity reduces false positives
Concrete, checkable conditions ("does user input reach a SQL string without parameterization? yes/no") give the model a binary test with a real answer. Vague conditions ("does this look like a risk?") invite open-ended judgment, and the model tends to flag anything superficially resembling the pattern — increasing noise.

### Common misconception
"A prompt that names only two specific risk categories is worse because it misses everything else" — this is true for **false negatives**, but the question of whether specific wording helps or hurts is often scoped to **false positives** specifically. Don't conflate the two metrics: narrowing scope trades recall for precision, it doesn't make the prompt strictly worse.
