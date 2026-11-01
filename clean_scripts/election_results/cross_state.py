# Author: Rishab
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw"
SW = RAW / "election_results" / "senate_statewide"
OUT = ROOT / "clean" / "election_results"

PRES_PARTY = {2004: 'R', 2006: 'R', 2008: 'R', 2010: 'D', 2012: 'D', 2014: 'D',
              2016: 'D', 2018: 'R', 2020: 'R', 2022: 'D', 2024: 'D', 2026: 'R'}

sen_all = pd.read_csv(SW / 'medsl_1976-2024-senate-state.csv', encoding='latin-1')
sen_all = sen_all[(sen_all.stage.str.upper() == 'GEN') & (~sen_all.writein)]
# Tally lines masquerading as candidates: Wyoming, Alaska and Washington all
# carry these as ordinary rows and they would otherwise be treated as people.
sen_all = sen_all[~sen_all.candidate.astype(str).str.upper()
                  .str.contains('VOTES|SCATTER', na=False)]
sen_all = sen_all[sen_all.candidate.astype(str).str.upper() != 'OTHER']

# Party: NEITHER MEDSL field is reliable on its own. party_simplified calls
# Duckworth (IL 2022) and Van Hollen (MD 2022) 'OTHER'; party_detailed is NaN
# for MS and NV 2024 and reads 'GOP' in WA 2024. Take a candidate as major-party
# if EITHER field says so. Independents stay 'O' -- Sanders, King, Lieberman,
# Murkowski, McMullin and Osborn are not Democrats and must not be scored as one.
_det = sen_all.party_detailed.astype(str).str.upper()
_sim = sen_all.party_simplified.astype(str).str.upper()
sen_all['party'] = np.where(_sim.eq('DEMOCRAT') | _det.str.startswith('DEMOCRAT'), 'D',
                   np.where(_sim.eq('REPUBLICAN') | _det.str.startswith('REPUBLICAN'), 'R', 'O'))

# sen_all keeps every year, because incumbency needs to look back six years
# from the earliest race in the panel. sen is the analysis window.
sen = sen_all[sen_all.year >= 2004]

# One row per candidate per race, summing their ballot lines first. New York,
# Connecticut and South Carolina run fusion tickets, so a candidate appears on
# two to four party lines; Schumer in 2016 is spread over four. Taking the top
# line instead of the candidate total understated him by 8% and his opponent by
# 14%, moving some two-party shares by up to 3.8 points.
def _party_of(lines):            # a fusion candidate is major-party if any line is
    s = set(lines)
    return 'D' if 'D' in s else ('R' if 'R' in s else 'O')


cand = (sen.groupby(['year', 'state_po', 'special', 'candidate'], as_index=False)
           .agg(votes=('candidatevotes', 'sum'), party=('party', _party_of)))

# Top D and top R per race rather than the sum, so Louisiana jungle primaries and
# California top-two races (which can field two candidates of one party) don't
# get added together into a fake combined share.
top = (cand[cand.party.isin(['D', 'R'])]
       .groupby(['year', 'state_po', 'special', 'party'], as_index=False).votes.max())
races = top.pivot_table(index=['year', 'state_po', 'special'],
                        columns='party', values='votes').reset_index()
races = races.dropna(subset=['D', 'R'])

# A two-party share is undefined when neither major party won the seat. Lieberman
# (CT 2006) and King (ME 2012, 2018, 2024) each won as independents, and the D
# and R candidates between them drew under half the vote, so the surviving
# 'two-party' numbers were 0.81, 0.30, 0.23 and 0.24 -- artefacts, not results.
winner_party = (cand.loc[cand.groupby(['year', 'state_po', 'special']).votes.idxmax()]
                [['year', 'state_po', 'special', 'party']]
                .rename(columns={'party': 'winner_party'}))
races = races.merge(winner_party, on=['year', 'state_po', 'special'], how='left')
dropped = races[~races.winner_party.isin(['D', 'R'])]
if len(dropped):
    print('dropped (won by neither major party):',
          dropped[['year', 'state_po']].to_dict('records'))
races = races[races.winner_party.isin(['D', 'R'])].drop(columns='winner_party')

races['dem2p_sen'] = races['D'] / (races['D'] + races['R'])
races['votes_sen'] = races['D'] + races['R']

pres = pd.read_csv(SW / 'medsl_1976-2024-president.csv', encoding='latin-1')
pres = pres[pres.party_simplified.isin(['DEMOCRAT', 'REPUBLICAN'])]
pres = (pres.groupby(['year', 'state_po', 'party_simplified'], as_index=False)
            .candidatevotes.sum()
            .pivot_table(index=['year', 'state_po'], columns='party_simplified',
                         values='candidatevotes').reset_index())
pres['dem2p_pres'] = pres['DEMOCRAT'] / (pres['DEMOCRAT'] + pres['REPUBLICAN'])
pres = pres[['year', 'state_po', 'dem2p_pres']].rename(columns={'year': 'pres_year'})

# Most recent presidential election strictly BEFORE each Senate race, so the
# baseline is always something known in advance. For 2026 that is 2024.
pyears = np.sort(pres.pres_year.unique())
races['pres_year'] = races.year.map(lambda y: pyears[pyears < y].max())
races = races.merge(pres, on=['pres_year', 'state_po'], how='left', validate='many_to_one')

# penalty = +1 in a midterm under a Democratic president, -1 under a Republican one,
# 0 in presidential years. A negative coefficient means the president's party loses ground.
races['midterm'] = (races.year % 4 == 2).astype(int)
races['pres_party'] = races.year.map(PRES_PARTY)
races['penalty'] = races.midterm * np.where(races.pres_party == 'D', 1, -1)

