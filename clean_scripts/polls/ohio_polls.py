import re
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

raw = pd.read_csv(ROOT / 'raw/polls/ohio_senate_polls2025.csv', encoding='utf-8-sig')
raw.columns = ['field_dates', 'pollster', 'affiliation', 'n', 'voter_type',
               'influence', 'brown', 'husted', 'displayed_margin', 'url']


def dates(s):
    # "Oct 15–19" or "Sep 29–Oct 9"; Dec poll is 2025, the rest 2026
    a, b = re.split(r'[–-]', s.strip())
    m1, d1 = a.split()
    m2, d2 = b.split() if ' ' in b.strip() else (m1, b)
    yr = lambda m: 2025 if m == 'Dec' else 2026
    return pd.Series([pd.Timestamp(f'{m1} {d1} {yr(m1)}'), pd.Timestamp(f'{m2} {d2} {yr(m2)}')])


raw[['start', 'end']] = raw.field_dates.apply(dates)
raw['affiliation'] = raw.affiliation.fillna('')       # '' = nonpartisan sponsor
raw['margin'] = raw.brown - raw.husted
# two party share and margin; undecideds dropped
raw['dem2p'] = raw.brown / (raw.brown + raw.husted)
raw['margin_2p'] = (2 * raw.dem2p - 1) * 100
# sampling SE of the two party margin
n2 = raw.n * (raw.brown + raw.husted) / 100
raw['se_2p'] = 2 * np.sqrt(raw.dem2p * (1 - raw.dem2p) / n2) * 100

# displayed margin vs toplines: off by 1 in three polls (rounding)
raw['displayed_margin'] = raw.displayed_margin.str.replace('D+', '').str.replace('R+', '-').astype(int)
assert (raw.displayed_margin - raw.margin).abs().le(1).all()

out = raw[['start', 'end', 'pollster', 'affiliation', 'voter_type', 'n', 'influence', 'brown', 'husted',
           'margin', 'displayed_margin', 'dem2p', 'margin_2p', 'se_2p', 'url']].sort_values('end')
out.to_csv(ROOT / 'clean/polls/ohio_senate_polls.csv', index=False)
print(out.shape)
