# Tool Use and Sessions

Session resumption, the multi-turn tool loop, maxTurns, structured output edge cases, and the Message Batches API.

---

## 7. Session Resumption — The API Is Stateless

**The Anthropic API has no session ID parameter.** A session ID alone carries no conversational content — the model only sees what is in `messages[]` for the current request. Passing a session ID to a non-existent parameter does nothing; the model starts fresh every call.

```python
# ❌ This does NOT work — session_id is not an API parameter
client.messages.create(
    model="claude-sonnet-4-6",
    session_id="sess_abc123",     # ignored / error — does not exist
    messages=[{"role": "user", "content": "What's my risk tolerance?"}]
)

# ✅ Correct — retrieve prior history from YOUR storage and inject it
prior_history = db.load_conversation("sess_abc123")
client.messages.create(
    model="claude-sonnet-4-6",
    messages=[
        *prior_history,           # full prior turns in the request
        {"role": "user", "content": "What's my risk tolerance?"}
    ]
)
```

### Correct session-resume pattern

Your application owns the storage. Persist history after every turn; reload and inject on resume:

```python
def save_turn(session_id, messages):
    db.store(session_id, messages)              # DB, Redis, or file

def resume_session(session_id, new_message):
    messages = db.load(session_id) + [         # inject full prior history
        {"role": "user", "content": new_message}
    ]
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=messages
    )
    messages.append({"role": "assistant", "content": response.content})
    save_turn(session_id, messages)             # persist updated history
    return response
```

### Session ID scope — it's yours to define

Since you own the storage, the session ID is just a key in your database. There is no API-side expiry — you can resume the same session ID today, tomorrow, or next year as long as your storage retains the data.

**The only real limit is the context window.** Every resume injects the full prior history into `messages[]`. Sessions that grow long enough will eventually exceed the context window:

```
Short session:    messages[] ≈ 2,000 tokens   ✅ fits
Multi-day session: messages[] ≈ 500,000 tokens ❌ context window exceeded
```

**Fix for long-lived sessions — summarize before injecting:**

```python
def resume_long_session(session_id, new_message):
    prior = db.load(session_id)

    if count_tokens(prior) > TOKEN_THRESHOLD:
        # Compress old history into a summary, replace in storage
        summary = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=prior + [{"role": "user",
                "content": "Summarize this conversation concisely, preserving key decisions and facts."}]
        )
        prior = [{"role": "user", "content": f"Prior conversation summary:\n{summary.content[0].text}"}]
        db.store(session_id, prior)   # replace full history with compressed version

    messages = prior + [{"role": "user", "content": new_message}]
    response = client.messages.create(model="claude-sonnet-4-6", max_tokens=1024, messages=messages)
    messages.append({"role": "assistant", "content": response.content})
    db.store(session_id, messages)
    return response
```

| Question | Answer |
|---|---|
| Does the API expire session IDs? | No — API has no session concept |
| Can I reuse the same ID tomorrow? | Yes — as long as your storage has it |
| Can sessions last forever? | Practically no — context window limits injectable history |
| Fix for very long sessions? | Summarize old turns before injecting |

### Claude Code CLI `--resume` is different

`claude --resume "session-name"` works because **Claude Code itself** manages conversation storage on disk — this is Claude Code's own layer, not an Anthropic API feature. The API underneath still receives the full message history in `messages[]`.

| | Anthropic API | Claude Code CLI |
|---|---|---|
| Session storage | ❌ None — you manage it | ✅ Claude Code manages it on disk |
| Resume mechanism | Inject prior `messages[]` yourself | `--resume <name>` loads from disk |
| `session_id` parameter | ❌ Does not exist | N/A |

---

## 11. Multi-turn Tool Loop Pattern

```python
messages = [{"role": "user", "content": user_input}]

response = client.messages.create(model=..., tools=..., messages=messages)

while response.stop_reason == "tool_use":
    tool_call = next(b for b in response.content if b.type == "tool_use")

    # Run your local tool
    tool_result = run_my_tool(tool_call.name, tool_call.input)

    # Append assistant turn + tool result
    messages.append({"role": "assistant", "content": response.content})
    messages.append({
        "role": "user",
        "content": [{
            "type": "tool_result",
            "tool_use_id": tool_call.id,  # must match
            "content": tool_result
        }]
    })

    response = client.messages.create(model=..., tools=..., messages=messages)

# Final text answer
final = next(b.text for b in response.content if b.type == "text")
```

### Handling tool execution failures — feed errors back, don't terminate

