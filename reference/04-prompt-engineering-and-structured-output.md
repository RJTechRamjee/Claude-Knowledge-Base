# Domain 4 — Prompt Engineering & Structured Output

**Exam weight: 20%.** Covers Task Statements 4.1–4.6: explicit criteria to reduce false positives, few-shot prompting, `tool_use` + JSON schema enforcement, validation/retry/feedback loops, batch processing strategy, and multi-instance/multi-pass review architectures.

**Running example used throughout:** *Scenario 5 — Claude Code for CI/CD* (false-positive-sensitive review criteria) and *Scenario 6 — Structured Data Extraction* (schema design, validation loops, batch processing).

---

## 31. Explicit Criteria to Improve Precision and Reduce False Positives

**Task Statement 4.1.**

### Specificity trades false positives against false negatives — there is no free lunch

| Criteria style | False positives | False negatives |
|---|---|---|
| Broad / open-ended ("flag anything that looks like a security risk") | **High** — flags superficially risky but benign code | Low — wide net |
| Narrow / specific and checkable ("flag code that concatenates unsanitized user input into a SQL string") | **Low** — only fires on an objectively true condition | Higher — misses issues outside the named categories |

Choose based on which failure mode is costlier for the use case: a lint-style gate blocking CI should minimize false positives (developer trust erodes fast); a first-pass triage a human reviews afterward can tolerate more false positives in exchange for fewer misses.

### Vague instructions don't improve precision — even when they sound cautious

"Be conservative" and "only report high-confidence findings" are **not** specific categorical criteria — they ask the model to self-assess confidence, which is exactly as unreliable here as self-reported confidence is for escalation decisions (see §58 in [05-context-management-and-reliability.md](05-context-management-and-reliability.md)). The fix that actually moves precision is naming the **concrete, checkable condition**:

```
❌ "Check that comments are accurate."
✅ "Flag a comment only when the claimed behavior directly contradicts the function's
   actual code behavior (e.g. comment says 'returns null on error' but the function throws).
   Do NOT flag comments that are merely incomplete, outdated in wording, or stylistically loose."
```

### Explicit severity criteria with concrete examples per level

```
<critical>
  Confirmed security vulnerability or data-loss bug.
  Example: `query = "SELECT * WHERE id=" + user_input` → critical.
</critical>
<high>
  Crash-inducing logic error.
  Example: array index starts at 1 against a 0-indexed array → high.
</high>
<low>
  Style-only: naming, missing docstring, line length.
</low>
```

Named XML tags (`<critical>`, `<high>`, `<low>` — see also `<security_criteria>`, `<correctness_criteria>` style tags) give each category an unambiguous boundary Claude respects, versus continuous prose or a single unheaded bullet list where criteria can bleed across categories.

### Temporarily disabling a high-false-positive category to restore trust

If one review category (e.g. "possible race condition") has a high false-positive rate, developers stop trusting **all** categories from the tool, including accurate ones. The correct move is to disable that specific category while its prompt is improved — not to soften every category's criteria, which degrades the categories that were already working.

---

## 19. Prompt Structuring — XML Tags for Category Isolation

**Task Statement 4.1 (supporting technique).** When a prompt defines multiple distinct categories — each with its own criteria, rules, and examples — **uniquely named** XML tags create unambiguous boundaries that prevent cross-contamination between them.

```xml
<security_criteria>
  Flag: hardcoded secrets, SQL injection, missing auth checks.
  Example: `query = "SELECT * WHERE id=" + user_input` → critical.
</security_criteria>

<correctness_criteria>
  Flag: off-by-one errors, null dereferences, wrong return types.
  Example: loop index starts at 1 on a 0-indexed array → high.
</correctness_criteria>

<style_criteria>
  Flag: inconsistent naming, missing docstrings, lines > 120 chars.
  Severity: all style issues = low.
</style_criteria>
```

Claude is trained to respect XML tag boundaries as semantic containers — criteria inside `<security_criteria>` apply only to security, and won't bleed into how correctness or style issues are judged.

