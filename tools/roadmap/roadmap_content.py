"""What the Serif AI Jumpstarts roadmap says. build_roadmap.py lays it out.

Each theme gathers roadmap items from Impulsive (the AIJ list, tag `roadmap`) under one
question Serif would ask. `items` keeps the Impulsive keys and sizes as the audit trail;
the page does not print them, because Serif does not see Impulsive, and the sizes are too
rough on umbrella items to show as effort.
"""

DOC = {
    "title": "AI Jumpstarts Roadmap",
    "subtitle": "GL Coding Review and P&L Flux",
    "date_line": "October 7, 2026",
    "status": "Draft for discussion",
    "eyebrow": "Serif Biomedicines &middot; CrossCountry Consulting &middot; Quantum Rise",
}

INTRO = [
    "Serif's two AI Jumpstarts, the GL Coding Review and the P&amp;L Flux, run today as Claude "
    "Projects: the month's exports go in, the scripts produce a review console, and Claude "
    "writes what the reviewer needs around it. They are built to be run by a trained analyst "
    "each close, with nothing to install and no connection to Serif's systems required.",
    "This roadmap is the path from there to a deployed solution. It gathers what Serif's "
    "finance team and the CrossCountry reviewers asked for during the demos and the parallel "
    "run, and what we found while building, into nine themes. Each theme says what it would "
    "change, and what the Projects can already do on request today.",
]

TODAY = {
    "heading": "What the Projects do today",
    "rows": [
        ("Run every close", "From NetSuite, Coupa, UKG and forecast exports as each system writes "
         "them. The same exports give the same findings."),
        ("Review in one console", "Coding findings by vendor with the last three months, the flux "
         "pack against the prior month, prior year and plan, payroll against the UKG roster, the "
         "balance sheet, and SOX &amp; GAAP checks."),
        ("Propose the entries", "Each proposed Journal Entry is filled in, editable and checked to "
         "balance; approved entries download as a NetSuite import file. A person imports it."),
        ("Draft, then decide", "Claude drafts vendor notes, commentary and the executive summary; "
         "the reviewer uses, edits or rejects each one. The decision record carries decisions "
         "through reruns in the month."),
        ("Share the review", "Published as a claude.ai Artifact, the console is one review for "
         "everyone with access, each decision attributed."),
        ("Answer after the close", "On request: the follow-up checklist, a check of posted entries "
         "against what was approved, the support behind any entry, what keeps recurring, a bill "
         "against its contract, and any cut of the data the console does not show."),
    ],
}

HOW_TO_READ = [
    ("Themes, not tickets", "Each theme opens with why it matters, then lists the capabilities "
     "it adds."),
    ("Crawl, Walk, Run", "Crawl is the Projects as delivered. Walk adds what a deployed solution "
     "needs: shared state across closes, connected data, controls. Run is agents working the "
     "close with people approving."),
    ("&#9670; Serif decides", "Items waiting on a decision, a system owner or data only Serif or "
     "Flagship can supply. Each one says what it needs."),
    ("Try it today", "Where the Projects can already do a version of the item on request, the "
     "theme names the prompt."),
]