When a tool raises an exception, append a `tool_result` block with `"is_error": true` and continue the loop. This keeps the failure visible in Claude's context so it can reason over it and decide the next step autonomously.

```python
while response.stop_reason == "tool_use":
    tool_call = next(b for b in response.content if b.type == "tool_use")

    try:
        tool_result = run_my_tool(tool_call.name, tool_call.input)
        result_block = {
            "type": "tool_result",
            "tool_use_id": tool_call.id,
            "content": tool_result
        }
    except Exception as e:
        result_block = {
            "type": "tool_result",
            "tool_use_id": tool_call.id,
            "content": str(e),
            "is_error": True        # ← tells Claude this is a failure, not a result
        }

    messages.append({"role": "assistant", "content": response.content})
    messages.append({"role": "user", "content": [result_block]})
    response = client.messages.create(model=..., tools=..., messages=messages)
```

With `is_error: true` in context, Claude can:
- Retry the same tool with different arguments
- Call a fallback tool instead
- Explain the failure and ask the user for clarification
- Decide the task is unrecoverable and stop

**Why not terminate immediately on failure?**

Terminating on any tool error discards Claude's ability to reason about the failure. Feeding the error back as a `tool_result` is consistent with model-driven reasoning — Claude sees the failure in context and decides the next step, rather than the loop logic making that decision blindly.

| Approach | Claude sees the error? | Can Claude recover? |
|---|---|---|
| Terminate loop on exception | ❌ No | ❌ No |
| Append `is_error: true` and continue | ✅ Yes | ✅ Yes — retry, fallback, or explain |

**What `is_error` does NOT do:**
- It does not remove the need for `stop_reason` checks — the loop still exits when `stop_reason != "tool_use"`
- It does not reset rate limits or guarantee retry success
- The Messages API does not auto-terminate on a missing or malformed `is_error` field

### Validating input before executing the tool — `strict` guarantees shape, not usability

`input_schema` (even with `strict`) only guarantees that `tool_call.input` matches the declared JSON shape — a required string field is guaranteed to be *a string*, not a *non-empty, correctly formatted, real* value. Before running the tool's actual logic (e.g. hitting an invoice API), validate business-level usability yourself and return an `is_error` `tool_result` if it fails — same feedback mechanism as an execution exception, just triggered earlier, before any real side effect runs:

```python
def run_get_invoice(input: dict) -> str:
    invoice_number = input.get("invoice_number", "").strip()

    # Guards strict/input_schema cannot express: non-empty, well-formed, exists
    if not invoice_number:
        raise ValueError("invoice_number is empty — cannot look up an invoice")
    if not re.match(r"^INV-\d{4}-\d{4,}$", invoice_number):
        raise ValueError(f"invoice_number '{invoice_number}' is not a valid format")

    record = invoice_db.lookup(invoice_number)
    if record is None:
        raise ValueError(f"No invoice found for '{invoice_number}'")

    return record.to_json()

# Reuses the same is_error tool_result pattern — Claude sees the
# validation failure and can retry with a corrected invoice_number
try:
    tool_result = run_get_invoice(tool_call.input)
    result_block = {"type": "tool_result", "tool_use_id": tool_call.id, "content": tool_result}
except ValueError as e:
    result_block = {"type": "tool_result", "tool_use_id": tool_call.id, "content": str(e), "is_error": True}
```

| Guard | Enforced by |
|---|---|
| `invoice_number` field is present | `input_schema.required` + `strict` |
| `invoice_number` is a string | `input_schema` type + `strict` |
| `invoice_number` is non-empty / correctly formatted / exists in the system | Your application code, at execution time — no schema keyword expresses this |

---

## 13. maxTurns

Controls how many agentic loop iterations Claude can take. **Not an API parameter** — enforced by your own loop logic.

### What counts as a turn
```
Turn 1: Claude thinks → calls a tool
Turn 2: Gets result  → calls another tool
Turn 3: Gets result  → writes final answer
```
Each tool call + response cycle = one turn.

### maxTurns vs max_tokens

| | `max_tokens` | `maxTurns` |
|---|---|---|
| Real API parameter | ✅ Yes | ❌ No |
| Who enforces it | Anthropic's servers | Your code |
| What it limits | Words per response | Loop iterations |
| Where it lives | Inside `messages.create()` | Around `messages.create()` |

### CLI usage
```bash
claude --max-turns 10 "refactor all files in /src"
```

