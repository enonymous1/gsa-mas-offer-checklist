"""Tests for gsa-mas-offer-checklist.

Run:  python3 -m unittest discover -s tests -v   (from the repo root)

Standard library only. The data tests exercise the production generator
code (tools/build_data.py + tools/xlsx_reader.py) rather than
reimplementing its parsing, so a passing suite means the shipped
checklist.json really is what the workbook contains.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from build_data import main as build_main, parse_workbook  # noqa: E402
from xlsx_reader import read_workbook  # noqa: E402

XLSX = ROOT / "data" / "source" / "New-Offer-Checklist_June2025_Industry_1_0.xlsx"
CHECKLIST = ROOT / "site" / "checklist.json"
PROVISIONS = ROOT / "site" / "provision_texts.json"

EXPECTED_SHEETS = 13
EXPECTED_ITEMS = 106
# (group id, section title) -> expected item count, from the source workbook.
EXPECTED_COUNTS = {
    ("offer-review-checklist", "Preliminary Review"): 5,
    ("offer-review-checklist", "Administrative Proposal"): 19,
    ("offer-review-checklist", "Technical Proposal"): 4,
    ("offer-review-checklist", "Price Proposal"): 9,
    ("offer-review-checklist", "Price Proposal - Services Only"): 9,
    ("office-management", "Office Management"): 5,
    ("facilities", "Facilities"): 4,
    ("furniture-and-furnishings", "Furniture and Furnishings"): 1,
    ("furniture-and-furnishings", "Specific Requirements for Packaged Furniture Program"): 5,
    ("industrial-products", "Industrial Products"): 4,
    ("information-technology", "Information Technology"): 27,
    ("miscellaneous", "Miscellaneous"): 1,
    ("professional-services", "Professional Services"): 6,
    ("transportation", "Transportation"): 6,
    ("travel", "Travel"): 1,
}


def load_checklist():
    return json.loads(CHECKLIST.read_text(encoding="utf-8"))


def all_items(payload):
    for group in payload["groups"]:
        for section in group["sections"]:
            for item in section["items"]:
                yield group, section, item


class TestGenerator(unittest.TestCase):
    def test_generator_reproduces_shipped_json_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "checklist.json"
            self.assertEqual(build_main(["--out", str(out)]), 0)
            self.assertEqual(
                out.read_bytes(),
                CHECKLIST.read_bytes(),
                "Regenerating checklist.json changed its bytes; commit the regenerated file.",
            )

    def test_parse_counts_match_expected(self):
        groups, total = parse_workbook(XLSX)
        self.assertEqual(total, EXPECTED_ITEMS)
        self.assertEqual(len(groups), EXPECTED_SHEETS)
        for group in groups:
            for section in group["sections"]:
                self.assertEqual(
                    len(section["items"]),
                    EXPECTED_COUNTS[(group["id"], section["title"])],
                    f"{group['id']} / {section['title']}",
                )

    def test_empty_categories_are_present_but_empty(self):
        groups, _ = parse_workbook(XLSX)
        by_id = {g["id"]: g for g in groups}
        for gid in ("human-capital", "scientific", "security"):
            self.assertIn(gid, by_id)
            self.assertEqual(by_id[gid]["sections"], [])

    def test_reader_sees_all_sheets_and_numbered_rows(self):
        sheets = read_workbook(XLSX)
        self.assertEqual(len(sheets), EXPECTED_SHEETS)
        numbered = 0
        for sheet in sheets:
            for row in sheet["rows"]:
                if len(row) > 1 and isinstance(row[1], int):
                    numbered += 1
        self.assertEqual(numbered, EXPECTED_ITEMS)


class TestChecklistJson(unittest.TestCase):
    def test_schema_and_uniqueness(self):
        payload = load_checklist()
        self.assertEqual(payload["meta"]["itemCount"], EXPECTED_ITEMS)
        self.assertEqual(
            payload["meta"]["sourceSha256"],
            hashlib.sha256(XLSX.read_bytes()).hexdigest(),
        )
        seen = set()
        for group, section, item in all_items(payload):
            self.assertEqual(set(item), {"line", "doc", "ref", "comments", "subcategory", "sin"})
            self.assertIsInstance(item["line"], int)
            for field in ("doc", "ref", "comments", "subcategory", "sin"):
                self.assertIsInstance(item[field], str)
                self.assertNotIn("\r", item[field])
                self.assertEqual(item[field], item[field].strip())
            self.assertTrue(item["doc"], "empty requirement text")
            key = (group["id"], section["title"], item["line"])
            self.assertNotIn(key, seen)
            seen.add(key)
        self.assertEqual(len(seen), EXPECTED_ITEMS)

    def test_line_numbers_consecutive_within_sections(self):
        payload = load_checklist()
        for group in payload["groups"]:
            previous_last = 0
            for section in group["sections"]:
                lines = [i["line"] for i in section["items"]]
                if lines:
                    self.assertEqual(lines, list(range(lines[0], lines[0] + len(lines))))
                    self.assertIn(lines[0], (1, previous_last + 1))
                    previous_last = lines[-1]

    def test_only_lines_4_and_30_lack_a_reference(self):
        payload = load_checklist()
        missing = [
            (g["title"], i["line"])
            for g, s, i in all_items(payload)
            if not i["ref"]
        ]
        self.assertEqual(missing, [("Offer Review Checklist", 4), ("Offer Review Checklist", 30)])

    def test_spot_checks_against_source(self):
        payload = load_checklist()
        by_key = {(g["id"], s["title"], i["line"]): i for g, s, i in all_items(payload)}
        line9 = by_key[("offer-review-checklist", "Administrative Proposal", 9)]
        self.assertIn("previously awarded a Schedule contract", line9["doc"])
        self.assertEqual(line9["ref"], "Provision SCP-FSS-001 (j) (1) (iv.)")
        line11 = by_key[("offer-review-checklist", "Administrative Proposal", 11)]
        self.assertEqual(line11["doc"], "Subcontracting Plan - (As Applicable)")
        it2 = by_key[("information-technology", "Information Technology", 2)]
        self.assertIn("Letter of Commitment/Supply", it2["doc"])
        self.assertEqual(it2["sin"], "Applicable to All")

    def test_no_fully_identical_items_within_a_section(self):
        # The source workbook itself repeats one requirement verbatim for
        # two SINs (IT lines 21/22: ICAM vs PKI). Items are therefore only
        # required to differ in their full (doc, ref, subcategory, sin)
        # tuple, never to be silently dropped as "duplicates".
        payload = load_checklist()
        for group in payload["groups"]:
            for section in group["sections"]:
                keys = [(i["doc"], i["ref"], i["subcategory"], i["sin"]) for i in section["items"]]
                self.assertEqual(len(keys), len(set(keys)), f"{group['id']} / {section['title']}")

    def test_it_lines_21_and_22_are_distinct_sins_with_same_text(self):
        payload = load_checklist()
        by_key = {(g["id"], s["title"], i["line"]): i for g, s, i in all_items(payload)}
        line21 = by_key[("information-technology", "Information Technology", 21)]
        line22 = by_key[("information-technology", "Information Technology", 22)]
        self.assertEqual(line21["doc"], line22["doc"])
        self.assertIn("ICAM", line21["sin"])
        self.assertIn("PKI", line22["sin"])


class TestProvisionTexts(unittest.TestCase):
    def test_keys_resolve_from_item_references(self):
        payload = load_checklist()
        provisions = json.loads(PROVISIONS.read_text(encoding="utf-8"))
        texts = provisions["texts"]
        self.assertEqual(len(texts), 23)

        def norm(s):
            return re.sub(r"\s+", "", s).rstrip(".")

        by_norm = {norm(k): k for k in texts}
        resolved = 0
        for _, _, item in all_items(payload):
            idx = item["ref"].find("SCP-FSS-001")
            if idx == -1:
                continue
            suffix = item["ref"][idx + len("SCP-FSS-001"):].strip()
            if norm(suffix) in by_norm:
                resolved += 1
        # The map covers the (c)/(d)/(e)/(i)/(j) excerpts the original
        # reference page embedded; at least the core Administrative and
        # Technical/Price items must resolve.
        self.assertGreaterEqual(resolved, 20, "provision-text coverage collapsed")

    def test_group_ids_unique(self):
        payload = load_checklist()
        ids = [g["id"] for g in payload["groups"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_provision_key_is_referenced(self):
        payload = load_checklist()
        provisions = json.loads(PROVISIONS.read_text(encoding="utf-8"))

        def norm(s):
            return re.sub(r"\s+", "", s).rstrip(".")

        suffixes = set()
        for _, _, item in all_items(payload):
            idx = item["ref"].find("SCP-FSS-001")
            if idx != -1:
                suffixes.add(norm(item["ref"][idx + len("SCP-FSS-001"):].strip()))
        for key in provisions["texts"]:
            self.assertIn(norm(key), suffixes, f"provision key never referenced: {key!r}")


class TestNoExternalRequests(unittest.TestCase):
    ALLOWED_PREFIXES = (
        "https://www.gsa.gov/",
        "https://eoffer.gsa.gov/",
        "https://sam.gov",
        "https://www.acquisition.gov/",
        "https://csrc.nist.gov/",
        "https://www.section508.gov/",
    )

    def test_site_files_make_no_unallowlisted_requests(self):
        url_pattern = re.compile(r"https?://[^\s\"'<>)]+")
        for path in (
            ROOT / "site" / "index.html",
            ROOT / "site" / "styles.css",
            ROOT / "site" / "app.js",
            ROOT / "site" / "checklist.json",
            ROOT / "site" / "provision_texts.json",
        ):
            text = path.read_text(encoding="utf-8")
            # Data URIs (the inline SVG favicon) are not requests: the
            # http://www.w3.org/2000/svg string inside one is an XML
            # namespace identifier, never fetched. Strip quoted data:
            # URIs first (they contain spaces and quotes of their own).
            text = re.sub(r'"data:[^"]*"', '""', text)
            for url in url_pattern.findall(text):
                url = url.rstrip(".,;")
                self.assertTrue(
                    url.startswith(self.ALLOWED_PREFIXES),
                    f"{path.name}: unallowlisted URL {url}",
                )

    def test_no_cdn_or_webfonts(self):
        for name in ("index.html", "styles.css", "app.js"):
            text = (ROOT / "site" / name).read_text(encoding="utf-8")
            for banned in ("cdn.tailwindcss", "fonts.googleapis", "fonts.gstatic", "unpkg.com", "cdn.jsdelivr"):
                self.assertNotIn(banned, text, name)

    def test_app_js_builds_dom_without_innerhtml_assignment(self):
        text = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
        self.assertNotIn(".innerHTML =", text)
        self.assertNotIn(".innerHTML=", text)
        self.assertIn("createElement", text)
        self.assertIn("textContent", text)


class TestScrubbedSource(unittest.TestCase):
    def test_author_metadata_removed(self):
        with zipfile.ZipFile(XLSX) as zf:
            core = zf.read("docProps/core.xml").decode("utf-8")
        self.assertNotIn("ShaunMKelly", core)
        self.assertNotIn("Justin Lyons", core)
        self.assertNotIn("justinplyons", core)
        with zipfile.ZipFile(XLSX) as zf:
            blob = b"".join(zf.read(name) for name in zf.namelist())
        self.assertNotIn(b"ShaunMKelly", blob)
        self.assertNotIn(b"justinplyons", blob)

    def test_source_hash_recorded_in_provenance(self):
        source_md = (ROOT / "data" / "SOURCE.md").read_text(encoding="utf-8")
        self.assertIn(hashlib.sha256(XLSX.read_bytes()).hexdigest(), source_md)


if __name__ == "__main__":
    unittest.main()
