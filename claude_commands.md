# Claude Code – Slash Commands Reference

> Commands are recognized only at the **start** of a message.  
> **Built-in** = always available. **Skill** = AI-powered prompt loaded from `.claude/skills/` or bundled.  
> Most important commands are listed first within each section.

---

## ⚡ Daily Drivers — Reach For These First

### `/clear`
**Built-in** | Wipe conversation history and start fresh.  
**When:** Context is polluted, Claude is confused, or you're switching tasks entirely.  
**Why:** Removes accumulated noise without closing the session. File state and project are untouched.  
**How:** Type `/clear` — no arguments needed.

---

### `/compact [instructions]`
**Built-in** | Compress conversation history into a summary to free up context.  
**When:** Session is long and approaching context limits but you need continuity.  
**Why:** Keeps Claude aware of what happened without burning the full token budget on verbatim history.  
**How:**
```
/compact
/compact focus on the auth changes and ignore the test output
```

---

### `/code-review [effort] [--fix] [--comment]`
**Skill** | Independent code review pass on the current diff.  
**When:** Before committing — want a fresh-perspective quality check.  
**Why:** Runs as a separate pass, not anchored to your generation reasoning. Catches bugs, simplifications, and efficiency issues.  
**How:**
```
/code-review              # default effort
/code-review high         # broader coverage
/code-review --fix        # apply findings automatically
/code-review --comment    # post as inline PR comments
```

---

### `/model [model-name]`
**Built-in** | Switch the AI model mid-session.  
**When:** Need a faster/cheaper model for simple tasks, or the most capable model for complex ones.  
**Why:** Avoids starting a new session just to change model.  
**How:**
```
/model                         # interactive picker
/model claude-sonnet-4-6
/model claude-opus-5
```

---

### `/usage`
**Built-in** | Show token and cost usage for the current session.  
**When:** Want to understand how much context a task consumed.  
**Why:** Helps optimize prompts and decide when to `/compact` or `/clear`.  
**How:** Type `/usage` — no arguments needed.

---

### `/rename "name"`
**Built-in** | Rename the current session.  
**When:** Starting a significant task you'll want to resume later.  
**Why:** Gives the session a human-readable handle for `--resume`.  
**How:**
```
/rename "q3-security-audit"
/rename "payment-refactor"
```

---

## Context & Session Management

### `/rewind`
**Built-in** | Step back to a previous point in the conversation.  
**When:** Claude went down a wrong path and you want to undo recent turns.  
**Why:** More precise than `/clear` — preserves earlier good context.  
**How:** `/rewind` — interactive picker shows recent turns to revert to.

---

### `/context`
**Built-in** | Show what's currently loaded in the context window.  
**When:** Debugging why Claude seems to be missing something or acting on stale info.  
**Why:** Makes the context window contents visible so you can identify what to remove or compact.  
**How:** `/context`

---

### `/btw [note]`
**Built-in** | Add a side-note to the conversation without making it a full user turn.  
**When:** You want to inject a reminder or constraint mid-task without interrupting Claude's flow.  
**Why:** Keeps the note out of the main conversation rhythm.  
**How:**
```
/btw don't touch the legacy auth module
/btw we're using Python 3.11 not 3.12
```

---

### `/memory`
**Built-in** | Edit CLAUDE.md memory files that persist across sessions.  
**When:** Want to add, update, or remove persistent instructions Claude uses in every session.  
**Why:** Memory files load automatically — editing here affects all future sessions in this project.  
**How:** `/memory` — opens memory editor.

---

### `/resume [session-name]`
**Built-in** | Resume a previously named session.  
**When:** Returning to a multi-day task.  
**How:**
```
/resume "q3-security-audit"
/resume                     # interactive picker if name forgotten
```

---

### `/fork`
**Built-in** | Fork the current conversation into a new branch.  
**When:** You want to explore an alternative approach without losing the current thread.  
**Why:** Lets you try two directions in parallel.  
**How:** `/fork`

---

## Project & Workspace

### `/init`
**Skill** | Analyze the repo and generate a `CLAUDE.md` file.  
**When:** Starting work in a new repository with no `CLAUDE.md`.  
**Why:** Gives future Claude instances instant context about commands, architecture, and conventions.  
**How:** `/init`

---

### `/add-dir [path]`
**Built-in** | Add an additional directory to Claude's workspace.  
**When:** Working across multiple repos or folders in the same session.  
**How:**
```
/add-dir ../shared-lib
/add-dir /workspace/config
```