| Approach | Problem |
|---|---|
| Continuous prose | No structural boundary — criteria can blend across categories |
| Single bullet list, no headers | Bullet order implies grouping but is ambiguous |
| Repeat full criteria in each section | Inflates prompt size; copies can drift and contradict |
| Generic, repeated tag names (`<criteria>...</criteria>` used twice) | Weaker — multiple instances of the same tag name lose distinguishing meaning |

Use named XML tags whenever a prompt has multiple **independent** sections that must not bleed into each other: criteria categories, evaluation dimensions, persona constraints, step-by-step instructions.

---

## 54. Few-Shot Prompting for Output Consistency

**Task Statement 4.2.**

### When few-shot beats more detailed prose

Detailed instructions alone often produce inconsistent formatting or inconsistent handling of ambiguous cases. Two to four **targeted** examples — especially ones that show *why* one action was chosen over a plausible alternative — generalize the model's judgment to novel cases better than an exhaustive rule list, because the model learns the underlying reasoning pattern, not just a lookup table of pre-specified cases.

```
Example 1 — customer states an order number in the same message as their name:
  Query: "Hi, I'm Dana Kim, checking on order #58291"
  Action: call get_customer first (verify identity), THEN lookup_order
  Why: an order number alone is not sufficient to authorize account actions
       without a verified customer_id — even though the order number was given.
```

### Demonstrating desired output format consistently

```
{location, issue, severity, suggested_fix}   ← every finding uses exactly this shape
```

Showing 2–3 findings in this exact shape is more reliable than describing the shape in prose, especially for getting severity labeling consistent across many findings.

### Reducing hallucination in extraction (Scenario 6)

Few-shot examples that show correct extraction from **varied document structures** (inline citations vs. a bibliography section, a narrative paragraph vs. an embedded table) teach the model to generalize the extraction pattern across formats it hasn't seen verbatim — this is what fixes empty/null extraction on documents whose layout differs from the most common training-adjacent shape, more reliably than adding more prose describing "handle different formats."

### Distinguishing acceptable patterns from genuine issues (false-positive reduction)

Pairing a "this looks risky but is actually fine, don't flag it" example with a "this is genuinely the issue, flag it" example in the same few-shot set teaches the boundary directly — this is often more effective than a purely negative instruction list of things not to flag.

---

## 55. Enforcing Structured Output with `tool_use` and JSON Schemas

**Task Statement 4.3.** Builds on §1, "Tool Choice", in [00-foundations-messages-api.md](00-foundations-messages-api.md).

### `tool_choice` modes for structured-output guarantees

| Mode | Guarantees a tool fires? | Use when |
|---|---|---|
| `auto` | ❌ No | A plain-text fallback is acceptable |
| `any` | ✅ Yes, but model picks which tool | Multiple extraction schemas exist and the document type is unknown ahead of time |
| `{"type": "tool", "name": "..."}` | ✅ Yes, this exact tool | A specific extraction (e.g. `extract_metadata`) must run before any enrichment step |

```python
# Document type unknown ahead of time — guarantee SOME structured extraction fires
response = client.messages.create(
    model="claude-sonnet-4-6",
    tools=[invoice_schema_tool, receipt_schema_tool, purchase_order_schema_tool],
    tool_choice={"type": "any"},
    messages=[{"role": "user", "content": document_text}],
)
```

### `strict` — eliminates syntax errors, not semantic errors

`tool_use` + a JSON schema (with `strict` enabled) guarantees the response is structurally valid — every required field present, every value the declared type, every enum value one of the allowed options. It does **not** guarantee the *content* is correct: a line-items array can still fail to sum to the stated total, or a value can land in the wrong field, while remaining perfectly schema-valid.

```python
result = run_extraction_tool(invoice_text)
calculated_total = sum(item["amount"] for item in result["line_items"])
if abs(calculated_total - result["invoice_total"]) > 0.01:
    flag_for_human_review(result, calculated_total)   # semantic check — schema can't do this
```

### Schema design: required/optional, nullable, and extensible enums

The fabrication problem: a field that is `required` *and* typed `number` forces Claude to invent a plausible value when the source document doesn't actually contain one — silently corrupting data.

