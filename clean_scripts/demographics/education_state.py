import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

edu = pd.read_csv(ROOT / 'raw/demographics/ers_education_1970_2023.csv', encoding='latin-1')
# state rows (FIPS ending in 000), bachelor's or higher, 2019-23
e = edu[(edu.Attribute == "Percent of adults with a bachelor's degree or higher, 2019-23")
        & (edu['FIPS Code'] % 1000 == 0) & (edu.State != 'US')]
out = pd.DataFrame({'state_po': e.State, 'coll_share_2019_23': e.Value / 100}).sort_values('state_po')
out.to_csv(ROOT / 'clean/demographics/state_college_share.csv', index=False)
print(out.shape)
