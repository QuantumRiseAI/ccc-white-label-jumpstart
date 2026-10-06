# Updated UI: How to Run

## Set Up the Project

Create a Claude Project and upload every file in this folder. Add
[`PROJECT_INSTRUCTIONS.md`](PROJECT_INSTRUCTIONS.md) as the Project's instructions.

## Each Month

1. Start a new chat in the Project, named for the close, such as "September close".
2. Attach the month's exports:
   * the NetSuite GL saved search (`.xls`);
   * the NetSuite Balance Sheet report (`.xls`);
   * the NetSuite Income Statement by month report (`.xls`);
   * the Coupa PO lines (`.csv`);
   * the two rolling forecast workbooks (`.xlsx`);
   * the UKG roster (`.csv`);
   * the NetSuite link IDs (`.csv`).
3. Ask: `Run the close review for Sep 2026.`
4. Claude runs the engines, the views and `build_pages.py`, and gives you the two consoles:
   * `serif-gl-coding-review-<period>-updated-ui-v1.html`;
   * `serif-pl-flux-<period>-updated-ui-v1.html`.

## Working the Consoles

* **Navigation:** click a section title (Review, Analysis, Close Workflow) to open its pages in
  the bar.
* **Flags and adjustments:** each shows its Journal Entry, filled in. Approve it, reject it, or
  edit it, which marks it Modified. Modify and Recode need a note.
* **Vendor history:** each card shows the vendor's last three months by account and department,
  with the line descriptions.
* **Flux lines:** a line at or over the threshold is marked Review. Write commentary on it.
* **Threshold:** set it in Settings, top right.
* **Close checklist:** each Overview shows what is open on each page.
* **NetSuite import:**
  * GL Coding Review: Documentation > Export downloads the approved recodes.
  * P&L Flux: Close Workflow > Adjustments downloads the approved entries.

  Entries go in as edited. One that is out of balance, unchanged or missing its note is left out.

  Import the file into NetSuite yourself.
* **Saving:** decisions, commentary and sign-off are kept in your browser.

## Running It Locally

From a folder holding these files and the exports, the commands are in
[`PROJECT_INSTRUCTIONS.md`](PROJECT_INSTRUCTIONS.md), under Run It. Python 3.9 or newer, nothing
else. In the repo, `updated-ui/build_runs.sh` and `updated-ui/build_pages.py` do the same for a
month whose exports are in `<jumpstart>/monthly-inputs/<period>/`.
