# Anthropic API – Quick Mental Map

> Scope note: this file maps the **general** API/Claude Code surface (including things outside exam scope, like Opus 5 / Sonnet 5 / Fable 5). For the **exam-scoped** structure (Claude Certified Architect – Foundations, target model `claude-sonnet-4-6`), see the exam domain map below and [anthropic_api_reference.md](anthropic_api_reference.md).

## Exam Domain Map (Claude Certified Architect – Foundations)

```
Domain 1 — Agentic Architecture & Orchestration (27%)
├── Agentic loop        → stop_reason is the ONLY reliable stop signal
│                          (not text content, not maxTurns alone — §40)
├── Hub-and-spoke        → coordinator owns routing/retry/synthesis; spokes isolated (§24)
├── Task tool            → exam term; built-in tool the model calls to spawn
│                          subagents. RENAMED to "Agent" in current tooling —
│                          exam still says "Task"/"allowedTools must include Task" (§36)
├── AgentDefinition      → {description, prompt, tools, model, ...} — the
│                          ClaudeAgentOptions(agents={...}) programmatic subagent config (§36)
├── fork_session         → resume=<id>, fork_session=True → NEW session id,
│                          copies history at fork point, diverges independently (§37)
├── Hooks (Agent SDK)    → PreToolUse (can block + rewrite input) vs
│                          PostToolUse (observe/normalize only, too late to block) (§21)
└── Task decomposition   → fixed pipeline (predictable) vs adaptive (open-ended) (§38)

Domain 2 — Tool Design & MCP Integration (18%)
├── Tool description     → THE tool-selection mechanism; thin descriptions →
│                          misrouting between similar tools (§41)
├── MCP isError          → structured errorCategory/isRetryable, not a
│                          generic "failed" string (§42)
├── Tool distribution    → 4-5 tools per agent, scoped to its role;
│                          too many degrades selection reliability (§43)
├── MCP scope            → project (.mcp.json, team) vs user (~/.claude.json, personal)
│                          precedence: managed > local > project > user > plugin > connectors (§44)
└── Grep→Read incremental → build understanding step by step, don't read
                           the whole repo upfront (§45)

Domain 3 — Claude Code Configuration & Workflows (20%)
├── Decision: which mechanism?
│     "always true, no exceptions"      → hook / permissions.deny  (deterministic)
│     "usually true, guidance is fine"  → CLAUDE.md / rules / skills (probabilistic) (§46-47)
├── PostToolUse quality gate → lint/format/test after every edit,
│                              independent of model remembering to ask (§48)
├── Plan mode             → architectural/multi-file/multiple-valid-approaches;
│                          direct execution → single-file, well-understood (§49)
└── CI integration        → -p/--print (non-interactive) + --output-format json
                           + --json-schema (structured, parseable findings) (§51)

Domain 4 — Prompt Engineering & Structured Output (20%)
├── Specificity tradeoff  → narrow criteria ↓ false positives, ↑ false negatives (§31)
├── Few-shot              → 2-4 targeted examples > more prose, for ambiguous cases (§54)
├── tool_use + schema      → strict:true eliminates SYNTAX errors only, never
│                          semantic ones (sums, wrong field) — validate those yourself (§55)
├── Nullable fields        → remove from required[] + add a _source enum,
│                          don't force the model to fabricate (§15/55)
├── detected_pattern       → tag findings so dismissal patterns become a
│                          feedback loop that improves the prompt/schema (§56)
├── Message Batches API    → 50% cheaper, ≤24h, NO mid-request tool round-trip;
│                          never for a blocking pre-merge check (§30)
└── Multi-instance review  → fresh instance > self-review (anchoring bias);
                           per-file passes + one cross-file pass for big diffs (§14)

Domain 5 — Context Management & Reliability (15%)
├── Escalation             → honor an explicit "get me a human" immediately;
│                          policy GAPS escalate too, not just "hard" cases;
│                          self-reported confidence ≠ actual complexity (§58/25)
├── Error propagation      → structured {failure_type, attempted, partial_results};
│                          access-failure ≠ valid-empty-result; never silently
│                          suppress, never abort the whole workflow (§59)
├── Human review routing   → confidence + doc-type + field-ambiguity ROUTES review;
│                          RANDOM sampling MEASURES error rate — different jobs (§61)
└── Provenance             → claim-source mappings must survive synthesis;
                           conflicting stats → annotate both, don't arbitrate (§62)
```

