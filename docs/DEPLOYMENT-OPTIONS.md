# Serif Jumpstarts: Deployment Options

**Purpose:** Internal decision doc.
Where the two Jumpstarts can run, what each option costs us, and what to take into the Flagship IT
conversation.

**Prepared:** 2026-09-17 · **Status:** DRAFT, updated after Flagship IT replied

---

## Where Flagship IT Landed

Asked on 2026-09-17 to choose between a local app, Vercel and Azure.
The answer was that **local is easiest and preferred**, and that Vercel access could be provided to
the Serif or fsplabs accounts, but that data segregation between companies is not yet ready.

Two things follow.

* A packaged local app is approved in principle, so option 3 moves from fallback to the target.
* Hosted options are not refused, only deferred.
  Revisit once their segregation work lands, at which point option 4 or 5 on their own tenancy
  becomes available.

Their reservation was specific to sharing a platform across companies, not to hosting as such.
That is worth carrying into the Claude question too: if Flagship is still separating company data,
it is worth confirming whose Claude organization Scott sits in and how it is structured.

## What Is Already Proven

Both Jumpstarts run today as Claude Projects, and a Project run reproduced a local run of the same
period exactly.

Verified 2026-09-17 against P&L Flux for Aug 2026, comparing a Claude Project output to a local build:

* Identical finding count, with identical rule, title and amount on every one
* Total amount at risk matching to the cent
* Identical sha256 fingerprints on all five input files
* Same tie-out result, same metrics, same absent feeds
* Same console, engine and ruleset versions

The only fields that differ are the ones designed to: `run_id`, `generated_at`, and `source_dir`,
which records `/home/claude/run` in the Project sandbox instead of a local path.

Two things this establishes.
Claude in a Project runs the prebuilt scripts rather than writing its own analysis, which is the
property the whole design depends on.
And the engine is deterministic across environments, not just across runs on one machine.

Both runs produced 95 findings and $4,883,211.33: 90 F1.VARIANCE findings worth $4,783,473.76 plus
5 F3.ACCRUAL_RECEIPT findings worth $99,737.57.

## The Options

### 1. Claude Project

Two Projects, one per use case.
Configure-once files uploaded as Project knowledge, the period's data dropped into a fresh chat.

* **Needs:** a Claude Team or Enterprise seat, and "Upgraded file creation and analysis" enabled
  for the org
* **Gives up:** no versioning, and setup is manual per person.
  Project knowledge is text-extracted into context, roughly 67K to 86K tokens per Project, which
  sits close enough to the context window that retrieval may kick in and make reference material
  load selectively
* **Effort:** none, built and audited
* **Status:** working and validated today

Behavioral rules belong in the Project Instructions field rather than in an uploaded file, because
that field is the only place guaranteed to be in context on every turn.
A prohibition that gets retrieved only sometimes fails silently.

### 2. Claude Plugin

One private git repo holding both skills and their scripts, distributed through Claude's own
organization settings.

* **Needs:** an Enterprise or Team admin to add the plugin, either by ZIP upload or by syncing a
  private GitHub repo
* **Gives up:** hooks and subagents do not run in chat, only in Cowork.
  Everything here is skills and scripts, so that limit does not bite yet
* **Effort:** low, mostly mechanical.
  The skill files already exist, the scripts move into the skill folders, and the manifest is about
  six lines
* **Status:** not started

This is the strongest end state for Scott, for four reasons.

* Scripts run without entering context, so it is more token-efficient than a Project by design
* An admin can set it to "installed by default" or "required", so Scott does nothing
* Users cannot edit an organization-managed plugin, which stops the configuration drifting
* Updates are version-gated through the manifest, which fits the three-axis versioning the consoles
  already carry

`claude plugin eval` also runs a set of test prompts with and without the plugin loaded, which
measures whether Claude reliably reaches for the script instead of improvising.
Worth running before this goes near a client.

### 3. Packaged Local App

**Selected as the target by Flagship IT.**
Scott runs it on his own machine, nothing hosted, nothing for their team to support.

The binding constraint is that Scott does not have Python, so the runtime has to come with it.
That forces a choice between three builds, which differ sharply in cost:

* **Bundled binary.**
  A single double-clickable application containing the runtime, both engines and the console
  builder.
  Feels like software.
  Needs an Apple Developer ID with notarization for macOS and an EV code signing certificate for
  Windows, both of which carry recurring cost and identity-validation lead time.
  Unsigned downloads are stopped by Gatekeeper and SmartScreen regardless of IT approval.
* **Double-clickable script.**
  A `.command` or `.bat` beside the scripts.
  No signing, but it depends on a Python already being present, which is usually true on macOS via
  Command Line Tools and usually false on Windows.
