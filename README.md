# Fence Clients On Demand — client-acquisition agent

Claude Managed Agents configuration for Samuel Scales Marketing. Anthropic runs the agent
loop and the sandbox; these files define what the agent is and what the first test has to
prove. Research and drafting only — this agent sends no outreach.

Project instructions live in `CLAUDE.md` and govern this repository.

## Status: configured vs. tested

Nothing here has been executed. No agent, environment, datastore, or session exists, and no
model cost has been incurred. `api.anthropic.com` was reachable from a sandbox (HTTP 401 with
no credentials), which shows the endpoint answers — nothing about valid credentials, account
entitlements, Managed Agents availability, or model access.

| Capability | Configured | Tested successfully |
|---|---|---|
| Public web research (search + read public pages) | Yes | **No** |
| Four-part verification bar for new prospects | Yes | **No** |
| Summit as an existing-client reference record, no outreach | Yes | **No** |
| Deliverables: prospects.csv, research-log.csv, briefs, drafts, daily brief, run log | Yes | **No** |
| Reference store, attached read-only (brief, exclusions, existing-client records) | Yes | **No** |
| Research-history store, attached read-write (dedupe + disposition history) | Yes | **No** |
| Prospecting exclusions (2 confirmed: SSM, Drone Syndrome Media) | Yes | **No** |
| $8.00 session cap | Yes | **No** |
| GoHighLevel connection | **No — deferred until the test is reviewed** | No |
| Business email / calendar | **No — deliberately not granted** | No |
| Recurring weekday schedule | **No — proposed only, not created** | No |

"Tested successfully" changes only after a run produces the deliverables and they survive
inspection. Until then every row is an intention, not a result.

## Files

| File | What it is |
|---|---|
| `CLAUDE.md` | Project instructions — the governing document |
| `fence-prospecting.agent.yaml` | Agent: model, tool surface, system prompt |
| `fence-prospecting.environment.yaml` | Sandbox: cloud, deny-by-default container egress |
| `rubric.md` | The 11 graded criteria for the first test |
| `agent.py` | All operations: setup, launch, watch, results, update-agent |
| `ghl-import-mapping.md` | Proposed CSV → GoHighLevel mapping, unverified against a live location |

`.ids.json` (the created object IDs), `.last-session`, and `deliverables/` are gitignored.
`.ids.json` is the one piece of local state worth keeping.

## Requirements

Python 3.8+ and pyyaml. Nothing else — `agent.py` calls the REST API with the standard
library, so there is no CLI, no SDK, and no bash dependency.

```powershell
py -m pip install pyyaml
```

## Authentication

Set the key in your own shell. Never paste it into a chat.

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

```sh
export ANTHROPIC_API_KEY=sk-ant-...   # macOS / Linux
```

Use a dedicated key scoped to the workspace these agents should live in, so it can be revoked
on its own.

Running this inside a Claude Code cloud session was considered and rejected: the secure
mechanism there — API credentials, where the key stays outside the sandbox and is attached at
egress — explicitly excludes `api.anthropic.com`, so the only route would be a plain
environment variable readable by the session and by anyone else using that environment.

## Tool surface (what the agent can actually do)

Enabled: `read`, `write`, `edit`, `glob`, `grep`, `web_search`, `web_fetch`.
Disabled: `bash` — the deliverables are CSV and Markdown, both produced with `write`, so
removing the shell costs nothing and removes arbitrary sandbox egress.
Not present at all: email, SMS, CRM, calendar, ad platform, payment.

`web_fetch` runs under the `auto` permission policy, which means the server evaluates each
call and may **allow it, deny it, or pause for a decision**. It is not a guarantee of human
review — a call judged safe runs before anyone sees it. And a reduced outbound surface is not
zero: a URL can act on the site that serves it. The system prompt forbids action URLs
(confirmation, unsubscribe, checkout, booking, submission), and `run-log.md` must record
anything blocked, denied, or refused rather than working around it.

## Two memory stores, on purpose

The agent reads untrusted third-party web pages. A memory store attached `read_write` is
therefore an injection target: content fetched from a page could write into it, and a later
session would read that back as trusted memory. So the offer brief, the prospecting
exclusions, and Summit's existing-client designation live in a **reference store attached
`read_only`** — the agent cannot alter them, and changes are made through the API instead.
Only the **research-history store** is `read_write`, because deduplication needs it.

## Beta headers

Memory store and memory endpoints take `agent-memory-2026-07-22`. Agents, environments, and
sessions — including attaching a memory store to a session — take
`managed-agents-2026-04-01`. **Sending both on a memory-store request returns HTTP 400.**
`agent.py` routes the header by endpoint in `beta_for()` and refuses to combine them.

## Sequence

```powershell
py agent.py setup              # creates the three objects -> .ids.json. No model cost.
py agent.py launch --confirm   # BILLABLE: one session, $8.00 cap
py agent.py watch              # poll until it stops, and see why it stopped
py agent.py results            # actual cost + download deliverables
```

`launch` without `--confirm` explains the cost and exits without starting anything.

The $8.00 cap is enforced between model requests, so a request already in flight can finish
above it. Whether $8.00 is enough for six records is unknown until a run produces evidence —
a budget pause with partial deliverables is a legitimate outcome to report, not a failure to
predict around.

Then review the files. Only after that: GoHighLevel, the proposed weekday 8:00 a.m.
America/Chicago schedule, and whatever cap that run should carry.

Editing the system prompt later is `py agent.py update-agent`, which versions the existing
agent rather than creating a second one.
