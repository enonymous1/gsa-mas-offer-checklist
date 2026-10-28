#!/usr/bin/env python3
"""Generate site/checklist.json from the source GSA checklist workbook.

The workbook at data/source/New-Offer-Checklist_June2025_Industry_1_0.xlsx
is the single source of truth. This script is the only place that knows the
workbook's layout, and it fails loudly instead of silently dropping items:

- every numbered row in every sheet must land in the output;
- line numbers within a section must be consecutive, and a section must
  either restart at 1 or continue the previous section's numbering;
- (group, section, line) keys must be unique;
- every item must have requirement text, and every item except the two
  that have no reference in the source workbook (the 8(a) question,
  line 4, and "Pricing Terms", line 30) must have a reference.

Usage:
    python3 tools/build_data.py [--xlsx PATH] [--out PATH]

Run from the repository root. No third-party dependencies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from xlsx_reader import read_workbook

# Sheets with no section-header row in the workbook. The friendly section
# names below match the names the original reference page used for them.
DEFAULT_SECTIONS = {
    "Category E-Industrial Products": "Industrial Products",
    "Category F-IT": "Information Technology",
    "Category K-Transportation": "Transportation",
    "Category L-Travel": "Travel",
}

# Group titles shown in the app, in workbook order. The three "(None)"
# categories have no items in the source; they are kept as empty groups so
# the app shows the full category set instead of silently omitting them.
GROUP_TITLES = {
    "Offer Review Checklist": "Offer Review Checklist",
    "Category A-Office Mgmt": "Office Management",
    "Category B-Facilities": "Facilities",
    "Category C-Furniture": "Furniture and Furnishings",
    "Category D-Human Capital (None)": "Human Capital",
    "Category E-Industrial Products": "Industrial Products",
    "Category F-IT": "Information Technology",
    "Category G-MISC": "Miscellaneous",
    "Category H-Prof Services": "Professional Services",
    "Category I-Scientific (None)": "Scientific",
    "Category J-Security (None)": "Security",
    "Category K-Transportation": "Transportation",
    "Category L-Travel": "Travel",
}

# Rows that are footer notes on the main sheet, not sections or items.
FOOTER_NOTES = {
    "For Category Specific Requirements see associated tabs",
    "SUMMARY:",
}


def _clean(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()


def _slug(text):
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in text)
    slug = "-".join(part for part in slug.split("-") if part)
    return slug or "group"


def parse_workbook(path):
    sheets = read_workbook(path)
    groups = []
    seen_keys = set()
    total = 0
    for sheet in sheets:
        title = sheet["title"]
        if title not in GROUP_TITLES:
            raise ValueError(f"Unexpected sheet title: {title!r}")
        rows = sheet["rows"]
        header_idx = None
        headers = {}
        for i, row in enumerate(rows):
            for j, cell in enumerate(row):
                if cell == "LINE Number":
                    header_idx = i
                    headers = {str(c).strip(): j for j, c in enumerate(row) if c}
                    break
            if header_idx is not None:
                break
        if header_idx is None:
            raise ValueError(f"No 'LINE Number' header row in sheet {title!r}")

        line_col = headers["LINE Number"]
        doc_col = headers["Required Documentation"]
        ref_col = headers.get(
            "Solicitation Reference", headers.get("Category Attachment Reference")
        )
        comments_col = headers.get("Additional Comments/Instructions")
        subcategory_col = headers.get("Subcategory")
        sin_col = headers.get("SIN")

        sections = []
        current = None
        if title in DEFAULT_SECTIONS:
            current = {"title": DEFAULT_SECTIONS[title], "items": []}
            sections.append(current)

        for row in rows[header_idx + 1 :]:
            line_value = row[line_col] if line_col < len(row) else None
            first = row[0] if row else None
            if isinstance(line_value, int) and not isinstance(line_value, bool):
                if current is None:
                    raise ValueError(
                        f"Numbered row before any section header in {title!r}: {row!r}"
                    )
                doc = _clean(row[doc_col]) if doc_col < len(row) else ""
                ref = _clean(row[ref_col]) if ref_col is not None and ref_col < len(row) else ""
                comments = (
                    _clean(row[comments_col])
                    if comments_col is not None and comments_col < len(row)
                    else ""
                )
                subcategory = (
                    _clean(row[subcategory_col])
                    if subcategory_col is not None and subcategory_col < len(row)
                    else ""
                )
                sin = (
                    _clean(row[sin_col])
                    if sin_col is not None and sin_col < len(row)
                    else ""
                )
                if not doc:
                    raise ValueError(f"Empty requirement text in {title!r} line {line_value}")
                key = (title, current["title"], line_value)
                if key in seen_keys:
                    raise ValueError(f"Duplicate checklist key: {key}")
                seen_keys.add(key)
                current["items"].append(
                    {
                        "line": line_value,
                        "doc": doc,
                        "ref": ref,
                        "comments": comments,
                        "subcategory": subcategory,
                        "sin": sin,
                    }
                )
                total += 1
            elif isinstance(first, str) and first.strip() and all(
                c in (None, "") for c in row[1:]
            ):
                label = first.strip()
                if label in FOOTER_NOTES:
                    current = None
                    continue
                current = {"title": label, "items": []}
                sections.append(current)
            elif any(c not in (None, "") for c in row):
                raise ValueError(f"Unparsed content row in {title!r}: {row!r}")

        # Line numbers within each section must be consecutive. A section
        # either restarts at 1 (category sheets) or continues the previous
        # section's numbering (the main checklist, numbered 1-46 overall).
        previous_last = 0
        for section in sections:
            lines = [item["line"] for item in section["items"]]
            if lines and lines != list(range(lines[0], lines[0] + len(lines))):
                raise ValueError(
                    f"Non-consecutive lines in {title!r} / {section['title']!r}: {lines}"
                )
            if lines and lines[0] not in (1, previous_last + 1):
                raise ValueError(
                    f"Unexpected first line in {title!r} / {section['title']!r}: {lines[0]}"
                )
            if lines:
                previous_last = lines[-1]
            # The two items allowed to have no reference in the source:
            # the 8(a) question (line 4) and "Pricing Terms" (line 30).
            for item in section["items"]:
                if not item["ref"] and not (
                    title == "Offer Review Checklist" and item["line"] in (4, 30)
                ):
                    raise ValueError(f"Missing reference in {title!r} line {item['line']}")

        groups.append(
            {
                "id": _slug(GROUP_TITLES[title]),
                "title": GROUP_TITLES[title],
                "sourceSheet": title,
                "sections": sections,
            }
        )
    return groups, total


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate site/checklist.json.")
    parser.add_argument("--xlsx", default=None, help="Source workbook path.")
    parser.add_argument("--out", default=None, help="Output JSON path.")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parent.parent
    xlsx_path = Path(args.xlsx) if args.xlsx else (
        root / "data" / "source" / "New-Offer-Checklist_June2025_Industry_1_0.xlsx"
    )
    out_path = Path(args.out) if args.out else root / "site" / "checklist.json"

    groups, total = parse_workbook(xlsx_path)
    if total != 106:
        raise ValueError(f"Expected 106 checklist items, got {total}")

    payload = {
        "meta": {
            "title": "GSA Multiple Award Schedule (MAS) New Offer Checklist",
            "sourceFile": xlsx_path.name,
            "sourceDate": "June 2025",
            "sourceSha256": hashlib.sha256(xlsx_path.read_bytes()).hexdigest(),
            "solicitation": "SCP-FSS-001, MAS Refresh 16 (July 2023)",
            "generatedBy": "tools/build_data.py",
            "itemCount": total,
            "warning": (
                "Checklist content is from the June 2025 source workbook. "
                "Verify every requirement against the current GSA MAS "
                "solicitation before submitting an offer; later refreshes "
                "may have changed requirements."
            ),
        },
        "groups": groups,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {out_path} ({total} items, {len(groups)} groups)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