* **Portable runtime in a folder.**
  An embeddable Python shipped alongside the scripts, launched by the script above.
  No installer, no certificates, works offline.
  Scrappier to look at and the pragmatic place to start.

Open before building: which platform Scott is on, and whether this has to look like an application
or simply work.
If an unzipped folder he double-clicks is acceptable, signing is avoided entirely and this is days
rather than weeks.
If it must be a signed app, the certificate process is the long-lead item and should start
immediately, since nothing else depends on us.

Either way it needs an update path, because there is no auto-update, and we own support on every
platform we ship to.

### 4. Static Hosting of the Output

The engine runs somewhere, and the finished HTML is published behind single sign-on.
Vercel, Azure Static Web Apps or SharePoint all serve this equally well.

* **Needs:** authentication in front of it, since the file carries real financial detail inline
* **Gives up:** still no shared decisions.
  Each viewer's approvals live in their own browser
* **Effort:** low to moderate
* **Status:** not started

### 5. Hosted App in Flagship's Tenant

The engine runs as a scheduled job, decisions persist in a database, single sign-on at the front.

* **Needs:** a real cloud footprint and somebody to support it
* **Gives up:** nothing functionally.
  This is the end state if this becomes a product rather than a monthly deliverable
* **Effort:** high
* **Status:** not started

Vercel and Azure are both viable.
Our lean is Azure, or whatever sits in Flagship's own tenant behind their existing identity
provider, because the output contains real financial detail and keeping it inside their tenancy
avoids a third-party data question entirely.
If Vercel is already established at Flagship with SAML and audit logging in place, that reasoning
weakens and we are equally happy there.

Note that Vercel is multi-tenant SaaS, so Flagship has a Vercel **account** and **teams** rather
than an instance.
The control question underneath option 4 or 5 on Vercel is which plan tier they are on, since SAML
single sign-on and audit logs come with Enterprise and mostly do not with Pro.

### 6. Hand the Code to Flagship

We write it, their team deploys and runs it in their own environment.

* **Needs:** a DevOps function with capacity
* **Gives up:** our control over the release cadence
* **Effort:** low for us, unknown for them
* **Status:** open question for the IT call

This is the cleanest answer for a security review, since nothing runs outside their tenancy.
It is also the option most likely to stall if they have no capacity, so it is worth asking whether
it is something they normally do rather than offering to hand over the work outright.

## Comparison

| Option | Effort | Infra | Versioned | Shared decisions | Client setup |
|---|---|---|---|---|---|
| 1. Claude Project | none | none | no | no | manual, per person |
| 2. Claude Plugin | low | none | yes | no | admin pushes once |
| 3. Local app | high | none | yes | no | download and install |
| 4. Static hosting | low to moderate | small | yes | no | a URL |
| 5. Hosted app | high | real | yes | yes | a URL |
| 6. Hand off code | low for us | theirs | yes | depends | theirs |

## Recommendation

Flagship IT has chosen local, so the sequence is now:

1. **Claude Projects this week.**
   Validated, zero dependencies, and the fastest way to put real output in front of Scott while the
   local app is built.
   It does not compete with the local app; it is what he uses in the meantime.
2. **Packaged local app as the deliverable.**
   Start with the portable-runtime folder unless Scott needs something that presents as an
   application, in which case begin the code signing process first because it is the long-lead
   item.
3. **Revisit hosted later.**
   Not refused, deferred until Flagship's data segregation work is done.
   Shared decisions across reviewers remains the one capability only a hosted app provides, and
   nobody has asked for it yet.

The plugin route stays worth knowing about, since it needs no infrastructure and an admin can push
it, but it is no longer the recommended path now that local is the stated preference.

## Open Questions for the IT Call

Answered: local is preferred, Vercel is possible later, segregation is the blocker on hosting.

Still open:

* Which platform is Scott on, and does the deliverable need to present as an application or simply
  work?
* Whose Claude organization is Scott in, Flagship's or Serif's, and who administers it?
  Relevant both for pushing a plugin and because their segregation concern may apply there too.
* Is there an internal pattern for distributing a desktop tool that we should conform to, and does
  a signed download need an endpoint exception logged?
* How is exported financial data classified as against production system access?
  This determines how much easier hosting gets once segregation is sorted.
* When do they expect the segregation work to land, so we know when to revisit hosting?

## Note: Absolute Paths in the Artifact

The engine records `source_dir` for every input, which on a local run embeds the full path,
including the operator's user folder and the client folder structure.
That path travels inside the HTML.
It is harmless to Flagship, who own the data, but it is the same class of leak as the personal names
already scrubbed from the codebase, and it is worth reducing to a basename before anything goes to a
wider audience.
