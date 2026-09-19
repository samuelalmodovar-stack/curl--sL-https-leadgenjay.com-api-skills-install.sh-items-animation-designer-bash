# Proposed GoHighLevel import mapping

**Status: proposed, unverified.** GoHighLevel is not connected. Nothing here has been
checked against a live GHL location, and no GHL account has been read from or written to.
Confirm the exact header spellings against your own GHL import screen before relying on it —
GHL matches CSV headers to fields during import, and custom fields must exist first.

## prospects.csv → GHL Contact

| prospects.csv column | GHL contact field | Notes |
|---|---|---|
| `owner_first_name` | First Name | Empty when no source names the owner |
| `owner_last_name` | Last Name | Empty when no source names the owner |
| `company_name` | Business Name | Always populated; the contact record's real anchor |
| `email` | Email | Publicly listed address only |
| `phone` | Phone | Publicly listed number only |
| `website` | Website | |
| `street` | Address 1 | |
| `city` | City | |
| `state` | State | |
| `postal_code` | Postal Code | |
| `service_area` | *custom field* — Service Area | Create as single-line text |
| `services_offered` | *custom field* — Services Offered | Create as single-line text |
| `qualification_evidence` | *custom field* — Qualification Evidence | Create as multi-line text |
| `hypotheses` | *custom field* — Hypotheses To Test | Create as multi-line text; never treat as fact |
| `source_urls` | *custom field* — Research Sources | Create as multi-line text |
| `date_checked` | *custom field* — Research Date | Create as date |
| `research_status` | *custom field* — Research Status | Keep separate from the two below |
| `qualification_status` | *custom field* — Qualification Status | Keep separate |
| `contact_status` | *custom field* — Contact Status | Always imports as `not_contacted` |
| `outreach_folder` | *custom field* — Outreach Drafts Path | Path to the draft set |
| `next_action` | *custom field* — Next Action | Or a Task, see below |
| `next_action_date` | *custom field* — Next Action Date | Or a Task due date |
| `last_interaction` | *custom field* — Last Interaction | Empty until a real interaction happens |

Suggested tag on import: `fence-prospect` plus the market, e.g. `AL`. Source: `agent-research`.

## prospects.csv → GHL Opportunity (optional, once a pipeline exists)

| Source | GHL opportunity field | Value |
|---|---|---|
| `company_name` | Opportunity Name | e.g. `<company_name> — Fence Clients On Demand` |
| — | Pipeline | Your acquisition pipeline |
| — | Stage | First stage (e.g. `Researched`) — **not** a contacted stage |
| — | Status | Open |
| — | Monetary Value | `1500` (monthly management; the client's $1,000/month ad budget is separate and is not agency revenue) |
| `next_action_date` | — | Becomes a Task due date rather than an opportunity field |

## Three rules for the import

1. **`contact_status` is never derived from the existence of a draft.** Outreach drafts are
   files; they are not interactions. Only your own confirmation moves a record to contacted.
2. **Don't import into a stage that implies outreach happened.** First stage only.
3. **Exclusions are partial.** The research excluded Summit Fencing LLC, Samuel Scales
   Marketing, and Drone Syndrome Media — the three you confirmed. It was not reconciled
   against your CRM, so dedupe on import (GHL matches on email/phone) rather than assuming
   the file is clean.