# Normalised to mean 1. Raw vote counts as weights give nonsense prediction
# intervals, because WLS scales prediction variance by 1/weight and a new row
# defaults to weight 1. Coefficients are identical either way.
races['w'] = races.votes_sen / races.votes_sen.mean()

# ---------------------------------------------------------------- incumbency
# Senate seats run on a six-year cycle, so the same seat was last contested in
# y-6. If the winner of that race is on the ballot again in year y, an elected
# incumbent is running. Match on surname: MEDSL is inconsistent about first
# names ("CHARLES E. GRASSLEY" one cycle, "CHUCK GRASSLEY" the next), and
# full-string matching wrongly flags about a third of races as open.

def surname(s):
    s = str(s).upper().replace('.', '').replace(',', '')
    parts = ''.join(ch for ch in s if ch.isalpha() or ch == ' ').split()
    while len(parts) > 1 and parts[-1] in {'JR', 'SR', 'II', 'III', 'IV'}:
        parts = parts[:-1]
    return parts[-1] if parts else ''


sen_all['sn'] = sen_all.candidate.map(surname)
sen = sen_all[sen_all.year >= 2004]

# Candidate-level over the FULL history, because the six-year lookback from 2004
# reaches back to 1998. Winners are taken over every candidate, independents
# included: an independent incumbent such as King or Sanders really is the
# sitting senator, and crediting the seat to the top major-party finisher
# instead would mislabel the next cycle.
cand_all = (sen_all.groupby(['year', 'state_po', 'special', 'candidate'], as_index=False)
                   .agg(votes=('candidatevotes', 'sum'), sn=('sn', 'first'),
                        party=('party', _party_of)))

winners = cand_all.loc[cand_all.groupby(['year', 'state_po', 'special']).votes.idxmax(),
                       ['year', 'state_po', 'special', 'sn', 'party']]
winners = (winners[~winners.special]
           .rename(columns={'sn': 'prev_sn', 'party': 'prev_party'})
           [['year', 'state_po', 'prev_sn', 'prev_party']])
winners['year'] = winners.year + 6          # winner of y-6 is the incumbent in y

ballot = sen.groupby(['year', 'state_po', 'special']).sn.apply(set).rename('ballot').reset_index()
races = races.merge(ballot, on=['year', 'state_po', 'special'], how='left')
races = races.merge(winners, on=['year', 'state_po'], how='left',
                    validate='many_to_one')

running = [isinstance(b, set) and isinstance(w, str) and w in b
           for b, w in zip(races.ballot, races.prev_sn)]
races['inc_derived'] = np.where(~np.array(running), 'open',
                                np.where(races.prev_party == 'D',
                                         'dem_elected', 'rep_elected'))

# The y-6 rule breaks in three cases. Two involve appointments: a special
# election itself, and the next regular election for a seat that had a special
# in between (the y-6 winner is no longer the sitting senator). The third is an
# independent incumbent seeking re-election, who is neither dem_elected nor
# rep_elected and would otherwise be silently filed as a Republican. Flag all.
indep_inc = np.array(running) & races.prev_party.eq('O').values
sp = races.loc[races.special, ['year', 'state_po']]
races['review_flag'] = [
    'indep_incumbent' if ii else
    ('special' if x.special else
     ('after_special' if ((sp.state_po == x.state_po) & (sp.year > x.year - 6)
                          & (sp.year < x.year)).any() else ''))
    for ii, (_, x) in zip(indep_inc, races.iterrows())]

races = races[['year', 'state_po', 'special', 'dem2p_sen', 'votes_sen', 'w',
               'pres_year', 'dem2p_pres', 'midterm', 'pres_party', 'penalty',
               'inc_derived', 'review_flag']]

assert races.dem2p_pres.notna().all()
# A genuine D-vs-R Senate race does not land outside this band. Values beyond it
# mean the two-party share was computed from candidates who did not actually
# contest the seat, which is how CT 2006 (0.81) and ME 2012/18/24 (0.23-0.30)
# used to slip through.
_odd = races.loc[~races.dem2p_sen.between(0.15, 0.85), ['year', 'state_po', 'dem2p_sen']]
assert _odd.empty, f'implausible two-party shares:\n{_odd}'
print('races', len(races), '| years', races.year.min(), '-', races.year.max())
print('inc_derived:', races.inc_derived.value_counts().to_dict())

# ------------------------------------------------- manual override, 33 rows
# FILL THIS IN. First run writes a blank template of the flagged races; later
# runs read it back and let inc_manual win over inc_derived.
MANUAL = OUT / 'senate_incumbency_manual.csv'

if MANUAL.exists():
    man = pd.read_csv(MANUAL)[['year', 'state_po', 'special', 'inc_manual']]
    races = races.merge(man, on=['year', 'state_po', 'special'], how='left')
    races['inc_status'] = races.inc_manual.fillna('').replace('', np.nan).fillna(races.inc_derived)
    print('manual rows filled:', int(races.inc_manual.notna().sum()), 'of', len(man))
else:
    blank = races.loc[races.review_flag != '',
                      ['year', 'state_po', 'special', 'review_flag', 'inc_derived']].copy()
    blank['inc_manual'] = ''          # <-- fill this column
    blank.sort_values(['year', 'state_po']).to_csv(MANUAL, index=False)
    races['inc_status'] = races.inc_derived
    print('wrote blank template:', MANUAL, f'({len(blank)} rows to fill)')

races.to_csv(OUT / 'senate_races.csv', index=False)
