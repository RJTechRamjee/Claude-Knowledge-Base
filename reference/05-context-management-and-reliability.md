# Domain 5 — Context Management & Reliability

**Exam weight: 15%.** Covers Task Statements 5.1–5.6: preserving critical information across long interactions, escalation/ambiguity resolution, error propagation across multi-agent systems, context management in large codebase exploration, human review workflows/confidence calibration, and information provenance/uncertainty handling in multi-source synthesis.

**Running example used throughout:** *Scenario 1 — Customer Support Resolution Agent* (escalation calibration) and *Scenario 3 — Multi-Agent Research System* (error propagation, provenance, coverage gaps) and *Scenario 6 — Structured Data Extraction* (human review routing).

---

## 17. Managing Conversation Context to Preserve Critical Information

**Task Statement 5.1.**

### The context eviction problem

Context is finite. In long sessions, early content gets compressed or evicted as the window fills — Claude does not "remember" facts from earlier turns once they fall outside active context, and may hallucinate a plausible-sounding replacement instead of admitting it doesn't know:

```
Hour 1: Claude reads code → "OrderService extends TransactionalBase"  ← in context
Hour 4: Early turns compressed → Claude says "extends a standard base controller" ← hallucinated
```

This is a context-**capacity** problem, not a model-quality problem — increasing `max_tokens` (output only), or switching to a larger model mid-session (more parameters ≠ restoring evicted history), fixes neither.

### Progressive summarization risk — losing precise values

Summarizing a long conversation risks condensing numerical values, percentages, dates, and customer-stated expectations into vague prose ("the customer mentioned some pricing concern") that loses exactly the detail later turns need. The fix is a persistent **"case facts" block** — extracted transactional facts (amounts, dates, order numbers, statuses) carried in every prompt *outside* the summarized history, not vulnerable to the summarization pass:

```
<case_facts>
  customer_id: CUST-88213
  order_id: #58291, ordered 2026-02-11, amount $142.50
  prior_offer: 10% loyalty discount (declined)
  customer_request: price-match a competitor's current $128 listing
</case_facts>
```

### Trimming verbose tool outputs before they accumulate

A raw order-lookup response with 40+ fields, when only 5 are relevant to a return/refund flow, consumes context disproportionately to its value if passed through unfiltered. Trim to only the relevant fields before the result enters context — do this consistently, not just for the first call, since accumulated verbose results compound over a multi-turn session.

### The "lost in the middle" effect

Models attend most strongly to content at the **beginning and end** of a long input; content buried in the middle of a large aggregated document (e.g. the third of five sections in a synthesized research report) is systematically under-attended regardless of its actual importance — this is a positional bias, not a quality signal about that content.

**Fix:** a key-findings summary at the very top of the aggregated document, plus explicit section headers throughout, so critical findings are seen in the high-attention zone regardless of where they physically sit in the body:

```markdown
## Key Findings Summary
- Market sizing: TAM $4.2B, growing 12% YoY
- **Regulatory risk: GDPR Article 22 requires human review for automated decisions** ← surfaced early
---
## 1. Market Sizing
[full detail...]
## 3. Regulatory Risk
[full detail...]
```

Reordering sections so the important finding lands last, or splitting into two shorter documents without headers, treats a symptom rather than the structural cause.

---

## 60. Context Management in Large Codebase Exploration

**Task Statement 5.4.**

### Scratchpad files as external memory

Have Claude write concrete findings to a file as it discovers them — the file persists outside the context window and can be re-read at any point, so facts survive context compression, instead of the model drifting into "typical pattern" guesses once the specific class it found earlier has been evicted:

```
findings.md
## OrderService
- Extends: TransactionalBase (custom, NOT a standard base controller)
- Located: src/services/order/OrderService.java:12
```

### Subagent delegation for verbose discovery

Spawn a subagent for a specific, bounded discovery question ("find all test files," "trace the refund flow's dependencies") while the main/coordinator agent stays at a high level of coordination — this isolates verbose exploration output from the main conversation, same principle as `context: fork` for skills (§16 in [03-claude-code-configuration-and-workflows.md](03-claude-code-configuration-and-workflows.md)). Summarize key findings from one exploration phase and inject that summary as the seed context for the next phase's subagents, rather than letting each new subagent re-explore from scratch.

### `/compact` for mid-session context relief

Use `/compact` to manually trigger context compaction mid-session once verbose discovery output has filled a meaningful fraction of the window — the right tool when exploration itself (not conversation length generally) is what's crowding context.

### Crash recovery via structured state manifests

For crash recovery in a long-running multi-agent job: have each agent export its state to a known location (a manifest) as it completes work; on resume, the coordinator loads the manifest and injects only what's needed to continue, rather than re-running completed work from scratch.

---

## 58. Escalation Triggers and Ambiguity Resolution

**Task Statement 5.2.**

### Appropriate escalation triggers

