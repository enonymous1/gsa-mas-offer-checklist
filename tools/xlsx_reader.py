"""Minimal read-only XLSX reader using only the Python standard library.

An .xlsx file is a zip of XML parts. This reader resolves shared strings,
workbook sheet order, and per-sheet cell values so tools/build_data.py and
the test suite can parse the source checklist without a third-party
dependency (and without an unpinned one).

Only the cell features the source workbook uses are supported: shared
strings, inline strings, numbers, and booleans. Formulas are not evaluated;
a cached string value (t="str") is returned as-is.
"""

from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_PR = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def _text(element):
    if element is None:
        return ""
    return "".join(t.text or "" for t in element.iter(NS_MAIN + "t"))


def read_workbook(path):
    """Return a list of sheets: {"title": str, "rows": [[value, ...], ...]}.

    Values are str, int, float, bool, or None. Rows are padded to the widest
    row in their sheet so column indexing by header name is safe.
    """
    path = Path(path)
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        shared_strings = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall(NS_MAIN + "si"):
                shared_strings.append(_text(si))

        wb_root = ET.fromstring(zf.read("xl/workbook.xml"))
        rels_root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rel_map = {
            rel.get("Id"): rel.get("Target") for rel in rels_root.findall(NS_PR + "Relationship")
        }

        sheets = []
        for sheet in wb_root.findall(".//" + NS_MAIN + "sheet"):
            title = sheet.get("name")
            rid = sheet.get(NS_REL + "id")
            target = rel_map[rid].lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            sheet_root = ET.fromstring(zf.read(target))
            rows = []
            for row_el in sheet_root.findall(".//" + NS_MAIN + "row"):
                cells = {}
                max_col = 0
                for c in row_el.findall(NS_MAIN + "c"):
                    ref = c.get("r", "")
                    col = _column_index(re.sub(r"\d+", "", ref))
                    max_col = max(max_col, col)
                    cells[col] = _cell_value(c, shared_strings)
                row = [cells.get(i) for i in range(1, max_col + 1)]
                rows.append(row)
            width = max((len(r) for r in rows), default=0)
            rows = [r + [None] * (width - len(r)) for r in rows]
            sheets.append({"title": title, "rows": rows})
    return sheets


def _column_index(letters):
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch.upper()) - ord("A") + 1)
    return index


def _cell_value(cell, shared_strings):
    cell_type = cell.get("t")
    value_el = cell.find(NS_MAIN + "v")
    if cell_type == "s":
        if value_el is None or value_el.text is None:
            return ""
        return shared_strings[int(value_el.text)]
    if cell_type == "inlineStr":
        return _text(cell.find(NS_MAIN + "is"))
    if cell_type == "b":
        return value_el is not None and value_el.text == "1"
    if cell_type in ("str", "e"):
        return value_el.text if value_el is not None else ""
    if value_el is None or value_el.text is None:
        return None
    text = value_el.text
    try:
        number = float(text)
    except ValueError:
        return text
    if number.is_integer():
        return int(number)
    return number
