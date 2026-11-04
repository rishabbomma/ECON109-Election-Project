import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SW = ROOT / 'raw/election_results/senate_statewide'
OUT = ROOT / 'clean/election_results'

# sitting president's party in each election year
PRES_PARTY = {2000: 'D', 2002: 'R', 2004: 'R', 2006: 'R', 2008: 'R', 2010: 'D', 2012: 'D', 2014: 'D',
              2016: 'D', 2018: 'R', 2020: 'R', 2022: 'D', 2024: 'D', 2026: 'R'}
START = 2000

sen_all = pd.read_csv(SW / 'medsl_1976-2024-senate-state.csv', encoding='latin-1')
sen_all = sen_all[(sen_all.stage.str.upper() == 'GEN') & ~sen_all.writein]
# tally rows (WY, AK, WA), not candidates
name = sen_all.candidate.astype(str).str.upper()
sen_all = sen_all[~name.str.contains('VOTES|SCATTER', na=False) & (name != 'OTHER')]

# party: D or R if either MEDSL party field says so (each is wrong for a few 2022/2024 races)
det = sen_all.party_detailed.astype(str).str.upper()
sim = sen_all.party_simplified.astype(str).str.upper()
sen_all['party'] = np.where(sim.eq('DEMOCRAT') | det.str.startswith('DEMOCRAT'), 'D',
                   np.where(sim.eq('REPUBLICAN') | det.str.startswith('REPUBLICAN'), 'R', 'O'))


def party_of(lines):
    # fusion candidates (NY, CT, SC) appear on several party lines
    return 'D' if 'D' in set(lines) else ('R' if 'R' in set(lines) else 'O')


def surname(s):
    parts = ''.join(ch for ch in str(s).upper() if ch.isalpha() or ch == ' ').split()
    while len(parts) > 1 and parts[-1] in {'JR', 'SR', 'II', 'III', 'IV'}:
        parts = parts[:-1]
    return parts[-1] if parts else ''


sen_all['sn'] = sen_all.candidate.map(surname)
sen = sen_all[sen_all.year >= START]
key = ['year', 'state_po', 'special']

# one row per candidate, votes summed over ballot lines
cand = sen.groupby(key + ['candidate'], as_index=False).agg(votes=('candidatevotes', 'sum'),
                                                            party=('party', party_of))
# top D and top R per race (LA and CA can field two of one party)
top = cand[cand.party.isin(['D', 'R'])].groupby(key + ['party'], as_index=False).votes.max()
races = top.pivot_table(index=key, columns='party', values='votes').reset_index().dropna(subset=['D', 'R'])

# drop races won by neither party (CT 2006, ME 2012/18/24)
winner = cand.loc[cand.groupby(key).votes.idxmax(), key + ['party']].rename(columns={'party': 'winner_party'})
races = races.merge(winner, on=key)
print('dropped:', races.loc[~races.winner_party.isin(['D', 'R']), ['year', 'state_po']].values.tolist())
races = races[races.winner_party.isin(['D', 'R'])]

races['dem2p_sen'] = races.D / (races.D + races.R)
races['votes_sen'] = races.D + races.R

# presidential share at the last presidential election before t
pres = pd.read_csv(SW / 'medsl_1976-2024-president.csv', encoding='latin-1')
pres = pres[pres.party_simplified.isin(['DEMOCRAT', 'REPUBLICAN'])]
pres = pres.pivot_table(index=['year', 'state_po'], columns='party_simplified',
                        values='candidatevotes', aggfunc='sum').reset_index()
pres['dem2p_pres'] = pres.DEMOCRAT / (pres.DEMOCRAT + pres.REPUBLICAN)
pres = pres[['year', 'state_po', 'dem2p_pres']].rename(columns={'year': 'pres_year'})
pyears = np.sort(pres.pres_year.unique())
races['pres_year'] = races.year.map(lambda y: pyears[pyears < y].max())
races = races.merge(pres, on=['pres_year', 'state_po'], how='left')

# midterm penalty: +1 D president, -1 R president, 0 presidential years
races['midterm'] = (races.year % 4 == 2).astype(int)
races['pres_party'] = races.year.map(PRES_PARTY)
races['penalty'] = races.midterm * np.where(races.pres_party == 'D', 1, -1)
races['w'] = races.votes_sen / races.votes_sen.mean()

# incumbency: winner of the same seat at t-6 back on the ballot at t (surname match)
cand_all = sen_all.groupby(key + ['candidate'], as_index=False).agg(
    votes=('candidatevotes', 'sum'), sn=('sn', 'first'), party=('party', party_of))
prev = cand_all.loc[cand_all.groupby(key).votes.idxmax()]
prev = prev[~prev.special][['year', 'state_po', 'sn', 'party']].rename(columns={'sn': 'prev_sn', 'party': 'prev_party'})
prev['year'] = prev.year + 6
ballot = sen.groupby(key).sn.apply(set).rename('ballot').reset_index()
races = races.merge(ballot, on=key, how='left').merge(prev, on=['year', 'state_po'], how='left')
running = np.array([isinstance(w, str) and w in b for b, w in zip(races.ballot, races.prev_sn)])
races['inc_status'] = np.where(~running | (races.prev_party == 'O'), 'open',
                               np.where(races.prev_party == 'D', 'dem_elected', 'rep_elected'))

races = races[key + ['dem2p_sen', 'votes_sen', 'w', 'pres_year', 'dem2p_pres', 'midterm', 'pres_party',
                     'penalty', 'inc_status']]
# shares outside 0.15-0.85 only in AK 2002 (Stevens 78%)
odd = races[~races.dem2p_sen.between(0.15, 0.85) & ~((races.year == 2002) & (races.state_po == 'AK'))]
assert odd.empty and races.dem2p_pres.notna().all()

# incumbency for races in or after a special election
fix = pd.read_csv(OUT / 'incumbency_specials.csv').rename(columns={'inc_status': 'inc_fix'})
races = races.merge(fix, on=key, how='left')
races['inc_status'] = races.inc_fix.fillna(races.inc_status)
races = races.drop(columns='inc_fix')
races.to_csv(OUT / 'senate_races.csv', index=False)
print(len(races), 'races')