---

### `/cd [path]`
**Built-in** | Change Claude's working directory.  
**When:** Need to switch context to a different folder mid-session.  
**How:**
```
/cd ../backend
/cd /workspace/project-mm
```

---

### `/plan`
**Built-in** | Enter planning mode — Claude drafts a plan before acting.  
**When:** Complex multi-step task where you want to review and approve the approach before any changes are made.  
**Why:** Prevents Claude from jumping straight into edits on tasks that need upfront alignment.  
**How:** `/plan` then describe the task — Claude proposes steps, you approve.

---

### `/permissions`
**Built-in** | View and manage tool permissions for the current session.  
**When:** Need to check what Claude is and isn't allowed to do, or grant/revoke access.  
**How:** `/permissions`

---

### `/mcp`
**Built-in** | Manage MCP (Model Context Protocol) server connections.  
**When:** Adding, removing, or checking status of MCP tool servers.  
**How:** `/mcp` — interactive server management.

---

## Code Quality Skills

### `/simplify`
**Skill** | Review changed code for reuse, simplification, and efficiency — then apply fixes.  
**When:** After completing a feature — pre-commit cleanup pass.  
**Why:** Quality-only pass (not bug hunting). Finds premature abstractions, redundant code, verbose patterns.  
**How:** `/simplify`

---

### `/security-review`
**Skill** | Security-focused review of pending changes.  
**When:** Before merging anything touching auth, input handling, data storage, or external APIs.  
**How:** `/security-review`

---

### `/diff`
**Built-in** | Show the current diff of changes.  
**When:** Want to see exactly what's changed before reviewing or committing.  
**How:** `/diff`

---

## Configuration & Setup

### `/config`
**Built-in** | Open Claude Code settings interactively (model, theme, editor mode, keybindings).  
**When:** Changing preferences without editing JSON directly.  
**How:** `/config` — menu-driven.  
> To enable vim keybindings: `/config` → Editor mode → Vim (vim is **not** a slash command itself)

---

### `/update-config`
**Skill** | Configure automated behaviors, permissions, and env vars in `settings.json`.  
**When:** "Whenever X happens, do Y" — these require hooks that only settings.json can provide.  
**Why:** Claude cannot fulfill automated behaviors through memory alone; hooks in settings.json run at the harness level.  
**How:**
```
/update-config      # then describe: "allow npm commands"
                    # "when Claude stops, show a desktop notification"
                    # "set DEBUG=true in env"
```

---

### `/keybindings-help`
**Skill** | Customize keyboard shortcuts and chord bindings.  
**How:**
```
/keybindings-help   # then: "rebind ctrl+s", "change the submit key"
```

---

### `/fewer-permission-prompts`
**Skill** | Scan transcripts for common approved read-only tool calls and add them to the allowlist.  
**When:** Claude keeps prompting for permission on the same safe operations every session.  
**How:** `/fewer-permission-prompts`

---

## Research & Reference

### `/claude-api`
**Skill** | Load the Claude API reference into context before writing Anthropic SDK code.  
**When:** About to write code that calls Claude — model IDs, pricing, params, streaming, tool use, caching.  
**Why:** API details change. Load this before coding to avoid stale model IDs or deprecated patterns.  
**How:** `/claude-api` then ask your question.

---

### `/deep-research [topic]`
**Skill** | Multi-step research using web search and synthesis.  
**When:** Need thorough answers on a topic rather than a quick lookup.  
**How:**
```
/deep-research Claude prompt caching best practices
```

---

## Diagnostics & Feedback

### `/doctor`
**Skill** | Run a setup health check on Claude Code.  
**When:** Tools not working, MCP servers not connecting, unexpected behavior.  
**How:** `/doctor` — outputs a diagnostic report.

---

### `/debug`
**Skill** | Debug mode — detailed logging and diagnostics for the current session.  
**When:** Something is failing silently and you need visibility into what's happening.  
**How:** `/debug`

---

### `/status`
**Built-in** | Show current session status — model, context usage, active connections.  
**How:** `/status`

---

### `/help`
**Built-in** | List all available commands and skills.  
**When:** Don't know what's available.  
**How:** `/help`

---

### `/bug`
**Built-in** | Report a Claude Code bug — opens GitHub issue pre-filled with session context.  
**How:** `/bug`

