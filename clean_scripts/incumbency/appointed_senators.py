import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

t = pd.read_csv(ROOT / 'raw/incumbency/appointed_senators_wikipedia.csv')
# state name -> postal code, from MEDSL
codes = pd.read_csv(ROOT / 'raw/election_results/senate_statewide/medsl_1976-2024-president.csv',
                    encoding='latin-1')[['state', 'state_po']].drop_duplicates()
codes = dict(zip(codes.state.str.upper(), codes.state_po))

# appointees who reached the November ballot
t = t[t.next_election.str.match(r'^(Elected|Defeated) in the ', na=False)].copy()
m = t.next_election.str.extract(r'^(Elected|Defeated) in the (\d{4})(?:[–-]\d{2})? ?(special)?')
t['won'] = m[0] == 'Elected'
t['year'] = m[1].astype(int)
t['special'] = m[2].notna()
t['state_po'] = t.state.str.replace(r'\s*\(Class \d\)', '', regex=True).str.upper().map(codes)
t['party'] = t.name.str.extract(r'\((\w)[^)]*\)$')[0]
t['name'] = t.name.str.replace(r'\s*\(.*\)$', '', regex=True)
out = t[t.year.between(2000, 2024)][['year', 'state_po', 'special', 'party', 'name', 'won']].sort_values(['year', 'state_po'])

# in the Senate sample? (MS 2008 special is not)
races = pd.read_csv(ROOT / 'clean/election_results/senate_races.csv')
out = out.merge(races[['year', 'state_po', 'special']], how='left', indicator=True)
out['in_senate_races'] = out._merge == 'both'
out = out.drop(columns='_merge')
out.to_csv(ROOT / 'clean/incumbency/appointed_senators.csv', index=False)
print(out)
