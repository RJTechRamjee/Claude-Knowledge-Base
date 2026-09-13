# Domain 3 — Claude Code Configuration & Workflows

**Exam weight: 20%.** Covers Task Statements 3.1–3.6: CLAUDE.md hierarchy/scoping, custom slash commands & skills, path-specific rules, plan mode vs. direct execution, iterative refinement, and CI/CD integration.

**Running example used throughout:** *Scenario 2 — Code Generation with Claude Code* (custom `/review` command, CLAUDE.md conventions, plan mode for a monolith→microservices split) and *Scenario 5 — Claude Code for CI/CD* (automated PR review and test generation).

This domain had the weakest measured coverage on the last practice attempt — sections 46/47/48 below target the 0%-scored objectives directly.

---

## 46. Choosing the Right Claude Code Configuration Mechanism

**Task Statement 3.1 / cross-cutting.** Five mechanisms exist, each answering a different question. Confusing them is the single most-tested configuration mistake in this domain.

| Mechanism | Answers | Loaded | Can it *block* an action? |
|---|---|---|---|
| **CLAUDE.md** | "What should Claude always know about this project?" | Every session, unconditionally | ❌ No — guidance only |
| **`.claude/rules/*.md`** (no `paths`) | Same as CLAUDE.md, but organized as separate topic files | Every session, unconditionally | ❌ No |
| **`.claude/rules/*.md`** (with `paths:`) | "What convention applies only when touching files matching X?" | Only when a matching file is read/edited | ❌ No |
| **Skills (`.claude/skills/`)** | "What's an on-demand, invokable workflow?" | Only when explicitly invoked (`/name`) | ❌ No (unless the skill itself uses a hook) |
| **Hooks (`settings.json`)** | "What must be true/false, guaranteed, every time?" | Fires on the matching lifecycle event | ✅ Yes — `PreToolUse` can deny |
| **`permissions` (`settings.json`)** | "What is this session allowed to do at all?" | Every tool call, checked against the allow/deny list | ✅ Yes — denies outright |

### Worked decision — "tests must follow one convention, regardless of directory"

Test files sit throughout the repo (`Button.test.tsx` next to `Button.tsx`, `handlers/order.test.ts` next to `order.ts`). The requirement is: apply the same testing convention automatically, based on file *type*, not directory.

- ❌ A separate CLAUDE.md per subdirectory — doesn't scale across many directories, and CLAUDE.md is directory-bound
- ❌ One root CLAUDE.md with a "testing conventions" header, relying on Claude to infer when it applies — inference is not deterministic matching
- ❌ A skill — requires manual invocation (or Claude choosing to load it); contradicts "automatic on file touch"
- ✅ **`.claude/rules/testing.md` with `paths: ["**/*.test.tsx", "**/*.test.ts"]`** — deterministic, glob-based, directory-independent

### Worked decision — "identity verification must happen before any refund, no exceptions"

- ❌ CLAUDE.md instruction "always verify identity first" — probabilistic; a documented 12% miss rate in production is exactly this failure mode (see §39 in [01-agentic-architecture-and-orchestration.md](01-agentic-architecture-and-orchestration.md))
- ❌ A skill that runs the verification step — still requires the model to choose to invoke it
- ✅ **`PreToolUse` hook** blocking `process_refund` until a verified `customer_id` exists in context — deterministic, cannot be skipped

### The general rule (also see §47)

**If the requirement can tolerate an occasional miss, it belongs in CLAUDE.md / rules / skills (guidance).** **If it cannot — compliance, financial, safety-critical, "must never happen" — it belongs in a hook or a `permissions` deny rule (enforcement).** Restructuring a misconfigured setup means moving the *specific instruction* to the layer whose guarantee matches its actual criticality, not adding more emphatic wording at the same layer.

---

## 47. Enforcement Layer vs. Guidance Layer — the Deterministic/Probabilistic Split

**Task Statement 3.1 / 1.4 / 1.5 (cross-domain).** A companion framing to §46, focused specifically on *why* prompt-based instructions have a non-zero failure rate even when worded emphatically.

