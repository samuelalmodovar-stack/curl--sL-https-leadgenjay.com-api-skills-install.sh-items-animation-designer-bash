#!/usr/bin/env python3
"""Manage the fence-prospecting managed agent.

Runs on Windows (PowerShell), macOS, and Linux. Uses only the standard library plus
pyyaml to read the two config files — no CLI, no SDK.

  py agent.py setup            create agent + environment + datastore   (no model cost)
  py agent.py launch --confirm start the test session                   (BILLABLE, $8 cap)
  py agent.py watch            poll until the session stops, and say why
  py agent.py results          actual cost + download deliverables
  py agent.py update-agent     apply a YAML edit as a new agent version
  py agent.py preflight        validate config offline                  (no key, no network)
  py agent.py verify           read the created objects back and check them
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IDS_FILE = ROOT / ".ids.json"
LAST_SESSION = ROOT / ".last-session"
AGENT_YAML = ROOT / "fence-prospecting.agent.yaml"
ENV_YAML = ROOT / "fence-prospecting.environment.yaml"
RUBRIC = ROOT / "rubric.md"

BASE = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")

# One beta header covers the whole Managed Agents surface: agents, environments,
# sessions, AND memory stores and memories. Per the Managed Agents endpoint reference,
# every one of those endpoints takes `managed-agents-2026-04-01`, and the SDKs send that
# same header for their memory_stores calls. There is no separate memory beta.
BETA = "managed-agents-2026-04-01"
# The Files endpoints carry their own beta alongside it.
FILES_BETA = f"{BETA},files-api-2025-04-14"

# Header fragments this tool must never send. An earlier revision routed memory-store
# requests to `agent-memory-2026-07-22`, which is not a documented beta — that split is
# what made `setup` fail at the first memory_stores call.
BAD_BETA_FRAGMENTS = ("agent-memory",)

# $8.00, in minor units as an integer string — the API rejects decimal forms.
BUDGET_CENTS = "800"


# Filled in from response headers as calls are made — not configuration.
RESOLVED = {}


class ApiError(RuntimeError):
    pass


def die(msg):
    sys.exit(f"ERROR: {msg}")


def api_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        die(
            "ANTHROPIC_API_KEY is not set in this shell.\n"
            "  PowerShell:  $env:ANTHROPIC_API_KEY = 'sk-ant-...'\n"
            "  bash/zsh:    export ANTHROPIC_API_KEY=sk-ant-...\n"
            "See README.md > Authentication."
        )
    return key


def beta_for(path, override=None):
    """Pick the beta header by endpoint family."""
    beta = override or (FILES_BETA if path.startswith("/files") else BETA)
    for bad in BAD_BETA_FRAGMENTS:
        if bad in beta:
            raise ApiError(
                f"refusing to send '{beta}' to {path} — the Managed Agents surface, "
                f"memory stores included, takes '{BETA}'"
            )
    return beta


def request(method, path, body=None, beta=None, query=None):
    beta = beta_for(path, beta)
    url = f"{BASE}/v1{path}"
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("x-api-key", api_key())
    req.add_header("anthropic-version", "2023-06-01")
    req.add_header("anthropic-beta", beta)
    # Required on every request for a key that is not scoped to one workspace; a
    # single-workspace key needs no header and resolves on its own.
    workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    if workspace:
        req.add_header("anthropic-workspace-id", workspace)
    if data:
        req.add_header("content-type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            # The API reports which workspace the credential resolved to. Remember it so
            # the Console session link can be built without guessing.
            seen = resp.headers.get("anthropic-workspace-id")
            if seen:
                RESOLVED["workspace_id"] = seen
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        # urllib raises on 4xx/5xx, so the API's own message is in the body.
        raw = e.read().decode(errors="replace")
        try:
            err = json.loads(raw).get("error") or {}
            msg = err.get("message", raw[:600])
            if "anthropic-workspace-id" in msg and not workspace:
                msg += (
                    "\n\n  This key is not scoped to a single workspace, so every request "
                    "needs the workspace id.\n  Either set ANTHROPIC_WORKSPACE_ID "
                    "(Console > Settings > Workspaces, ID column),\n  or create a key "
                    "scoped to one workspace, which needs no header at all."
                )
            raise ApiError(f"HTTP {e.code} {err.get('type', '?')}: {msg}") from None
        except json.JSONDecodeError:
            raise ApiError(f"HTTP {e.code}: {raw[:600]}") from None
    except urllib.error.URLError as e:
        raise ApiError(f"could not reach {BASE}: {e.reason}") from None


def download(path, dest, beta=FILES_BETA):
    req = urllib.request.Request(f"{BASE}/v1{path}", method="GET")
    req.add_header("x-api-key", api_key())
    req.add_header("anthropic-version", "2023-06-01")
    req.add_header("anthropic-beta", beta)
    try:
        with urllib.request.urlopen(req) as resp:
            dest.write_bytes(resp.read())
    except urllib.error.HTTPError as e:
        raise ApiError(f"HTTP {e.code} downloading {path}: {e.read()[:300]}") from None


def load_yaml(path):
    try:
        import yaml
    except ImportError:
        die(
            "pyyaml is required to read the config files.\n"
            "  py -m pip install pyyaml      (Windows)\n"
            "  python3 -m pip install --user pyyaml"
        )
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_ids():
    if not IDS_FILE.exists():
        die("no .ids.json — run `py agent.py setup` first.")
    return json.loads(IDS_FILE.read_text())


def money(minor, currency=""):
    if minor is None:
        return "n/a"
    return f"${int(minor) / 100:.2f} {currency}".strip()


# --------------------------------------------------------------------------- setup

REFERENCE_SEEDS = {
    "/exclusions/README.md": """PARTIAL exclusion information — user-confirmed entries only.

