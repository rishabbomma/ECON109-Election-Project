import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'clean/campaign_finance'

r = pd.read_csv(OUT / 'finance_reports_clean_v2.csv')
# net contributions = contributions - refunds; net operating = operating - offsets
assert np.allclose(r.net_contributions_period, r.total_contributions_period - r.total_contribution_refunds_period)
assert np.allclose(r.net_operating_expenditures_period,
                   r.operating_expenditures_period - r.offsets_to_operating_expenditures_period)

# Q3 2026 report of each committee (Jul 1 - Sep 30)
snap = r[r.coverage_end_date <= '2026-09-30'].sort_values('coverage_end_date').groupby('committee_id').tail(1)
assert (snap.coverage_start_date == '2026-07-01').all() and (snap.coverage_end_date == '2026-09-30').all()
snap.to_csv(OUT / 'finance_snapshot_20260930_v2.csv', index=False)
print(snap[['candidate_name', 'committee_id', 'total_receipts_period', 'cash_on_hand_end_period']])