| Layer | Failure mode if used for the wrong requirement |
|---|---|
| CLAUDE.md / rules (guidance) | Model *usually* complies but occasionally doesn't — acceptable for style/preference, unacceptable for compliance |
| Skills | Only fires if invoked — never a substitute for "must always happen" |
| Hooks / permissions (enforcement) | Overkill (and adds latency/complexity) for a soft preference that doesn't need a hard guarantee |

The exam frames this explicitly under Domain 1 Task 1.4/1.5 (Agent SDK hooks — see §21 and §39 in [01-agentic-architecture-and-orchestration.md](01-agentic-architecture-and-orchestration.md)) **and** under Domain 3 Task 3.1 (CLAUDE.md/rules hierarchy) — it is the same underlying principle tested from two angles: *build* it right (Domain 1's hook mechanics) and *choose the right place to put it* (Domain 3's configuration-mechanism selection, §46).

---

## 48. `PostToolUse` Hooks for Automatic Code-Quality Enforcement

**Task Statement 3.1 / 1.5.** A concrete, fully-worked example of deterministic enforcement that does not depend on the model remembering to run linting/tests.

```jsonc
// .claude/settings.json — runs after every Edit or Write, unconditionally
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {"type": "command", "command": "npx prettier --write $CLAUDE_FILE_PATH"},
          {"type": "command", "command": "npx eslint --fix $CLAUDE_FILE_PATH"},
          {"type": "command", "command": "npm test -- --findRelatedTests $CLAUDE_FILE_PATH"}
        ]
      }
    ]
  }
}
```

Why this must be a hook and not a CLAUDE.md instruction ("run the linter after editing files"): a model that is deep in a multi-file refactor can simply forget, skip it under time/context pressure, or judge (incorrectly) that it's optional for a given edit. A `PostToolUse` hook runs **every time**, independent of whether the model thought to ask for it — this is exactly the "independent of model instruction-following" framing the exam uses for this objective.

`PostToolUse` cannot *block* the edit (the file write already happened) — it's the right hook for *reactive* enforcement (fix formatting, re-run affected tests) as opposed to `PreToolUse`, which is for *preventing* an action before it happens (§21, §39).

---

## 16. Custom Slash Commands and Skills — Scope and Configuration

**Task Statement 3.2.**

### Project vs. user scope

