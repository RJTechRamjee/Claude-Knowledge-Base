# Claude Code Configuration

CLI session management, path-scoped rules and symlinks, permission modes, `.claude/rules/`, and tool selection (Bash vs. Read/Glob/Grep).

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

### Resuming by explicit `session_id` — the CI/parallel-job pattern

When multiple `claude -p` invocations run concurrently (e.g., parallel GitHub Actions jobs reviewing different PRs), `--continue` is unreliable because it attaches to the *most recent* session by timestamp — which may belong to a different concurrent job.

The deterministic approach: capture the `session_id` from the first call's JSON output and pass it explicitly to the second call.

```bash
# Step 1 — first invocation, capture session_id from JSON output
RESPONSE=$(git diff origin/main | claude -p 'review this PR for bugs' --output-format json)
SESSION_ID=$(echo "$RESPONSE" | jq -r '.session_id')

# Step 2 — second invocation, resume exactly that session
claude -p 'what is the most critical issue you found?' --resume "$SESSION_ID"
```

`--output-format json` makes the CLI emit a JSON object whose `session_id` field is the stable identifier for that conversation. Passing it to `--resume` bypasses any "most recent" heuristic.

### Cost tracking from the same JSON output — no new flags needed

The Claude Code CLI's `--output-format json` payload already includes `total_cost_usd` and a **per-model cost breakdown**, alongside `result` and `session_id` — a pipeline that only reads `.result` can extend to cost tracking by reading more fields from the same response, no additional flags required.

**Note on scope:** `total_cost_usd` is specific to the Claude Code CLI's JSON output — it is not a field the raw Messages API returns. Calling the API directly via `client.messages.create()` gives you `usage` (token counts) instead; cost must be computed from `usage` against the pricing table (section 6):

```python
import anthropic

client = anthropic.Anthropic()

PRICE_PER_1M = {"claude-sonnet-4-6": {"input": 3.00, "output": 15.00}}

response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": "summarize the changes in this release"}],
    )

price = PRICE_PER_1M[response.model]
cost_usd = (
    response.usage.input_tokens / 1_000_000 * price["input"]
    + response.usage.output_tokens / 1_000_000 * price["output"]
)

print(response.content[0].text)  # existing behavior
print(cost_usd)                  # new: total spend for this invocation
```

### `--continue` vs `--resume "$session_id"` — when each is correct

| Approach | How it selects the session | Safe when concurrent? |
|---|---|---|
| `--continue` | Most recent session by timestamp | ❌ Attaches to wrong job if another runs simultaneously |
| `--resume "name"` | Named session (set with `--name`) | ✅ if names are unique per job |
| `--resume "$session_id"` | Exact session ID from JSON output | ✅ Always — explicit, not heuristic |

### What does NOT work for cross-invocation context sharing

| Wrong approach | Why it fails |
|---|---|
| Re-send original prompt verbatim | Starts a new conversation — Claude has no memory of the previous call |
| `--no-session-persistence` (or similar) | Disables persistence; separate OS processes cannot share in-memory state |
| `--continue` in parallel CI jobs | Attaches to *most recent* session — ambiguous under concurrency |

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

## 20. Claude Code Permission Modes

Controls what happens when Claude Code wants to run an action that hasn't been explicitly approved.

| Mode | Unapproved action | Human required? | Use for |
|---|---|---|---|
| `default` (interactive) | Prompts user | ✅ Yes | Normal development |
| `acceptEdits` | Auto-approves file edits + common filesystem ops; prompts for shell commands and network requests | ✅ For non-edit/non-filesystem actions | Dev workflows with frequent file changes |
| `dontAsk` | Denies silently — no prompt | ❌ No | CI/CD, automated pipelines |
| `bypassPermissions` | Allows everything | ❌ No | Dangerous — avoid unless sandboxed |

### `acceptEdits` — exact scope

`acceptEdits` auto-approves a defined set of actions. Anything outside that set still requires explicit approval (or causes an abort in a CI/non-interactive context).

**Auto-approved under `acceptEdits`:**
- File writes (Edit, Write tools)
- Common filesystem operations: `mkdir`, `mv`, `cp`

