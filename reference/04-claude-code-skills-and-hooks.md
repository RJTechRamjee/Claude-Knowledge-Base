# Claude Code Skills and Hooks

Skills scope and resolution (project vs. user, sharing across repos) and hooks (hook types, blocking vs. observational, enforcement patterns).

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

### Skills vs Commands — format comparison

**Commands** (`.claude/commands/*.md` or `~/.claude/commands/*.md`) are the **legacy format**: a plain Markdown file whose content becomes the prompt for a slash command. No frontmatter, no configuration options.

**Skills** (`.claude/skills/<name>/SKILL.md`) are the **current best-practice format**: YAML frontmatter + Markdown instructions. Skills unlock the full configuration layer.

| Capability | Commands (legacy) | Skills (current) |
|---|---|---|
| Becomes a slash command | ✅ | ✅ (unified — same `/name` invocation) |
| `allowed-tools` (auto-approve tools) | ❌ | ✅ |
| `context: fork` (isolated subagent) | ❌ | ✅ |
| `paths:` (auto-activate on file match) | ❌ | ✅ |
| `user-invocable: false` (hide from `/` menu) | ❌ | ✅ |
| Anthropic current recommendation | ❌ Legacy | ✅ Yes |

**When to use which:** Use **skills** for all new work. Commands still function but offer none of the frontmatter configuration and are not the recommended approach.

`~/.claude/commands/my-standup.md` is technically valid (user-level, never committed), but it is **not the best-practice answer** — Anthropic recommends `~/.claude/skills/my-standup/SKILL.md` with frontmatter for any reusable workflow.

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

| Location | In git repo? | Visible to teammates? | Best practice? |
|---|---|---|---|
| `~/.claude/skills/my-standup/SKILL.md` | ❌ Never | ❌ No | ✅ Yes — recommended |
| `~/.claude/commands/my-standup.md` | ❌ Never | ❌ No | ⚠️ Valid but legacy format |
| `.claude/skills/my-standup/SKILL.md` | ✅ Yes (committed) | ✅ Yes | ❌ Not for personal use |
| `.claude/commands/my-standup.md` | ✅ Yes (committed) | ✅ Yes | ❌ No |

### `context: fork` — isolated subagent execution

`context: fork` in `SKILL.md` frontmatter causes the skill to run in an **isolated subagent context**. All intermediate steps (brainstorming, reasoning, tool calls) stay inside the forked context and never enter the main conversation history. Only the final result is returned to the user.

```yaml
---
# .claude/skills/explore-alternatives/SKILL.md
context: fork
---
Brainstorm several competing architecture approaches, evaluate each,
and return only your final recommendation with rationale.
```

**What `context: fork` does:**
- Spawns a subagent for the skill's execution
- All intermediate back-and-forth stays inside the forked context
- Only the subagent's final output surfaces back to the main conversation
- Main conversation history is never polluted with exploratory reasoning

**Without `context: fork`:** the skill runs inline — every intermediate step is visible in the main conversation, cluttering history.

### `context: fork` + `agent: <type>` — the agent type controls starting context, not `fork` itself

`context: fork` only establishes *isolation* (subagent runs, only final result returns to the main conversation). It does **not**, by itself, determine which files the forked subagent starts with — that is a property of the **agent type** named in `agent:`.

```yaml
---
# .claude/skills/pr-summary/SKILL.md
context: fork
agent: Explore
---
Fetch PR data and summarize it.
```

`agent: Explore` runs the skill inside Claude Code's built-in **Explore** agent — a fast, read-only search agent deliberately designed for **lean context** (progressive disclosure: start minimal, load more only if needed). As part of that design, `Explore` does **not** load broad project-level files like `CLAUDE.md` at startup. A skill forked into `Explore` sees only the skill's own content plus `Explore`'s system prompt — project conventions defined in `CLAUDE.md` never enter that context, so a summary it produces cannot reflect those conventions.

This is agent-type-specific, not a general `fork` behavior — forking into a different agent type (e.g. `general-purpose`) would load CLAUDE.md normally, since that agent isn't built around the same lean-context constraint.

| Claim | Reality |
|---|---|
| `context: fork` always strips CLAUDE.md from every subagent | ❌ Fork only isolates; content available inside the fork depends on the agent type used |
| `allowed-tools: Read` is required for CLAUDE.md to load into a forked agent | ❌ Not a real mechanism — CLAUDE.md loading isn't gated by tool permissions |
| CLAUDE.md loads only when a skill is invoked without arguments | ❌ Invented — argument presence has no bearing on CLAUDE.md loading |

