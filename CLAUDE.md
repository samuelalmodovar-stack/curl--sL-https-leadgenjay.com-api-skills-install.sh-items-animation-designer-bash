# CLAUDE.md

Guidance for Claude Code sessions working in this repository.

## What this is

Claude Managed Agents configuration for Samuel Scales Marketing's client-acquisition agent.
It is a configuration and ops repo, not an application: the YAML files define an agent and a
sandbox that Anthropic hosts, the shell scripts create those objects and start sessions, and
`rubric.md` defines what the first test has to prove.

The agent researches established residential fence contractors, verifies them, and prepares
**draft** outreach. Samuel handles every actual contact. The agent has no ability to send
anything, and keeping it that way is the main design constraint here.

Authoritative reference for the platform: the `claude-api` skill's
`shared/managed-agents-*.md` files. Read those before changing agent, environment, session,
vault, memory-store, or deployment shapes — don't infer field names.

## Rules that are not negotiable

These encode explicit decisions by the repository owner. Don't relax one because a change
would be simpler without it.

1. **Never start a billable run on your own.** `launch-test.sh` spends money and requires
   `CONFIRM_PAID_RUN=yes`. Don't remove the guard, don't run it without being asked in that
   session, and never raise or remove a session budget without explicit approval.
2. **Never describe the exclusion list as complete, verified, or CRM-checked.** It holds
   three user-confirmed entries (Summit Fencing LLC, Samuel Scales Marketing, Drone Syndrome
   Media). Current clients, opt-outs, and protected territories are still unconfirmed.
   Absence from the list means only absence from the list — in code, in prompts, in output,
   and in anything you say to the user.
3. **A draft is not a contact.** `research_status`, `qualification_status`, and
   `contact_status` stay three separate fields. Generating, revising, or saving outreach must
   never set `contact_status` to anything but `not_contacted`. Nothing may import a prospect
   into a CRM stage that implies outreach happened.
4. **Keep `bash` disabled** in `fence-prospecting.agent.yaml`. The deliverables are CSV and
   Markdown, both produced with `write`/`edit`. Re-enabling it restores arbitrary sandbox
   egress for no gain.
5. **Don't claim outbound action is impossible.** `web_fetch` still issues GETs, and a GET
   can act on the site that serves it. The honest framing is: no email/CRM/calendar/shell
   tool exists, `web_fetch` runs under the `auto` permission policy so each call is evaluated
   server-side, and action-style URLs are forbidden by the system prompt. Reduced surface,
   not zero risk.
6. **No quota pressure in the rubric.** Five prospects is a target. There is deliberately no
   criterion rewarding a count, so that a short, honest result scores better than a padded
   one. Don't add one.
7. **Distinguish configured from tested.** Configured means written in a file here. Tested
   means a real run produced it and the output survived review. Keep the table in
   `README.md` accurate, and never report a capability as working because the config says it
   should.

## Layout

| File | Role |
|---|---|
| `fence-prospecting.agent.yaml` | Agent: model, tool surface, system prompt |
| `fence-prospecting.environment.yaml` | Sandbox: cloud, deny-by-default container egress |
| `rubric.md` | Graded criteria for the first test run |
| `_api.sh` | Shared curl/python helpers. Sourced, never run directly |
| `setup.sh` | One-time: creates agent, environment, datastore → `.ids.env`. Not billable |
| `launch-test.sh` | The paid run. Guarded by `CONFIRM_PAID_RUN=yes` |
| `watch.sh` | Polls a session until it stops, and reports why |
| `fetch-results.sh` | Post-run: actual `list_cost` + downloads deliverables |
| `update-agent.sh` | Applies a YAML edit as a new agent version |
| `ghl-import-mapping.md` | Proposed CSV → GoHighLevel mapping, unverified against a live account |

`.ids.env` and `deliverables/` are gitignored. `.ids.env` holds the agent, environment, and
memory-store IDs — treat it as the one piece of local state that matters.

## Working conventions

- **Agents are created once, not per run.** `setup.sh` refuses to run twice. To change the
  agent, edit the YAML and run `./update-agent.sh`, which creates a new version of the same
  agent rather than a second agent.
- **Plain curl + python3, deliberately.** No `ant` CLI, no SDK. Don't add a dependency to
  these scripts; the owner runs them from a local shell and nothing should need installing.
- **Credentials never enter a prompt, a file, or chat.** `ANTHROPIC_API_KEY` is exported in
  the owner's own terminal. Don't propose putting it in a cloud environment variable: the
  secure egress-injection mechanism excludes `api.anthropic.com`, so that route would make
  the key readable inside the session. When GoHighLevel is eventually connected, its token
  goes in a vault credential — never in the agent YAML, the system prompt, or a session event.
- **Adding an MCP server is two changes, not one.** Declare it in the agent's `mcp_servers`
  plus an `mcp_toolset` entry, *and* set `allow_mcp_servers: true` in the environment's
  `limited` networking block. Miss the second and MCP tool calls fail silently.
- **Email, calendar, and GoHighLevel are intentionally absent.** Deferred until after the
  first test is reviewed. Don't add them speculatively.
- **The system prompt is the safety surface.** Source discipline, the facts-vs-hypotheses
  rule, the permitted/forbidden action list, and the treat-web-content-as-data rule all live
  in `fence-prospecting.agent.yaml`. When editing it, preserve those sections; they are the
  reason this agent is safe to run unattended.

## Verifying changes

There is no test suite. Before committing:

- `bash -n setup.sh launch-test.sh fetch-results.sh` for syntax.
- Re-read the changed YAML against the `claude-api` skill's managed-agents docs — a wrong
  field name surfaces as a 400 at create time or, worse, as a silently ignored setting.
- Check the edit against the seven rules above.