```python
# ❌ Forces fabrication when data is genuinely absent
"required": ["square_footage"], "properties": {"square_footage": {"type": "number"}}

# ✅ Correct — not required, plus a companion source/confidence enum
"required": ["address", "price"],   # square_footage removed from required
"properties": {
    "square_footage": {"type": "number"},
    "square_footage_source": {"type": "string", "enum": ["stated", "estimated", "unknown"]}
}
```

Extend enum categories safely with an `"other"` + free-text detail pattern, and mark genuinely ambiguous cases explicitly rather than forcing a best-guess enum value:

```python
"document_type": {"type": "string", "enum": ["invoice", "receipt", "purchase_order", "other"]},
"document_type_detail": {"type": "string", "description": "Only used when document_type is 'other'."},
"amount_clarity": {"type": "string", "enum": ["clear", "unclear"]}
```

### Format normalization rules alongside a strict schema

A strict schema controls *shape*; it does not normalize inconsistent source formatting (dates as "3/3/26" vs "March 3, 2026" vs "2026-03-03"). Pair the schema with explicit normalization instructions in the prompt (target format, how to handle ambiguity) — the schema and the normalization rule solve different problems and both are needed.

---

## 56. Validation, Retry, and Feedback Loops for Extraction Quality

**Task Statement 4.4.**

### Retry-with-error-feedback

On a validation failure, the follow-up request should include the **original document**, the **failed extraction**, and the **specific validation error** — giving the model a concrete target to correct, rather than re-sending the same prompt and hoping for a different result:

```python
retry_prompt = (
    f"Your previous extraction failed validation: {validation_error}\n\n"
    f"Original document:\n{document_text}\n\n"
    f"Your previous (invalid) extraction:\n{json.dumps(failed_extraction)}\n\n"
    "Correct the specific field(s) that failed validation."
)
```

### When retry will and won't help

| Failure type | Will retry fix it? |
|---|---|
| Format/structural mismatch (wrong date format, field in wrong shape) | ✅ Yes — the information exists, the model just needs to re-express it |
| Information genuinely absent from the provided document | ❌ No — no amount of retrying recovers data that was never in the input |

Retrying a "genuinely absent" case wastes calls; the correct response is a nullable field (§55) with a `_source: "unknown"` marker, not a retry loop.

### Semantic validation vs. schema syntax errors

A schema (with `strict`) eliminates syntax errors (missing fields, wrong types) at the API layer. Semantic errors — line items that don't sum to the stated total, a value that landed in the wrong field, a date that's internally inconsistent — require **your own post-extraction validation code**, run after the tool call returns:

```python
result = run_extraction_tool(invoice_text)
result["calculated_total"] = sum(i["amount"] for i in result["line_items"])
result["conflict_detected"] = abs(result["calculated_total"] - result["stated_total"]) > 0.01
```

### Feedback loops that improve the *system*, not just one document

Add a `detected_pattern` field to structured findings/extractions — a short label for what code construct or document shape triggered this result. When developers dismiss a finding as a false positive, aggregating `detected_pattern` values across dismissals surfaces which *pattern* is over-triggering, turning individual dismissals into a systematic input for improving the prompt, schema, or few-shot set — rather than each dismissal being a one-off with no lasting signal.

```python
finding = {
    "issue": "Possible race condition on shared counter",
    "detected_pattern": "unlocked_increment_in_async_handler",   # ← aggregatable across many findings
    "severity": "medium",
}
```

---

## 30. Message Batches API and Batch Processing Strategy

**Task Statement 4.5.**

### What it is, and its hard limitation

Fire-and-forget: submit a batch, it processes asynchronously (up to 24h), no guaranteed latency SLA, ~50% cost savings vs. synchronous calls. The Batches API does **not** support a live round-trip mid-request — if Claude needs an external tool result to finish reasoning, that result must already be embedded in `messages[]` at submission time; it cannot be supplied after the model emits `tool_use`.

| Feature | Allowed in a batch request? |
|---|---|
| `tools=` parameter, and `tool_use` blocks in the response | ✅ Yes |
| Pre-populated multi-turn history including prior `tool_use`/`tool_result` | ✅ Yes |
| Pausing mid-request to inject a freshly-fetched tool result | ❌ No |