**NOT auto-approved under `acceptEdits`:**
- Arbitrary shell commands
- Network requests (e.g. fetching a dependency list, calling an external API)
- Any Bash invocation that goes beyond the filesystem operations listed above

```bash
# Example: this run aborts when Claude tries to make a network request
claude -p "apply the lint fixes" --permission-mode acceptEdits
# → File edits auto-approved ✅
# → Network request to fetch updated dependency list → requires explicit approval ❌
#   → aborts in CI (no human present)

# Fix: explicitly allow the network tool
claude -p "apply the lint fixes" --permission-mode acceptEdits --allowedTools WebFetch
# or add a permissions.allow rule for the specific action
```

**Mental model:** the mode is named for what it auto-approves — *edits* and basic filesystem movement. Anything outside that scope still gates on a human or an explicit `--allowedTools` / `permissions.allow` entry.

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

### Symlinks in `.claude/rules/` — sharing rules across repositories

`.claude/rules/` resolves symlinks normally. Symlinks to an external shared folder (outside the repository) are a **supported pattern** for keeping rules in sync across multiple repos from a single source of truth.

**What is supported:**
- Symlinking individual rule files: `ln -s ~/shared-rules/security.md .claude/rules/security.md`
- Symlinking an entire rules directory: `ln -s ~/shared-rules .claude/rules`
- Pointing symlinks to locations **outside** any git repository (no submodule requirement)
- Claude Code has **circular symlink detection** — infinite loops are caught

**What the architect must verify:**

Symlink targets are filesystem paths — they must exist on **each developer's machine** independently. If a developer clones the repo without having the shared source at the expected path, the symlink is dead and the rule silently goes missing.

```
Repo structure (committed):
  .claude/rules/security.md → ~/org-shared-rules/security.md  (symlink)

Developer A: ~/org-shared-rules/ exists → ✅ rule loads
Developer B: ~/org-shared-rules/ missing → ❌ symlink is dead, rule not loaded
```

Document the symlink setup in onboarding so all developers clone or install the shared source at the expected path before opening the project.

**Comparison with skills symlinks** (see [[skills-scope-and-resolution]] section 16):

| | `.claude/rules/` symlinks | `.claude/skills/` symlinks |
|---|---|---|
| Supported? | ✅ | ✅ |
| Individual file symlinks? | ✅ | ✅ |
| Directory symlinks? | ✅ | ✅ |
| Requires submodule? | ❌ No | ❌ No |
| Auto-updates when source changes? | ✅ Yes (live symlink) | ✅ Yes (live symlink) |
| Per-developer setup required? | ✅ Yes (source must exist at path) | ✅ Yes |

### `paths` glob pattern semantics — `*` vs `**`

The `paths` field (and skill `paths` frontmatter) accepts a YAML list of glob patterns. The critical distinction:

| Pattern token | Matches | Crosses `/`? |
|---|---|---|
| `*` | Any characters within a **single directory segment** | ❌ No |
| `**` | Zero or more **directory levels** | ✅ Yes |

**Practical examples:**

| Pattern | Matches | Misses |
|---|---|---|
| `**/*.test.tsx` | `.test.tsx` files at **any depth** in the project | Nothing — most inclusive |
| `src/**/*.test.tsx` | `.test.tsx` files anywhere under `src/` | Files outside `src/` |
| `**/__tests__/*.tsx` | `.tsx` files in any `__tests__/` directory | Colocated tests, `tests/` dirs, files outside `__tests__/` |
| `src/components/*.test.tsx` | `.test.tsx` directly in `src/components/` | Nested subdirectories, other locations |

**Rule:** To match a file extension at any directory depth across the whole project, use `**/*.ext`. Single `*` never crosses a `/` boundary.

**YAML syntax note:** `paths` is a **list**, even for a single pattern. A bare string is invalid frontmatter:

```yaml
# ❌ Wrong — bare string, not a list
paths: "terraform/**/*"

# ✅ Correct — list with one item
paths:
  - "terraform/**/*"
```

**Complete example — `.claude/rules/terraform.md`:**

````markdown
---
paths:
  - "terraform/**/*"
---

# Terraform Conventions

Apply these rules to any file under `terraform/`, at any subfolder depth.

