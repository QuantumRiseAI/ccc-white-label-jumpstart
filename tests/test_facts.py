"""facts(), which keeps an item's note and reason to what was found: instructions to the
reviewer go, facts that happen to start with the same word stay, and spacing is kept.

    python3 tests/test_facts.py
"""
import os
import re
import sys

SRC = open(os.path.join(os.path.dirname(__file__), "..", "src", "build_pages.py"), encoding="utf-8").read()
g = {"re": re}
exec(SRC[SRC.index("STEP = re.compile("):SRC.index("def draft(")], g)
facts = g["facts"]
fails = 0


def ok(cond, msg):
    global fails
    print(("  PASS " if cond else "  FAIL ") + msg)
    fails += not cond


KEEP = ["Use tax of $4K was accrued.", "Open purchase orders total $1M.", "Book value is $5K.", "Review fees rose 8%.",
        "Check run fees fell.", "If the lease renews, the cost rises 3%.", "Reject rates were low in August."]
for s in KEEP:
    ok(facts(s) == s, "keeps a fact: " + s)
DROP = ["Read the bill.", "Ask the owner whether it shipped.", "If it is right, choose Cleared.", "Book it or reject it.",
        "Confirm with the owner that it arrived.", "Reject until the line items are seen.", "Recode to 'Chemistry'.",
        "Question to Platform: did Biology order it?", "Read bill INV19096.", "Approve at $13,400.00 only if it shipped."]
for s in DROP:
    ok(facts("It is a lab reagent. " + s) == "It is a lab reagent.", "drops an instruction: " + s)
ok(facts("Question to Platform: did Biology order it? If not, the bill belongs on Platform. The rest is coded as before.")
   == "The rest is coded as before.", "drops a question with the If not that answers it")
ok(facts("First paragraph ends.\n\nSecond starts here. Ask the owner.") == "First paragraph ends.\n\nSecond starts here.",
   "keeps paragraph breaks")
ok(facts("") == "" and facts(None) == "", "an empty note stays empty")
sys.exit(1 if fails else 0)