This has NOT been reconciled against the CRM. It is not a complete list of companies that
must be excluded. A company being absent from it means only that it is absent from it.
Never describe the exclusions as complete, verified, or CRM-checked.

Still unconfirmed: the full current-client list, opt-outs, and protected territories.""",
    "/exclusions/confirmed.md": """Excluded from prospecting — do not research as prospects, do not draft outreach for:

- Samuel Scales Marketing (own business)
- Drone Syndrome Media (own business)

Summit Fencing LLC is NOT an exclusion. It is an existing-client reference record — see
/references/existing_clients.md.""",
    "/references/existing_clients.md": """Existing clients — reference records, never acquisition targets.

## Summit Fencing LLC

- Label every output for it: "Existing client — no acquisition outreach."
- Produce its research brief and structured company record, like any other included company.
- relationship=existing_client
- Never generate acquisition outreach for it (no first-contact, no follow-ups, no discovery
  questions) and never place it in an acquisition sequence or a proposed acquisition import.
- Never infer its payment status, current fees, sales results, or historic communications
  from the fact that it is included. None of that is known here.
- contact_status: use a verified historic value if one is recorded here, otherwise `unknown`.
  Record that no outreach occurred during a run without asserting it has never been
  contacted.""",
    "/brief/offer.md": """Samuel Scales Marketing helps established residential fence contractors generate
qualified estimate opportunities through the Fence Clients On Demand System: Meta
advertising, a conversion page or form, and GoHighLevel lead follow-up.

Pricing: $1,500/month management. The client's $1,000/month advertising budget is separate
and is the client's spend, not agency revenue.

Goal: $100,000+ in annual agency revenue. Six retained clients would be $9,000/month
management revenue, a $108,000 annualized pace before expenses — arithmetic, not a
guarantee and not a claim about actual collections.

Voice: direct, practical, conversational, natural contractions, only substantiated proof.
Samuel owns sales calls, closing, campaign approval, client relationships, and delivery.""",
}

RESEARCH_SEED = {
    "/README.md": """Research history — one record per company considered, written by sessions.

Record every company: verified, rejected, incomplete, excluded, and reference records.
Deduplicate by normalized company domain and business identity. Revisit an incomplete
record only with a stated reason rather than rediscovering it as new.

Keep research, qualification, and contact dispositions separate. A draft is never a contact.

