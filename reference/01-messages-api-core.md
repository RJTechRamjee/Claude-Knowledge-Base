# Messages API — Core Reference

Tool choice, content blocks, stop reasons, built-in and local tools, current models/pricing, message roles, request parameters, and response fields.

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

**`auto`** — Claude decides whether to call a tool *or skip all tools entirely* and reply with plain text. It selects the best option, including the option of calling no tool.

**`any`** — Claude must call one of the registered tools. It cannot reply with plain text. It picks which tool fits the input best using its semantic understanding.

### When to use `tool` (force a specific tool)

Use `{"type": "tool", "name": "..."}` when a **specific tool must run on this turn** — regardless of what other tools are registered.

```python
# Pipeline step 1: extract_metadata must run before enrichment or summarization
response = client.messages.create(
    model="claude-sonnet-4-6",
    tools=[extract_metadata_tool, translate_text_tool, summarize_document_tool],
    tool_choice={"type": "tool", "name": "extract_metadata"},  # only this fires
    messages=[{"role": "user", "content": document_text}]
)
```

`any` is wrong here: it guarantees *some* tool fires, but Claude could pick `translate_text` or `summarize_document` first, violating the dependency order.

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
        {"role": "user",  "content": [{"type": "tool_result", ...metadata_result}]},
    ]
)
```

Key insight: all three tools are ultimately invoked, but ordering is enforced by structuring turns — not by hoping Claude calls them in the right sequence within a single turn.

### When to use `any` instead of `auto`

Use `any` when you need **guaranteed structured output for every input** and cannot tolerate a plain-text fallback.

```python
# Support ticket router — must always call one extraction tool, never reply with text
response = client.messages.create(
    model="claude-sonnet-4-6",
    tools=[bug_report_tool, feature_request_tool, billing_issue_tool],
    tool_choice={"type": "any"},   # ← guarantees one tool fires; Claude picks which
    messages=[{"role": "user", "content": ticket_text}]
)
```

Why `auto` fails here: an ambiguous ticket might cause Claude to reply *"I'm not sure how to classify this"* in plain text instead of calling any tool — breaking the guarantee of a structured extraction result for every ticket. `any` removes that escape hatch.

Why regex pre-classification fails: fragile keyword matching misroutes tickets. Letting Claude read the ticket and pick among all registered tools (`any`) uses semantic understanding instead.

### Extended thinking — tool_choice compatibility

When extended thinking is enabled, only `"auto"` and `"none"` are compatible `tool_choice` values. Using `"any"` or `"tool"` with extended thinking results in an API error:

```
"Thinking may not be enabled when tool_choice forces tool use."
```

| `tool_choice` value | Compatible with extended thinking? |
|---|---|
| `{"type": "auto"}` | ✅ Yes |
| `{"type": "none"}` | ✅ Yes |
| `{"type": "any"}` | ❌ No — forces tool call, incompatible |
| `{"type": "tool", "name": "..."}` | ❌ No — forces tool call, incompatible |

**Remedy:** set `tool_choice` to `"auto"` and use prompt engineering to encourage tool use:

```python
response = client.messages.create(
    model="claude-sonnet-4-6",
    thinking={"type": "enabled", "budget_tokens": 5000},
    tools=[my_tool],
    tool_choice={"type": "auto"},   # ← only valid forcing-free mode with thinking
    messages=[{
        "role": "user",
        "content": "Use the search tool to find information about X."  # prompt nudge
    }]
)
```

Extended thinking is also incompatible with: streaming (in some SDK versions), `temperature` values other than 1, and `top_p` / `top_k` overrides.

---

## 2. Content Block Types

Appear in `response.content` or in message `content` arrays.

### `text` — Claude's text response
```python
{"type": "text", "text": "Hello!"}
```

### `tool_use` — Claude calling a tool (in assistant response)
```python
{
    "type": "tool_use",
    "id": "toolu_01abc...",         # unique ID for this call
    "name": "calculator",           # tool name
    "input": {"expression": "2+2"}  # arguments
}
```

### `tool_result` — your result sent back to Claude (in user message)
```python
{
    "type": "tool_result",
    "tool_use_id": "toolu_01abc...",  # must match tool_use id
    "content": "4"                    # result string or content blocks
}
```

### `image` — sending an image
```python
{
    "type": "image",
    "source": {
        "type": "base64",
        "media_type": "image/jpeg",  # image/png, image/gif, image/webp
        "data": "<base64 string>"
    }
}
```

### `document` — sending a PDF
```python
{
    "type": "document",
    "source": {
        "type": "base64",
        "media_type": "application/pdf",
        "data": "<base64 string>"
    }
}
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
| `"pause_turn"` | Claude paused mid-turn (e.g. awaiting human approval). Opus 4.6+ | Send next user message to resume |
| `"refusal"` | Safety classifier declined. HTTP 200. Check `stop_details.category`. Opus 4.7+ | Handle gracefully; optionally use server-side fallbacks |

