# Foundations — Messages API Core Mechanics

Prerequisite building blocks used across every exam domain: tool choice, content blocks, stop reasons, built-in/local tools, current models, message roles, request/response shape, the agentic tool loop, `maxTurns`, and why the API is stateless. Not itself one of the 5 blueprint domains — every domain file below assumes this one.

> Scope note: examples target `claude-sonnet-4-6` (the exam's documented model) and the Python `anthropic` SDK, per [CLAUDE.md](../CLAUDE.md).

---

## 1. Tool Choice

Controls whether and how Claude uses tools.

```python
tool_choice={"type": "auto"}                        # Claude decides (default)
tool_choice={"type": "any"}                         # Claude must call some tool
tool_choice={"type": "tool", "name": "calculator"}  # Force a specific tool
tool_choice={"type": "none"}                        # Disable all tools
```

### `auto` vs `any` — the critical distinction

| Mode | Must call a tool? | Can respond with plain text? | Claude picks which tool? |
|---|---|---|---|
| `auto` | ❌ No — optional | ✅ Yes | ✅ Yes |
| `any` | ✅ Yes — guaranteed | ❌ No | ✅ Yes |
| `tool` | ✅ Yes — guaranteed | ❌ No | ❌ No (forced) |
| `none` | ❌ Prohibited | ✅ Yes | — |

**`auto`** — Claude decides whether to call a tool *or skip all tools entirely* and reply with plain text.

**`any`** — Claude must call one of the registered tools. It cannot reply with plain text. It picks which tool fits the input best using its semantic understanding.

### When to use `tool` (force a specific tool)

Use `{"type": "tool", "name": "..."}` when a **specific tool must run on this turn** — regardless of what other tools are registered. Exam-relevant case: a structured-extraction pipeline (Domain 4 / Scenario 6) where `extract_metadata` must run before any enrichment tool.

```python
# Pipeline step 1: extract_metadata must run before enrichment
response = client.messages.create(
    model="claude-sonnet-4-6",
    tools=[extract_metadata_tool, translate_text_tool, summarize_document_tool],
    tool_choice={"type": "tool", "name": "extract_metadata"},  # only this fires
    messages=[{"role": "user", "content": document_text}]
)
```

`any` is wrong here: it guarantees *some* tool fires, but Claude could pick a different one first, violating the dependency order.

### Enforcing tool ordering across a pipeline

`tool_choice` is a **per-request** setting, not a session-wide execution plan. To guarantee ordering when all tools are eventually needed, split into multiple turns:

```python
# Turn 1 — force the prerequisite tool
resp1 = client.messages.create(
    tools=[extract_metadata_tool, translate_text_tool, summarize_document_tool],
    tool_choice={"type": "tool", "name": "extract_metadata"},
    messages=[{"role": "user", "content": doc}]
)
metadata_result = run_tool(resp1)   # execute extract_metadata locally

# Turn 2 — pass metadata back; Claude calls remaining tools freely
resp2 = client.messages.create(
    tools=[translate_text_tool, summarize_document_tool],
    tool_choice={"type": "any"},    # must call one of the remaining tools
    messages=[
        {"role": "user", "content": doc},
        {"role": "assistant", "content": resp1.content},
        {"role": "user",  "content": [{"type": "tool_result", **metadata_result}]},
    ]
)
```

### When to use `any` instead of `auto`

Use `any` when you need **guaranteed structured output for every input** (Domain 4 / Scenario 6) and cannot tolerate a plain-text fallback.

```python
# Support ticket router — must always call one extraction tool, never reply with text
response = client.messages.create(
    model="claude-sonnet-4-6",
    tools=[bug_report_tool, feature_request_tool, billing_issue_tool],
    tool_choice={"type": "any"},   # ← guarantees one tool fires; Claude picks which
    messages=[{"role": "user", "content": ticket_text}]
)
```

Why `auto` fails here: an ambiguous ticket might cause Claude to reply *"I'm not sure how to classify this"* in plain text — breaking the guarantee of a structured result for every ticket.

### Extended thinking — `tool_choice` compatibility

When extended thinking is enabled, only `"auto"` and `"none"` are compatible `tool_choice` values:

| `tool_choice` value | Compatible with extended thinking? |
|---|---|
| `{"type": "auto"}` | ✅ Yes |
| `{"type": "none"}` | ✅ Yes |
| `{"type": "any"}` | ❌ No — forces tool call, incompatible |
| `{"type": "tool", "name": "..."}` | ❌ No — forces tool call, incompatible |

---

## 2. Content Block Types

Appear in `response.content` or in message `content` arrays.

```python
{"type": "text", "text": "Hello!"}                                    # Claude's text

{"type": "tool_use", "id": "toolu_01abc...", "name": "calculator",    # Claude calling a tool
 "input": {"expression": "2+2"}}

{"type": "tool_result", "tool_use_id": "toolu_01abc...", "content": "4"}  # your result back to Claude

{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": "<b64>"}}

{"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": "<b64>"}}
```

---

## 3. Stop Reasons

`response.stop_reason` — why Claude stopped generating:

| Value | Meaning | What to do next |
|---|---|---|
| `"end_turn"` | Claude finished naturally (including asking questions) | Get user input → append → call API again |
| `"tool_use"` | Claude wants to call a tool | Run tool → return `tool_result` → call API again |
| `"max_tokens"` | Hit the `max_tokens` ceiling mid-response | Optionally continue by appending partial response |
| `"stop_sequence"` | Hit a custom stop sequence you defined | Application-specific |
| `"pause_turn"` | A long-running turn (e.g. an extended server-tool-use turn) was paused so it can be continued | Send the next request to resume it |
| `"refusal"` | Safety classifier declined. HTTP 200 | Check `stop_details.category`; handle gracefully |
| `"model_context_window_exceeded"` | The response filled the model's context window mid-generation | Treat as truncated, same as `max_tokens` |

**There is no "waiting for user input" stop reason.** The API is pure request-response. When Claude asks a clarifying question mid-task, `stop_reason` is still `"end_turn"` — indistinguishable from a final answer without parsing text content.

**Better pattern — a `request_clarification` tool for structural detectability:**

```python
{
    "name": "request_clarification",
    "description": "Ask the user a clarifying question before proceeding",
    "input_schema": {
        "type": "object",
        "properties": {"question": {"type": "string"}, "reason": {"type": "string"}},
        "required": ["question"]
    }
}
```

```python
while response.stop_reason == "tool_use":
    tool_call = next(b for b in response.content if b.type == "tool_use")
    if tool_call.name == "request_clarification":
        result = input(f"Claude asks: {tool_call.input['question']}\n> ")
    else:
        result = run_my_tool(tool_call.name, tool_call.input)
    # append tool_result and continue loop ...
```

| Approach | `stop_reason` | Detectable without parsing? |
|---|---|---|
| Claude asks in plain text | `end_turn` | ❌ |
| `request_clarification` tool | `tool_use` | ✅ |

---

## 4. Built-in (Standard) Tools

Anthropic-managed tools — no `input_schema` needed, no result handling required.

```python
{"type": "web_search_20260209",   "name": "web_search"}                  # Web search
{"type": "web_fetch_20260209",    "name": "web_fetch"}                   # Web fetch
{"type": "bash_20250124",         "name": "bash"}                        # Run bash commands
{"type": "text_editor_20250728",  "name": "str_replace_based_edit_tool"} # Edit files
{"type": "computer_20251124",     "name": "computer"}                    # Control computer (out of scope — see §63)
{"type": "code_execution_20260521", "name": "code_execution"}            # Server-side code execution
```

| | Built-in | Local |
|---|---|---|
| Has `type` field | ✅ Yes (versioned) | ❌ No |
| Has `input_schema` | ❌ No | ✅ Yes |
| Who runs the tool | Anthropic | You |
| Needs second turn | ❌ No | ✅ Yes |

> Type strings are versioned and change between API versions — note the version suffix whenever it appears in a question (e.g. `bash_20250124`).

---

## 5. Local Tool Definition

You define the schema; you run the tool and return the result. This is the shape used for every custom/MCP tool in the exam scenarios (`get_customer`, `lookup_order`, `process_refund`, etc.):

```python
{
    "name": "get_customer",
    "description": "Look up a verified customer record by email or phone. Returns a customer_id used by all other support tools. Call this FIRST for any request that will touch order or billing data.",
    "input_schema": {
        "type": "object",
        "properties": {
            "identifier": {"type": "string", "description": "Customer email or phone number"}
        },
        "required": ["identifier"]
    }
}
```

---

## 6. Current Models and Pricing

| Model | Model ID | Context | Input $/1M | Output $/1M |
|---|---|---|---|---|
| Claude Opus 5 | `claude-opus-5` | 1M | $5.00 | $25.00 |
| Claude Sonnet 5 | `claude-sonnet-5` | 1M | $2.00 | $10.00 |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | 1M | $3.00 | $15.00 |
| Claude Haiku 4.5 | `claude-haiku-4-5` | 200K | $1.00 | $5.00 |

Use **exact model ID strings** — never append date suffixes. The exam guide (effective July 2026) documents `claude-sonnet-4-6` as the target model; this reference keeps that scope for consistency. Newer families (Opus 5, Sonnet 5, Fable 5/5.1) exist in the current live API but are **not** the exam's documented scope — see [06-out-of-scope.md](06-out-of-scope.md).

---

## 7. Session Resumption — The API Is Stateless

**The Anthropic API has no session ID parameter.** The model only sees what is in `messages[]` for the current request.

```python
# ❌ This does NOT work — session_id is not an API parameter
client.messages.create(model="claude-sonnet-4-6", session_id="sess_abc123", messages=[...])

# ✅ Correct — retrieve prior history from YOUR storage and inject it
prior_history = db.load_conversation("sess_abc123")
client.messages.create(
    model="claude-sonnet-4-6",
    messages=[*prior_history, {"role": "user", "content": "What's my risk tolerance?"}]
)
```

### Correct session-resume pattern

```python
def save_turn(session_id, messages):
    db.store(session_id, messages)

def resume_session(session_id, new_message):
    messages = db.load(session_id) + [{"role": "user", "content": new_message}]
    response = client.messages.create(model="claude-sonnet-4-6", max_tokens=1024, messages=messages)
    messages.append({"role": "assistant", "content": response.content})
    save_turn(session_id, messages)
    return response
```

### Claude Code CLI / Agent SDK session management is a different, higher layer

`claude --resume "session-name"` and the Agent SDK's `resume=` option work because **Claude Code itself** manages conversation storage on disk / server-side — this is a layer built on top of the stateless API, not an API feature itself. See §12, "Session Management", and §37, "`fork_session`", in [01-agentic-architecture-and-orchestration.md](01-agentic-architecture-and-orchestration.md) for the exam-tested mechanics.

| | Anthropic API | Claude Code CLI / Agent SDK |
|---|---|---|
| Session storage | ❌ None — you manage it | ✅ Managed for you |
| Resume mechanism | Inject prior `messages[]` yourself | `--resume <name>` / `resume=` option |
| `session_id` parameter | ❌ Does not exist on `messages.create()` | A real concept at this layer |

---

## 8. Message Roles

```python
{"role": "user",      "content": "..."}  # Human turn
{"role": "assistant", "content": "..."}  # Claude turn
# System prompt is a separate top-level param, NOT a role in messages[]
```

---

## 9. Top-level Request Parameters

```python
client.messages.create(
    model=          "claude-sonnet-4-6",  # required
    max_tokens=     1024,                  # required — hard ceiling on output tokens
    messages=       [...],                 # required — conversation history
    system=         "You are...",          # optional — system prompt
    tools=          [...],                 # optional — tool definitions
    tool_choice=    {...},                 # optional — see section 1
    stop_sequences= ["STOP"],              # optional — custom stop strings
    stream=         True,                  # optional — streaming mode
    metadata=       {"user_id": "123"},    # optional — request metadata
)
```

---

## 10. Response Object Fields

```python
response.id                    # unique message ID
response.type                  # always "message"
response.role                  # always "assistant"
response.content               # list of content blocks
response.model                 # model that responded
response.stop_reason           # why it stopped (see section 3)
response.stop_sequence         # which stop sequence triggered (if any)
response.usage.input_tokens    # tokens consumed by input
response.usage.output_tokens   # tokens consumed by output
```

---

## 11. Multi-turn Tool Loop Pattern

The core mechanic behind **Domain 1, Task Statement 1.1** — the agentic loop lifecycle.

```python
messages = [{"role": "user", "content": user_input}]
response = client.messages.create(model="claude-sonnet-4-6", max_tokens=1024, tools=tools, messages=messages)

while response.stop_reason == "tool_use":
    tool_call = next(b for b in response.content if b.type == "tool_use")
    tool_result = run_my_tool(tool_call.name, tool_call.input)

    messages.append({"role": "assistant", "content": response.content})
    messages.append({
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": tool_call.id, "content": tool_result}]
    })
    response = client.messages.create(model="claude-sonnet-4-6", max_tokens=1024, tools=tools, messages=messages)

final = next(b.text for b in response.content if b.type == "text")
```

### Handling tool execution failures — feed errors back, don't terminate

```python
try:
    tool_result = run_my_tool(tool_call.name, tool_call.input)
    result_block = {"type": "tool_result", "tool_use_id": tool_call.id, "content": tool_result}
except Exception as e:
    result_block = {"type": "tool_result", "tool_use_id": tool_call.id, "content": str(e), "is_error": True}
```

With `is_error: true` in context, Claude can retry with different arguments, call a fallback tool, explain the failure, or decide the task is unrecoverable — model-driven reasoning over the failure, rather than the loop terminating blindly.

> See §40, "Agentic Loop Anti-Patterns", in [01-agentic-architecture-and-orchestration.md](01-agentic-architecture-and-orchestration.md) for the exam's specific list of wrong ways to decide when to stop this loop — this is a directly tested gap area.

---

## 13. `maxTurns`

Controls how many agentic loop iterations Claude can take. **Not an API parameter** — enforced by your own loop logic (or by the CLI's `--max-turns`).

```bash
claude --max-turns 10 "refactor all files in /src"
```

```python
MAX_TURNS = 5
turn_count = 0
while True:
    if turn_count >= MAX_TURNS:
        print(f"Reached max turns ({MAX_TURNS}). Stopping.")
        break
    response = client.messages.create(model="claude-sonnet-4-6", max_tokens=1000, tools=tools, messages=messages)
    turn_count += 1
    if response.stop_reason == "end_turn":
        break
    if response.stop_reason == "tool_use":
        # ... execute + append, as in section 11 ...
        pass
```

| | `max_tokens` | `maxTurns` |
|---|---|---|
| Real API parameter | ✅ Yes | ❌ No |
| Who enforces it | Anthropic's servers | Your code / the CLI |
| What it limits | Words per response | Loop iterations |

**Exam framing (Task 1.1):** a fixed iteration cap is a legitimate *safety net*, but it must never be the *primary* mechanism for deciding the loop is done — that decision belongs to `stop_reason`. Relying on `maxTurns` alone to end a loop is one of the anti-patterns the exam tests directly (see section 40).

---