## Formatting
- Run `terraform fmt` conventions: 2-space indentation, aligned `=` in argument blocks.
- One resource or module block per logical unit — do not combine unrelated resources in a single block.

## Tagging
Every `aws_*` resource that supports `tags` must include:
```hcl
tags = {
  Environment = var.environment
  Team        = "infra"
  ManagedBy   = "terraform"
}
```

## Naming
- Resource names use `snake_case`, prefixed with the service: `aws_s3_bucket.logs_bucket`, not `aws_s3_bucket.bucket1`.
- Variable names must match their `.tfvars` counterpart exactly — no aliasing.
````

Because this file carries `paths`, it stays out of context until Claude touches a file matching `terraform/**/*` — a file at `terraform/main.tf` or `terraform/modules/vpc/network.tf` both trigger it; a file at `src/terraform-docs.md` does not.

### Key facts
- `.claude/rules/` is scanned **recursively** for `.md` files — organizing rules into subdirectories (e.g. `frontend/`, `backend/`) is a pure maintainability convention and does not affect discovery or loading; each file's own `paths` frontmatter (or lack thereof) still governs its load behavior regardless of nesting
- Omitting `paths` does **not** disable a rule and does **not** scope it to the `.claude/rules/` directory itself — it makes the rule unconditional (always loaded)
- `paths` patterns are project-root-relative globs, matched against files Claude actually reads/edits during the session
- A file with `paths` and a file without `paths` can coexist in the same `.claude/rules/` folder with completely different load timing
- User-level rules load before project-level rules, but this is not a strict override — conflicting unconditional rules are non-deterministic; reconcile conflicts structurally
- This mirrors the [[path-scoped rules]] behavior in section 18, but that section covers symlink path-matching; this section covers the `paths`-vs-no-`paths` load-trigger distinction

### `.claude/` — recognized subfolders and files (project-level)

| Path | Committed? | Purpose |
|---|---|---|
| `CLAUDE.md` (repo root, or `.claude/CLAUDE.md`) | ✅ Yes | Project instructions, loaded every session |
| `CLAUDE.local.md` (repo root) | ❌ Gitignored | Personal instructions for this developer only — never committed |
| `.claude/rules/*.md` | ✅ Yes | Topic-scoped instructions, optionally gated by `paths:` frontmatter (this section) |
| `.claude/skills/<name>/SKILL.md` | ✅ Yes | Reusable prompt packages, invoked as `/<name>` |
| `.claude/agents/<name>.md` | ✅ Yes | Subagent definitions with isolated context |
| `.claude/agent-memory/<name>/` | ✅ Yes | Persistent memory storage for project-scoped subagents |
| `.claude/output-styles/<name>.md` | ✅ Yes | Custom system-prompt sections |
| `.claude/settings.json` | ✅ Yes | Permissions, hooks, env vars, model defaults |
| `.claude/settings.local.json` | ❌ Gitignored | Personal per-project overrides |
| `.claude/.mcp.json` | ✅ Yes | Team-shared MCP server configs |
| `.claude/.worktreeinclude` | ❌ Gitignored | Files to copy into new worktrees |

**`CLAUDE.local.md`** is the gitignored personal counterpart to `CLAUDE.md` — analogous to `settings.local.json` vs `settings.json`. Use it for instructions that are real (enforced by the session, not just conversational preference) but personal (must not be committed to the shared repo).

User-level mirrors exist under `~/.claude/` for `CLAUDE.md`, `rules/`, `skills/`, `agents/`, `agent-memory/`, and `output-styles/`. Hooks have **no dedicated folder** — they are configured entirely inside `settings.json` under the `hooks` key (see section 21). Commands are not a separate folder either; slash commands are served by `skills/`.

### `/memory` — diagnosing instruction-loading inconsistencies

`/memory` is a slash command that lists **exactly which files are loaded** in the current session: every CLAUDE.md, CLAUDE.local.md, and rules file currently in context.

**Fastest way to debug inconsistent Claude behavior across developers:**

1. Have each engineer run `/memory` in their session
2. Compare the file lists side by side
3. If a file is missing from one engineer's list → loading/scoping issue (wrong working directory, missing file, symlink dead, `claudeMdExcludes` filtering it out)
4. If both lists are identical → the problem is in the rule text itself, not loading

