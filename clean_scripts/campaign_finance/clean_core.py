# Author: Jingyang
"""Shared current financial-cleaning functions; preserve raw and source issues.

Run with Python 3. No third-party packages or network connection are needed.
Supports the local course layout, the group's campaign_finance
subfolders in raw/, clean/ and clean_scripts/, or the older flat group layout.
This is AI-assisted working code; student understanding/run evidence is separate.
"""
# code developed with assistance from ChatGPT
import csv
import hashlib
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

# code developed with assistance from ChatGPT
ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "02-data/raw/campaign-finance"
OUT = ROOT / "02-data/processed/campaign-finance"
AS_OF = "2026-10-18"
SNAPSHOT = "2026-09-30"
MANIFEST_NAME = "manifest_campaign_finance.json"
if not (RAW / MANIFEST_NAME).is_file():
    for ROOT in (Path(__file__).resolve().parent.parent,
                 Path(__file__).resolve().parent.parent.parent):
        RAW = ROOT / "raw" / "campaign_finance"
        OUT = ROOT / "clean" / "campaign_finance"
        if (RAW / MANIFEST_NAME).is_file():
            break
        RAW, OUT = ROOT / "raw", ROOT / "clean"
        if (RAW / MANIFEST_NAME).is_file():
            break
    else:
        raise FileNotFoundError("Source manifest not found in course, grouped or flat group layout")
MANIFEST = json.loads((RAW / MANIFEST_NAME).read_text(encoding="utf-8"))
MAP = {committee: candidate for candidate in MANIFEST["candidate_committee_mapping"]
       for committee in candidate["authorized_committees"]}
ISSUES = []


# code developed with assistance from ChatGPT
def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


# code developed with assistance from ChatGPT
def source_path(filename):
    if (RAW / filename).is_file():
        return RAW / filename
    item = next(item for item in MANIFEST["files"] if item["local_filename"] == filename)
    return RAW / item["drive_filename"]


# code developed with assistance from ChatGPT
def read_source(filename):
    with source_path(filename).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for number, row in enumerate(rows, start=2):
        row.update(source_file=filename, source_row=str(number))
    return rows


# code developed with assistance from ChatGPT
def money(value):
    return "" if value in (None, "") else format(Decimal(value).quantize(Decimal("0.01")), "f")


# code developed with assistance from ChatGPT
def iso(value):
    return "" if not value else datetime.fromisoformat(value).date().isoformat()


# code developed with assistance from ChatGPT
def number_id(value):
    return "" if not value else str(int(Decimal(value)))


# code developed with assistance from ChatGPT
def issue(row, code, detail, disposition="retained_with_flag"):
    ISSUES.append(dict(source_file=row["source_file"], source_row=row["source_row"],
                       record_id=row.get("sub_id") or row.get("file_number", ""),
                       issue_code=code, detail=detail, disposition=disposition))


# code developed with assistance from ChatGPT
def clean_finance():
    common = ["cash_on_hand_beginning_period", "cash_on_hand_end_period",
              "total_receipts_period", "total_disbursements_period", "total_contributions_period",
              "individual_itemized_contributions_period", "individual_unitemized_contributions_period",
              "total_individual_contributions_period", "political_party_committee_contributions_period",
              "other_political_committee_contributions_period", "debts_owed_by_committee", "debts_owed_to_committee"]
    form_specific = ["candidate_contribution_period", "total_loans_received_period", "all_loans_received_period",
                     "transfers_from_other_authorized_committee_period", "transfers_to_other_authorized_committee_period",
                     "transfers_from_affiliated_party_period", "transfers_to_affiliated_committee_period"]
    clean = []
    for form, filename in [("F3", "F3Reports_5Committees_2026_raw.csv"),
                           ("F3X", "F3XReports_HustedNominee_2026_raw.csv")]:
        for raw in read_source(filename):
            current = raw["most_recent"] == "t"
            assert current == (number_id(raw["file_number"]) == number_id(raw["most_recent_file_number"]))
            if not current:
                issue(raw, "superseded_report", "Replacement file " + number_id(raw["most_recent_file_number"]), "excluded_from_clean")
                continue
            candidate = MAP[raw["committee_id"]]
            row = dict(candidate_id=candidate["candidate_id"], candidate_name=candidate["candidate"],
                       committee_id=raw["committee_id"], committee_name=raw["committee_name"],
                       source_form=form, file_number=number_id(raw["file_number"]),
                       report_year=raw["report_year"], report_type=raw["report_type"], currency="USD",
                       coverage_start_date=iso(raw["coverage_start_date"]), coverage_end_date=iso(raw["coverage_end_date"]),
                       receipt_date=iso(raw["receipt_date"]), most_recent="true",
                       source_cumulative_basis="election_cycle_to_date" if form == "F3" else "calendar_year_to_date")
            row.update({field: money(raw.get(field, "")) for field in common + form_specific})
            row.update({"source_" + field: money(raw[field]) for field in
                        ["total_receipts_ytd", "total_disbursements_ytd", "total_contributions_ytd"]})
            row.update(source_file=raw["source_file"], source_row=raw["source_row"], quality_flags="")
            assert row["coverage_start_date"] <= row["coverage_end_date"] <= row["receipt_date"] <= AS_OF
            balance = (Decimal(row["cash_on_hand_beginning_period"]) + Decimal(row["total_receipts_period"])
                       - Decimal(row["total_disbursements_period"]) - Decimal(row["cash_on_hand_end_period"]))
            assert balance == 0, (row["file_number"], "Cash identity failed")
            clean.append(row)
    clean.sort(key=lambda row: (row["committee_id"], row["coverage_start_date"], row["file_number"]))
    assert len({row["file_number"] for row in clean}) == len(clean)
    for committee in MAP:
        reports = [row for row in clean if row["committee_id"] == committee]
        for previous, row in zip(reports, reports[1:]):
            assert row["coverage_start_date"] > previous["coverage_end_date"], "Overlapping current reports"
            adjacent = date.fromisoformat(row["coverage_start_date"]) == date.fromisoformat(previous["coverage_end_date"]) + timedelta(days=1)
            gap = Decimal(row["cash_on_hand_beginning_period"]) - Decimal(previous["cash_on_hand_end_period"])
            if adjacent and gap:
                row["quality_flags"] = "opening_cash_differs_from_previous_close"
                issue(row, "cash_continuity_gap", f"Previous file {previous['file_number']}; gap USD {gap}")
        if Decimal(reports[0]["cash_on_hand_beginning_period"]):
            issue(reports[0], "nonzero_initial_observed_cash", "Observed report history starts with an existing cash balance; period sum is not complete campaign history")
    snapshot = [max((row for row in clean if row["committee_id"] == committee and row["coverage_end_date"] <= SNAPSHOT),
                    key=lambda row: row["coverage_end_date"]) for committee in MAP]
    assert all(row["coverage_start_date"] == "2026-07-01" and row["coverage_end_date"] == SNAPSHOT for row in snapshot)
    return clean, snapshot


