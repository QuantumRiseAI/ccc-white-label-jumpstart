"""Amalgamate the repo's stdlib-only packages into one self-contained .py file.

Modules keep their own namespaces (the rules modules all define VERSION/RULES),
so this embeds each module's source and serves them through a sys.meta_path
finder rather than concatenating text.
"""
import pathlib, sys

REPO = pathlib.Path(sys.argv[1])
OUT = pathlib.Path(sys.argv[2])
PKGS = ["coding_engine", "coupa_extract", "gl_extract"]

sources = {}
for pkg in PKGS:
    root = REPO / "packages" / pkg
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(REPO / "packages")
        parts = list(rel.parts)
        if parts[-1] == "__init__.py":
            name = ".".join(parts[:-1])
            is_pkg = True
        elif parts[-1] == "__main__.py":
            continue  # CLI entry points are replaced by this file's own main
        else:
            parts[-1] = parts[-1][:-3]
            name = ".".join(parts)
            is_pkg = False
        sources[name] = (is_pkg, path.read_text(encoding="utf-8"))

header = '''#!/usr/bin/env python3
"""Serif UC1 — GL Coding Review engine, bundled as a single file.

Generated from the ccc-serif-jumpstarts repo. Do not edit by hand: change the
repo and re-bundle, or the two will drift.

Stdlib only. No network. No pip install. Runs anywhere Python 3.10+ runs,
including inside a Claude Project's code execution sandbox.

    python3 serif_uc1_engine.py --current <gl.csv> [--prior <gl.csv>]
                                [--prior-year <gl.csv>] [--coupa <coupa.csv>]
                                [--pending <dir>] --out <dir>

Writes <out>/<period>/run.json and prints a load summary. A failed debit/credit
tie-out halts the run: findings are not trustworthy until the ledger balances.
"""

import importlib.abc
import importlib.util
import sys
import types

__BUNDLED_SOURCES__ = {}


class _BundleLoader(importlib.abc.Loader):
    def create_module(self, spec):
        return None

    def exec_module(self, module):
        is_pkg, source = __BUNDLED_SOURCES__[module.__name__]
        if is_pkg:
            module.__path__ = []
        exec(compile(source, f"<bundled:{module.__name__}>", "exec"), module.__dict__)


class _BundleFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname not in __BUNDLED_SOURCES__:
            return None
        is_pkg, _ = __BUNDLED_SOURCES__[fullname]
        return importlib.util.spec_from_loader(
            fullname, _BundleLoader(), is_package=is_pkg
        )


sys.meta_path.insert(0, _BundleFinder())

'''

body = ["__BUNDLED_SOURCES__.update({"]
for name, (is_pkg, src) in sorted(sources.items()):
    body.append(f"    {name!r}: ({is_pkg}, {src!r}),")
body.append("})\n")

footer = '''

def main(argv=None):
    import argparse, json, os
    from coding_engine.runner import run, write_artifact

    parser = argparse.ArgumentParser(
        prog="serif_uc1_engine",
        description="Serif UC1 GL coding review — deterministic rules engine.",
    )
    parser.add_argument("--current", required=True, help="current period GL CSV")
    parser.add_argument("--prior", help="prior month GL CSV")
    parser.add_argument("--prior-year", dest="prior_year", help="prior year same month GL CSV")
    parser.add_argument("--coupa", help="Coupa PO line export CSV (raw)")
    parser.add_argument("--pending", help="directory of pending feed templates")
    parser.add_argument("--out", default="out", help="artifact output directory")
    parser.add_argument("--quiet", action="store_true", help="suppress the summary")
    args = parser.parse_args(argv)

    for label, path in (("--current", args.current), ("--prior", args.prior),
                        ("--prior-year", args.prior_year), ("--coupa", args.coupa)):
        if path and not os.path.exists(path):
            parser.error(f"{label} file not found: {path}\\n"
                         f"  Put the export in place and run again.")

    result = run(
        current_path=args.current,
        prior_path=args.prior,
        prior_year_path=args.prior_year,
        pending_dir=args.pending,
        coupa_path=args.coupa,
    )
    path = write_artifact(result, args.out)
    if not args.quiet:
        _summarize(result, path)
    return 0


def _summarize(result, path):
    m, s = result["manifest"], result["summary"]
    tie = m["tie_out"]
    bar = "-" * 72
    print(bar)
    print(f"SERIF UC1 GL CODING REVIEW - {m['period']}")
    print(f"Entity: {m['entity']}")
    print(bar)
    for item in m["inputs"]:
        print(f"  {item['path']:<44}{item['rows']:>8,} rows")
    print(f"\\nTIE-OUT  {'PASS' if tie['passed'] else 'FAIL'}   {tie['note']}")
    if not tie["passed"]:
        print("\\n  HALTED - findings are not trustworthy until the ledger balances.")
        return
    absent = [f["feed"] for f in m.get("absent_feeds", []) if f.get("in_uc1_scope")]
    if absent:
        print(f"\\nFEEDS ABSENT ({len(absent)}) - their tests are suppressed, not clean:")
        for feed in absent:
            print(f"    {feed}")
    print(f"\\nFINDINGS  {s['finding_count']}   "
          f"High {s.get('by_severity', {}).get('high', 0)} - "
          f"Medium {s.get('by_severity', {}).get('medium', 0)} - "
          f"Low {s.get('by_severity', {}).get('low', 0)}")
    print(f"AMOUNT AT RISK  ${s.get('amount_at_risk', 0):,.2f}")
    print(f"\\nWrote {path}")
    print("Next: python3 serif_views.py " + path + ", then build_pages.py")


if __name__ == "__main__":
    raise SystemExit(main())
'''

OUT.write_text(header + "\n".join(body) + footer, encoding="utf-8")
print(f"bundled {len(sources)} modules -> {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")
for n in sorted(sources):
    print("   ", n)
