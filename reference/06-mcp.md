# MCP (Model Context Protocol)

MCP server resources and @ mention syntax, `.mcp.json` environment variable expansion, server authentication mechanisms, and scope precedence for duplicate server names.

---

## 26. MCP Server Resources: @ Mention Reference Syntax

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

## 27. MCP Config: Environment Variable Expansion in `.mcp.json`

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

## 28. MCP Server Authentication: `headers` vs `headersHelper` vs `oauth`

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

---

## 29. MCP Server Config: Scope Precedence for Duplicate Server Names

An MCP server can be defined at multiple scopes simultaneously. When the **same server name** appears in more than one scope, Claude Code does not merge the entries — it uses the **entire definition** from the single highest-precedence scope and discards the rest.

### Precedence order (highest to lowest)

```
local  >  project  >  user  >  plugin-provided  >  claude.ai connectors
```

| Scope | Typical location | Notes |
|---|---|---|
| **local** | Developer's own machine, not checked into git | Highest precedence — a personal override always wins over anything shared |
| **project** | `.mcp.json` at repo root | Checked into version control, shared with the team |
| **user** | User-level config (`~/.claude/...`) | Applies across all of that user's projects |
| **plugin-provided** | Bundled with an installed plugin | Lower precedence than any explicit project/user/local config |
| **claude.ai connectors** | Configured via claude.ai, not local files | Lowest precedence |

### Example

A repo's `.mcp.json` defines `analytics` (project scope). A developer also has a **local**-scoped `analytics` entry pointing at a different endpoint. Result: the developer's Claude Code session uses the **local** entry — local scope always outranks project scope, regardless of which one is version-controlled.

### Common misconceptions

| Claim | Why it's wrong |
|---|---|
| Version control / "checked into git" grants precedence | Precedence is determined purely by scope level, not by where or how a config is stored |
| The two entries get merged field-by-field | Claude Code picks one complete entry from the highest-precedence scope — it never splices fields from multiple scopes together |
| A duplicate server name across scopes is a configuration error | This is expected and resolved automatically via the precedence order; it does not cause Claude Code to skip the server |

### Key facts
- Precedence order: **local → project → user → plugin-provided → claude.ai connectors**
- Resolution takes the whole entry from the winning scope — no field-level merging
- A duplicate name is normal, not an error — it's how personal overrides of shared/project servers work