---

## Workflow & Automation

### `/loop [interval] [command]`
**Skill** | Run a command repeatedly on an interval or self-paced.  
**When:** Polling CI status, watching for changes, or running iterative tasks automatically.  
**How:**
```
/loop 5m /code-review       # run every 5 minutes
/loop /babysit-prs          # self-paced, model sets interval
```

---

### `/batch`
**Skill** | Run a task across multiple files or targets in parallel.  
**When:** Applying the same change or check to many files at once.  
**How:** `/batch` then describe the task and targets.

---

### `/background`
**Built-in** | Run a task in the background while continuing the current session.  
**When:** Long-running tasks that don't need your immediate attention.  
**How:** `/background` followed by the task description.

---

### `/tasks`
**Built-in** | View and manage background tasks.  
**How:** `/tasks`

---

### `/goal [description]`
**Built-in** | Set an explicit goal for the session that Claude tracks throughout.  
**When:** Long sessions where you want Claude to stay oriented to the primary objective.  
**How:**
```
/goal migrate all API calls from v1 to v2 without breaking tests
```

---

### `/effort [level]`
**Built-in** | Set reasoning effort level for the session.  
**When:** Simple tasks don't need maximum reasoning; complex tasks benefit from it.  
**How:**
```
/effort low       # faster, lighter reasoning
/effort high      # more thorough reasoning
```

---

## Account & Integrations

### `/login` / `/logout`
**Built-in** | Authenticate or sign out of Claude Code.

### `/upgrade`
**Built-in** | Upgrade your Claude Code plan.

### `/install-github-app`
**Built-in** | Install the Claude GitHub App for PR review integration.

### `/install-slack-app`
**Built-in** | Install Claude Tag in a Slack workspace.

### `/import`
**Built-in** | Import configuration from another agent tool (Codex, Gemini, etc.).

---

## Quick Reference Table

| Command | Type | Best for |
|---|---|---|
| `/clear` | Built-in | Reset context — confused Claude or task switch |
| `/compact` | Built-in | Compress long session to free context |
| `/code-review` | Skill | Pre-commit independent quality pass |
| `/model` | Built-in | Switch model mid-session |
| `/usage` | Built-in | Check token/cost usage |
| `/rename` | Built-in | Name a session for later resume |
| `/rewind` | Built-in | Undo recent turns |
| `/context` | Built-in | Inspect what's in context window |
| `/btw` | Built-in | Inject side-notes without a full turn |
| `/memory` | Built-in | Edit persistent CLAUDE.md memory |
| `/resume` | Built-in | Return to a named session |
| `/fork` | Built-in | Branch conversation to try alternate approach |
| `/init` | Skill | Generate CLAUDE.md for new repo |
| `/add-dir` | Built-in | Add another directory to workspace |
| `/cd` | Built-in | Change working directory |
| `/plan` | Built-in | Review+approve plan before Claude acts |
| `/permissions` | Built-in | View/manage tool permissions |
| `/mcp` | Built-in | Manage MCP server connections |
| `/simplify` | Skill | Post-feature cleanup pass |
| `/security-review` | Skill | Pre-merge security check |
| `/diff` | Built-in | Show current changes |
| `/config` | Built-in | Change settings (model, theme, editor mode) |
| `/update-config` | Skill | Automate behaviors via hooks, set env vars |
| `/keybindings-help` | Skill | Customize keyboard shortcuts |
| `/fewer-permission-prompts` | Skill | Reduce repetitive approval dialogs |
| `/claude-api` | Skill | Load API reference before writing SDK code |
| `/deep-research` | Skill | Multi-step web research |
| `/doctor` | Skill | Health check when Claude Code misbehaves |
| `/debug` | Skill | Detailed diagnostics for silent failures |
| `/status` | Built-in | Session status — model, context, connections |
| `/help` | Built-in | List all commands |
| `/bug` | Built-in | Report a Claude Code bug |
| `/loop` | Skill | Recurring/self-paced repeated tasks |
| `/batch` | Skill | Same task across many files in parallel |
| `/background` | Built-in | Run long task without blocking session |
| `/tasks` | Built-in | View background tasks |
| `/goal` | Built-in | Set session-level objective Claude tracks |
| `/effort` | Built-in | Set reasoning effort level |

---

*Source: Anthropic Claude Code official documentation. Commands verified August 2026.*