**`pause_turn`** — added in Opus 4.6+. Claude pauses mid-turn (e.g. awaiting human confirmation before a risky action). Resume by sending the next user message; the loop continues.

**`refusal`** — added in Opus 4.7+. Safety classifier declined the request. HTTP 200 returned. `response.stop_details` is populated **only** for this reason (fields: `type: "refusal"`, `category` e.g. `"cyber"` / `"bio"`, `explanation`). Always guard before reading `stop_details` — it is `null` for all other stop reasons.

```python
response = client.messages.create(...)
if response.stop_reason == "refusal":
    category = response.stop_details.category   # "cyber", "bio", etc.
    print(f"Refused: {category}")
elif response.stop_reason == "tool_use":
    ...
```

**There is no "waiting for user input" stop reason.** The API is pure request-response — Claude does not wait. When Claude asks a question, `stop_reason` is `"end_turn"`. The conversation only continues when your code collects user input and makes the next `messages.create()` call.

```
Claude: "What is your name?"  → stop_reason: "end_turn"  (API call is complete)
Your code: prompt user → append answer to messages[] → call messages.create() again
```

### Clarification mid-task also returns `end_turn`

Even when Claude has been given a task but needs clarification before continuing, `stop_reason` is still `"end_turn"`. Your code cannot tell from `stop_reason` alone whether Claude is done or asking for more — you'd have to parse the text content.

```
You:   "Build me a REST API for user management"
Claude: "Should auth use JWT or sessions?"  → stop_reason: "end_turn"  (same as a final answer)
```

**Better pattern — `request_clarification` tool for structural detectability:**

Define clarification as a tool so Claude signals it via `tool_use` instead of `end_turn`:

```python
{
    "name": "request_clarification",
    "description": "Ask the user a clarifying question before proceeding",
    "input_schema": {
        "type": "object",
        "properties": {
            "question": {"type": "string"},
            "reason":   {"type": "string"}
        },
        "required": ["question"]
    }
}
```

Your loop detects by tool name — no text parsing needed:

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
# Current type strings (Opus 5 / 4.8 / 4.7 / 4.6, Sonnet 5 / 4.6)
{"type": "web_search_20260209",   "name": "web_search"}                  # Web search (dynamic filtering)
{"type": "web_fetch_20260209",    "name": "web_fetch"}                   # Web fetch (dynamic filtering)
{"type": "bash_20250124",         "name": "bash"}                        # Run bash commands
{"type": "text_editor_20250728",  "name": "str_replace_based_edit_tool"} # Edit files
{"type": "computer_use_20251022", "name": "computer"}                    # Control computer
{"type": "code_execution_20260521", "name": "code_execution"}            # Server-side code execution

