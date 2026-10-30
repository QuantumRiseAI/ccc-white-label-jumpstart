"""Unity Biomedicines deployment-option run-cost model.

One usage profile is applied to every option so the columns stay comparable.
All unit prices are list-price assumptions (Oct 2026) to confirm against
Unity/Plurality contracts. Edit ASSUMPTIONS and rerun: python3 cost_model.py
"""

ASSUMPTIONS = {
    # usage (from the deck: 3 analyses/day during close, 2 follow-ups each)
    "users": 6,
    "analyses_per_close_day": 3,
    "followups_per_analysis": 2,
    # token shape per analysis. Project knowledge is 67K-86K tokens per Project
    # (DEPLOYMENT-OPTIONS.md); engine output summary adds roughly 40K.
    "input_tokens_first_turn": 120_000,
    "output_tokens_first_turn": 8_000,
    "new_input_tokens_per_followup": 10_000,
    "output_tokens_per_followup": 3_000,
    # Claude API list prices, $ per million tokens (Sonnet 5.5 / Opus 5.5)
    "price": {
        "sonnet": {"in": 2.00, "out": 10.00, "cache_read": 0.20},
        "opus": {"in": 4.00, "out": 20.00, "cache_read": 0.20},
    },
    # seats: confirm plan. $20 on the slide is consumer Pro pricing.
    "seat_price": 30.0,  # Team standard seat, monthly billing (assumption)
    "ops_rate": 100.0,   # $/hour, as on the slide
}

# Fixed monthly infrastructure and ops hours per option (assumptions).
OPTIONS = [
    # name, seats?, api?, infra $/mo, ops hrs/mo, infra note
    ("Claude Projects", True, False, 0, 4,
     "seats only; ops = monthly file drop and run check"),
    ("Windows VM (current)", False, True, 140, 8,
     "1 VM ~2 vCPU/8GB + disk + backup; ops = patching, runtime, drops"),
    ("Claude + Snowflake", True, False, 60, 8,
     "XS warehouse, ~20 credit-hrs/mo at $3; seats for the Claude UI"),
    ("Azure application", False, True, 260, 16,
     "App Service P1v3 + Azure SQL + Key Vault + App Insights + storage"),
    ("Snowflake application", False, True, 150, 12,
     "Streamlit/Container in Snowflake, XS warehouse ~50 credit-hrs/mo"),
]

SCENARIOS = {
    "Low":  {"close_days": 5,  "model": "sonnet", "analyses_mult": 1},
    "Base": {"close_days": 8,  "model": "sonnet", "analyses_mult": 1},
    "High": {"close_days": 20, "model": "opus",   "analyses_mult": 2},
}


def api_cost_per_analysis(model, a=ASSUMPTIONS):
    p = a["price"][model]
    first = (a["input_tokens_first_turn"] * p["in"]
             + a["output_tokens_first_turn"] * p["out"]) / 1e6
    # follow-ups reread the cached prefix and add new input
    fu = (a["input_tokens_first_turn"] * p["cache_read"]
          + a["new_input_tokens_per_followup"] * p["in"]
          + a["output_tokens_per_followup"] * p["out"]) / 1e6
    return first + a["followups_per_analysis"] * fu


def run(a=ASSUMPTIONS):
    rows = []
    for sname, s in SCENARIOS.items():
        analyses = a["analyses_per_close_day"] * s["close_days"] * s["analyses_mult"]
        per = api_cost_per_analysis(s["model"], a)
        for name, seats, api, infra, ops_h, note in OPTIONS:
            seat_cost = a["users"] * a["seat_price"] if seats else 0
            api_cost = analyses * per if api else 0
            tech = seat_cost + api_cost + infra
            ops = ops_h * a["ops_rate"]
            rows.append((sname, name, analyses, seat_cost, api_cost, infra,
                         tech, ops, tech + ops, (tech + ops) * 12))
    return rows


if __name__ == "__main__":
    for m in ("sonnet", "opus"):
        print(f"API cost per analysis ({m}, incl. follow-ups): "
              f"${api_cost_per_analysis(m):.2f}")
    hdr = ("Scenario", "Option", "Analyses/mo", "Seats", "API", "Infra",
           "Tech/mo", "Ops/mo", "Total/mo", "Annual")
    print("\n" + " | ".join(hdr))
    for r in run():
        print(f"{r[0]} | {r[1]} | {r[2]} | ${r[3]:,.0f} | ${r[4]:,.2f} | "
              f"${r[5]:,.0f} | ${r[6]:,.0f} | ${r[7]:,.0f} | ${r[8]:,.0f} | ${r[9]:,.0f}")
