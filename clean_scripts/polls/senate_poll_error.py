import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

d = pd.read_csv(ROOT / 'raw/polls/fivethirtyeight/senate_polls_historical_wayback_20250305.csv', low_memory=False)
d = d[d.cycle.isin([2022, 2024]) & (d.stage == 'general')].copy()
codes = pd.read_csv(ROOT / 'raw/election_results/senate_statewide/medsl_1976-2024-president.csv',
                    encoding='latin-1')[['state', 'state_po']].drop_duplicates()
d['state_po'] = d.state.str.upper().map(dict(zip(codes.state.str.upper(), codes.state_po)))

# special = seat class differs from that year's regular class
d['special'] = d.seat_name != d.cycle.map({2022: 'Class III', 2024: 'Class I'})
# CA: regular and special with the same candidates; keep the regular (more polls)
ca = d[d.state_po == 'CA'].groupby(['cycle', 'race_id']).poll_id.nunique().reset_index()
ca_keep = ca.sort_values('poll_id').groupby('cycle').tail(1).race_id
d = d[(d.state_po != 'CA') | d.race_id.isin(ca_keep)]

# races with a D and an R as the top two in the polls
top2 = (d.groupby(['race_id', 'party', 'candidate_name']).pct.mean().reset_index()
        .sort_values('pct', ascending=False).groupby('race_id').head(2))
dr = top2.groupby('race_id').party.apply(lambda p: sorted(p) == ['DEM', 'REP'])
top2 = top2[top2.race_id.isin(dr[dr].index)]
d = d.merge(top2[['race_id', 'candidate_name']], on=['race_id', 'candidate_name'])

# same filters as the Ohio polls: LV, nonpartisan, not hypothetical, final 21 days
d['days_out'] = (pd.to_datetime(d.election_date, format='%m/%d/%y') - pd.to_datetime(d.end_date, format='%m/%d/%y')).dt.days
d = d[(d.population == 'lv') & d.partisan.isna() & ~d.hypothetical.astype(bool) & d.days_out.between(0, 21)]

# two party margin per question, averaged within each poll
q = d.pivot_table(index=['cycle', 'state_po', 'special', 'poll_id', 'question_id', 'sample_size'],
                  columns='party', values='pct', aggfunc='sum').dropna().reset_index()
q['margin_2p'] = (2 * q.DEM / (q.DEM + q.REP) - 1) * 100
p = q.groupby(['cycle', 'state_po', 'special', 'poll_id'], as_index=False).agg(margin_2p=('margin_2p', 'mean'),
                                                                             n=('sample_size', 'max'))
p['mn'] = p.margin_2p * p.n
race = p.groupby(['cycle', 'state_po', 'special'], as_index=False).agg(
    n_polls=('poll_id', 'size'), poll_avg=('margin_2p', 'mean'), mn=('mn', 'sum'), n=('n', 'sum'))
race['poll_avg_n'] = race.mn / race.n
race = race.drop(columns=['mn', 'n']).rename(columns={'cycle': 'year'})

# actual results; CT 2022 not in MEDSL, so dropped
res = pd.read_csv(ROOT / 'clean/election_results/senate_races.csv')[['year', 'state_po', 'special', 'dem2p_sen']]
race = race.merge(res, on=['year', 'state_po', 'special'])
# drop races with an appointed senator on the ballot (CA 2022, NE 2024 special)
app = pd.read_csv(ROOT / 'clean/incumbency/appointed_senators.csv')[['year', 'state_po', 'special']]
race = race.merge(app, how='left', indicator=True)
race = race[race._merge == 'left_only'].drop(columns='_merge')

race['actual'] = (2 * race.dem2p_sen - 1) * 100
race['error'] = race.actual - race.poll_avg
race['error_n'] = race.actual - race.poll_avg_n
race = race.drop(columns='dem2p_sen').sort_values(['year', 'state_po'])
race.to_csv(ROOT / 'clean/polls/senate_poll_error.csv', index=False)
print(race.groupby('year').error.agg(['count', 'mean', 'std']))