| Location | Committed / shared? | Use for |
|---|---|---|
| `.claude/commands/` or `.claude/skills/<name>/SKILL.md` | ✅ Yes — version-controlled | Team-wide workflows every developer should get on clone (Scenario 2: a `/review` command running the team's checklist) |
| `~/.claude/commands/` or `~/.claude/skills/<name>/SKILL.md` | ❌ No — personal | Individual habits/preferences, never pushed onto teammates |

**Exam sample-question framing:** a `/review` command meant for every developer on clone belongs in `.claude/commands/` (project-scoped, version-controlled) — not `~/.claude/commands/` (personal only), not CLAUDE.md (project context/instructions, not a command definition), and there is no `.claude/config.json` commands array in Claude Code.

### Skills are the current best-practice format; commands are legacy

Both become a `/name` slash command. **Skills** (`SKILL.md` + YAML frontmatter) unlock configuration options that plain commands don't have:

```yaml
---
name: pr-review-checklist
description: Runs the team's standard PR review checklist against the current diff.
argument-hint: "[severity-level]"
allowed-tools: Read, Grep, Glob
context: fork
---
Review the current diff against .claude/rules/api-conventions.md and report
findings grouped by severity. If an argument is given, only report findings
at or above that severity.
```

| Frontmatter field | Purpose |
|---|---|
| `description` | What the skill does (also used for autocomplete / model-invocation decisions) |
| `argument-hint` | A hint string shown in autocomplete when the user types `/pr-review-checklist` with no arguments yet — prompts them for the expected parameter shape |
| `allowed-tools` | Auto-approves the listed tools for this invocation (a UX convenience, not a security sandbox — unlisted tools still work, just with a prompt) |
| `context: fork` | Runs the skill in an isolated subagent; only the final result returns to the main conversation — keeps verbose intermediate steps (e.g. a full codebase scan) out of the main session's context |
| `paths:` | Auto-activates the skill when a matching file is touched |
| `user-invocable: false` | Hides the skill from the `/` menu (still usable programmatically) |

### `context: fork` — isolating verbose or exploratory output

Use `context: fork` for skills that produce a lot of intermediate noise (a full codebase analysis, brainstorming several competing approaches) so only the final recommendation pollutes the main conversation:

```yaml
---
context: fork
agent: Explore
---
Map this codebase's module structure and return a one-paragraph summary.
```

Caveat: the agent type named in `agent:` (not `context: fork` itself) determines what context the forked subagent starts with. `Explore` is deliberately lean and does **not** load CLAUDE.md by default — a skill forked into `Explore` cannot reflect project conventions defined there. Forking into `general-purpose` instead loads CLAUDE.md normally.

### Personal skill customization

A personal variant lives at `~/.claude/skills/<name>/SKILL.md` under a **different name** from the project version, so it doesn't shadow or conflict with the team's shared skill and never appears in the repo.

---

## 22. `.claude/rules/` and Path-Scoped Loading

**Task Statement 3.3.**

### `paths:` frontmatter — conditional vs. unconditional loading

`.claude/rules/*.md` files carry the same YAML-frontmatter convention as skills. Whether the frontmatter has a `paths:` key changes **when** the rule loads:

```yaml
---
# no `paths` key — loads at session start, every session, same priority as CLAUDE.md
---
Use 2-space indentation. Prefer named exports.
```

```yaml
---
paths:
  - "terraform/**/*"
---
Apply terraform-specific conventions here. Stays out of context until a
matching file is read or edited.
```

### Why glob-scoped rules beat directory-level CLAUDE.md for scattered conventions

A convention that must apply to every test file regardless of location (`Button.test.tsx` beside `Button.tsx`, `order.test.ts` beside `order.ts`, `__tests__/checkout.test.tsx`) cannot be expressed by a directory-scoped CLAUDE.md, because CLAUDE.md files apply per-directory, and tests aren't confined to one directory. A single `.claude/rules/testing.md` with `paths: ["**/*.test.tsx", "**/*.test.ts"]` applies uniformly regardless of where the file lives.

### `/memory` — diagnosing instruction-loading inconsistencies across developers

`/memory` lists every CLAUDE.md, CLAUDE.local.md, and rules file actually loaded in the current session. If two engineers' outputs differ, the cause is a loading/scoping issue (wrong working directory, missing file, dead symlink, `claudeMdExcludes` — see §34 below — filtering it out); if the lists match, the problem is in the instruction wording itself, not loading.

---

## 18. Path-Scoped Rules and Symlinks in Claude Code

**Task Statement 3.3 (continued).**

### Glob semantics — `*` vs `**`

| Pattern | Matches |
|---|---|
| `**/*.test.tsx` | `.test.tsx` files at **any depth** — the right choice for tests scattered across the repo |
| `src/**/*.test.tsx` | Same, but only under `src/` |
| `src/components/*.test.tsx` | Only directly in `src/components/`, no subdirectories |

`*` never crosses a `/` boundary; `**` does. `paths` is always a YAML **list**, even for one pattern (`paths: "x"` is invalid; `paths: ["x"]` is correct).

### Symlinks — rules travel across repos

`.claude/rules/` supports symlinking individual files or the whole directory from an external shared source (`ln -s ~/org-shared-rules/security.md .claude/rules/security.md`), auto-updating when the source changes, with no submodule requirement. Rules also match on both the symlinked path **and** the canonical path — no extra `paths` entries are needed for a symlinked checkout.

---

## 20. Claude Code Permission Modes

**Task Statement 3.1 / CI context (3.6).**

| Mode | Unapproved action | Human required? | Use for |
|---|---|---|---|
| `default` | Prompts user | ✅ Yes | Normal interactive development |
| `acceptEdits` | Auto-approves file edits + basic filesystem ops; still prompts for shell commands / network requests | Partial | Dev workflows with frequent file changes |
| `plan` | Explores/plans without executing changes (see §49) | ✅ Yes, to approve the plan | Architectural or multi-file work needing review before execution |
| `dontAsk` | Denies silently, no prompt | ❌ No | CI/CD — deterministic, non-hanging |
| `bypassPermissions` | Allows everything | ❌ No | Dangerous — sandboxed use only |

There is also an `auto` mode (model-classified approvals) in current tooling, not covered by the exam guide's own permission-mode enumeration — the four above are the ones the exam explicitly tests.

`dontAsk` + an explicit `permissions.allow` list is the deterministic CI pattern: everything not on the allowlist fails fast and silently rather than hanging on a human who isn't present.

```jsonc
// .claude/settings.json — locked-down CI runner
{
  "permissionMode": "dontAsk",
  "permissions": {"allow": ["Bash(git log:*)", "Bash(git diff:*)", "Read"]}
}
```

---

## 32. Blocking Bash in Non-Interactive / CI Pipelines — `--disallowedTools`

**Supporting fact for Domain 3 (CI context, Task Statement 3.6), gathered from prior Q&A.**

```bash
git diff main | claude -p "you are a typo linter..." --disallowedTools Bash
```

The only authoritative ways to restrict tool access: `--disallowedTools <Tool>`, `--allowedTools <Tool>`, or a project-level `permissions.deny` in `.claude/settings.json`. Prompt text ("do not use Bash") is not a permission control — it's probabilistic guidance, same failure mode as §46/§47 above.

---

## 33. Piped Stdin Size Limit in Claude Code — 10 MB Cap

Claude Code enforces a hard 10 MB limit on piped stdin; exceeding it exits immediately with an error rather than truncating. For large inputs, reference the file path instead of piping — `claude -p 'explain the root cause in build-error.txt'` lets Claude `Read` the file directly, bypassing the stdin cap.

---

## 34. `claudeMdExcludes` — Personal Monorepo Filtering

Set in `.claude/settings.local.json` (gitignored, personal) to exclude sibling-package CLAUDE.md files from loading, without affecting teammates who still need them. Setting it in the committed `.claude/settings.json` instead would affect the whole team — the wrong file for a personal preference.

---

## 35. CLAUDE.md `@path` Import Syntax

`@README` or `@package.json` in CLAUDE.md/skill Markdown **imports that file's contents** into context at that point, not just a textual mention. To reference a path as visible prose *without* triggering an import, wrap it in a code span: `` `@docs/legacy-notes.md` ``.

---

## 49. Plan Mode vs. Direct Execution

**Task Statement 3.4.**

| Signal | Use plan mode | Use direct execution |
|---|---|---|
| Scope | Multi-file, architectural (e.g. monolith → microservices, a 45+ file library migration) | Single-file, well-understood (a clear stack trace, one validation check) |
| Number of valid approaches | Multiple, with real tradeoffs (different infra requirements) | One obvious approach |
| Cost of getting it wrong | High — rework across many files | Low — easy to fix |
| Reversibility | Committing to a structure is hard to unwind later | Trivially reversible |

**Exam sample-question framing:** a monolith→microservices restructuring task should enter plan mode to explore dependencies and design service boundaries *before* any changes — starting with direct execution and letting boundaries emerge from incremental changes risks costly rework once dependencies surface late; comprehensive upfront instructions without exploration assume you already know the right structure; waiting to switch to plan mode only if "unexpected complexity" appears ignores that the complexity is already known from the task description itself, not something that might emerge later.

### Combining both

Plan mode for investigation and design, then direct execution to implement the approved plan — not an either/or choice for a task that has both an exploratory phase and a mechanical implementation phase.

### The `Explore` subagent

Use a dedicated `Explore` subagent for verbose discovery phases (mapping a large codebase, scanning many files for a pattern) so the exploration's noisy intermediate output doesn't fill the main conversation's context — only the summary returns. See §16 above for the `context: fork` + `agent: Explore` combination that achieves this inside a skill.

---

## 50. Iterative Refinement Techniques

**Task Statement 3.5.**

### Concrete input/output examples beat prose descriptions

When a transformation is described only in prose ("normalize the date format"), the model can interpret it inconsistently across edge cases. Two to three concrete input→output examples pin down the exact expected transformation far more reliably than more prose:

```
Input:  "March 3rd, 2026"        → Output: "2026-03-03"
Input:  "3/3/26"                 → Output: "2026-03-03"
Input:  "sometime in early 2026" → Output: null  (ambiguous — do not guess)
```

### Test-driven iteration

Write the test suite first (expected behavior, edge cases, performance requirements), implement, then iterate by sharing the specific **test failures** — not a vague "it's not working" — to guide the next revision. This gives the model a concrete, checkable target rather than open-ended re-interpretation.

### The interview pattern

Before implementing in an unfamiliar domain, have Claude **ask clarifying questions first** (cache invalidation strategy, failure-mode expectations) rather than silently picking a default and building on an assumption the developer may not have anticipated needing to state.

### Batching interacting issues vs. sequential fixes

| Situation | Approach |
|---|---|
| Multiple issues that **interact** (fixing one changes the correct fix for another — e.g. two related null-handling bugs in the same function) | Provide all of them in **one** detailed message so the model reasons about them jointly |
| Multiple **independent** issues (unrelated files, no interaction) | Fix **sequentially** — one at a time, verify, move to the next |

### Specific test cases for edge-case gaps (Scenario 6: extraction)

When a null-value edge case is mishandled in a migration script, give the specific input and expected output for that case, not a restated general instruction — "handle nulls better" reproduces the same ambiguity that caused the miss in the first place.

---

## 51. Integrating Claude Code into CI/CD Pipelines

**Task Statement 3.6.**

### `-p` / `--print` — non-interactive mode

```bash
# ❌ Hangs — waiting for interactive input in a pipeline with no human present
claude "Analyze this pull request for security issues"

# ✅ Correct — non-interactive, exits after producing output
claude -p "Analyze this pull request for security issues"
```

`CLAUDE_HEADLESS=true` and a `--batch` flag are **not real** — `-p`/`--print` is the only documented mechanism. Redirecting stdin from `/dev/null` is a workaround, not the intended fix, and doesn't address the actual cause (Claude Code waiting for interactive input, not a stdin-format issue).

### Structured JSON output for automated PR comments

```bash
git diff origin/main | claude -p 'review this PR for security issues' \
  --output-format json --json-schema review-findings.schema.json
```

`--output-format json` emits a JSON object (including `session_id` and cost fields); `--json-schema` constrains the output to a given JSON Schema shape — together, this is the mechanism for producing machine-parseable structured findings a CI step can post as inline PR comments, rather than parsing free-text output.

### CLAUDE.md as the CI context-injection mechanism

Document testing standards, fixture conventions, and review criteria in CLAUDE.md so CI-invoked Claude Code sessions have the same project context an interactive session would — e.g. "these are the fixtures already available; don't suggest tests that duplicate existing coverage in `tests/fixtures/`."

### Session isolation for review — don't let the generator review itself

The same session that generated a code change is measurably less effective at reviewing it than an independent instance — see §14, "Multi-Instance and Multi-Pass Review Architectures", in [04-prompt-engineering-and-structured-output.md](04-prompt-engineering-and-structured-output.md) for the full mechanism and why (anchoring bias).

### Matching API/CLI approach to workflow latency (batch vs. blocking)

A **blocking** pre-merge check and a **non-blocking** overnight report have different correct backing mechanisms — see §30, "Message Batches API and Batch Processing Strategy", in [04-prompt-engineering-and-structured-output.md](04-prompt-engineering-and-structured-output.md) (Message Batches API has no latency SLA and cannot be used for a check developers are actively waiting on).

### Avoiding duplicate findings across re-runs

Include prior review findings in context on a re-run (after new commits) and instruct Claude to report only new or still-unaddressed issues — otherwise every re-run re-flags everything from scratch, drowning genuinely new findings in noise.

---
