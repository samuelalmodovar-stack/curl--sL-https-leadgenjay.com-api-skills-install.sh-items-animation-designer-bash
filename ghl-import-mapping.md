# Proposed GoHighLevel import mapping

**Status: proposed, unverified.** GoHighLevel is not connected. Nothing here has been checked
against a live GHL location, and no GHL account has been read from or written to. Confirm the
exact header spellings against your own GHL import screen before relying on it — GHL matches
CSV headers to fields during import, and custom fields must exist before they can receive
data.

The agent also emits its own `ghl-import-mapping.md` from the columns it actually produced.
This file is the proposal that mapping starts from.

## prospects.csv → GHL Contact

| prospects.csv column | GHL contact field | Notes |
|---|---|---|
| `first_name` | First Name | Blank unless a source names the person |
| `last_name` | Last Name | Blank unless a source names the person |
| `title` | *custom field* — Contact Title | Blank unless a source states the role |
| `company` | Business Name | Always populated; the record's real anchor |
| `email` | Email | Publicly listed address only, never guessed |
| `phone` | Phone | Publicly listed number only |
| `website` | Website | |
| `street` | Address 1 | |
| `city` | City | |
| `state` | State | |
| `postal_code` | Postal Code | |
| `service_area` | *custom field* — Service Area | Single-line text |
| `sources` | *custom field* — Research Sources | Multi-line text |
| `date_checked` | *custom field* — Research Date | Date |
| `relationship` | *custom field* — Relationship | `prospect` or `existing_client`; drives the filter below |
| `research_status` | *custom field* — Research Status | Keep separate from the two below |
| `qualification_status` | *custom field* — Qualification Status | Keep separate |
| `contact_status` | *custom field* — Contact Status | New prospects import as `not_contacted` |
| `last_interaction` | *custom field* — Last Interaction | Blank until a real interaction happens |
| `next_action` | *custom field* — Next Action | Or a Task, see below |
| `next_action_date` | *custom field* — Next Action Date | Or a Task due date. A suggestion, not a scheduled event |
| `output_folder` | *custom field* — Outreach Drafts Path | Path to that company's draft set |

Suggested tags on import: `fence-prospect` plus the market, e.g. `AL`. Source:
`agent-research`.

## prospects.csv → GHL Opportunity (optional, once a pipeline exists)

Applies to **new prospects only** — filter `relationship=prospect` before creating any
opportunity.

| Source | GHL opportunity field | Value |
|---|---|---|
| `company` | Opportunity Name | e.g. `<company> — Fence Clients On Demand` |
| — | Pipeline | The acquisition pipeline |
| — | Stage | First stage, e.g. `Researched` — **never** a contacted stage |
| — | Status | Open |
| — | Monetary Value | `1500` monthly management. The client's $1,000/month ad budget is their spend, not agency revenue, and does not belong here |
| `next_action_date` | — | A Task due date rather than an opportunity field |

## Four rules for the import

1. **`contact_status` is never derived from a draft.** Outreach drafts are files, not
   interactions. Only your own confirmation moves a record to contacted.
2. **Never import into a stage that implies outreach happened.** First stage only.
3. **Summit Fencing LLC is in the CSV deliberately, and must stay out of acquisition.** It is
   an existing-client reference record carrying `relationship=existing_client`. Filter it out
   of any new-prospect acquisition import, sequence, or opportunity creation. Its presence
   says nothing about its payment status, fees, results, or past communications.
4. **Exclusions are partial.** Samuel Scales Marketing and Drone Syndrome Media are excluded
   from prospecting, but the wider exclusion information — current clients, opt-outs,
   protected territories — has not been reconciled against the CRM. Dedupe on import (GHL
   matches on email and phone) rather than assuming the file is clean.
