# GSA MAS New Offer Checklist

An interactive, single-page checklist of the submission requirements for a
GSA Multiple Award Schedule (MAS) new offer — all 106 numbered requirements
from the June 2025 GSA checklist workbook, in one place, with progress
tracking that stays in your browser.

> **Verify against the current solicitation before you rely on this list.**
> The content comes from the June 2025 workbook and SCP-FSS-001, MAS
> Refresh 16 (July 2023). Later GSA refreshes may have changed requirements.
> This project is not affiliated with GSA and is not legal advice.

## What it does

- **Complete data.** Every numbered requirement from all 13 workbook tabs:
  the 46-item Offer Review Checklist plus the category tabs (Office
  Management, Facilities, Furniture, Industrial Products, IT, Miscellaneous,
  Professional Services, Transportation, Travel). The three categories with
  no items in the source (Human Capital, Scientific, Security) are shown as
  empty rather than silently omitted.
- **Progress tracking.** Check items off; progress, per-item notes, and
  offer details are saved in `localStorage` under `gsa-offer-checklist.v1`.
  Nothing is sent anywhere — there is no backend.
- **Search and filter.** Full-text search across requirements, references,
  guidance, subcategories, and SINs; filter by category and by
  remaining / completed / noted.
- **Details view.** Each item opens a dialog with its reference, category
  details, the source checklist's guidance, your note, and — where the
  original project embedded one — the SCP-FSS-001 provision excerpt
  (Refresh 16).
- **Export and print.** Export your progress as JSON (re-importable),
  export the whole checklist with your status as CSV, or print it.
- **Accessible and offline-capable.** Native buttons, labels, dialog, and
  progressbar semantics; dark/light theme that respects your system
  setting. No CDN, no web fonts, no external requests at all — the only
  outbound links are the reference links you click (GSA, SAM.gov, FAR,
  NIST, Section 508).

## Run it

Any static file server works. The page loads `checklist.json` with
`fetch`, so opening `index.html` directly from disk (`file://`) will not
work in most browsers.

```powershell
# From the repository root (PowerShell):
python -m http.server 8000 --directory site
# Then open http://localhost:8000
```

```bash
# macOS / Linux:
python3 -m http.server 8000 --directory site
```

## Project layout

```
data/source/   Scrubbed source workbook (see data/SOURCE.md for provenance)
site/          The whole app: index.html, styles.css, app.js,
               checklist.json, provision_texts.json — deploy this folder
tools/         build_data.py: the ONLY place that reads the workbook.
               xlsx_reader.py: dependency-free XLSX reader (stdlib only)
tests/         unittest suite: data completeness, workbook parity,
               no-external-requests and no-innerHTML guards
```

## Regenerating the data

Checklist content is generated, never hand-edited in `site/`:

```bash
python3 tools/build_data.py
python3 -m unittest discover -s tests -v
```

`build_data.py` fails loudly if the workbook layout changes: it expects
exactly 106 items, consecutive line numbers within each section, unique
`(group, section, line)` keys, and a reference on every item except the
two that have none in the source (lines 4 and 30). To update to a newer
GSA checklist, replace the workbook in `data/source/`, re-run the
generator, update `sourceDate`/`solicitation` in `tools/build_data.py`
and the provision excerpts in `site/provision_texts.json`, and let the
tests catch any drift.

## Privacy

Offer details, checked items, and notes live only in your browser.
Clearing saved data (the button in the toolbar) removes the
`gsa-offer-checklist.v1` key. Exported JSON/CSV files contain whatever
you entered — treat them like any other offer working papers.

## History

This is a modernization of a February 2026 static prototype that kept two
divergent copies of the checklist: a full-featured reference page and a
distributable page that embedded only 12 of the 106 requirements, with no
tests, no license, and Tailwind/Google Fonts loaded from CDNs. The
modernized version merges them into one app, generates the complete
dataset from the workbook, drops all external dependencies, and adds
search, export, print, and accessibility support. The original
repository history was not carried over; see `data/SOURCE.md` for the
source workbook's provenance.

## License

MIT — see [LICENSE](LICENSE).