### API usage — enforce it yourself
```python
import anthropic

client = anthropic.Anthropic()

tools = [
    {
        "name": "calculator",
        "description": "Perform arithmetic",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string"}
            },
            "required": ["expression"]
        }
    }
]

messages = [{"role": "user", "content": "Calculate 123 * 456, then multiply result by 789"}]

MAX_TURNS = 5    # ← you define this
turn_count = 0   # ← you track this

while True:
    if turn_count >= MAX_TURNS:          # ← you enforce this
        print(f"Reached max turns ({MAX_TURNS}). Stopping.")
        break

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1000,
        tools=tools,
        messages=messages
    )

    turn_count += 1                      # ← you increment this
    print(f"Turn {turn_count} | stop_reason: {response.stop_reason}")

    if response.stop_reason == "end_turn":
        final = next(b.text for b in response.content if b.type == "text")
        print("Final answer:", final)
        break

    if response.stop_reason == "tool_use":
        tool_call = next(b for b in response.content if b.type == "tool_use")
        result = str(eval(tool_call.input["expression"]))
        print(f"  Tool: {tool_call.name}({tool_call.input}) → {result}")

        messages.append({"role": "assistant", "content": response.content})
        messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": result
            }]
        })
```

### What happens when limit is hit
Claude halts the loop at the turn boundary and returns whatever it has — no crash, no error, just stops.

---

## 15. Structured Output — Handling Missing Data in Tool Schemas

### The fabrication problem
When a field is `required` **and** typed as `number`, Claude *must* return a number. If the source data doesn't contain one, Claude invents a plausible value rather than violate the schema — silently corrupting data quality.

### Wrong fix: change type to string
```python
# Bad — type hack; downstream consumers expecting a number now get strings
"square_footage": {"type": "string"}  # allows "N/A" but breaks numeric consumers
```

### Correct fix: two schema changes together

```python
# 1. Remove from required[] — Claude omits the field when data is absent
#    instead of fabricating a value
"required": ["address", "price"],     # square_footage no longer required
"properties": {
    "square_footage": {"type": "number"},   # still a number when present

    # 2. Add a source/confidence enum so consumers know data provenance
    "square_footage_source": {
        "type": "string",
        "enum": ["stated", "estimated", "unknown"]
    }
}
```

### Why this works
| Scenario | Model returns | Downstream sees |
|---|---|---|
| Listing has explicit sq ft | `square_footage: 1200, source: "stated"` | Reliable number |
| Listing is vague prose | field omitted, `source: "unknown"` | `null` — not fabricated |

### General rule
If a field may genuinely be absent in the source data, **remove it from `required[]`** rather than forcing Claude to invent a value or corrupting the type. Add a companion `_source` or `_confidence` enum to preserve downstream filterability.

### JSON schema guarantees syntax, not semantic correctness

A tool-use schema enforces:
- Fields are present (if `required`)
- Values have the declared types (`number`, `string`, etc.)
- Enum fields match one of the allowed values

A tool-use schema **cannot** enforce:
- Cross-field arithmetic relationships (e.g. `sum(line_items) == total`)
- Business logic constraints (e.g. `end_date > start_date`)
- Consistency between independently extracted values

**Invoice extraction example:** Even when both `line_items[].amount` and `invoice_total` are extracted and typed correctly, a schema will not detect when their values are arithmetically inconsistent. Claude returns syntactically valid JSON; the mismatch is a semantic error invisible to the schema validator.

### `strict` tool use vs. prompt-only JSON requests

| Approach | Structural guarantee | Content accuracy guarantee |
|---|---|---|
| Prompt-only ("return only a JSON object matching this format") | ❌ None — model can drift into invalid syntax, add prose, omit required fields | ❌ None |
| `tool_use` with `input_schema`, `strict` enabled | ✅ Guaranteed — API uses constrained decoding server-side, output cannot violate the schema | ❌ None |

With `strict: true`, the API restricts which tokens can be sampled at each generation step, so the response is *structurally* forced to match `input_schema` (types, required fields, enum values). This eliminates syntax errors and missing-field failures entirely — no post-hoc JSON-repair step is needed for those failure modes.

It does **not** make the extracted values correct. Given a messy scanned document, Claude can still misread a smudged digit and populate a schema-valid field (`"invoice_total": 42.00`) with the wrong number. Strict tool use collapses one axis of failure (structure) to zero; it leaves the other axis (semantic/content accuracy) exactly where it was.

### Naming gotcha: `input_schema` describes Claude's *output*

