# Fence Clients On Demand — client-acquisition agent

Claude Managed Agents configuration for Samuel Scales Marketing. Anthropic runs the agent
loop and the sandbox; these files define what the agent is and what the first test must
prove. Research and drafting only — this agent has no ability to send outreach.

## Status: configured vs. tested

Nothing in this repository has been executed. No agent, environment, datastore, or session
exists yet, and no cost has been incurred.

| Capability | Configured | Tested successfully |
|---|---|---|
| Public web research (search + read public pages) | Yes | **No** |
| Prospect verification against a four-part bar | Yes | **No** |
| Deliverables: prospects.csv, research-log.csv, drafts, daily brief, run log | Yes | **No** |
| Persistent datastore (exclusions + research history) | Yes | **No** |
| Partial exclusions (3 user-confirmed entries) | Yes | **No** |
| $8.00 session cost cap | Yes | **No** |
| GoHighLevel connection | **No — deliberately deferred** | No |
| Business email / calendar | **No — deliberately not granted** | No |
| Recurring weekday schedule | **No — not created** | No |

"Tested successfully" changes only after a run produces the deliverables and they survive
review. Until then treat every row as an intention.

## Files

| File | What it is |
|---|---|
| `fence-prospecting.agent.yaml` | Agent: model, tool surface, system prompt |
| `fence-prospecting.environment.yaml` | Sandbox: cloud, deny-by-default container egress |
| `rubric.md` | Graded criteria for the first test |
| `setup.sh` | One-time: creates agent, environment, datastore → `.ids.env`. Not billable |
| `launch-test.sh` | The paid run. Requires `CONFIRM_PAID_RUN=yes` |
| `fetch-results.sh` | After the run: actual cost + downloads every deliverable |
| `ghl-import-mapping.md` | Proposed CSV → GoHighLevel mapping, unverified against a live location |

## Tool surface (what the agent can actually do)

Enabled: `read`, `write`, `edit`, `glob`, `grep`, `web_search`, `web_fetch`.
Disabled: `bash` — the CSV and Markdown deliverables are produced with `write`, so the shell
is not needed, and removing it removes arbitrary egress from the sandbox.
Not present at all: email, SMS, CRM, calendar, ad platform, payment.

`web_fetch` runs under the `auto` permission policy: every fetch is evaluated server-side
before it executes, and one that looks state-changing pauses for approval rather than
running. This reduces the outbound surface to reading public pages; it does not make an
external effect impossible, because a URL can act on the site that serves it. The system
prompt forbids fetching action-style URLs, and `run-log.md` records anything blocked or
refused.

## Sequence

1. `./setup.sh` — creates the three objects, writes `.ids.env`. No charge.
2. `CONFIRM_PAID_RUN=yes ./launch-test.sh` — one session, $8.00 cap.
3. `./fetch-results.sh <session_id>` — actual cost and deliverables.
4. Review. Then, and only then, decide on GoHighLevel, the recurring schedule, and its cap.
