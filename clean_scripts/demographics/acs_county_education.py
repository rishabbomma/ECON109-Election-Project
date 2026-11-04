import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'raw/demographics/acs5'

# ACS B15002: bachelor's or higher = male 015-018 + female 032-035, over adults 25+
BA = [f'B15002_{i:03d}E' for i in list(range(15, 19)) + list(range(32, 36))]
out = None
for period, col in [('2006-2010', 'ba_share_2010'), ('2020-2024', 'ba_share_2024')]:
    d = pd.read_csv(RAW / f'acs5_{period}_B15002_ohio_counties.csv')
    d['county_fips'] = d.GEO_ID.str[-5:].astype(int)
    d['county_name'] = d.NAME.str.replace(' County, Ohio', '')
    d[col] = d[BA].sum(axis=1) / d.B15002_001E
    d = d[['county_fips', 'county_name', col]]
    out = d if out is None else out.merge(d[['county_fips', col]], on='county_fips')

out = out.sort_values('county_fips')
out.to_csv(ROOT / 'clean/demographics/ohio_county_education.csv', index=False)
print(out.describe())
