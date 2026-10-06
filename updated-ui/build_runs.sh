#!/bin/bash
# The runs the updated-UI consoles read, for one close month, both jumpstarts.
#
#   bash updated-ui/build_runs.sh [period slug]
#   python3 updated-ui/build_pages.py [period slug]
#
# Runs each engine on the month's exports and adds the views with names kept
# (--keep-names) and, for the flux, the NetSuite balance sheet (--balance-sheet).
# The runs are written to updated-ui/runs/<period>/<jumpstart>/run.json.
# The standard consoles and their runs are not touched.
set -e
B="$(cd "$(dirname "$0")/.." && pwd)"
SLUG="${1:-aug2026}"
PERIOD="$(python3 -c "import sys; s=sys.argv[1]; print(s[:3].title()+' '+s[3:])" "$SLUG")"
U=upload-to-project

# The shared scripts are edited in pl-flux; the coding Project carries the same files.
for f in serif_sources.py serif_views.py build_report.py serif_uc2_flux.py; do
  cmp -s "$B/pl-flux/$U/$f" "$B/gl-coding-review/$U/$f" || cp "$B/pl-flux/$U/$f" "$B/gl-coding-review/$U/$f"
done
# The updated-UI Project folder carries them too, with the coding engine and build_pages.py.
P="$B/updated-ui/upload-to-project"
for f in serif_sources.py serif_views.py build_report.py serif_uc2_flux.py serif_fonts.py; do
  cmp -s "$B/pl-flux/$U/$f" "$P/$f" || cp "$B/pl-flux/$U/$f" "$P/$f"
done
cmp -s "$B/gl-coding-review/$U/serif_uc1_engine.py" "$P/serif_uc1_engine.py" || cp "$B/gl-coding-review/$U/serif_uc1_engine.py" "$P/"
cmp -s "$B/updated-ui/build_pages.py" "$P/build_pages.py" || cp "$B/updated-ui/build_pages.py" "$P/"

for J in gl-coding-review pl-flux; do
  I="$B/$J/monthly-inputs/$SLUG"
  GL=$(ls "$I"/netsuite_gl_detail_*.xls)
  CO=$(ls "$I"/coupa_po_lines_*.csv)
  FC=$(ls "$I"/serif_rolling_forecast_*.xlsx | head -1)
  RO=$(ls "$I"/ukg_full_roster_*.csv)
  EXTRA=()
  for f in "$I"/netsuite_link_ids_*.csv; do [ -e "$f" ] && EXTRA+=(--netsuite-ids "$f"); done
  RUN="$B/updated-ui/runs/$SLUG/$J"
  mkdir -p "$RUN"
  cd "$B/$J"
  if [ "$J" = gl-coding-review ]; then
    python3 $U/serif_uc1_engine.py --period "$PERIOD" --gl "$GL" --coupa "$CO" --pending $U --out "$RUN/engine" >/dev/null
  else
    python3 $U/serif_uc2_flux.py --period "$PERIOD" --gl "$GL" --coupa "$CO" --forecast "$FC" --plan "$FC" \
      --plan-vintage 2026-06 --pending $U --out "$RUN/engine" >/dev/null
  fi
  cp "$RUN/engine/$SLUG/run.json" "$RUN/run.json"; rm -rf "$RUN/engine"
  if [ "$J" = pl-flux ]; then
    for f in "$I"/netsuite_balance_sheet_*.xls; do [ -e "$f" ] && EXTRA+=(--balance-sheet "$f"); done
  fi
  python3 $U/serif_views.py "$RUN/run.json" --gl "$GL" --plan "$FC" --plan-vintage 2026-06 --coupa "$CO" \
    --roster "$RO" "${EXTRA[@]}" --keep-names | tail -1
done
