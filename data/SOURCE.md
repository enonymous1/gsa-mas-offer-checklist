# Source workbook provenance

## File

`New-Offer-Checklist_June2025_Industry_1_0.xlsx` — the GSA Multiple Award
Schedule (MAS) New Offer Checklist workbook, June 2025. A public GSA
checklist; the workbook itself contains no contractor data, no credentials,
and no personal data beyond the file metadata noted below.

## What was scrubbed, and why

The copy shipped here was re-saved with the workbook's author metadata
cleared (`creator` and `lastModifiedBy` removed). The original file's
core properties named its GSA author and the last modifier; neither name
belongs in a published artifact. Every cell value was verified identical
after re-saving (78,258 cells compared, 0 mismatches).

- Original core properties: created 2025-06-06, last modified 2025-07-07.
- Shipped copy SHA-256:
  `c782419ee85d4c42e6b06c7aa166c789f84b94e0331ac178a863436edea0626a`
  (recompute with `sha256sum data/source/*.xlsx`; `tools/build_data.py`
  records the hash in `site/checklist.json`'s metadata on every run).
- 13 sheets, 106 numbered requirements: Offer Review Checklist (46),
  Office Management (5), Facilities (4), Furniture (6), Human Capital (0),
  Industrial Products (4), IT (27), Miscellaneous (1), Professional
  Services (6), Scientific (0), Security (0), Transportation (6),
  Travel (1).

## Currency warning

This workbook is dated June 2025 and cites SCP-FSS-001 from MAS Refresh 16
(July 2023). GSA has since issued further MAS refreshes. Do not treat this
workbook as the current solicitation. When a newer checklist is available,
replace this file, re-run `tools/build_data.py`, and update the
provision-text excerpts and the `sourceDate`/`solicitation` labels — the
generator and tests will fail loudly if the new workbook's layout or
item count differs.

## What is NOT shipped

The original prototype also bundled `SCP-FSS-001.pdf` (17 pages, Refresh 16).
It is not shipped here: the app links to the same document on gsa.gov
instead, so a stale local copy cannot be mistaken for a current one. The
provision-text excerpts in `site/provision_texts.json` are labeled as
Refresh 16 excerpts for the same reason.
