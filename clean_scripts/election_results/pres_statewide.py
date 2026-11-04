import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

pres = pd.read_csv(ROOT / 'raw/election_results/senate_statewide/medsl_1976-2024-president.csv', encoding='latin-1')
pres = pres[pres.party_simplified.isin(['DEMOCRAT', 'REPUBLICAN'])]

# D and R presidential votes by state and year
st = pres.pivot_table(index=['year', 'state_po'], columns='party_simplified',
                      values='candidatevotes', aggfunc='sum').reset_index()
# national row, summed over states
us = st.groupby('year', as_index=False)[['DEMOCRAT', 'REPUBLICAN']].sum()
us['state_po'] = 'US'

out = pd.concat([st, us]).rename(columns={'DEMOCRAT': 'dem_pres', 'REPUBLICAN': 'rep_pres'})
out['dem2p_pres'] = out.dem_pres / (out.dem_pres + out.rep_pres)
out = out[['year', 'state_po', 'dem_pres', 'rep_pres', 'dem2p_pres']].sort_values(['year', 'state_po'])
out.to_csv(ROOT / 'clean/election_results/pres_statewide.csv', index=False)
print(out.shape)