---

## General API / Claude Code Structural Map

```
Models (default: claude-opus-5; never append date suffixes)
├── claude-fable-5     → most capable, $10/$50 per MTok, 1M ctx
├── claude-opus-5      → default, $5/$25 per MTok, 1M ctx
├── claude-sonnet-5    → $2/$10 per MTok, 1M ctx
├── claude-sonnet-4-6  → $3/$15 per MTok, 1M ctx
└── claude-haiku-4-5   → $1/$5 per MTok, 200K ctx

Request
├── messages[]         → conversation history (user / assistant turns)
├── tools[]            → tool definitions (built-in or local)
├── tool_choice        → auto | any | tool | none
├── system             → system prompt
├── thinking           → {type: "adaptive"} current; budget_tokens deprecated/rejected on 4.7+
├── output_config      → {effort: low|medium|high|xhigh|max, format: {...}}
└── model, max_tokens  → always required

Response
├── content[]          → text | tool_use blocks
├── stop_reason        → end_turn | tool_use | max_tokens | stop_sequence | pause_turn | refusal
│   └── refusal only  → stop_details.category populated (e.g. "cyber", "bio")
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

.claude/ directory (project-level)
├── CLAUDE.md          → always loaded, top priority
├── rules/*.md         → no `paths:` field  = unconditional load, same priority as CLAUDE.md
│                      → has `paths:` field = loads only when a matching file is read/edited
├── skills/<n>/SKILL.md → slash-command-invoked prompt packages
├── agents/<n>.md      → subagent definitions
├── agent-memory/<n>/  → persistent subagent memory
├── output-styles/     → custom system-prompt sections
├── settings.json      → permissions, hooks, env vars (committed)
├── settings.local.json→ personal overrides (gitignored)
├── .mcp.json          → team-shared MCP server config
└── no dedicated hooks/ or commands/ folder — hooks live in settings.json, commands = skills/

Claude Code hooks
├── PreToolUse      → runs BEFORE tool; can block OR rewrite input (updatedInput)
│   ├── shape       → {hookSpecificOutput: {hookEventName, permissionDecision, ...}}
│   ├── allow       → permissionDecision: "allow"
│   ├── allow+mutate→ permissionDecision: "allow", updatedInput: {...}
│   ├── deny        → permissionDecision: "deny", permissionReason: "..."
│   └── ask         → permissionDecision: "ask"  (no "defer" value exists)
├── PostToolUse     → runs AFTER tool, observational only (cannot block)
├── Notification    → status events only, cannot block
├── Stop            → end of turn, observational only
├── matcher         → regex; scope hook to specific tool(s); no matcher = fires for all
└── updatedInput    → does NOT propagate between hooks; each hook sees original input

.mcp.json env var expansion
├── ${VAR}            → unset + no default → warning logged, literal "${VAR}" text used (not blanked)
├── ${VAR:-default}   → falls back to `default` if unset, everywhere
└── scope             → works in command, args, env, url, AND headers (not just env)

MCP server authentication
├── headers            → static, hand-rotated credential
├── headersHelper       → runs script fresh per connection (dynamic tokens, Kerberos)
│                       (also called apiKeyHelper)
├── oauth block         → only when a real OAuth authorization server exists
└── transport (http/sse/stdio) → orthogonal to auth, never carries auth logic itself

MCP server scope precedence (duplicate server name across scopes)
├── managed (org) > local  > project  > user  > plugin-provided  > claude.ai connectors
├── winner takes the ENTIRE entry — no field-level merging
└── version control status (checked-in vs not) has NO effect on precedence
```

*Kept in a separate file so the main reference sections can grow without renumbering.*