| Trigger | Escalate? |
|---|---|
| Customer **explicitly asks for a human** | ✅ Immediately — honor the request without first attempting autonomous resolution |
| A genuine **policy gap** — the policy is silent on this exact request (e.g. competitor price-matching, when policy only covers own-site price adjustments) | ✅ Yes — this is a policy exception requiring human judgment, not "just a complex case" |
| Agent cannot make **meaningful progress** (contradictory account data, tool failures with no fallback) | ✅ Yes |
| A **routine, well-covered** case (standard damage replacement with photo evidence, squarely inside policy) | ❌ No — resolve autonomously |

### Honoring an explicit request vs. offering to help first

If a customer's *first* message already demands a human, escalate immediately — do not spend a turn attempting resolution first. If the customer is frustrated but the issue is squarely within the agent's capability, **acknowledge the frustration and offer resolution**; escalate only if they reiterate the preference for a human after that offer. These are different situations with different correct responses — collapsing them into one rule (either "always try first" or "always escalate on any frustration signal") gets one of the two wrong.

### Why self-reported confidence and sentiment are unreliable escalation proxies

A model's own confidence score reflects its *internal uncertainty*, not the case's actual complexity — these diverge in both directions:

| Situation | Self-reported confidence | Actual complexity |
|---|---|---|
| Clear evidence, unfamiliar phrasing | **Low** | Low — still resolve directly |
| Genuinely ambiguous/contradictory evidence | Low | **High** — may warrant escalation |

The correct signal is **evidence quality** (is the account data clear and unambiguous, does policy clearly address this case), not the magnitude of a self-reported number. A fixed threshold rule ("escalate if confidence < 50%") systematically over-escalates easy-but-unfamiliar-phrasing cases and under-escalates hard-but-familiar-phrasing ones. The same logic applies to sentiment-based escalation: frustration doesn't correlate with case complexity, so an escalation trigger tied to negative-sentiment detection solves a different problem than "is this case actually hard."

### Multiple customer matches — ask, don't guess

When a lookup returns multiple matching customer records, the correct response is to **request an additional identifier** from the customer (e.g. "can you confirm the billing zip code?") — not to heuristically pick the most-likely match. Selecting by heuristic risks acting on the wrong account entirely, which is a far worse failure than asking one extra clarifying question.

---

## 25. Agent Escalation Design — Self-Reported Confidence, in Detail

**Task Statement 5.2 (supporting detail for §58).**

### Why numeric thresholds on self-reported confidence are wrong

Setting "escalate if confidence < 50%" treats the score as objective ground truth about the case, when it is really a proxy for the model's own uncertainty about its training-data familiarity with the phrasing. No category of question (e.g. billing proration) is automatically exempt from or guaranteed to trigger confidence-based escalation — evidence quality is what matters in every category.

### Building escalation logic around structured evidence, not raw confidence

```python
escalation_signal = {
    "source_reliability": "high",       # was the account data internally consistent?
    "contradictions_found": False,       # did multiple sources/records disagree?
    "policy_match": "exact",             # "exact" | "partial" | "silent"
}
should_escalate = (
    escalation_signal["contradictions_found"]
    or escalation_signal["policy_match"] == "silent"
    or escalation_signal["source_reliability"] == "low"
)
```

This routes on the actual drivers of case difficulty, not a single scalar the model reports about itself.

---

## 59. Error Propagation Strategies Across Multi-Agent Systems

**Task Statement 5.3.** Complements the coordinator-side handling in §24, "Multi-Agent Architecture — Hub-and-Spoke Pattern", in [01-agentic-architecture-and-orchestration.md](01-agentic-architecture-and-orchestration.md).

### Structured error context enables intelligent recovery

A subagent reporting a failure should return: failure type, what was attempted, any partial results obtained, and possible alternatives — not a generic status string like `"search unavailable"`, which hides everything the coordinator would need to decide what to do next.

```python
# ✅ Structured — the coordinator can actually decide something from this
{
    "status": "error",
    "failure_type": "timeout",
    "attempted_query": "AI adoption statistics in independent music production 2025-2026",
    "partial_results": [...],           # whatever was retrieved before the timeout
    "suggested_alternative": "retry with a narrower date range",
}

# ❌ Generic — coordinator has nothing to act on
{"status": "search unavailable"}
```

### Access failures vs. valid empty results (again, at the multi-agent level)

A timed-out subagent and a subagent that successfully found zero matching results are different outcomes requiring different coordinator responses — conflating them (e.g. by silently returning an empty list for both) either hides a real failure or, worse, marks it as success. See also §42 in [02-tool-design-and-mcp-integration.md](02-tool-design-and-mcp-integration.md) for the same distinction at the individual-tool-call level.

### Two anti-patterns: silent suppression, and total abort

| Anti-pattern | Why it fails |
|---|---|
| Catch the failure inside the subagent, return an empty result marked "success" | Coordinator believes the query succeeded with nothing to find — a false negative that corrupts downstream synthesis |
| Propagate any single subagent failure straight to a top-level handler that terminates the entire workflow | Discards all other subagents' completed work over one recoverable or non-critical failure |

### Correct pattern: proceed on partial results, annotate the gap

