# Copilot Instructions — GSA MAS New Offer Checklist

## What this is

A dependency-free static web app (`site/`) for the GSA Multiple Award
Schedule new-offer checklist. No build step, no backend, no CDN. Progress
is saved in the browser only (`localStorage` key `gsa-offer-checklist.v1`).

## Single source of truth

- Checklist content lives **only** in the source workbook
  `data/source/New-Offer-Checklist_June2025_Industry_1_0.xlsx`
  (scrubbed copy; provenance in `data/SOURCE.md`).
- `site/checklist.json` is **generated** by `tools/build_data.py` — never
  hand-edit it. Re-run the generator after any workbook change and commit
  the regenerated file.
- `site/provision_texts.json` holds the SCP-FSS-001 Refresh 16 excerpts
  transcribed from the original prototype. It is curated data, not
  generated; keep its `meta` note accurate if you update it.

## Rules for edits

- Never add a CDN, web font, or any other external request. The test suite
  asserts the site makes no unallowlisted requests. Reference links in
  content may point only at GSA, SAM.gov, acquisition.gov (FAR), NIST, and
  Section 508.
- Never insert checklist or user text with `innerHTML`. Build DOM nodes
  with `textContent` and use the `linkify()` helper in `site/app.js` for
  the allowlisted reference links.
- Keep the generator's invariants: 106 items, consecutive line numbers
  per section, unique `(group, section, line)` keys, a reference on every
  item except lines 4 and 30 of the main checklist. If a newer workbook
  changes any of this, update the generator and the tests together —
  do not weaken the assertions silently.
- Content is dated: the workbook is June 2025 / Refresh 16. Any content
  update must re-verify against the current GSA MAS solicitation and
  update the staleness warning in `site/index.html` and `README.md`.
  Do not present June 2025 content as current.

## How to run and check

```bash
python3 -m http.server 8000 --directory site   # file:// will not load checklist.json
python3 tools/build_data.py
python3 -m unittest discover -s tests -v
node --check site/app.js
```

## Deployment

GitHub Pages deploys the `site/` folder via `.github/workflows/pages.yml`.
CI (`.github/workflows/ci.yml`) runs the tests, the generator
reproducibility check, and `node --check`.