`input_schema` is named for "input to the tool," but that input is exactly what appears in the `input` field of the `tool_use` block **in Claude's response** — it is not scoped only to a hypothetical downstream tool execution. So `required` in `input_schema` does constrain the structure Claude returns; the open question is only whether that constraint is *enforced* (`strict`) or merely *suggested* (no `strict`).

```python
tool_definition = {
    "name": "extract_invoice",
    "input_schema": {
        "type": "object",
        "properties": {
            "invoice_id": {"type": "string"},
            "invoice_total": {"type": "number"},
            "vendor_name": {"type": "string"}
        },
        "required": ["invoice_id", "invoice_total", "vendor_name"]
    }
    # strict NOT set -> required is advisory only
}
```

Without `strict`, a required field can still be missing from the response with no error:
```python
# response.content — invoice_total silently dropped
[ToolUseBlock(type='tool_use', id='toolu_01Abc', name='extract_invoice',
    input={'invoice_id': 'INV-2024-0093', 'vendor_name': 'Acme Corp'})]
```

Adding `"strict": True` to the same tool definition makes `required` a hard, server-enforced constraint via constrained decoding — all three fields are now guaranteed present with correct types (content can still be wrong, just never missing/malformed):
```python
tool_definition["strict"] = True

# response.content — all required fields present & correctly typed
[ToolUseBlock(type='tool_use', id='toolu_01Xyz', name='extract_invoice',
    input={'invoice_id': 'INV-2024-0093', 'invoice_total': 42.00, 'vendor_name': 'Acme Corp'})]
```

The fix for the *content-accuracy* gap (not addressed by `strict`) is a post-extraction validation step in application code:

```python
result = run_extraction_tool(invoice_text)

calculated_total = sum(item["amount"] for item in result["line_items"])
if abs(calculated_total - result["invoice_total"]) > 0.01:
    flag_for_human_review(result, calculated_total)
```

**What does NOT fix this:**
- Adding more `required` fields — `required` only enforces presence, not relationships between values
- Changing `tool_choice` mode — `tool_choice` controls which tool fires, not arithmetic validation
- Resending the schema on follow-up turns — the schema is not hallucinated; the data mismatch is in the extracted values

Validation logic for cross-field semantic rules must live **outside the schema**, in your application code.

---

## 30. Message Batches API: Fire-and-Forget Model and Tool-Use Limitation

### What the Message Batches API is
The Message Batches API is designed for **fire-and-forget workloads**: you submit a batch of requests, they are processed asynchronously, and you poll or retrieve results later. Each request resolves independently in one shot — there is no mechanism for mid-request interaction.

### The key limitation: no live round-trips within a single request
Interactive tool-use loops require the application to inject external data back into an ongoing Claude turn:

```
Interactive tool loop (requires synchronous API):

1. Claude generates tool_use block  →  stop_reason: "tool_use"
2. Application executes the tool   →  (e.g. database query)
3. Application submits tool_result →  new API call, same conversation
4. Claude reasons over result       →  final answer

Step 3 is a round-trip WITHIN one logical exchange.
The Message Batches API cannot pause mid-processing for step 3.
```

Each batch request must complete entirely from the inputs provided at submission time. If Claude would need an external result to finish its reasoning, that result must already be embedded in the `messages[]` array — it cannot be supplied live.

### What IS allowed in batch requests
| Feature | Allowed in Message Batches API? |
|---|---|
| `tools=` parameter (tool definitions) | ✅ Yes |
| Multi-turn `messages[]` with prior `tool_use` / `tool_result` blocks | ✅ Yes — pre-populated history is fine |
| `tool_use` blocks in the response | ✅ Yes — the model can still request tools |
| Pausing mid-request to supply a live tool result | ❌ No — fire-and-forget, no round-trip |
| `tool_result` blocks injected after model generates `tool_use` | ❌ No — would require a new request |

### When to use each API
| Workload type | Use |
|---|---|
| Tool results are static / pre-computed and can be embedded upfront | Message Batches API |
| Workflow needs to call real external systems and feed results back | Synchronous `messages.create()` with real-time tool loop |
| High-volume classification, summarization, extraction (no tools or pre-known tool results) | Message Batches API (cost savings apply) |

### Common misconceptions
| Claim | Why it's wrong |
|---|---|
| "Batch requests are limited to one message per conversation" | False — `messages[]` can include full multi-turn history including prior tool turns |
| "Tool definitions can't be attached to batch requests" | False — `tools=` is fully supported |
| "Batch API strips `tool_use` blocks from responses" | False — `tool_use` blocks appear in batch responses normally |