```python
results, errors = {}, {}
for name, outcome in subagent_outputs.items():
    (errors if outcome.is_error else results)[name] = outcome.content_or_error_context

report = synthesize(results)
for name, ctx in errors.items():
    report.add_coverage_gap(name, reason=ctx)   # honest, not fabricated
```

Re-running every subagent from scratch after one failure wastes the other completed work for no gain; fabricating content to paper over the gap silently corrupts the report in a way readers cannot detect.

### What subagents report for internally-resolved transient failures

If a subagent retries a transient failure internally and succeeds (e.g. a DB reconnect on attempt 3), it reports **success only** — not partial results, not `is_error`, not the retry history. The task completed; surfacing resolved noise to the coordinator adds nothing.

---

## 61. Human Review Workflows and Confidence Calibration

**Task Statement 5.5.**

### Aggregate accuracy can hide segment-level failure

A 97% overall extraction accuracy figure can mask a document type or field that performs far worse than average — e.g. handwritten forms at 60% accuracy, buried inside an aggregate that looks healthy. Validate accuracy **by document type and by field**, not only in aggregate, before reducing human review based on the aggregate number.

### Two distinct mechanisms — don't conflate them

| Mechanism | Purpose | What it answers |
|---|---|---|
| **Stratified random sampling** of *high-confidence* extractions | Ongoing measurement — is the error rate on "confident" outputs actually as low as assumed? Are there novel error patterns emerging? | "Is our confidence calibration still trustworthy?" |
| **Confidence-based / field-level-ambiguity routing** | Which specific extractions get a human reviewer's attention, given limited reviewer capacity | "Which of *these* extractions needs a human right now?" |

Routing review attention should be driven by **confidence scores, document characteristics (e.g. known-hard document types), and field-level ambiguity** — not by random sampling. Random sampling is the right tool for *measuring* the system's error rate (including on the high-confidence bucket, to catch calibration drift); it is the wrong tool for *deciding which items a limited reviewer pool should look at right now*, since it ignores exactly the signal (confidence, ambiguity) that would make review time efficient.

```python
def route_for_review(extraction):
    if extraction["low_confidence_fields"]:
        return "human_review"                      # field-level ambiguity signal
    if extraction["document_type"] in KNOWN_HARD_TYPES:
        return "human_review"                       # document-characteristic signal
    if extraction["conflict_detected"]:              # see §56
        return "human_review"
    return "auto_approve"

def measure_error_rate_sample():
    # separate process — stratified RANDOM sample of "auto_approve" outputs,
    # to check whether confidence calibration still holds and catch novel error patterns
    return stratified_random_sample(auto_approved_extractions, strata="document_type")
```

### Calibrating thresholds with labeled validation data

Field-level confidence scores are only useful once calibrated against a labeled validation set (does "confidence: 0.9" on this field actually correspond to ~90% correctness on held-out labeled examples?) — an uncalibrated raw confidence number from the model is not directly interpretable as a probability of correctness.

---

## 62. Information Provenance and Uncertainty in Multi-Source Synthesis

**Task Statement 5.6.**

### Claim-source mappings must survive summarization

Source attribution is commonly lost exactly at the summarization step — a synthesis agent that compresses findings without preserving which source backs which claim leaves the final report unable to say where anything came from. Require every subagent to output **structured claim-source mappings** (claim, evidence excerpt, source URL/document name, and any page/section reference), and require the synthesis step to **preserve and merge** these mappings rather than re-summarizing them away:

```python
finding = {
    "claim": "...",
    "evidence_excerpt": "...",
    "source_url": "https://example.org/report-2026",
    "document_name": None,
    "published_date": "2026-02-14",
}
```

### Conflicting statistics from credible sources — annotate, don't arbitrate

When two credible sources report different numbers for the same metric, the correct handling is to **include both values, explicitly annotated with their sources**, and let the coordinator (or the reader) decide how to reconcile them — not to silently pick one, and not to average them into a number neither source actually reported.

```markdown
## Market size estimates (conflicting)
- Source A (Industry Report 2026): $4.2B TAM
- Source B (Analyst Brief, Feb 2026): $3.1B TAM
  *(Difference may reflect differing scope — Source A includes adjacent services.)*
```

### Temporal data — dates prevent false "contradictions"

Two findings that look contradictory can simply be from different points in time. Requiring every subagent to include a publication/collection date in its structured output lets the synthesis step correctly interpret an apparent conflict as a temporal trend instead of a genuine disagreement.

### Structuring the report — well-established vs. contested, and content-appropriate rendering

Explicit report sections should distinguish well-established findings (multiple consistent sources) from contested ones (conflicting sources, annotated as above) — and different content types should render in their natural form (financial data as tables, narrative findings as prose, technical/structured findings as lists) rather than flattening everything into one uniform format for consistency's sake.

### Coverage-gap annotation ties back to §59

When a subagent's failure means a topic area has thin or no coverage, the synthesis output should say so explicitly (a "coverage gaps" section) rather than silently presenting a partial picture as if it were complete — this is the same honesty principle as annotating an unrecoverable subagent error in §59, applied to the final report a user actually reads.

---