```
/memory output (example):
  Loaded context files:
    CLAUDE.md (project root)
    CLAUDE.local.md (project root) ← personal, gitignored
    .claude/rules/linting.md
    .claude/rules/security.md
    ~/.claude/CLAUDE.md (user-level)
```

If engineer B's output is missing `.claude/rules/linting.md`, the root cause is a loading/scoping issue — not wording, not version mismatch, not git corruption.

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

## 34. `claudeMdExcludes` — Filtering CLAUDE.md Loading in Monorepos

### The problem

In a monorepo, Claude Code loads CLAUDE.md files from multiple packages into context at startup. An engineer working exclusively in one package (`packages/web`) finds their context cluttered with instructions from sibling packages (`packages/admin-dashboard`, `packages/legacy-*`) they never touch. They want to exclude those files **without affecting teammates** who do work in those packages.

### The solution — `claudeMdExcludes` in `settings.local.json`

`claudeMdExcludes` accepts glob patterns and filters which CLAUDE.md files are loaded into context. Setting it in `.claude/settings.local.json` keeps the exclusion personal — the file is gitignored and never affects other developers.

```json
// .claude/settings.local.json  (gitignored — personal to this engineer)
{
  "claudeMdExcludes": [
    "packages/admin-dashboard/**",
    "packages/legacy-*/**"
  ]
}
```

### Settings scope for `claudeMdExcludes`

`claudeMdExcludes` can be set at any settings scope:

| File | Scope | Affects teammates? | Use when |
|---|---|---|---|
| `~/.claude/settings.json` | User-level (all projects) | ❌ No | Personal preference across all repos |
| `.claude/settings.json` | Project-level (committed) | ✅ Yes | Team-wide exclusion everyone should have |
| `.claude/settings.local.json` | Project-local (gitignored) | ❌ No | Personal preference for this project only |

### Why other approaches fail

| Approach | Why it fails |
|---|---|
| Move sibling CLAUDE.md files to `.claude/rules/` | Doesn't change loading scope — those files still load; just relocates them |
| Add `claudeMdExcludes` to committed `.claude/settings.json` | Affects all teammates — engineers who need those files lose them |
| Delete the CLAUDE.md files from other packages | Removes instructions other teammates depend on — destructive |

### Key facts
- `claudeMdExcludes` filters CLAUDE.md loading; it is not a security feature — it is a context-management convenience
- `.claude/settings.local.json` is gitignored by design: personal settings that should never be committed (developer preferences, local path overrides, personal exclusions)
- The committed `.claude/settings.json` is for team-wide defaults; `settings.local.json` overrides it locally for the individual developer

---

## 33. Piped Stdin Size Limit in Claude Code — 10 MB Cap

### The behavior

Claude Code enforces a hard **10 MB limit on piped stdin**. When the piped input exceeds this cap, the CLI:
- Exits **immediately** with a non-zero status code
- Emits a **clear error message** (does not silently discard or truncate)
- Produces **no output** — the prompt is never processed

```bash
# Fails if build-error.txt > 10 MB
cat build-error.txt | claude -p 'explain the root cause' > output.txt
# → exits with error, output.txt is empty
```

### The workaround — reference the file path instead of piping

Write the content to a file and let Claude read it via the Read tool:

```bash
# Works regardless of file size
claude -p 'explain the root cause of errors in build-error.txt'
```

Claude will use the `Read` tool to access the file directly, bypassing the stdin size constraint entirely.

### Why other explanations are wrong

| Wrong claim | Reality |
|---|---|
| `>` redirect not supported with `-p` | The shell processes `>` before Claude sees anything — standard stdout redirect, works fine |
| Plain text piping requires `--input-format stream-json` | Plain text is the **default** stdin format; `--input-format stream-json` is only needed for structured JSON input |
| Non-UTF8 bytes cause immediate rejection | Encoding issues may cause content problems but are not the mechanism for an immediate exit on oversized logs; size is the documented trigger |

### Key facts
- Piped stdin cap: **10 MB** — exceeding it exits with error, never truncates silently
- `--input-format stream-json` is for structured JSON piping, not a requirement for plain text
- The `>` shell redirect is orthogonal to Claude's `-p` flag — both work together normally
- For large inputs, always prefer file-path references over piped stdin

