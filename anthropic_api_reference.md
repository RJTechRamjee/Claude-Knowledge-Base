# Anthropic API – Reusable Reference

> Model: `claude-sonnet-4-6` | SDK: `anthropic` (Python)

---

## 1. Tool Choice

Controls whether and how Claude uses tools.

```python
tool_choice={"type": "auto"}                        # Claude decides (default)
tool_choice={"type": "any"}                         # Claude must call some tool
tool_choice={"type": "tool", "name": "calculator"}  # Force a specific tool
tool_choice={"type": "none"}                        # Disable all tools
```

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
{"type": "web_search_20250305",   "name": "web_search"}         # Web search
{"type": "bash_20250124",         "name": "bash"}                # Run bash commands
{"type": "text_editor_20250124",  "name": "str_replace_editor"}  # Edit files
{"type": "computer_use_20251022", "name": "computer"}            # Control computer
```

### Built-in vs Local Tool Comparison

| | Built-in | Local |
|---|---|---|
| Has `type` field | ✅ Yes (versioned) | ❌ No |
| Has `input_schema` | ❌ No | ✅ Yes |
| Who runs the tool | Anthropic | You |
| Needs second turn | ❌ No | ✅ Yes |

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

## 6. Session Resumption — The API Is Stateless

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

## 7. Message Roles

```python
{"role": "user",      "content": "..."}  # Human turn
{"role": "assistant", "content": "..."}  # Claude turn
# System prompt is a separate top-level param, NOT a role in messages[]
```

---

## 8. Top-level Request Parameters

```python
client.messages.create(
    model=          "claude-sonnet-4-6",  # required
    max_tokens=     1000,                 # required — hard ceiling on output
    messages=       [...],                # required — conversation history
    system=         "You are...",         # optional — system prompt
    tools=          [...],                # optional — tool definitions
    tool_choice=    {...},                # optional — see section 1
    temperature=    0.7,                  # optional — 0.0–1.0, default 1.0
    top_p=          0.9,                  # optional — nucleus sampling
    top_k=          50,                   # optional — top-k sampling
    stop_sequences= ["STOP"],             # optional — custom stop strings
    stream=         True,                 # optional — streaming mode
    metadata=       {"user_id": "123"},   # optional — request metadata
)
```

---

## 9. Response Object Fields

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

## 10. Multi-turn Tool Loop Pattern

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

---

## 11. Session Management (Claude Code CLI)

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

## 12. maxTurns

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

## 13. Multi-Instance Review Architecture

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

---

## 14. Structured Output — Handling Missing Data in Tool Schemas

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

---

## 15. Claude Code Skills – Scope and Resolution

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

### Key facts
- Skills are **not** resolved through the Skills API — that path is for Claude API workspaces, not Claude Code
- `~/.claude/skills/` does **not** sync across machines automatically; copy the file manually or use dotfiles management
- Parent-directory `.claude/skills/` is inherited by all child project directories (directory tree walk-up)

---

## 16. Context Window Management in Long Sessions

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

---

## 17. Path-Scoped Rules and Symlinks in Claude Code

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

## 18. Prompt Structuring — XML Tags for Category Isolation

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

## 19. Claude Code Permission Modes

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

## 20. Claude Code Hooks — Hook Types and Enforcement

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

### Key facts
- Only `PreToolUse` can block a tool call — all other hooks are observational
- `PreToolUse` can also rewrite tool input via `updatedInput` before the tool executes
- `updatedInput` from one PreToolUse hook does NOT propagate to the next — each hook sees the original input
- `Notification` hooks fire after the fact and cannot prevent execution
- Hook matchers can be scoped to specific tool names (not session-wide)
- `PostToolUse` cannot block — the tool has already executed by the time it fires

---

*Reference based on Anthropic API as of August 2026. Check [docs.anthropic.com](https://docs.anthropic.com) for the latest. See [mental_map.md](mental_map.md) for a full structural overview.*