# Older models only (pre-Opus 4.6 / pre-Sonnet 4.6)
{"type": "web_search_20250305",  "name": "web_search"}   # basic variant
{"type": "web_fetch_20250910",   "name": "web_fetch"}    # basic variant
# On Vertex AI: only web_search_20250305 is available (no web fetch)
```

### Built-in vs Local Tool Comparison

| | Built-in | Local |
|---|---|---|
| Has `type` field | ✅ Yes (versioned) | ❌ No |
| Has `input_schema` | ❌ No | ✅ Yes |
| Who runs the tool | Anthropic | You |
| Needs second turn | ❌ No | ✅ Yes |

> **Note:** Type strings are versioned and change between API versions. Always use the latest for your target model. Web search/fetch `_20260209` variants include dynamic domain filtering (`allowed_domains`/`blocked_domains`).

---

## 5. Local Tool Definition

You define the schema; you run the tool and return the result.

```python
{
    "name": "calculator",
    "description": "Perform arithmetic calculations",
    "input_schema": {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "Math expression"}
        },
        "required": ["expression"]
    }
}
```

---

## 6. Current Models and Pricing

Use **exact model ID strings** — never append date suffixes (`claude-sonnet-4-6`, never `claude-sonnet-4-6-20251114`). Default to `claude-opus-5` unless the user specifies otherwise.

| Model | Model ID | Context | Input $/1M | Output $/1M |
|---|---|---|---|---|
| Claude Fable 5 | `claude-fable-5` | 1M | $10.00 | $50.00 |
| Claude Opus 5 | `claude-opus-5` | 1M | $5.00 | $25.00 |
| Claude Opus 4.8 | `claude-opus-4-8` | 1M | $5.00 | $25.00 |
| Claude Opus 4.7 | `claude-opus-4-7` | 1M | $5.00 | $25.00 |
| Claude Opus 4.6 | `claude-opus-4-6` | 1M | $5.00 | $25.00 |
| Claude Sonnet 5 | `claude-sonnet-5` | 1M | $2.00 | $10.00 |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | 1M | $3.00 | $15.00 |
| Claude Haiku 4.5 | `claude-haiku-4-5` | 200K | $1.00 | $5.00 |

**Prices above are Anthropic first-party API rates.** Bedrock and Vertex AI have separate pricing.

### Fast Mode (API-level, not CLI `/fast`)

Separate from the Claude Code CLI `/fast` command. API fast mode applies to Claude Opus 5 and Opus 4.8 only:

```python
# Requires beta endpoint + beta flag + speed param — all three required
client.beta.messages.create(
    model="claude-opus-5",
    max_tokens=4096,
    speed="fast",                          # top-level param (not in extra_body)
    betas=["fast-mode-2026-02-01"],
    messages=[...],
)
```

- Up to 2.5× higher output tokens/second at premium pricing ($10/$50 per MTok for Opus 5 fast)
- Not available on Bedrock, Vertex, Foundry, or Batch API
- A 429 on fast mode: retry with `speed` omitted to fall back to standard (note: switching speed invalidates prompt cache)

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
    model=          "claude-opus-5",      # required — use claude-opus-5 by default
    max_tokens=     1000,                 # required — hard ceiling on output tokens
    messages=       [...],                # required — conversation history
    system=         "You are...",         # optional — system prompt
    tools=          [...],                # optional — tool definitions
    tool_choice=    {...},                # optional — see section 1
    thinking=       {"type": "adaptive"}, # optional — adaptive thinking (current pattern)
    output_config=  {                     # optional — output controls
        "effort":   "high",              #   low | medium | high | xhigh | max (default: high)
        "format":   {...},               #   structured output schema (replaces deprecated output_format)
    },
    stop_sequences= ["STOP"],             # optional — custom stop strings
    stream=         True,                 # optional — streaming mode (required for large max_tokens)
    metadata=       {"user_id": "123"},   # optional — request metadata
    # temperature / top_p / top_k removed on Opus 4.7+ and Fable 5 (returns 400 if sent)
)
```

### Thinking parameter — current rules

| Model | Correct `thinking` value | Notes |
|---|---|---|
| Fable 5 / Opus 5 | `{"type": "adaptive"}` or omit | `budget_tokens` returns 400; `disabled` also returns 400 on Fable 5 |
| Opus 4.8 / 4.7 / Sonnet 5 | `{"type": "adaptive"}` | `budget_tokens` returns 400 |
| Opus 4.6 / Sonnet 4.6 | `{"type": "adaptive"}` recommended | `budget_tokens` still works as transitional escape hatch |
| Older (Haiku 4.5, etc.) | `{"type": "enabled", "budget_tokens": N}` | Required for thinking; min 1024, less than `max_tokens` |

> `budget_tokens` is **deprecated** on 4.6 and **rejected with 400** on 4.7+. Always use `{"type": "adaptive"}` for new code on current models.

### Effort levels (`output_config.effort`)

Controls thinking depth and token spend without changing the model:

| Level | Use for |
|---|---|
| `"low"` | Simple tasks, subagents, high-volume routes |
| `"medium"` | Routine work where quality holds at lower cost |
| `"high"` | Default — most tasks, coding, balanced quality |
| `"xhigh"` | Coding and long-horizon agentic work (Opus 4.7+) |
| `"max"` | When correctness matters more than cost |

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
