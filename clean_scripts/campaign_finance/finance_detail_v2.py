# Author: Jingyang
"""Add financial detail to current reports without changing raw or v1 outputs.

Keep this file beside clean_core.py and run with Python 3.
Supports the course layout and grouped or older flat group folders.
Only financial v2 files are written; existing IE files and source flags remain.
"""
# code developed with assistance from ChatGPT
import csv
import importlib.util
import json
from decimal import Decimal
from pathlib import Path


# code developed with assistance from ChatGPT
BASE_PATH = Path(__file__).with_name("clean_core.py")
BASE_SHA256 = "B9C2612751D06FD6060309C9E3C611362F6DD5CBEEACE656AE3CDCF52F382D68"
spec = importlib.util.spec_from_file_location("campaign_finance_v1", BASE_PATH)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
assert base.digest(BASE_PATH) == BASE_SHA256, "Unexpected base cleaning code"


# code developed with assistance from ChatGPT
FIELDS = ["net_contributions_period", "total_contribution_refunds_period",
          "refunded_individual_contributions_period",
          "refunded_other_political_committee_contributions_period",
          "refunded_political_party_committee_contributions_period",
          "net_operating_expenditures_period", "offsets_to_operating_expenditures_period",
          "loans_made_by_candidate_period", "all_other_loans_period",
          "loan_repayments_candidate_loans_period", "loan_repayments_other_loans_period",
          "other_receipts_period", "other_disbursements_period"]
CHECKS = {"net_contributions": 0, "net_operating_expenditures": 0,
          "F3_receipts_breakdown": 0, "F3_disbursements_breakdown": 0}


# code developed with assistance from ChatGPT
def verify_sources():
    for item in base.MANIFEST["files"]:
        assert base.digest(base.source_path(item["local_filename"])) == item["sha256"], item["local_filename"]


# code developed with assistance from ChatGPT
def enrich(rows, source_rows):
    enriched = []
    for old in rows:
        row = dict(old)
        raw = source_rows[(row["source_file"], row["source_row"])]
        assert base.number_id(raw["file_number"]) == row["file_number"]
        assert raw["committee_id"] == row["committee_id"]
        for field in FIELDS:
            row[field] = base.money(raw.get(field, ""))
        is_f3 = row["source_form"] == "F3"
        operating_field = "operating_expenditures_period" if is_f3 else "total_fed_operating_expenditures_period"
        repayment_field = "total_loan_repayments_made_period" if is_f3 else "loan_repayments_made_period"
        row["operating_expenditures_period"] = base.money(raw[operating_field])
        row["operating_expenditures_basis"] = "F3_line17" if is_f3 else "F3X_federal_line36"
        row["source_total_operating_expenditures_period"] = base.money(raw["total_operating_expenditures_period"])
        row["total_loan_repayments_period"] = base.money(raw[repayment_field])
        row["net_amounts_source"] = "FEC_reported_checked_against_period_components"
        D = lambda field: Decimal(row[field])
        assert D("net_contributions_period") == D("total_contributions_period") - D("total_contribution_refunds_period")
        assert D("net_operating_expenditures_period") == D("operating_expenditures_period") - D("offsets_to_operating_expenditures_period")
        CHECKS["net_contributions"] += 1
        CHECKS["net_operating_expenditures"] += 1
        if is_f3:
            assert D("total_receipts_period") == sum(D(field) for field in (
                "total_contributions_period", "total_loans_received_period",
                "transfers_from_other_authorized_committee_period",
                "offsets_to_operating_expenditures_period", "other_receipts_period"))
            assert D("total_disbursements_period") == sum(D(field) for field in (
                "operating_expenditures_period", "transfers_to_other_authorized_committee_period",
                "total_loan_repayments_period", "total_contribution_refunds_period", "other_disbursements_period"))
            CHECKS["F3_receipts_breakdown"] += 1
            CHECKS["F3_disbursements_breakdown"] += 1
        assert all(row[field] == value for field, value in old.items()), "Existing field changed"
        enriched.append(row)
    return enriched


# code developed with assistance from ChatGPT
def save(name, rows):
    path = base.OUT / f"{name}_v2.csv"
    fields = list(dict.fromkeys(field for row in rows for field in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return {"filename": path.name, "rows": len(rows), "columns": len(fields), "sha256": base.digest(path)}


# code developed with assistance from ChatGPT
if __name__ == "__main__":
    verify_sources()
    previous_hashes = {path.name: base.digest(path) for path in base.OUT.glob("*_v1.*")}
    finance, snapshot = base.clean_finance()
    source_rows = {}
    for suffix in ["F3Reports_5Committees_2026_raw.csv", "F3XReports_HustedNominee_2026_raw.csv"]:
        for row in base.read_source(suffix):
            source_rows[(row["source_file"], row["source_row"])] = row
    finance_v2 = enrich(finance, source_rows)
    enriched_by_file = {row["file_number"]: row for row in finance_v2}
    snapshot_v2 = [enriched_by_file[row["file_number"]] for row in snapshot]
    base.OUT.mkdir(parents=True, exist_ok=True)
    outputs = [save("finance_reports_clean", finance_v2), save("finance_snapshot_20260930", snapshot_v2)]
    verify_sources()
    assert all(base.digest(base.OUT / name) == sha for name, sha in previous_hashes.items()), "v1 output changed"
    summary = {
        "version": "financial_detail_v2", "snapshot_date": base.SNAPSHOT,
        "sources_as_of": base.AS_OF, "base_code_sha256": BASE_SHA256,
        "raw_and_v1_unchanged": True, "outputs": outputs, "exact_decimal_checks": CHECKS,
        "definitions": {
            "net_contributions_period": "Period contributions less period contribution refunds; loans excluded; candidate contributions remain included.",
            "net_operating_expenditures_period": "F3 operating expenditures or F3X federal operating expenditures less period operating offsets.",
            "cash_on_hand_end_period": "Actual closing cash, unchanged; do not subtract period loans.",
            "missing_fields": "Unavailable form-specific fields stay blank, not zero."
        },
        "preserved_issues": base.ISSUES,
        "limitations": ["Net metrics do not replace total receipts/disbursements in the cash identity.",
                        "Operating expenditures include staff, administration and fundraising, not just advertising.",
                        "Contribution refunds may relate to contributions received in an earlier period.",
                        "Exploratory IE raw sources are retained; IE derived tables are not part of current output."]
    }
    summary_path = base.OUT / "finance_detail_summary_v2.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"outputs": outputs, "checks": CHECKS, "raw_and_v1_unchanged": True}, indent=2))