THEMES = [
    {
        "name": "Close data arrives on its own, read-only",
        "dimension": "Data",
        "stage": "Walk",
        "standfirst": "About sixty uploads a close become none.",
        "lead": "Each close starts with the reviewer exporting and uploading the NetSuite saved "
        "search, the Coupa PO lines, the roster and the forecast. Serif already has a read-only "
        "NetSuite connector in Claude, and the Projects use it for document links. Coupa has no "
        "connector yet; Flagship IT is working on one.",
        "clusters": [
            ("Pull the ledger from NetSuite", "The month's GL read through the NetSuite connector "
             "in place of the saved search export, kept as a file with its fingerprint so the "
             "findings still reproduce. A trial pull returned the lines but left out the "
             "AP side of each bill, which the coding checks read.", False),
            ("Decide connector or upload, per source", "For NetSuite now and Coupa when its "
             "connector lands: usage cost, preparation time, freshness, size limits and who "
             "maintains each connection.", True),
            ("Coupa at the invoice level", "The invoice export, the 2025 and Open tabs, and the "
             "missing columns (NetSuite PO reference, budget check status, amounts invoiced and "
             "paid, requisition ID). They enable a three-way match, budget-check and "
             "payment-hold tests.", True),
            ("Scheduled, read-only delivery", "Flagship schedules or delivers the reports "
             "read-only, and nothing writes back to a source system.", True),
        ],
        "items": [("AIJ-103", "L"), ("AIJ-79", "M"), ("SERIF-136", "M")],
        "today": "The Projects pull each month's NetSuite link IDs through the connector, and "
        "Claude can look a document up in NetSuite to see that a fix is there.",
    },
    {
        "name": "More source feeds",
        "dimension": "Data",
        "stage": "Walk",
        "standfirst": "Checks that are off today because their feed has not arrived.",
        "lead": "Every run lists the checks it could not run and the feed each one needs. Most "
        "are sub-ledgers and registers that exist at Serif but are not exported.",
        "clusters": [
            ("Payroll register", "The ADP register adds pay by person and pay date: a payroll "
             "tie-out to the GL, a payroll cutoff accrual, headcount against plan, and salary "
             "variance by person, in place of reading offer and termination letters.", True),
            ("Sub-ledgers", "Vendor master, fixed asset register, prepaid schedule, accruals log, "
             "external research unbilled work and the EBITDA add-back mapping. Each switches on "
             "a check the run names as off today.", True),
            ("Expensify", "The expense register and its category-to-account mapping, to explain "
             "why expense lines arrive miscoded, not only catch them. Much of it lands on "
             "Non-Specific with an empty memo.", True),
            ("Contract terms", "A short record per contract or amendment: dates, billing "
             "frequency, rate, proration and renewal terms. Each bill is checked against it for "
             "an amount that does not agree, a partial month with no proration, or billing "
             "after the end date.", True),
            ("Plan coverage", "Payroll and depreciation in the plan, so they have a budget "
             "variance too.", True),
        ],
        "items": [("AIJ-105", "L"), ("SERIF-20", "S"), ("SERIF-140", "L")],
        "today": "Ask “Check this invoice against the SOW” with the contract attached.",
    },
    {
        "name": "Coding right at the source",
        "dimension": "Process",
        "stage": "Walk",
        "standfirst": "Fewer corrections each close, because fewer errors reach it.",
        "lead": "The coding review catches miscoding after it posts. The same patterns come back "
        "each month: lab suppliers on Facilities, spend on Non-Specific, a vendor recorded "
        "twice. Fixing them where they start is cheaper than correcting them every close.",
        "clusters": [
            ("Guide the requester", "Constrain account choices in Coupa, and prefill coding from "
             "the invoice and the requester.", True),
            ("The person behind the spend", "Each invoice or PO line shows its requester and "
             "approver, and proposes the department from theirs, with the person it was based "
             "on.", False),
            ("Flag what recurs", "An issue corrected two or three months running is flagged with "
             "the months, the total corrected and a fix at the source, and stays open until the "
             "cause is fixed.", True),
            ("Learn from the reclasses", "The reclass history by source system, requester and "
             "category shows what to fix upstream.", False),
        ],
        "items": [("AIJ-106", "M"), ("SERIF-138", "M"), ("SERIF-141", "M")],
        "today": "Ask “What came up again this month?” with earlier months' decision "
        "records attached, or ask who requested a PO and their department.",
    },
    {
        "name": "Entries that post cleanly",
        "dimension": "Process",
        "stage": "Walk to Run",
        "standfirst": "From a proposed entry to a posted one, with fewer touches.",
        "lead": "The Projects propose balanced, editable entries and a NetSuite import file. A "
        "deployed solution checks them against NetSuite before upload, codes every dimension "
        "the way the team has before, and in time posts what is approved.",
        "clusters": [
            ("One checked import", "Every approved entry from both reviews in one NetSuite import, "
             "checked first: each entry balances, accounts and segments are valid, the period "
             "is open.", False),
            ("Reverse what was booked", "A reclass reverses the original transaction on every "
             "dimension it hit (program, class, location and custom segments as well as account "
             "and department), so it leaves no balance behind.", True),
            ("Code from history", "Every proposed line takes the dimensions similar entries used "
             "before, and flags where history is mixed.", True),
            ("Run on a schedule, post what is approved", "The review runs weekly and through the "
             "close days, and approved entries post to NetSuite with the work paper attached.",
             True),
        ],
        "items": [("SERIF-137", "M"), ("SERIF-139", "L"), ("SERIF-135", "M"), ("AIJ-104", "M")],
        "today": "Ask “Check the posted entries” after the import, or ask how a vendor "
        "was coded by department, program and project over the last year.",
    },
    {
        "name": "Follow-ups that carry across closes",
        "dimension": "Process",
        "stage": "Walk",
        "standfirst": "One list of what is open, from every review, until it is closed.",
        "lead": "Every review raises items someone has to chase. Today they live in notes on "
        "the console for one close. Tracked across closes, each has an owner and a status, "
        "and every posted entry traces back to the item that raised it.",
        "clusters": [
            ("A permanent ID", "Each follow-up gets an ID by review type (DR1, DR2 for Department "
             "Review), never reused, with the review period as its own field.", True),
            ("One checklist", "ID, review and period, description, owner, due date, status and "
             "notes, with open items carried into the next review.", False),
            ("Tied to the entry", "The ID travels into the entry's memo and the import, and the "
             "item closes against the posted entry.", False),
            ("Linked items", "Related follow-ups link both ways, with suggested links the "
             "reviewer confirms.", True),
        ],
        "items": [("SERIF-127", "L"), ("SERIF-128", "S"), ("SERIF-129", "M"), ("SERIF-130", "S"),
                  ("SERIF-131", "M")],
        "today": "Ask “List the follow-ups” for a checklist with IDs, owners, due dates "
        "and status for the close.",
    },
    {
        "name": "One shared review for preparer and reviewer",
        "dimension": "Organization",
        "stage": "Walk",
        "standfirst": "No files passed between people.",
        "lead": "The shared console already holds one set of decisions for everyone with "
        "access. A hosted review goes further: sign-off in the app, the invoice beside the "
        "line, and Claude answering questions in place.",
        "clusters": [
            ("Live decisions and sign-off", "Preparer and reviewer see the same decisions as they "
             "are made, and the reviewer signs off in the app.", False),
            ("The invoice in view", "The Coupa or NetSuite invoice PDF shows inside the line "
             "detail.", False),
            ("Ask about a finding", "A question on a finding asks Claude for more detail, drafts "
             "the email to the owner, or looks up an unfamiliar part or vendor.", False),
        ],
        "items": [("AIJ-101", "L")],
        "today": "Publish the console as a claude.ai Artifact to share one review.",
    },
    {
        "name": "Deployed and governed in production",
        "dimension": "Agentic Orchestration",
        "stage": "Walk",
        "standfirst": "The controls a finance team needs before it relies on it.",
        "lead": "A Claude Project is managed by hand, one person at a time. Production needs a "
        "managed release, access control and an audit trail. Where it runs is Flagship IT's "
        "call; they have said local is easiest today and hosted options wait on their data "
        "separation between companies.",
        "clusters": [
            ("Where it runs", "The console hosted behind single sign-on, an app in Flagship's "
             "tenant, or the code handed to Flagship to run.", True),
            ("Managed releases", "The jumpstarts as an organization-managed Claude plugin, "
             "versioned and approved by the admin, with an update path and rollback.", True),
            ("Controls", "Checks that Claude runs the scripts rather than improvising, agent "
             "identity with least privilege, audit logging and SOX-style controls.", False),
        ],
        "items": [("AIJ-102", "L")],
        "today": None,
    },
    {
        "name": "Shared across Serif and Flagship",
        "dimension": "Organization",
        "stage": "Walk",
        "standfirst": "More of the close, and more of the portfolio.",
        "lead": "The context built for the jumpstarts (policies, chart of accounts, vendor "
        "coding, the data readers) is reusable well beyond two reviews.",
        "clusters": [
            ("A close-calendar site", "One site laid out like Serif's close calendar, with each "
             "jumpstart on its day, the accounting manual and training beside them.", False),
            ("Skills for the rest of the close", "Serif's team builds Claude skills for other "
             "close work from the same context.", False),
            ("Show it, then offer it", "Demos to the auditors, finance mentors, Flagship IT and "
             "Flagship Finance; offering it to other Flagship companies needs Flagship's data "
             "separation and a multi-company deployment.", True),
        ],
        "items": [("AIJ-108", "M"), ("AIJ-75", "S"), ("AIJ-74", "S")],
        "today": None,
    },
    {
        "name": "Next jumpstarts and the agent platform",
        "dimension": "Agentic Orchestration",
        "stage": "Run",
        "standfirst": "From two reviews to agents working the close.",
        "lead": "The same approach (deterministic scripts for the numbers, Claude for the "
        "judgment, people for the decisions) extends to more of finance. Serif has not chosen "
        "any of these.",
        "clusters": [
            ("Candidate jumpstarts", "Headcount intelligence, payroll review, cash flow and "
             "runway, research accruals, CRO invoice three-way match, ASC 718 stock "
             "compensation, board package assembly, a tax and deductibility review, and an "
             "FP&amp;A view of spend planned in one area that lands in another.", True),
            ("An agent suite for the close", "eController and eForecaster agents for AP, T&amp;E, "
             "accruals, prepaids, bank reconciliation and unrecorded liabilities.", False),
            ("The platform", "A multi-agent orchestration platform with a command center and "
             "AI and ML operations monitoring.", False),
        ],
        "items": [("AIJ-107", "L")],
        "today": None,
    },
]

CLOSING = {
    "heading": "Where to start",
    "paragraphs": [
        "Two decisions open most of this roadmap, and both sit with Serif and Flagship rather "
        "than with engineering. The first is where the jumpstarts run once they leave the "
        "Projects, which Flagship IT is weighing against its data separation work. The second "
        "is whether the ledger arrives through the NetSuite connector Serif already has: it "
        "removes most of the monthly uploads and is the base for checking entries against "
        "NetSuite and reversing reclasses on every dimension.",
        "With those settled, the follow-up tracker and the shared review are one piece of work: "
        "both need state that outlives a single close and more than one person working it, "
        "which is exactly what a Project cannot hold.",
    ],
}
