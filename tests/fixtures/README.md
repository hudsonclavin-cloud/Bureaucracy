# Test fixtures

## `mts_table5_latest.json`

The Monthly Treasury Statement, Table 5 ("Outlays of the U.S. Government"),
for one `record_date`, exactly as the FiscalData API returned it.

- Fetched 2026-09-08 (UTC; the exact timestamp is in `fetched_at`) with the
  crawler's own calls, `fetch_latest_record_date` and
  `fetch_rows_for_record_date` in `data_pipeline/crawler/treasury_outlays.py`.
- `record_date` is the statement fetched (`2026-07-31` at the time of writing);
  `api_url` is the first page's request URL.
- `rows` is the verbatim `data` list from every page of that request: every
  field, every row, in `print_order_nbr` order, nothing renamed, filtered,
  parsed or rounded. Amounts are the API's strings; level-1 section headers
  carry the string `"null"`.
- It exists so the section-netting design (netting an agency's negative rows
  against its own positive rows instead of setting negatives aside globally)
  can be written and tested offline against the statement's real shape:
  level-2 `Total--` section rows, sub-unit `Total--` rows at deeper levels,
  headers with no amount, and the 150-odd negative lines.

This file is refreshed only by re-fetching from the API and never edited by
hand. Pretty-printed with `indent=1, sort_keys=True` so a refresh diffs
row by row.
