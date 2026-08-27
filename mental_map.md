# Anthropic API – Quick Mental Map

```
Request
├── messages[]         → conversation history (user / assistant turns)
├── tools[]            → tool definitions (built-in or local)
├── tool_choice        → auto | any | tool | none
├── system             → system prompt
└── model, max_tokens  → always required

Response
├── content[]          → text | tool_use blocks
├── stop_reason        → end_turn | tool_use | max_tokens | stop_sequence
└── usage              → input_tokens, output_tokens

You send back (when stop_reason == "tool_use")
└── tool_result        → type, tool_use_id, content

Agentic loop (your code)
├── maxTurns           → counter you manage around messages.create()
└── turn               → one tool call + response cycle

CLI session
├── --name             → set name at startup
├── /rename            → rename during session
└── --resume <name>    → resume by name (omit name for picker)

Skills (filesystem-based)
├── ~/.claude/skills/  → user-level, all projects
├── .claude/skills/    → project-level, repo-scoped
└── conflict           → project-level wins

Multi-instance review
├── generator          → fresh messages.create() call
├── reviewer           → separate messages.create(), no generation history
└── in Claude Code     → new chat, subagent prompt, or /code-review skill

Session resumption (API)
├── NO session_id parameter — does not exist in the Anthropic API
├── API is stateless — model sees only what is in messages[] per request
├── resume = YOU load prior history from storage + inject into messages[]
└── Claude Code CLI --resume is different: Claude Code manages disk storage itself

Context window — long sessions
├── early turns get compressed/evicted as context fills
├── max_tokens = output limit only (does NOT expand input context)
├── larger model = more params, NOT restored history
└── fix: scratchpad file → write findings to disk → read back on demand

Path-scoped rules + symlinks
├── rules match on symlinked path AND canonical path
├── no extra absolute-path entries needed for symlinked checkouts
└── write rules as project-root-relative globs (src/handlers/**/*.go)

Prompt structuring — XML tags
├── named tags          → unambiguous category scope, no cross-contamination
├── generic tags        → weaker (multiple <criteria> tags lose meaning)
└── prose / bullets     → no structural boundary, categories can bleed

Structured output — missing data
├── required field + wrong type → model fabricates values
├── fix: remove from required[] → model omits cleanly
└── companion enum (_source)   → downstream filterability preserved

Claude Code permission modes
├── default         → prompts user for unapproved actions (needs human)
├── acceptEdits     → auto-approves file edits; prompts for everything else
├── dontAsk         → denies silently without prompting (CI-safe)
├── bypassPermissions → allows everything (dangerous)
└── dontAsk + permissions.allow = deterministic CI (no hanging, no surprises)

MCP tool naming
├── format          → mcp__<server-name>__<tool-name>  (double underscore)
├── max length      → 64 characters
└── matcher regex   → mcp__billing__(issue_refund|void_authorization|apply_credit)

Claude Code hooks
├── PreToolUse      → runs BEFORE tool; can block OR rewrite input (updatedInput)
│   ├── allow       → {decision: "allow"}
│   ├── allow+mutate→ {decision: "allow", updatedInput: {...}}
│   └── deny        → {decision: "deny", reason: "..."}
├── PostToolUse     → runs AFTER tool, observational only (cannot block)
├── Notification    → status events only, cannot block
├── Stop            → end of turn, observational only
├── matcher         → regex; scope hook to specific tool(s); no matcher = fires for all
└── updatedInput    → does NOT propagate between hooks; each hook sees original input
```

*Kept in a separate file so the main reference sections can grow without renumbering.*