### Matching workload to API — blocking vs. non-blocking (Scenario 5: CI)

| Workload | Correct API |
|---|---|
| Blocking pre-merge check — a developer is waiting on the result before merging | **Synchronous** `messages.create()` — batch's uncapped latency (up to 24h) is unacceptable here regardless of the cost savings |
| Overnight technical-debt report, weekly audit, nightly test generation | **Message Batches API** — latency-tolerant, and the 50% saving compounds over routine/scheduled runs |

A proposal to move *both* workflows to batch processing to capture the discount should be pushed back on for exactly this reason — cost savings do not override a hard latency requirement.

### Failure handling by `custom_id`

Each batch request/response pair is correlated by a `custom_id` you supply — results can return in any order, so key by `custom_id`, never by position. On partial batch failure, resubmit only the failed `custom_id`s (with any needed fix, e.g. chunking a document that exceeded context limits) rather than resubmitting the entire batch.

### Prompt refinement before scaling up

Refine the extraction/review prompt against a small sample **before** submitting a large batch — a prompt issue discovered only after processing 10,000 documents costs far more (in both money and turnaround time) to fix than one caught on a 20-document sample.

---

## 14. Multi-Instance and Multi-Pass Review Architectures

**Task Statement 4.6.**

### Why self-review misses issues — anchoring bias

A Claude instance reviewing its own output within the same conversation is anchored to its own prior reasoning: it tends to justify its earlier decisions rather than question them. A fresh instance, with no attachment to those decisions, reviews the artifact as a stranger would — this is *not* about extended-thinking budget or a stricter self-review prompt; both leave the anchoring effect largely intact.

```python
# Instance 1 — Generator
gen_response = client.messages.create(
    model="claude-sonnet-4-6", max_tokens=2000,
    system="You are a senior developer. Write clean, efficient code.",
    messages=[{"role": "user", "content": "Write a Python function to parse JWT tokens"}],
)
generated_code = next(b.text for b in gen_response.content if b.type == "text")

# Instance 2 — Fresh reviewer, no shared conversation history
review_response = client.messages.create(
    model="claude-sonnet-4-6", max_tokens=1000,
    system="You are a security-focused code reviewer. Find bugs and vulnerabilities.",
    messages=[{"role": "user", "content": f"Review this code for bugs:\n\n{generated_code}"}],
)
```

### Pass the raw artifact, not a generator-authored summary

A generator-written summary of its own changes frames the decisions in a self-justifying way; the reviewer then evaluates that framing rather than forming an independent judgment from the raw diff. If token budget is a real constraint, **truncate** the raw diff (fewer lines, changed hunks only) — truncation preserves independence; summarization loses it.

| Input to reviewer | Independence preserved? |
|---|---|
| Raw diff / raw output (or a truncated version of it) | ✅ Yes |
| Generator-authored summary | ❌ No — anchored to the generator's framing |
| Generator's extended-thinking trace | ❌ No — worst case, adopts the generator's entire reasoning chain |

### Multi-pass review for large changesets

For a large PR (14+ files), one combined pass produces inconsistent depth and even contradictory findings (the same pattern flagged in one file, approved in another) — this is attention dilution, covered in depth at §38, "Task Decomposition Strategies for Complex Workflows", in [01-agentic-architecture-and-orchestration.md](01-agentic-architecture-and-orchestration.md). The fix is the same principle applied to review specifically: **per-file local-analysis passes, plus one separate cross-file integration pass** for data-flow and consistency issues — not a bigger model/context window (that doesn't fix attention *quality*), and not a "3 runs, keep only issues found twice" consensus filter (which actively suppresses real bugs that only manifest intermittently).

### Confidence-annotated verification passes

Have a verification pass have the model self-report a confidence level alongside each finding — this is useful for **routing** (send low-confidence findings to a human, auto-apply high-confidence ones), which is different from using the same confidence number to decide *whether to escalate a customer case* (§58) — confidence as a review-routing signal and confidence as an escalation-trigger are not interchangeable uses of the same number.

---