Exclusions, existing-client references, and the offer brief are NOT here — they live in the
read-only reference store and are changed through the API, not by a session."""
}


REFERENCE_STORE = {
    "name": "Samuel Scales Marketing - Reference",
    "description": (
        "Offer brief, partial user-confirmed prospecting exclusions, and existing-client "
        "reference records including Summit Fencing LLC. Read this before researching or "
        "including any company. Read-only: it is maintained outside the session. The "
        "exclusion information is NOT reconciled against the CRM and is not a complete "
        "list of who must be excluded."
    ),
}

HISTORY_STORE = {
    "name": "Samuel Scales Marketing - Research History",
    "description": (
        "One record per company considered — verified, rejected, incomplete, excluded, "
        "reference — so later runs neither repeat the research nor re-approach a company. "
        "Deduplicate by normalized company domain and business identity. Research, "
        "qualification, and contact dispositions stay separate."
    ),
}


def save_ids(ids):
    IDS_FILE.write_text(json.dumps(ids, indent=2) + "\n")


def seed_memory(store_id, path, content):
    """Create one memory, treating an already-occupied path as already seeded.

    The API returns 409 memory_path_conflict_error when `path` exists, which is what
    makes re-running `setup` safe: seeding never duplicates and never overwrites.
    """
    try:
        request(
            "POST", f"/memory_stores/{store_id}/memories", {"path": path, "content": content}
        )
        return "seeded "
    except ApiError as e:
        if "memory_path_conflict" in str(e):
            return "present"
        raise


def cmd_setup(args):
    """Create the four objects and seed the two stores. Resumable and idempotent.

    Each ID is written to .ids.json the moment its object exists, so a call that fails
    partway leaves a record of what was already created. Re-running reuses those objects
    instead of orphaning them and creating a second set.
    """
    ids = {}
    if IDS_FILE.exists():
        ids = json.loads(IDS_FILE.read_text())
        print(f"==> Found {IDS_FILE.name} — reusing the objects recorded in it")

    def ensure(key, label, body_or_path):
        if ids.get(key):
            print(f"==> {label}: reusing {ids[key]}")
            return ids[key]
        print(f"==> Creating {label}")
        path, body = body_or_path
        obj = request("POST", path, body() if callable(body) else body)
        ids[key] = obj["id"]
        save_ids(ids)  # checkpoint before anything else can fail
        print(f"    {obj['id']}" + (f" (version {obj['version']})" if obj.get("version") else ""))
        return obj["id"]

    agent_id = ensure("agent_id", "agent", ("/agents", lambda: load_yaml(AGENT_YAML)))
    ensure("environment_id", "environment", ("/environments", lambda: load_yaml(ENV_YAML)))
    # Two stores on purpose. The agent reads untrusted web pages, so a prompt injection
    # could otherwise write to the exclusions or Summit's designation and a later session
    # would read that back as trusted memory. Reference material is attached read_only and
    # is only ever changed through the API.
    ref_id = ensure(
        "reference_store_id", "reference store (attached read-only)",
        ("/memory_stores", REFERENCE_STORE),
    )
    hist_id = ensure(
        "history_store_id", "research-history store (attached read-write)",
        ("/memory_stores", HISTORY_STORE),
    )

    for store_id, label, seeds in (
        (ref_id, "reference", REFERENCE_SEEDS),
        (hist_id, "research-history", RESEARCH_SEED),
    ):
        print(f"==> Seeding the {label} store")
        for path, content in seeds.items():
            print(f"    {seed_memory(store_id, path, content)} {path}")

    print(f"\nIDs written to {IDS_FILE.name}. No session started, no model cost incurred.")
    print("Confirm what exists:  py agent.py verify")
    print("Then, when you are ready to authorize the test: py agent.py launch --confirm")


# -------------------------------------------------------------------------- launch

OUTCOME_DESCRIPTION = (
    "Target market: Alabama. Produce a six-company table: the Summit Fencing LLC "
    "existing-client reference record, plus up to five verified new residential fence "
    "contractor prospects. Aim for five new prospects but never relax the four-part "
    "verification bar to reach that number — return fewer with an explanation instead. "
    "Every included company gets a prospect brief. New prospects additionally get one "
    "personalized first-contact message, two follow-up drafts, and discovery-call "
    "questions, all as drafts, none sent. Summit gets a brief and a record only, labeled "
    "'Existing client - no acquisition outreach', with no outreach drafts and no place in "
    "any acquisition import. Produce prospects.csv with the 22 specified columns, "
    "research-log.csv covering every company considered including rejects and excluded "
    "records, ghl-import-mapping.md, daily-brief.md ranking the new prospects with the "
    "evidence behind each ranking and showing Summit separately, and run-log.md. Contact "
    "nobody: public search and reading public pages only - no outreach, no forms, no "
    "signups, no bookings, no purchases, no CRM import, no ad or budget changes."
)


def session_body(ids):
    return {
        "agent": ids["agent_id"],
        "environment_id": ids["environment_id"],
        "title": "Fence prospecting test - Summit reference + up to 5 new AL prospects",
        "budget": {
            "type": "limit",
            "max_list_cost": {"amount": BUDGET_CENTS, "currency": "USD"},
        },
        "resources": [
            {
                "type": "memory_store",
                "memory_store_id": ids["reference_store_id"],
                "access": "read_only",
                "instructions": (
                    "Read this before researching or including any company: the offer brief, "
                    "the partial prospecting exclusions, and the existing-client references. "
                    "Summit Fencing LLC is an existing-client reference here - not an "
                    "exclusion and not a prospect. The exclusion information is not complete "
                    "and not CRM-reconciled; never describe it as either. This store is "
                    "read-only by design: propose changes in run-log.md instead of writing."
                ),
            },
            {
                "type": "memory_store",
                "memory_store_id": ids["history_store_id"],
                "access": "read_write",
                "instructions": (
                    "Your research history. Check it before researching a company to avoid "
                    "repeating work or re-approaching anyone, and record every company you "
                    "consider here - verified, rejected, incomplete, excluded, reference - "
                    "with its disposition and reason."
                ),
            },
        ],
        "initial_events": [
            {
                "type": "user.define_outcome",
                "description": OUTCOME_DESCRIPTION,
                "rubric": {"type": "text", "content": RUBRIC.read_text(encoding="utf-8")},
                "max_iterations": 5,
            }
        ],
    }


def cmd_launch(args):
    ids = load_ids()
    if not args.confirm:
        print(
            "This starts a BILLABLE session with a $8.00 cap.\n"
            "The cap is checked before each model request; a request already in flight "
            "finishes, so the final figure can land above $8.00.\n"
            "Whether $8.00 covers six records is unknown until a run produces evidence.\n\n"
            "Re-run with --confirm to authorize it."
        )
        return
    session = request("POST", "/sessions", session_body(ids))
    sid = session["id"]
    LAST_SESSION.write_text(sid + "\n")
    print(f"Session:  {sid}")
    print(f"Status:   {session.get('status')}")
    ws = RESOLVED.get("workspace_id") or "<YOUR_WORKSPACE>"
    print(f"Watch:    https://platform.claude.com/workspaces/{ws}/sessions/{sid}")
    print("\nPoll:     py agent.py watch")
    print("When it stops: py agent.py results")


# --------------------------------------------------------------------- watch/results


def session_id_arg(args):
    if getattr(args, "session_id", None):
        return args.session_id
    if LAST_SESSION.exists():
        return LAST_SESSION.read_text().strip()
    die("no session id given and no .last-session file — pass one explicitly.")


def classify(session):
    """-> (keep_polling, headline). Mirrors the documented idle/terminated gate."""
    status = session.get("status")
    stop = (session.get("stop_reason") or {}).get("type")
    if status == "terminated":
        return False, "Session terminated. Fetch whatever it produced."
    if status == "idle":
        if stop == "requires_action":
            return False, (
                "PAUSED FOR A DECISION — a tool call is waiting. The server's `auto` "
                "evaluation reached no determination, so it neither ran nor denied it.\n"
                "Open the Console session to allow or deny."
            )
        if stop == "budget_reached":
            return False, (
                "PAUSED AT THE $8.00 CAP. Deliverables are likely partial.\n"
                "It resumes only if the cap is changed — do not change it without "
                "authorization."
            )
        return False, "Session is idle and finished working."
    return True, None


def cmd_watch(args):
    sid = session_id_arg(args)
    while True:
        s = request("GET", f"/sessions/{sid}")
        usage = s.get("usage") or {}
        cost = usage.get("list_cost") or {}
        stop = (s.get("stop_reason") or {}).get("type")
        print(
            f"{s.get('status'):<13} cost {money(cost.get('amount')):>10}   stop_reason={stop}"
        )
        keep_going, headline = classify(s)
        if not keep_going:
            print(f"\n{headline}")
            print(f"\nNext: py agent.py results {sid}")
            return
        time.sleep(args.interval)


def cmd_results(args):
    sid = session_id_arg(args)
    s = request("GET", f"/sessions/{sid}")
    usage = s.get("usage") or {}
    cost = usage.get("list_cost") or {}
    server_tools = usage.get("server_tool_use") or {}

    print("==> Session status and actual usage")
    print(f"    status:         {s.get('status')}")
    print(f"    stop_reason:    {(s.get('stop_reason') or {}).get('type')}")
    print(f"    actual cost:    {money(cost.get('amount'), cost.get('currency', ''))}")
    print(f"    active seconds: {usage.get('active_seconds')}")
    print(f"    input tokens:   {usage.get('input_tokens')}")
    print(f"    output tokens:  {usage.get('output_tokens')}")
    print(f"    web searches:   {server_tools.get('web_search_requests')}")
    for ev in s.get("outcome_evaluations") or []:
        print(f"    outcome:        {ev.get('result')} — {(ev.get('explanation') or '')[:300]}")

    out = ROOT / args.out
    print(f"\n==> Deliverables -> {out}")
    files = []
    for attempt in range(1, 4):
        listing = request(
            "GET", "/files", beta=FILES_BETA, query={"scope_id": sid}
        )
        files = listing.get("data") or []
        if files:
            break
        print(f"    nothing indexed yet (attempt {attempt}/3)")
        time.sleep(3)

    if not files:
        print("    No output files found. If the session did real work, check the Console —")
        print("    outputs are only captured from /mnt/session/outputs/.")
        return

    out.mkdir(parents=True, exist_ok=True)
    for f in files:
        name = f.get("filename") or f["id"]
        dest = out / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        download(f"/files/{f['id']}/content", dest)
        print(f"    {name} ({f.get('size_bytes')} bytes)")

    print("\nRead run-log.md first — it records what could not be verified and what was")
    print("blocked or refused. Inspect the files themselves; the grader's verdict is")
    print("supporting information, not proof.")


# -------------------------------------------------------------------- update-agent


def cmd_update_agent(args):
    ids = load_ids()
    current = request("GET", f"/agents/{ids['agent_id']}")
    version = current.get("version")
    print(f"==> Current version: {version}")
    body = load_yaml(AGENT_YAML)
    body["version"] = version  # optimistic lock: a concurrent edit becomes a 409
    updated = request("POST", f"/agents/{ids['agent_id']}", body)
    print(f"==> Now version: {updated.get('version')}")
    print("\nRunning sessions keep the version they started on; new sessions get this one.")


# ------------------------------------------------------------------ verify/preflight

EXPECTED_SEEDS = {
    "reference_store_id": sorted(REFERENCE_SEEDS),
    "history_store_id": sorted(RESEARCH_SEED),
}


def flat(text):
    """Normalize for substring checks: collapse whitespace, fold case.

    Seeds and the rubric are prose that wraps, so a literal substring match would fail
    on a line break or a capitalized word rather than on missing content.
    """
    return " ".join(text.split()).lower()


class Checks:
    def __init__(self):
        self.failed = []

    def __call__(self, ok, label, detail=""):
        print(f"  [{'OK  ' if ok else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
        if not ok:
            self.failed.append(label)
        return ok

    def report(self, what):
        if self.failed:
            print(f"\n{len(self.failed)} {what} check(s) FAILED:")
            for f in self.failed:
                print(f"  - {f}")
            sys.exit(1)
        print(f"\nAll {what} checks passed.")


def check_session_config(chk, ids):
    """The session configuration is validated, never created — creating one is billable.

    This is the body `launch` would POST, so what it asserts is what a run would carry.
    """
    body = session_body(ids)
    by_id = {r["memory_store_id"]: r for r in body["resources"]}
    ref = by_id.get(ids["reference_store_id"], {})
    hist = by_id.get(ids["history_store_id"], {})
    chk(len(body["resources"]) == 2, "session attaches exactly 2 memory stores")
    chk(ref.get("access") == "read_only",
        "reference store attached read_only", ref.get("access", "missing"))
    chk(hist.get("access") == "read_write",
        "research history attached read_write", hist.get("access", "missing"))
    chk(all(r.get("type") == "memory_store" for r in body["resources"]),
        "both resources are memory_store resources")
    budget = body["budget"]["max_list_cost"]
    chk(budget["amount"].isdigit() and budget["currency"] == "USD",
        "budget is an integer-string minor-unit USD cap", money(budget["amount"], "USD"))
    ev = body["initial_events"][0]
    chk(ev["type"] == "user.define_outcome" and ev.get("rubric", {}).get("content"),
        "kickoff is a single user.define_outcome carrying the rubric")
    desc = ev["description"]
    chk("Summit Fencing LLC existing-client reference" in desc,
        "outcome names Summit as an existing-client reference")
    chk("no outreach drafts" in desc and "acquisition import" in desc,
        "outcome keeps Summit out of outreach and acquisition import")


def cmd_preflight(args):
    """Offline validation. Needs no API key, makes no network call, costs nothing."""
    chk = Checks()

    print("==> Config files parse")
    agent = load_yaml(AGENT_YAML)
    env = load_yaml(ENV_YAML)
    chk(bool(agent.get("system")), "agent.yaml has a system prompt")
    chk(agent.get("model") == "claude-opus-5", "agent model", str(agent.get("model")))
    toolsets = [t for t in agent.get("tools") or [] if t.get("type") == "agent_toolset_20260401"]
    chk(len(toolsets) == 1, "exactly one agent_toolset_20260401")
    configs = {c.get("name"): c for c in (toolsets[0].get("configs") if toolsets else [])}
    chk(configs.get("bash", {}).get("enabled") is False, "bash disabled in the agent toolset")
    chk(configs.get("web_fetch", {}).get("permission_policy", {}).get("type") == "auto",
        "web_fetch runs under the auto permission policy")
    chk((env.get("config") or {}).get("networking", {}).get("type") == "limited",
        "environment egress is deny-by-default (limited)")

    print("==> Beta header routing")
    chk(beta_for("/memory_stores") == BETA, "memory_stores uses the managed-agents beta", BETA)
    chk(beta_for("/agents") == BETA, "agents uses the managed-agents beta")
    chk(beta_for("/files") == FILES_BETA, "files adds the files beta")
    try:
        beta_for("/memory_stores", "agent-memory-2026-07-22")
        chk(False, "an undocumented memory beta is refused")
    except ApiError:
        chk(True, "an undocumented memory beta is refused")

    print("==> Session configuration (validated, not created)")
    check_session_config(chk, {k: f"<{k}>" for k in
                               ("agent_id", "environment_id",
                                "reference_store_id", "history_store_id")})

    print("==> Summit handling across the seeds and rubric")
    ref = "\n".join(REFERENCE_SEEDS.values())
    chk("Summit Fencing LLC is NOT an exclusion" in ref,
        "exclusion seed states Summit is not an exclusion")
    chk("relationship=existing_client" in ref, "reference seed sets relationship=existing_client")
    chk("Never generate acquisition outreach" in ref, "reference seed forbids acquisition outreach")
    chk("Samuel Scales Marketing" in ref and "Drone Syndrome Media" in ref,
        "both confirmed exclusions are seeded")
    chk("not been reconciled against the crm" in flat(ref),
        "exclusions are seeded as PARTIAL")
    rubric = flat(RUBRIC.read_text(encoding="utf-8"))
    chk("existing client — no acquisition outreach" in rubric, "rubric grades Summit's label")
    chk("summit has **no** outreach drafts" in rubric, "rubric grades no drafts for Summit")

    chk.report("preflight")
    print("This validates configuration only. Nothing was created and no key was used.")


def list_memory_paths(store_id):
    """Flat list of memory paths in a store, walking prefix nodes."""
    paths, queue, seen = [], ["/"], set()
    while queue:
        prefix = queue.pop(0)
        if prefix in seen:
            continue
        seen.add(prefix)
        after = None
        while True:
            query = {"path_prefix": prefix, "view": "basic", "limit": 100}
            if after:
                query["after_id"] = after
            page = request("GET", f"/memory_stores/{store_id}/memories", query=query)
            items = page.get("data") or []
            for item in items:
                if item.get("type") == "memory_prefix":
                    queue.append(item["path"].rstrip("/") + "/")
                elif item.get("path"):
                    paths.append(item["path"])
            if not page.get("has_more") or not page.get("last_id"):
                break
            after = page["last_id"]
    return sorted(set(paths))


def cmd_verify(args):
    """Confirm what actually exists, by reading it back from the API."""
    ids = load_ids()
    chk = Checks()

    print("==> Agent")
    agent = request("GET", f"/agents/{ids['agent_id']}")
    print(f"    {agent['id']}  version {agent.get('version')}")
    model = agent.get("model")
    chk(bool(agent.get("id")), "agent exists", agent["id"])
    chk((model if isinstance(model, str) else (model or {}).get("id")) == "claude-opus-5",
        "agent model is claude-opus-5")
    system = flat(agent.get("system") or "")
    chk("summit fencing llc is an existing client" in system,
        "system prompt carries the Summit existing-client rule")
    chk("never generate acquisition outreach for it" in system,
        "system prompt forbids acquisition outreach for Summit")

    print("==> Environment")
    env = request("GET", f"/environments/{ids['environment_id']}")
    cfg = env.get("config") or {}
    print(f"    {env['id']}")
    chk(cfg.get("type") == "cloud", "environment is a cloud sandbox", str(cfg.get("type")))
    chk((cfg.get("networking") or {}).get("type") == "limited",
        "container egress is deny-by-default")

    print("==> Memory stores")
    for key, label in (("reference_store_id", "reference"),
                       ("history_store_id", "research history")):
        store = request("GET", f"/memory_stores/{ids[key]}")
        print(f"    {label}: {store['id']}  {store.get('name')}")
        chk(bool(store.get("id")), f"{label} store exists", store["id"])
        chk(not store.get("archived_at"), f"{label} store is not archived")

    print("==> Seeded records")
    for key, expected in EXPECTED_SEEDS.items():
        found = list_memory_paths(ids[key])
        for path in expected:
            chk(path in found, f"{key}: {path}")
        extra = sorted(set(found) - set(expected))
        if extra:
            print(f"    note: {len(extra)} additional record(s) present: {', '.join(extra)}")

    print("==> Session configuration (validated, not created)")
    check_session_config(chk, ids)

    chk.report("verification")
    print("No session was created and no model cost was incurred by this command.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("setup", help="create agent, environment, datastore (no model cost)")

    launch = sub.add_parser("launch", help="start the billable test session")
    launch.add_argument("--confirm", action="store_true", help="authorize the paid run")

    watch = sub.add_parser("watch", help="poll until the session stops")
    watch.add_argument("session_id", nargs="?")
    watch.add_argument("--interval", type=int, default=20)

    results = sub.add_parser("results", help="actual cost + download deliverables")
    results.add_argument("session_id", nargs="?")
    results.add_argument("--out", default="deliverables")

    sub.add_parser("update-agent", help="apply a YAML edit as a new agent version")
    sub.add_parser("preflight", help="offline config validation (no key, no network)")
    sub.add_parser("verify", help="read the created objects back and check them")

    args = p.parse_args()
    handlers = {
        "setup": cmd_setup,
        "launch": cmd_launch,
        "watch": cmd_watch,
        "results": cmd_results,
        "update-agent": cmd_update_agent,
        "preflight": cmd_preflight,
        "verify": cmd_verify,
    }
    try:
        handlers[args.cmd](args)
    except ApiError as e:
        die(str(e))
    except KeyboardInterrupt:
        sys.exit("\ninterrupted")


if __name__ == "__main__":
    main()
