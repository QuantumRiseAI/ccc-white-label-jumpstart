"""Compare two run.json files from the same engine and inputs, field by field.

    python3 tools/compare_runs.py project/run.json local/run.json

Two fields differ by design and are left out: when the run was made
(`generated_at`) and where the input files sat (`source_dir`). Claude's drafts
are not in run.json, so they are not compared. Everything else must match:
findings, amounts, Journal Entries, schedules and the run id. Exits 1 on any
difference and lists the first ones.
"""

import json
import sys

IGNORED = {"generated_at", "source_dir"}


def differences(a, b, path=""):
    if type(a) is not type(b):
        return [path or "(root)"]
    if isinstance(a, dict):
        out = []
        for key in sorted(set(a) | set(b)):
            if key in IGNORED:
                continue
            if key not in a or key not in b:
                out.append(path + "." + key)
            else:
                out += differences(a[key], b[key], path + "." + key)
        return out
    if isinstance(a, list):
        if len(a) != len(b):
            return ["%s (%d items vs %d)" % (path, len(a), len(b))]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += differences(x, y, "%s[%d]" % (path, i))
        return out
    return [] if a == b else [path]


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    runs = [json.load(open(p, encoding="utf-8")) for p in argv[1:]]
    for p, r in zip(argv[1:], runs):
        m = r.get("manifest", {})
        print("%s: run %s, engine %s, %d findings, $%s" % (
            p, m.get("run_id"), m.get("engine_version"), len(r.get("findings", [])),
            format(round(sum(f.get("amount_at_risk") or 0 for f in r.get("findings", [])), 2), ",.2f")))
    found = differences(*runs)
    if found:
        print("%d differences:" % len(found))
        for d in found[:20]:
            print("  " + d)
        sys.exit(1)
    print("Identical, apart from generated_at and source_dir.")


if __name__ == "__main__":
    main(sys.argv)
