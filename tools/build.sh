#!/bin/bash
# Build one close month in the repo, the way a Claude Project runs it.
#
#   bash tools/build.sh [period slug]          (default aug2026; or: make build PERIOD=aug2026)
#
# Packages both Projects (tools/package.py), then runs each Project's commands from its
# packaged folder, out/dist/<project>/, on the exports in inputs/<period>/: the engine,
# the views, and build_pages.py. Writes out/<period>/<project>/run.json and the month's
# console, and copies it to consoles/serif-<project>.html. Commit and tag a new version.
set -e
B="$(cd "$(dirname "$0")/.." && pwd)"
SLUG="${1:-aug2026}"
PERIOD="$(python3 -c "import sys; s=sys.argv[1]; print(s[:3].title()+' '+s[3:])" "$SLUG")"
I="$B/inputs/$SLUG"
[ -d "$I" ] || { echo "No exports in inputs/$SLUG/"; exit 1; }
python3 "$B/tools/package.py"

GL=$(ls "$I"/netsuite_gl_detail_*.xls*)
CO=$(ls "$I"/coupa_po_lines_*.csv)
FC=$(ls "$I"/serif_rolling_forecast_*.xlsx | head -1)
RO=$(ls "$I"/ukg_full_roster_*.csv)
IDS=(); for f in "$I"/netsuite_link_ids_*.csv; do [ -e "$f" ] && IDS+=(--netsuite-ids "$f"); done
BS=(); for f in "$I"/netsuite_balance_sheet_*.xls; do [ -e "$f" ] && BS+=(--balance-sheet "$f"); done
IS=(); for f in "$I"/netsuite_income_statement_by_month_*.xls; do [ -e "$f" ] && IS+=(--income-statement "$f"); done

for J in gl-coding-review pl-flux; do
  O="$B/out/$SLUG/$J"; mkdir -p "$O"
  cd "$B/out/dist/$J"
  # First, as the Projects do: the ledger tied to the Income Statement by account. A failed tie stops here.
  if [ ${#IS[@]} -gt 0 ]; then python3 serif_sources.py tie --period "$PERIOD" --gl "$GL" "${IS[@]}" $([ "$J" = pl-flux ] && echo --prior); fi
  if [ "$J" = gl-coding-review ]; then
    python3 serif_uc1_engine.py --period "$PERIOD" --gl "$GL" --coupa "$CO" --pending . --out "$O/engine" >/dev/null
  else
    python3 serif_uc2_flux.py --period "$PERIOD" --gl "$GL" --coupa "$CO" --forecast "$FC" --plan "$FC" \
      --plan-vintage 2026-06 --pending . --out "$O/engine" >/dev/null
  fi
  mv "$O/engine/$SLUG/run.json" "$O/run.json"; rm -rf "$O/engine"
  if [ "$J" = gl-coding-review ]; then
    python3 serif_views.py "$O/run.json" --gl "$GL" --plan "$FC" --plan-vintage 2026-06 --coupa "$CO" \
      --roster "$RO" "${IDS[@]}" --keep-names | tail -1
    python3 build_pages.py --only coding --coding-run "$O/run.json" --gl "$GL" "${IS[@]}" --out "$O"
  else
    python3 serif_views.py "$O/run.json" --gl "$GL" --plan "$FC" --plan-vintage 2026-06 --coupa "$CO" \
      --roster "$RO" "${IDS[@]}" "${BS[@]}" --keep-names | tail -1
    python3 build_pages.py --only flux --flux-run "$O/run.json" --gl "$GL" "${IS[@]}" --out "$O"
  fi
  V=$(python3 -c "import re,sys; print(re.search(r'^VERSION = \"(.+)\"', open(sys.argv[1]).read(), re.M).group(1))" build_pages.py)
  cp "$O/serif-$J-$SLUG-v$V.html" "$B/consoles/serif-$J.html"
done
