#!/bin/bash
# The shared scripts are edited in pl-flux/upload-to-project. Copy them to the coding Project folder,
# then rerun the views step and the standard console for both jumpstarts on Aug 2026.
#   bash tools/rebuild_views.sh
B="$(cd "$(dirname "$0")/.." && pwd)"
set -e
for f in serif_sources.py serif_views.py build_report.py serif_uc2_flux.py; do
  for i in 1 2 3 4 5 6; do cp "$B/pl-flux/upload-to-project/$f" "$B/gl-coding-review/upload-to-project/$f" 2>/dev/null && break; sleep 2; done
  cmp -s "$B/pl-flux/upload-to-project/$f" "$B/gl-coding-review/upload-to-project/$f" || { echo "COPY FAILED $f"; exit 1; }
done
GL=netsuite_gl_detail_jan2025-aug2026.xls; CO=coupa_po_lines_2026.csv; FC=serif_rolling_forecast_2026-08.xlsx; RO=ukg_full_roster_hrbp_2026-09-24.csv
for d in gl-coding-review pl-flux; do
  cd "$B/$d"; I=monthly-inputs/aug2026; U=upload-to-project
  python3 $U/serif_views.py out/aug2026/run.json --gl $I/$GL --plan $I/$FC --plan-vintage 2026-06 --coupa $I/$CO --roster $I/$RO --netsuite-ids $I/netsuite_link_ids_aug2026.csv | tail -6
  python3 $U/build_report.py out/aug2026/run.json | tail -3
done