---

## 32. Blocking Bash in Non-Interactive / CI Pipelines — `--disallowedTools`

### The problem

A step like `git diff main | claude -p "you are a typo linter..."` pipes input to Claude and runs non-interactively. The maintainer wants Claude to have **zero ability to run arbitrary Bash commands** during that step, while keeping the invocation portable across Windows and Linux CI runners.

### The solution — `--disallowedTools Bash`

```bash
git diff main | claude -p "you are a typo linter..." --disallowedTools Bash
```

`--disallowedTools` is a CLI flag that removes named tools from Claude's available tool set for that invocation. It works the same on every platform because it is a Claude CLI argument, not a shell feature.

The complement flag `--allowedTools` restricts Claude to an explicit allowlist instead.

### Why other approaches do NOT work

| Approach | Why it fails |
|---|---|
| Run via `npm run lint` instead of a direct shell invocation | npm is a process runner — it has no effect on Claude's internal tool permissions; Bash still available |
| Pipe input via stdin | Input delivery method is irrelevant to tool permissions; Claude still has Bash by default |
| Write "do not use Bash" in the prompt string | Prompt text is probabilistic guidance, not a permission control; tools are configured by CLI flags or settings files, not conversation text |
| No config (rely on default) | Default grants Bash access; nothing strips it |

### Key mental model

Tool permissions are a **configuration layer** that is entirely independent of:
- How input is delivered (stdin pipe, file, interactive)
- How Claude is invoked (npm, shell script, CI step)
- What the prompt text says

The only authoritative ways to restrict tools are:
1. `--disallowedTools <Tool>` — remove specific tools for this invocation
2. `--allowedTools <Tool>` — restrict to an explicit allowlist for this invocation
3. `permissions.deny` in `.claude/settings.json` — project-level permanent restriction (see section 20)

### When to use `--disallowedTools` vs `--allowedTools`

| Goal | Use |
|---|---|
| Remove one or two dangerous tools, keep everything else | `--disallowedTools Bash` |
| Restrict Claude to a minimal set (e.g. Read-only) | `--allowedTools Read,Glob,Grep` |
| Fully locked CI with deterministic behaviour | `--permission-mode dontAsk` + `--allowedTools ...` (see section 20) |

---

## 35. CLAUDE.md `@path` Import Syntax — Triggering vs. Suppressing Imports

### The behavior

CLAUDE.md (and skill Markdown files) support an `@path` syntax that **imports another file's contents directly into context** at the point of reference:

```markdown
See @README for project overview and @package.json for available npm commands.
```

Both `@README` and `@package.json` are resolved and their file contents are loaded into context — not just mentioned as text.

### Suppressing an import — wrap the path in backticks

To reference a file path in prose **without** triggering an import (e.g., pointing a human reader to a file, not asking Claude to load it), wrap it in a Markdown code span:

```markdown
For legacy context, see `@docs/legacy-notes.md` (not auto-loaded).
```

**Why this works:** import parsing is Markdown-aware — it skips content inside inline code spans (`` `...` ``) and fenced code blocks (` ```...``` `). Text inside backticks is treated as literal, displayed text, never scanned for `@path` import triggers.

### What does NOT suppress an import

| Attempted escape | Why it fails |
|---|---|
| Double `@@` prefix (`@@docs/legacy-notes.md`) | Not a recognized escape sequence — no special "doubled @" parsing rule exists |
| HTML comment (`<!-- @docs/legacy-notes.md -->`) | HTML comments are typically hidden from rendered output — fails the goal of being a *visible* pointer; also not a documented import-exclusion mechanism |
| Space between `@` and path (`@ docs/legacy-notes.md`) | No documented rule ties import triggering to adjacency; inventing whitespace-sensitivity here is incorrect |

### Key facts
- `@path` in CLAUDE.md / skill Markdown = literal file import into context, resolved at load time
- Backtick-wrapped paths (code spans or fenced blocks) are the documented way to mention a path as visible text without importing it
- This import syntax is distinct from MCP `@server:resource` mention syntax (see section 26) — CLAUDE.md imports pull local file contents; MCP mentions reference server-hosted resources

---
