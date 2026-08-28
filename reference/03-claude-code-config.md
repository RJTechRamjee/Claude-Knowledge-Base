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
