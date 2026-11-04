import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'raw/campaign_finance'

# authorized committees of each candidate (FEC)
COMMITTEES = {'C00916288': 'Sherrod Brown', 'C00896019': 'Jon Husted', 'C00895276': 'Jon Husted',
              'C00918839': 'Gregory Lee Levy', 'C00937300': 'William Redpath'}
COLS = ['candidate_name', 'committee_id', 'committee_name', 'source_form', 'file_number', 'report_year',
        'report_type', 'coverage_start_date', 'coverage_end_date', 'receipt_date',
        'cash_on_hand_beginning_period', 'cash_on_hand_end_period', 'total_receipts_period',
        'total_disbursements_period', 'total_contributions_period', 'total_contribution_refunds_period',
        'net_contributions_period', 'operating_expenditures_period', 'offsets_to_operating_expenditures_period',
        'net_operating_expenditures_period', 'debts_owed_by_committee']

f3 = pd.read_csv(RAW / 'F3Reports_5Committees_2026_raw.csv').assign(source_form='F3')
f3x = pd.read_csv(RAW / 'F3XReports_HustedNominee_2026_raw.csv').assign(source_form='F3X')
f3x['operating_expenditures_period'] = f3x.total_fed_operating_expenditures_period   # F3X federal line
r = pd.concat([f3, f3x], ignore_index=True)

# drop amended (superseded) reports
r = r[r.most_recent == 't'].copy()
r['candidate_name'] = r.committee_id.map(COMMITTEES)
for c in ['coverage_start_date', 'coverage_end_date', 'receipt_date']:
    r[c] = pd.to_datetime(r[c]).dt.strftime('%Y-%m-%d')
r = r[COLS].sort_values(['committee_id', 'coverage_start_date', 'file_number'])

# cash identity: start + receipts - disbursements = end
gap = r.cash_on_hand_beginning_period + r.total_receipts_period - r.total_disbursements_period - r.cash_on_hand_end_period
assert np.allclose(gap, 0, atol=0.005) and r.candidate_name.notna().all()
r.to_csv(ROOT / 'clean/campaign_finance/finance_reports_clean_v2.csv', index=False)
print(len(r), 'current reports')
