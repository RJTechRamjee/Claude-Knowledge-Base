# Anthropic API – Reusable Reference

> Model: `claude-sonnet-4-6` | SDK: `anthropic` (Python)

---

## Contents

**Next available section number: 29** — when adding a new section, use this number and bump it here.

1. [Tool Choice](#1-tool-choice)
2. [Content Block Types](#2-content-block-types)
3. [Stop Reasons](#3-stop-reasons)
4. [Built-in (Standard) Tools](#4-built-in-standard-tools)
5. [Local Tool Definition](#5-local-tool-definition)
6. [Current Models and Pricing](#6-current-models-and-pricing)
7. [Session Resumption — The API Is Stateless](#7-session-resumption-the-api-is-stateless)
8. [Message Roles](#8-message-roles)
9. [Top-level Request Parameters](#9-top-level-request-parameters)
10. [Response Object Fields](#10-response-object-fields)
11. [Multi-turn Tool Loop Pattern](#11-multi-turn-tool-loop-pattern)
12. [Session Management (Claude Code CLI)](#12-session-management-claude-code-cli)
13. [maxTurns](#13-maxturns)
14. [Multi-Instance Review Architecture](#14-multi-instance-review-architecture)
15. [Structured Output — Handling Missing Data in Tool Schemas](#15-structured-output-handling-missing-data-in-tool-schemas)
16. [Claude Code Skills – Scope and Resolution](#16-claude-code-skills-scope-and-resolution)
17. [Context Window Management in Long Sessions](#17-context-window-management-in-long-sessions)
18. [Path-Scoped Rules and Symlinks in Claude Code](#18-path-scoped-rules-and-symlinks-in-claude-code)
19. [Prompt Structuring — XML Tags for Category Isolation](#19-prompt-structuring-xml-tags-for-category-isolation)
20. [Claude Code Permission Modes](#20-claude-code-permission-modes)
21. [Claude Code Hooks — Hook Types and Enforcement](#21-claude-code-hooks-hook-types-and-enforcement)
22. [Claude Code Rules — `.claude/rules/` and Path-Scoped Loading](#22-claude-code-rules-clauderules-and-path-scoped-loading)
23. [Claude Code Tool Selection — Bash vs. Read / Glob / Grep](#23-claude-code-tool-selection-bash-vs-read-glob-grep)
24. [Multi-Agent Architecture — Hub-and-Spoke Pattern](#24-multi-agent-architecture-hub-and-spoke-pattern)
25. [Agent Escalation Design — Self-Reported Confidence Scores](#25-agent-escalation-design-self-reported-confidence-scores)
26. [MCP Server Resources — @ Mention Reference Syntax](#26-mcp-server-resources-mention-reference-syntax)
27. [MCP Config — Environment Variable Expansion in `.mcp.json`](#27-mcp-config-environment-variable-expansion-in-mcpjson)
28. [MCP Server Authentication — `headers` vs `headersHelper` vs `oauth`](#28-mcp-server-authentication-headers-vs-headershelper-vs-oauth)

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

---

## 12. Session Management (Claude Code CLI)

Named sessions give you a human-readable, resumable handle for long-running tasks.

### Starting a named session
```bash
claude --name "migration-task"
```

### Renaming during a session
```bash
/rename "migration-task"   # slash command inside an active session
```

### Resuming by name
```bash
claude --resume "migration-task"
```

### Resuming with interactive picker (if name forgotten)
```bash
claude --resume   # no argument → shows list of recent sessions with summaries
```

### Typical workflow
```bash
# Day 1 — start the work
claude --name "q3-security-audit"

# Day 2 — pick up where you left off
claude --resume "q3-security-audit"
```

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

The fix is a post-extraction validation step in application code:

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

## 16. Claude Code Skills – Scope and Resolution

Skills are filesystem-based (not API-hosted). They resolve at two levels:

| Level | Location | Scope |
|---|---|---|
| Project | `.claude/skills/` (inside repo, committed) | Anyone who clones the repo |
| User | `~/.claude/skills/` | You, across all your projects |

### When to use each level
- **Project-level** — skills that are repo-specific (deployment checklist, project conventions). Commit `.claude/skills/` so contributors get it automatically on clone.
- **User-level** — skills you reuse across many projects (personal review template, a prompt you always use). Define once, available everywhere.

### Conflict resolution
If the same skill name exists at both levels, **project-level wins** (more specific overrides less specific).

### Sharing a skill across multiple team project folders

When different developer teams work in separate project folders but need the same skill:

| Strategy | Zero per-dev setup? | Single source of truth? | Best when |
|---|---|---|---|
| Parent-level `.claude/skills/` | ❌ Manual per machine | ❌ Not git-tracked | Folders are co-located, not independent repos |
| Git submodule | ✅ Yes (`--recurse-submodules`) | ✅ Yes | Folders are **independent git repos** |
| CI sync script | ✅ Yes (automated) | ✅ Yes | Independent repos, CI already in place |
| Duplicate per repo | ❌ Manual updates | ❌ No | Repos are independent and infrequently updated |

#### Independent git repos — recommended approach (git submodule)

```bash
# One-time: create a shared skills repo (e.g. org/shared-skills)
# Then in each project repo:
git submodule add https://github.com/org/shared-skills .claude/skills
git commit -m "Add shared Claude Code skills as submodule"
```

Developers clone with:
```bash
git clone --recurse-submodules https://github.com/org/project-sd
```

To pull skill updates into a project:
```bash
git submodule update --remote .claude/skills
git add .claude/skills
git commit -m "Update shared skills"
git push
```

#### Do changes to shared-skills auto-reflect in all projects? No.

Each project pins a **specific commit SHA** of the submodule. Pushing to `shared-skills` does not update consumer projects — they stay on the old commit until explicitly updated.

```
shared-skills:  commit A → commit B (new skill added)
project-sd:     still pinned to commit A  ← unchanged until you run submodule update
project-mm:     still pinned to commit A  ← unchanged until you run submodule update
```

**Options to propagate updates:**

| Approach | Automatic? | Effort |
|---|---|---|
| Manual `git submodule update --remote` per project | ❌ | Low — someone must remember |
| Scheduled GitHub Action in each consumer repo | ✅ periodic | Medium — one workflow per repo |
| `repository_dispatch` fan-out from `shared-skills` | ✅ on every push | Higher — needs PAT + trigger wiring |

**Scheduled GitHub Action (per consumer repo):**
```yaml
# .github/workflows/update-skills.yml
on:
  schedule:
    - cron: '0 9 * * 1'   # every Monday
  workflow_dispatch:

jobs:
  update-skills:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: true
      - run: git submodule update --remote .claude/skills
      - run: |
          git config user.email "ci@org.com"
          git config user.name "CI"
          git add .claude/skills
          git diff --cached --quiet || git commit -m "chore: update shared skills"
          git push
```

#### Keeping skills outside all project repos (symlink approach)

Skills can live in an external clone of `shared-skills` and be symlinked into each project. Requires one-time per-developer setup (document in onboarding).

```bash
# Developer onboarding — do once
git clone https://github.com/org/shared-skills ~/shared-claude-skills

# In each project repo
ln -s ~/shared-claude-skills/skills .claude/skills
```

To get skill updates: just `git pull` inside `~/shared-claude-skills` — symlinks point to live files, so all linked projects see the update instantly. No per-project action needed.

**Selective use — symlink only the projects that need it:**

```bash
# project-sd gets all shared skills
ln -s ~/shared-claude-skills/skills project-sd/.claude/skills

# project-mm gets only one specific skill
mkdir -p project-mm/.claude/skills
ln -s ~/shared-claude-skills/skills/deploy-checklist.md project-mm/.claude/skills/deploy-checklist.md

# project-billing gets nothing → skill not available there
```

Full layout:
```
~/shared-claude-skills/skills/        ← one git pull, updates everywhere
    deploy-checklist.md
    code-review.md

project-sd/.claude/skills/            → symlink → all shared skills
project-mm/.claude/skills/
    deploy-checklist.md               → symlink → one specific skill
project-billing/                         no symlink → no shared skills
```

| Approach | Outside project? | Per-dev setup? | Auto-updates? |
|---|---|---|---|
| Submodule inside repo | ❌ | ❌ clone handles it | ❌ needs CI/manual bump |
| Symlink to external clone | ✅ | ✅ once (onboarding) | ✅ `git pull` in shared repo |
| Copy to `~/.claude/skills/` | ✅ | ✅ once | ❌ manual re-copy |
| Devcontainer / onboarding script | ✅ | ✅ automated | ✅ if scripted |

#### Parent-directory `.claude/skills/` caveat
This only works reliably if all repos are cloned under a common workspace folder **and** each developer manually creates the parent `.claude/skills/`. It is not git-tracked, so it does not travel with a clone — avoid for team use with independent repos.

Claude Code walks up the directory tree (same as CLAUDE.md), so a skill in a **parent directory's** `.claude/skills/` is available to all subdirectories on that machine.

### Personal skills — keeping a skill private to one developer

To create a skill that is **never committed to the shared repo** and **invisible to teammates**:

```
~/.claude/skills/my-standup/SKILL.md
```

- `~` = the user's **home directory** (e.g. `C:\Users\alice\.claude\` on Windows, `~/.claude/` on macOS/Linux) — entirely outside any git repository
- Skills and slash commands are unified: the above file is invokable as `/my-standup`
- The `SKILL.md` file uses YAML frontmatter + Markdown instructions (same format as project skills)
- Because it lives in the home directory, it is **never staged, committed, or visible in pull requests**

**Do NOT use** `.claude/commands/my-standup.md` (no `~`) — that path is inside the project folder, will appear in `git status`, and teammates will see `/my-standup` in their `/` menus.

| Location | In git repo? | Visible to teammates? | Correct for personal use? |
|---|---|---|---|
| `~/.claude/skills/my-standup/SKILL.md` | ❌ Never | ❌ No | ✅ Yes |
| `.claude/skills/my-standup/SKILL.md` | ✅ Yes (committed) | ✅ Yes | ❌ No |
| `.claude/commands/my-standup.md` | ✅ Yes (committed) | ✅ Yes | ❌ No |

### Key facts
- Skills are **not** resolved through the Skills API — that path is for Claude API workspaces, not Claude Code
- `~/.claude/skills/` does **not** sync across machines automatically; copy the file manually or use dotfiles management
- Parent-directory `.claude/skills/` is inherited by all child project directories (directory tree walk-up)
- `~/.claude/` (home directory) is **never inside any git repo** — files there are always private to that developer

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

## 18. Path-Scoped Rules and Symlinks in Claude Code

### How path-scoped rules work

Path-scoped rules (defined in `.claude/settings.json` or CLAUDE.md) apply only when the file being acted on matches a glob pattern. Example:

```json
{
  "rules": [
    {
      "paths": ["src/handlers/**/*.go"],
      "description": "Go handler conventions..."
    }
  ]
}
```

### Symlinked checkouts — rules still trigger

Claude Code evaluates path-scoped rules against **both the symlinked path and the canonical path**. If the project is accessed through a symlink, the rule still fires — no extra configuration needed.

```
Repo lives at:     /Users/eng/code/service
Symlinked to:      /workspace/service
Claude launched from: /workspace/service

File edited:       /workspace/service/src/handlers/middleware/auth.go
Rule paths:        ["src/handlers/**/*.go"]

Result: ✅ rule triggers — Claude Code matches on the symlinked path
```

### What does NOT happen

| Misconception | Reality |
|---|---|
| Rules only evaluate against canonical (resolved) filesystem path | ❌ Claude Code also matches against symlinked paths |
| Must add absolute symlink path as a second `paths` entry | ❌ Not required |
| Rules apply differently for read vs. edit through a symlink | ❌ No distinction — same rule evaluation either way |

### Practical implication

Write path-scoped rules using relative project-root-relative patterns (`src/handlers/**/*.go`). They work correctly whether the project is opened directly or through a symlink — no absolute path entries needed.

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

## 20. Claude Code Permission Modes

Controls what happens when Claude Code wants to run an action that hasn't been explicitly approved.

| Mode | Unapproved action | Human required? | Use for |
|---|---|---|---|
| `default` (interactive) | Prompts user | ✅ Yes | Normal development |
| `acceptEdits` | Auto-approves file edits; prompts for everything else | ✅ For non-edit actions | Dev workflows with frequent file changes |
| `dontAsk` | Denies silently — no prompt | ❌ No | CI/CD, automated pipelines |
| `bypassPermissions` | Allows everything | ❌ No | Dangerous — avoid unless sandboxed |

### `dontAsk` — the CI-safe mode

Anything not covered by `permissions.allow` rules or the built-in read-only command set is **denied immediately without prompting**. The run aborts cleanly rather than hanging for a human who is not present.

```bash
# CLI — locked-down CI runner
claude --permission-mode dontAsk \
       --allowedTools "Bash(git log),Bash(git diff),Read" \
       "Summarize what changed in the last 5 commits"
```

```json
// .claude/settings.json — project-level equivalent
{
  "permissionMode": "dontAsk",
  "permissions": {
    "allow": [
      "Bash(git log:*)",
      "Bash(git diff:*)",
      "Read"
    ]
  }
}
```

### Why other approaches fail in CI

| Approach | Why it fails |
|---|---|
| `acceptEdits` | Auto-approves file writes — not locked down; still prompts for shell commands |
| No allowedTools + timeout | Run hangs until timeout fires — non-deterministic, wastes CI time |
| `--max-turns 1` | Limits loop iterations only; does nothing to control permissions |
| No config (default) | First unapproved action blocks the run waiting for a human |

### Rule: `dontAsk` + explicit `permissions.allow` = deterministic CI

The allowlist defines exactly what Claude can do. Everything else fails fast and silently — no hanging, no surprises.

---

## 21. Claude Code Hooks — Hook Types and Enforcement

Hooks are shell commands Claude Code runs automatically at lifecycle events. The critical distinction is whether a hook can **block** execution or only **observe** it.

### Hook types

| Hook | Runs | Can block? | Use for |
|---|---|---|---|
| `PreToolUse` | Before the tool executes | ✅ Yes — set `permissionDecision` | Enforcing preconditions, access control |
| `PostToolUse` | After the tool executes | ❌ No — tool already ran | Logging, side effects, cleanup |
| `Notification` | On status/notification events | ❌ No — carries status only | Alerting, logging |
| `Stop` | When Claude finishes a turn | ❌ No | Summaries, notifications |

### Why Notification hooks cannot enforce ordering

A Notification hook only carries a status message — it cannot set a `permissionDecision` to block the call. The tool **executes before the notification fires**, so logging a warning in a Notification hook means the refund already ran.

```
Notification hook timeline:
  refund_tool called → refund_tool EXECUTES → notification fires → warning logged
                                 ↑
                          too late to block
```

### MCP tool naming convention

MCP tools exposed through Claude Code follow a fixed naming format:

```
mcp__<server-name>__<tool-name>
```

Examples:
```
mcp__billing__issue_refund
mcp__billing__void_authorization
mcp__billing__apply_credit
mcp__billing__get_balance        ← read-only, same server
```

- Double underscores separate segments
- Tool names are max **64 characters**
- The server-name prefix is how you scope hooks to a specific MCP server

### Targeting multiple MCP tools with one regex matcher

Use a regex alternation in the `matcher` field to cover several tools in one hook registration — no duplication, excludes unrelated tools from the same server:

```json
// .claude/settings.json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__billing__(issue_refund|void_authorization|apply_credit)",
        "hooks": [{
          "type": "command",
          "command": "python3 /scripts/verify_identity.py"
        }]
      }
    ]
  }
}
```

Full example — MCP tool definitions + PreToolUse enforcement:

```python
import anthropic

client = anthropic.Anthropic()

# MCP tools exposed by the billing server
# Named: mcp__billing__<tool-name>
tools = [
    {
        "name": "mcp__billing__issue_refund",
        "description": "Issue a refund to a customer",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "amount":      {"type": "number"}
            },
            "required": ["customer_id", "amount"]
        }
    },
    {
        "name": "mcp__billing__void_authorization",
        "description": "Void a pending authorization",
        "input_schema": {
            "type": "object",
            "properties": {"auth_id": {"type": "string"}},
            "required": ["auth_id"]
        }
    },
    {
        "name": "mcp__billing__apply_credit",
        "description": "Apply a credit to an account",
        "input_schema": {
            "type": "object",
            "properties": {
                "account_id": {"type": "string"},
                "amount":     {"type": "number"}
            },
            "required": ["account_id", "amount"]
        }
    },
    {
        "name": "mcp__billing__get_balance",   # read-only — hook does NOT fire for this
        "description": "Get current account balance",
        "input_schema": {
            "type": "object",
            "properties": {"account_id": {"type": "string"}},
            "required": ["account_id"]
        }
    }
]

# Hook in settings.json fires ONLY for the three money-moving tools
# matcher: "mcp__billing__(issue_refund|void_authorization|apply_credit)"
```

### Three layers: schema vs. implementation vs. hook

```
Schema         → tells Claude the tool exists and what args it takes (Claude reads this)
Implementation → your Python function with the actual business logic (DB/API calls)
Router         → maps tool name → implementation function (your code runs this)
PreToolUse hook→ runs BEFORE the router; if it denies, implementation never executes
```

Full working example — schema + implementation + router + agentic loop:

```python
import anthropic, json
client = anthropic.Anthropic()

# 1. SCHEMAS — Claude sees these
tools = [
    {
        "name": "mcp__billing__issue_refund",
        "description": "Issue a refund to a customer",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "amount":      {"type": "number"}
            },
            "required": ["customer_id", "amount"]
        }
    },
    {
        "name": "mcp__billing__get_balance",
        "description": "Get current account balance",
        "input_schema": {
            "type": "object",
            "properties": {"account_id": {"type": "string"}},
            "required": ["account_id"]
        }
    }
]

# 2. IMPLEMENTATIONS — your actual business logic
def issue_refund(customer_id: str, amount: float) -> dict:
    if amount > 10000:
        return {"success": False, "error": "Exceeds single-refund limit"}
    # billing_db.refund(customer_id, amount)  ← real call goes here
    return {"success": True, "refund_id": "REF-9921", "customer_id": customer_id, "amount": amount}

def get_balance(account_id: str) -> dict:
    # billing_db.get_balance(account_id)  ← real call goes here
    return {"account_id": account_id, "balance": 4250.00, "currency": "USD"}

# 3. ROUTER — maps tool name → implementation
def run_tool(tool_name: str, tool_input: dict) -> str:
    if tool_name == "mcp__billing__issue_refund":
        result = issue_refund(**tool_input)
    elif tool_name == "mcp__billing__get_balance":
        result = get_balance(**tool_input)
    else:
        result = {"error": f"Unknown tool: {tool_name}"}
    return json.dumps(result)

# 4. AGENTIC LOOP
messages = [{"role": "user", "content": "Issue a $500 refund to customer C-42, then check their balance."}]
response = client.messages.create(model="claude-sonnet-4-6", max_tokens=1024, tools=tools, messages=messages)

while response.stop_reason == "tool_use":
    tool_call = next(b for b in response.content if b.type == "tool_use")
    tool_result = run_tool(tool_call.name, tool_call.input)   # PreToolUse hook already ran here
    messages.append({"role": "assistant", "content": response.content})
    messages.append({"role": "user", "content": [{
        "type": "tool_result",
        "tool_use_id": tool_call.id,
        "content": tool_result
    }]})
    response = client.messages.create(model="claude-sonnet-4-6", max_tokens=1024, tools=tools, messages=messages)

print(next(b.text for b in response.content if b.type == "text"))
```

### Matcher scope comparison

| Matcher | Fires for |
|---|---|
| `mcp__billing__(issue_refund\|void_authorization\|apply_credit)` | ✅ Exactly the 3 money-moving tools |
| `mcp__billing__.*` | All tools from billing server (including read-only) |
| `mcp__billing` | ❌ Nothing — incomplete name format |
| *(no matcher)* | Every tool call in the session |
| `*` | Every tool call in the session |

### Correct pattern: PreToolUse hook for deterministic enforcement

To enforce "refund_tool must never run before verify_tool succeeds":

```json
// .claude/settings.json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "refund_tool",
        "hooks": [{
          "type": "command",
          "command": "bash -c 'cat /tmp/verify_status | grep -q SUCCESS || (echo \"verify_tool has not succeeded\" && exit 1)'"
        }]
      }
    ]
  }
}
```

- `matcher` targets a specific tool name — the hook fires only for `refund_tool`, not every tool call
- Exit code `1` from the command sets `permissionDecision` to block — the tool never runs
- Exit code `0` allows execution to proceed

### PreToolUse: modifying input with `updatedInput`

A PreToolUse hook can do more than block — it can **rewrite the tool's input** before execution by returning `updatedInput`. This enables normalization + enforcement in one hook.

```python
# Hook return shapes
{"decision": "allow"}                          # pass through unchanged
{"decision": "allow", "updatedInput": {...}}   # pass through with modified input
{"decision": "deny",  "reason": "..."}         # block — tool never runs
```

**Single hook: normalize + enforce (correct)**
```python
def pre_tool_hook(tool_name, tool_input):
    if tool_name == "process_payment":
        # Step 1: normalize
        amount = tool_input["amount"]
        if isinstance(amount, str):
            amount = float(amount.replace("$", "").replace(",", ""))

        # Step 2: enforce threshold
        if amount > COMPLIANCE_LIMIT:
            return {"decision": "deny", "reason": f"{amount} exceeds compliance limit"}

        # Step 3: return clean input to the tool
        return {"decision": "allow", "updatedInput": {**tool_input, "amount": amount}}
```

### `updatedInput` does NOT propagate between multiple PreToolUse hooks

Each PreToolUse hook receives the **original input**, not a previous hook's `updatedInput`. If you split normalization and enforcement into two separate hooks, the enforcement hook sees the raw un-normalized value.

```
Two hooks (wrong for transform + enforce):
  original input: {amount: "$1,250.00"}
  Hook 1 → normalizes → returns updatedInput: {amount: 1250.0}
  Hook 2 → still sees {amount: "$1,250.00"} ← original, not Hook 1's output
           → threshold check runs against string → broken
```

**Rule: if Hook B depends on Hook A's transformation, combine them into one hook.**

### Multiple PreToolUse hooks on the same event — conflict resolution

When several hooks fire for the same event, the **most restrictive decision wins**:

```
deny > defer > ask > allow
```

Example: three hooks registered for `process_refund`:
- Identity verification hook → `"deny"`
- Fraud-score hook → `"allow"`
- Audit logging hook → `{}` (empty object, i.e. no decision)

Result: **tool call is blocked** — `deny` from any hook overrides `allow` results from all others. The empty-object response is treated as abstention and does not influence the outcome.

| Decision priority (highest → lowest) | Meaning |
|---|---|
| `deny` | Block the tool call unconditionally |
| `defer` | Block but allow a human to override |
| `ask` | Pause and prompt the user |
| `allow` | Permit execution |
| `{}` (empty / no field) | Abstain — does not affect outcome |

### Key facts
- Only `PreToolUse` can block a tool call — all other hooks are observational
- `PreToolUse` can also rewrite tool input via `updatedInput` before the tool executes
- `updatedInput` from one PreToolUse hook does NOT propagate to the next — each hook sees the original input
- When multiple PreToolUse hooks disagree, the most restrictive decision wins (`deny > defer > ask > allow`)
- `Notification` hooks fire after the fact and cannot prevent execution
- Hook matchers can be scoped to specific tool names (not session-wide)
- `PostToolUse` cannot block — the tool has already executed by the time it fires

---

## 22. Claude Code Rules — `.claude/rules/` and Path-Scoped Loading

`.claude/rules/*.md` files carry the same YAML-frontmatter convention as skills. The presence or absence of a `paths` field in that frontmatter changes *when* the rule is loaded into context — it does not change *whether* it is a valid rule.

### No `paths` field → unconditional, session-start load

```yaml
---
# .claude/rules/general-style.md — no `paths` key
---
Use 2-space indentation. Prefer named exports.
```

Loads at session start with the **same priority as `.claude/CLAUDE.md`** — every session, regardless of which files are touched.

### `paths` field present → conditional, per-file load

```yaml
---
paths: ["src/api/**/*.ts"]
---
All API handlers must validate input with zod before touching the DB.
```

This rule stays out of context until Claude reads (or edits) a file matching the glob. It is injected only when a matching file enters the working context — not at launch, and not for unrelated files.

### User-level vs project-level rules — load order and conflict resolution

Both `~/.claude/rules/` (user-level) and `.claude/rules/` (project-level) files load unconditionally when they have no `paths` field. **User-level rules load before project-level rules.**

However, load order does **not** guarantee deterministic conflict resolution. When two unconditional rules give conflicting guidance for the same behaviour, Claude sees both instructions in context simultaneously and may choose between them arbitrarily. There is no strict "project overrides user" guarantee for rules.

**This is different from Skills:**

| Feature | Conflict resolution |
|---|---|
| **Skills** | Only one skill fires per invocation — the most specific level wins (project > user). The other is never loaded. |
| **Rules** | Both files load into context simultaneously. Claude sees two contradictory instructions and must resolve them linguistically — which is non-deterministic. |

**The fix is structural, not sequential:** if two rules conflict, remove or reconcile the conflict rather than relying on load order. Options:
- Consolidate into a single file at one level
- Add a `paths:` field to one rule so they never both apply in the same context
- Remove the user-level rule if the project rule supersedes it

**What does NOT work:**
- Assuming project-level always wins (it does not — both load)
- Assuming user-level is ignored when a same-named project file exists (both files load independently; the name match is irrelevant)

### Key facts
- Omitting `paths` does **not** disable a rule and does **not** scope it to the `.claude/rules/` directory itself — it makes the rule unconditional (always loaded)
- `paths` patterns are project-root-relative globs, matched against files Claude actually reads/edits during the session
- A file with `paths` and a file without `paths` can coexist in the same `.claude/rules/` folder with completely different load timing
- User-level rules load before project-level rules, but this is not a strict override — conflicting unconditional rules are non-deterministic; reconcile conflicts structurally
- This mirrors the [[path-scoped rules]] behavior in section 18, but that section covers symlink path-matching; this section covers the `paths`-vs-no-`paths` load-trigger distinction

### `.claude/` — recognized subfolders and files (project-level)

| Path | Purpose |
|---|---|
| `CLAUDE.md` (repo root, or `.claude/CLAUDE.md`) | Project instructions, loaded every session |
| `.claude/rules/*.md` | Topic-scoped instructions, optionally gated by `paths:` frontmatter (this section) |
| `.claude/skills/<name>/SKILL.md` | Reusable prompt packages, invoked as `/<name>` |
| `.claude/agents/<name>.md` | Subagent definitions with isolated context |
| `.claude/agent-memory/<name>/` | Persistent memory storage for project-scoped subagents |
| `.claude/output-styles/<name>.md` | Custom system-prompt sections |
| `.claude/settings.json` | Permissions, hooks, env vars, model defaults — committed |
| `.claude/settings.local.json` | Personal per-project overrides — gitignored |
| `.claude/.mcp.json` | Team-shared MCP server configs |
| `.claude/.worktreeinclude` | Gitignored files to copy into new worktrees |

User-level mirrors exist under `~/.claude/` for `CLAUDE.md`, `rules/`, `skills/`, `agents/`, `agent-memory/`, and `output-styles/`. Hooks have **no dedicated folder** — they are configured entirely inside `settings.json` under the `hooks` key (see section 21). Commands are not a separate folder either; slash commands are served by `skills/`.

---

## 23. Claude Code Tool Selection — Bash vs. Read / Glob / Grep

Choosing the wrong tool produces no result or a misleading one. The rule: **static file operations use dedicated tools; execution and live output require Bash.**

| Goal | Correct tool | Wrong tool (and why it fails) |
|---|---|---|
| Run a test suite and capture stack trace | **Bash** — invokes the runner, captures stdout/stderr | `Read` — reads config, not live output; `Glob` — finds files, not pass/fail status |
| Find files by name pattern | **Glob** | `Bash(find …)` — works but slower and less integrated |
| Search file contents for a symbol | **Grep** | `Bash(grep …)` — works but bypasses the optimised tool |
| Read a specific file's contents | **Read** | `Bash(cat …)` — unnecessary shell overhead |
| Run any terminal command (build, lint, deploy, git) | **Bash** | No substitute — only Bash executes commands |

### Why Glob / Grep / Read cannot replace Bash for test execution

- **Glob** lists files that *match a pattern* — finding `**/*.test.*` only confirms test files exist, not that they pass.
- **Grep** finds text in files — matching the word "test" in source code says nothing about runtime behaviour.
- **Read** opens a file — reading a test runner's config describes how tests are *configured*, not the current pass/fail outcome.

Only **Bash** actually executes the command and returns its stdout and stderr (including the stack trace), which is what is needed to reproduce and observe a failure.

### Finding files across multiple naming conventions — still Glob, not Grep

A task like "find every test file, where naming mixes `.test.tsx`, `.spec.tsx`, and legacy `Test.tsx`" is still a pure **path-pattern** problem — having several conventions just means running Glob with several patterns (or one call per pattern), not switching tools:

```python
Glob(pattern="**/*.test.tsx")
Glob(pattern="**/*.spec.tsx")
Glob(pattern="**/*Test.tsx")
```

The classic trap here is reaching for **Grep** with a pattern like "the word `test` anywhere in the file" — that searches **file contents**, not file names. It fails in both directions: it can match unrelated files that merely mention testing in a comment/string, and it can miss genuine test files whose contents never contain the literal word "test". Grep is for content; Glob is for path/name patterns — mixing them up is the same category error as using Bash+manual-Read to answer a pure name-matching question (previous subsection).

### Grep — `type` parameter and multiline mode

#### Scoping to a language with `type`
The `type` parameter restricts Grep to files of a given language, equivalent to `rg --type`. This is more efficient than a glob and works repo-wide:

```python
# Search only Python files
Grep(pattern="BaseHandler", type="py")

# Search only TypeScript files
Grep(pattern="interface User", type="ts")
```

Common type values: `py`, `ts`, `js`, `rust`, `go`, `java`, `rb`, `cs`, `cpp`.

#### Matching patterns that span multiple lines — `multiline: true`

By default, Grep matches within single lines only. If a class definition (or any construct) wraps across lines, a single-line search misses it. Enable `multiline: true` to allow the pattern to cross line boundaries:

```python
# Matches both:
#   class OrderHandler(BaseHandler):
#   class OrderHandler(\n    BaseHandler, LoggingMixin\n):
Grep(
    pattern=r"class \w+\([^)]*BaseHandler",
    type="py",
    multiline=True
)
```

Without `multiline=True`, the second form is invisible to Grep — the newline breaks the match.

#### `output_mode` does NOT affect search thoroughness

`output_mode` controls the *format* of results, not how deeply Grep searches:
- `"files_with_matches"` — returns file paths only (default)
- `"content"` — returns matching lines with context
- `"count"` — returns match counts per file

Switching from `"files_with_matches"` to `"content"` does not make Grep search more files or match more patterns. Use `multiline: true` to fix missed multi-line matches.

#### Wrong alternatives
- **Glob + Read every file** — lists files correctly but requires reading each one in full to check content; does not scale across large codebases
- **Bash(grep …)** — works but bypasses the optimised tool and requires shell permissions

### `Edit` vs `Write` — surgical change vs. whole-file reformat

Use **`Edit`** for targeted changes to a few known strings. Use **`Write`** when nearly every line of a file must be changed (e.g., re-indenting a generated 900-line file).

| Scenario | Right tool | Wrong tool (and why) |
|---|---|---|
| Fix a single function name in a file | **`Edit`** | `Write` — rewrites the entire file unnecessarily |
| Reformat indentation across 900 lines | **`Write`** (after `Read`) | `Edit` × 900 — hundreds of fragile per-line calls; `Grep` — read-only, does not write back |
| Replace a hard-coded string in 3 places | **`Edit`** with `replace_all` | `Write` — overkill |
| Normalize whitespace on nearly every line | **`Write`** (after `Read`) | `Edit` per line — infeasible and error-prone at scale |

#### The read-modify-write pattern for whole-file reformatting

1. **`Read`** — confirm current file state (even if read earlier; ensures no concurrent edits)
2. Apply transformation in memory (re-indent, reformat, etc.)
3. **`Write`** — replace the entire file in a single call

```python
# Claude's internal flow for whole-file reformat:
content = Read(file_path="generated_output.py")   # step 1: confirm state
reformatted = reindent(content)                    # step 2: transform
Write(file_path="generated_output.py",             # step 3: single write
      content=reformatted)
```

**Why not `Edit` per line?** `Edit` requires `old_string` to match exactly. On a 900-line file with inconsistent whitespace on nearly every line, issuing ~900 Edit calls is slow, fragile (any mismatch aborts), and was not designed for this workload.

**Why not `Grep`?** `Grep` is a **read-only** search tool. Retrieving lines with `output_mode: "content"` returns matching text — it does not rewrite or modify the file in place.

**Why not `Glob`?** `Glob` returns file *paths* sorted by modification time. It has no ability to read or rewrite file content.

### Key facts
- Use `Bash` whenever you need a process to run and return its live output
- Reading a config file is not a substitute for running the program
- Prefer the dedicated `Read`, `Glob`, `Grep` tools over their Bash equivalents for pure file operations — they are faster and require fewer permissions
- Use `type` to scope Grep to a language repo-wide; use `multiline: true` when patterns span line breaks
- `output_mode` changes result format only — it does not affect which lines are matched
- For whole-file reformats: `Read` → transform → `Write`; never `Edit` per line at scale

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

## 26. MCP Server Resources — @ Mention Reference Syntax

MCP servers expose two distinct mechanisms:
- **Tools** — callable functions Claude invokes via tool use
- **Resources** — readable documents or data Claude can pull into context

### Referencing a resource inline in a prompt

Use the prescribed **@ mention** syntax to include a specific MCP resource directly in a prompt, the same way you would reference a local file:

```
@<server-name>:<protocol>://<resource-path>
```

**Example** — server named `docs`, resource at `file://api/authentication`:
```
@docs:file://api/authentication
```

Claude fetches that resource and inlines it into the context. The developer can place this anywhere in their prompt message.

### Why other approaches fail

| Approach | Why it fails |
|---|---|
| Add `resources` field to `.mcp.json` | `.mcp.json` configures server connections (command, args, env). No `resources` field exists that auto-loads docs into every session. |
| Ask Claude in plain language to "open the docs server" | No prescribed syntax — Claude may guess, access the wrong resource, or call `list_resources` instead. |
| Call `list_resources` first, paste raw JSON | A manual workaround that bypasses the purpose of the @ mention syntax. |

### Key facts
- MCP **resources** → referenced with `@server:protocol://path` inline in the prompt
- MCP **tools** → called by Claude via tool use during the agentic loop
- The @ mention syntax is the prescribed way to point at a specific resource, equivalent to referencing a local file
- The server name in the @ mention must match the name configured in `.mcp.json`

---

## 27. MCP Config — Environment Variable Expansion in `.mcp.json`

`.mcp.json` supports shell-style variable expansion so machine-specific values (API keys, regions, ports) don't need to be hardcoded into a team-shared config file.

### Syntax

| Form | Behavior when `VAR` is unset |
|---|---|
| `${VAR}` | Expands to blank (or triggers a parse failure, depending on strictness) — no fallback exists |
| `${VAR:-default}` | Expands to the literal `default` text — the fallback only triggers because a default was explicitly supplied |

### Where expansion applies

The expansion is a config-wide text substitution — it is **not** scoped to a single field. It works identically in:
- `command`
- `args`
- `env`
- `url`
- `headers`

**Example:**
```jsonc
{
  "mcpServers": {
    "my-server": {
      "command": "my-server-bin",
      "args": ["--region", "${API_REGION:-us-east-1}"],
      "env": { "API_KEY": "${MY_API_KEY}" }
    }
  }
}
```

If `API_REGION` is unset on the host machine, Claude Code passes the literal string `us-east-1` as the `args` value — the same `${VAR:-default}` mechanic that works in `env` also works in `args` (and `url`/`headers`).

### Common misconceptions

| Claim | Why it's wrong |
|---|---|
| Default-value expansion only works inside `env`, not `args` | Expansion is config-wide; `args`, `url`, and `headers` all support the same `${VAR:-default}` syntax |
| An unset variable always expands to an empty string | Only true for bare `${VAR}` with no default. `${VAR:-default}` overrides that behavior by design |
| Claude Code requires every referenced variable to be set, or config parsing fails | A parse failure risk applies only to bare `${VAR}` (no default) left unset — supplying `:-default` is specifically what avoids that failure |

### Key facts
- `${VAR:-default}` is standard POSIX-shell-style parameter expansion, adopted by Claude Code for `.mcp.json`
- Supplying a default is what makes an otherwise-unset variable resolve safely and predictably across machines
- This lets a single `.mcp.json` be checked into git and shared across a team, while still tolerating machines where an optional env var (e.g. a region override) isn't set

---

## 28. MCP Server Authentication — `headers` vs `headersHelper` vs `oauth`

MCP server configs in `.mcp.json` support three distinct authentication mechanisms, each suited to a different token lifecycle:

| Mechanism | Use when | Behavior |
|---|---|---|
| `headers` (static) | The auth value is stable and rarely rotates | A hardcoded header value sits in config; rotating it requires manually editing the file |
| `headersHelper` (also called `apiKeyHelper`) | The token must be generated dynamically — short-lived tokens, Kerberos, signed requests | Claude Code runs an external script/command on **each connection**; the script writes fresh header JSON to stdout, which is used for that connection |
| `oauth` block (e.g. `authServerMetadataUrl`) | An actual OAuth authorization server exists | Claude Code discovers and drives the OAuth flow automatically against that server |

### Example — `headersHelper`

```jsonc
{
  "mcpServers": {
    "kerberos-server": {
      "url": "https://internal-mcp.example.com",
      "headersHelper": "generate-kerberos-token.sh"
    }
  }
}
```

`generate-kerberos-token.sh` runs fresh on every connection and prints the resulting header JSON (e.g. `{"Authorization": "Negotiate <token>"}`) to stdout — satisfying a "freshly minted per connection" requirement that a static value or an OAuth flow cannot.

### Why the other two mechanisms don't fit a "freshly minted, no OAuth server" scenario

- **Static `headers`** — a hardcoded token is minted once and reused until someone manually rotates the config file. This is the opposite of "freshly minted for every connection."
- **`oauth` block** — exists specifically so Claude Code can discover and run a flow against a real OAuth authorization server. If no such server exists (e.g. auth is Kerberos-derived), there is nothing for `authServerMetadataUrl` to point at — the mechanism doesn't apply.
- **Changing `--transport` (e.g. to `sse`)** — transport (`http`/`sse`/`stdio`) only affects how data is streamed over the wire. It carries no authentication logic of its own; auth is always handled via `headers`/`headersHelper`/`oauth`, independent of transport choice.

### Key facts
- `headersHelper`/`apiKeyHelper` = the mechanism for **dynamically generated, per-connection** credentials via an external script
- `headers` = static, hand-rotated credentials
- `oauth` block = only applicable when a real OAuth authorization server is in play
- Transport (`http` vs `sse` vs `stdio`) is orthogonal to authentication — never conflate the two
