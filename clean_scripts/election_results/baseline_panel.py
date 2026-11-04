import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / 'clean/election_results'

races = pd.read_csv(CLEAN / 'senate_races.csv')
P = pd.read_csv(CLEAN / 'pres_statewide.csv').pivot(index='year', columns='state_po', values='dem2p_pres')
LEAN = P.drop(columns='US').sub(P['US'], axis=0)      # state minus national

# incumbency: +1 D, -1 R, 0 open
INC = {'dem_elected': 1, 'dem_appointed': 1, 'rep_elected': -1, 'rep_appointed': -1, 'open': 0}
races['inc'] = races.inc_status.map(INC)

# Ohio 2026 row (Husted not counted as incumbent)
oh = pd.DataFrame([{'year': 2026, 'state_po': 'OH', 'special': True, 'pres_year': 2024, 'pres_party': 'R', 'inc': 0}])
df = pd.concat([races[['year', 'state_po', 'special', 'pres_year', 'pres_party', 'dem2p_sen', 'inc']], oh],
               ignore_index=True)

df['lean'] = [LEAN.at[y, s] for y, s in zip(df.pres_year, df.state_po)]
mid = df.year % 4 == 2
df['midD'] = (mid & (df.pres_party == 'D')).astype(int)
df['midR'] = (mid & (df.pres_party == 'R')).astype(int)

# rho(t): state's previous Senate race year in the panel
years = races.groupby('state_po').year.unique()
df['rho'] = [max([y for y in years[s] if y < t], default=np.nan) for s, t in zip(df.state_po, df.year)]

# lagged Senate share; regular + special averaged
S = races.groupby(['state_po', 'year']).dem2p_sen.mean()
# run-ahead of the presidential share, minus that year's median run-ahead
pi = np.where(races.year % 4 == 0, races.year, races.year - 2)
races['run'] = races.dem2p_sen - [P.at[y, s] for y, s in zip(pi, races.state_po)]
races['dev'] = races.run - races.groupby('year').run.transform('median')
DEV = races.groupby(['state_po', 'year']).dev.mean()

df['S_lag'] = [S.get((s, r), np.nan) for s, r in zip(df.state_po, df.rho)]
df['SL_run'] = [DEV.get((s, r), np.nan) for s, r in zip(df.state_po, df.rho)]
df['rho'] = df.rho.astype('Int64')

out = df[['year', 'state_po', 'special', 'dem2p_sen', 'pres_year', 'lean', 'midD', 'midR', 'rho', 'S_lag', 'inc', 'SL_run']]
out.to_csv(CLEAN / 'baseline_panel.csv', index=False)
print(out[out.year == 2026].T)