**Rule:** when debugging "why doesn't my forked skill see project conventions," check which `agent:` type is forked into and whether that agent type is designed to skip broad context loading — not whether `context: fork` is present.

### SKILL.md frontmatter field reference

| Field | Purpose | What it does NOT do |
|---|---|---|
| `context: fork` | Run skill in isolated subagent; only final result returns | Does not restrict tools or hide the skill |
| `allowed-tools: <list>` | Auto-approve listed tools (no prompt) | Does not restrict or sandbox tool access |
| `paths: <glob>` | Auto-activate skill when matching files are touched | Does not affect execution context or tool access |
| `user-invocable: false` | Hide skill from the `/` command menu | Does not isolate execution — skill still runs inline |

### `allowed-tools` frontmatter — auto-approval, NOT restriction

The `allowed-tools` field in `SKILL.md` frontmatter is a **permission-prompt bypass**, not a sandbox:

```yaml
---
# .claude/skills/report-generator/SKILL.md
allowed-tools: Write Edit
---
Generate a report and write it to a file.
```

**What it does:** Tools listed under `allowed-tools` are auto-approved for that skill invocation — the user is not prompted to click "Approve" when they fire.

**What it does NOT do:** It does not restrict which tools the skill can access. Bash, Glob, and any other tool are still available to the skill; they will simply trigger a normal permission prompt when invoked.

| Belief | Reality |
|---|---|
| `allowed-tools: Write Edit` restricts the skill to file operations only | ❌ Bash and all other tools remain accessible |
| `allowed-tools` is the recommended least-privilege mechanism | ❌ It is a UX convenience (fewer prompts), not a security boundary |
| `allowed-tools` sandboxes the skill and disables unlisted tools | ❌ No sandboxing occurs — unlisted tools still run (with prompt) |

**To actually restrict tool access**, apply restrictions at the CLI or settings layer:
- `--allowedTools Write,Edit` — restrict this invocation to listed tools
- `--disallowedTools Bash` — remove a specific tool from this invocation
- `permissions.deny` in `.claude/settings.json` — project-level permanent restriction

### Workspace trust gates `allowed-tools` for project-level skills

`allowed-tools` grants in project skills (`.claude/skills/`) are **inactive until the user accepts the workspace trust dialog**. This is a security measure: a cloned repo's skills cannot auto-approve dangerous commands until the developer explicitly signals they trust the workspace.

```
Flow for a newly cloned repo:
  1. Developer clones repo containing .claude/skills/publish/SKILL.md
     (frontmatter: allowed-tools: Bash(npm publish *))
  2. Developer opens project in Claude Code
  3. Workspace trust dialog NOT yet accepted
  4. Developer invokes /publish skill
  5. Claude Code prompts for approval — allowed-tools grant is inactive
  6. Developer accepts workspace trust dialog
  7. Next invocation of /publish: no prompt — grant is now active
```

| Skill location | Trust requirement for `allowed-tools` to activate |
|---|---|
| `~/.claude/skills/` (user-level) | None — user placed it there, implicitly trusted |
| `.claude/skills/` (project-level) | Must accept workspace trust dialog for that project |

**Common misconception:** `allowed-tools` only works for user-level skills (`~/.claude/skills/`). Reality: it works for both levels — project skills just require workspace trust acceptance first.

**Syntax note:** Scoped bash commands use the pattern `Bash(command-prefix *)`:
```yaml
allowed-tools: Bash(npm publish *)   # pre-approves any npm publish invocation
allowed-tools: Bash(git log *) Read  # pre-approves git log and Read tool
```

### Key facts
- Skills are **not** resolved through the Skills API — that path is for Claude API workspaces, not Claude Code
- `~/.claude/skills/` does **not** sync across machines automatically; copy the file manually or use dotfiles management
- Parent-directory `.claude/skills/` is inherited by all child project directories (directory tree walk-up)
- `~/.claude/` (home directory) is **never inside any git repo** — files there are always private to that developer
- `allowed-tools` in `SKILL.md` = auto-approve listed tools (no prompt); it does NOT sandbox or restrict the skill's tool access

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
