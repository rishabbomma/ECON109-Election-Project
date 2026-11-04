import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'raw/election_results'
OHIO = RAW / 'ohio_county'
OUT = ROOT / 'clean/election_results'

# Ohio county presidential results, MEDSL
cp = pd.read_csv(RAW / 'county_president/countypres_2000-2024.tab', sep='\t', encoding='latin-1', low_memory=False)
cp = cp[(cp.state_po == 'OH') & cp.party.isin(['DEMOCRAT', 'REPUBLICAN'])].copy()
cp['county_fips'] = cp.county_fips.astype(int)

# county name -> fips, for files without fips
fips = cp[['county_name', 'county_fips']].drop_duplicates()
fips['key'] = fips.county_name.str.upper().str.replace(r'[^A-Z]', '', regex=True)
fips = fips[['key', 'county_fips']]


def shares(w, dem, rep, name):
    # two party Dem share and D+R votes
    out = pd.DataFrame(index=w.index)
    out[name] = w[dem] / (w[dem] + w[rep])
    out['votes_' + name.replace('dem2p_', '')] = w[dem] + w[rep]
    return out


def attach_fips(df, county):
    cols = list(df.columns)
    out = df.reset_index()
    out['key'] = out[county].str.upper().str.replace(r'[^A-Z]', '', regex=True)
    return out.merge(fips, on='key', validate='one_to_one')[['county_fips'] + cols]


def medsl_share(path, office, name, sep=','):
    # MEDSL precinct files, summed to counties
    d = pd.read_csv(path, sep=sep, encoding='latin-1', low_memory=False)
    d = d[(d.office == office) & ~d.writein & d.party_simplified.isin(['DEMOCRAT', 'REPUBLICAN'])]
    w = d.pivot_table(index='county_fips', columns='party_simplified', values='votes', aggfunc='sum')
    return shares(w, 'DEMOCRAT', 'REPUBLICAN', name).reset_index()


def name_share(path, dem, rep, name, office=None):
    # OpenElections / Ohio SoS long files
    d = pd.read_csv(path, encoding='latin-1', low_memory=False)
    if office:
        d = d[d.office == office]
    w = d.pivot_table(index='county', columns='party', values='votes', aggfunc='sum')
    return attach_fips(shares(w, dem, rep, name), 'county')


def wide_share(d, county, dcol, rcol, name):
    # one column per candidate
    w = d.groupby(county)[[dcol, rcol]].sum()
    return attach_fips(shares(w, dcol, rcol, name), county)


pres = cp.pivot_table(index=['county_fips', 'county_name', 'year'], columns='party',
                      values='candidatevotes', aggfunc='sum').reset_index()
pres['dem2p'] = pres.DEMOCRAT / (pres.DEMOCRAT + pres.REPUBLICAN)
pres['votes'] = pres.DEMOCRAT + pres.REPUBLICAN
panel = pres.pivot(index=['county_fips', 'county_name'], columns='year', values=['dem2p', 'votes'])
panel.columns = [f'{a}_pres_{y}' for a, y in panel.columns]
panel = panel.reset_index()

xls10 = pd.read_excel(OHIO / '2010precinct.xlsx', sheet_name='AllCounties', header=1)
xls10.columns = [str(c).strip() for c in xls10.columns]
xls10 = xls10[xls10.PRECINCT_CODE == 'ZZZ'].drop_duplicates(subset='COUNTY NAME')   # county total rows
xls04 = pd.read_excel(OHIO / 'precincts.xls', sheet_name='Election Results', header=1)
xls04.columns = [str(c).strip() for c in xls04.columns]
gen06 = pd.read_csv(OHIO / 'gen06statewide.csv', encoding='latin-1', low_memory=False)

races = [
    wide_share(xls04, 'COUNTY NAME', 'D_USSEN', 'R_USSEN', 'dem2p_sen_2004'),
    wide_share(gen06, 'COUNTY_NAME', 'US_SENATE_D_BROWN', 'US_SENATE_R_DEWINE', 'dem2p_sen_2006'),
    wide_share(xls10, 'COUNTY NAME', 'U.S. Senate - Fisher, Lee', 'U.S. Senate - Portman, Rob', 'dem2p_sen_2010'),
    wide_share(gen06, 'COUNTY_NAME', 'GOV_D_STRICKLAND', 'GOV_R_BLACKWELL', 'dem2p_gov_2006'),
    wide_share(xls10, 'COUNTY NAME', 'Governor/Lieutenant Governor - Strickland, Ted',
               'Governor/Lieutenant Governor - Kasich, John', 'dem2p_gov_2010'),
    name_share(OHIO / 'openelections_20121106__oh__general__senate.csv', 'Democratic', 'Republican', 'dem2p_sen_2012'),
    name_share(OHIO / '20141104__oh__general.csv', 'D', 'R', 'dem2p_gov_2014', office='Governor'),
    name_share(OHIO / 'openelections_20161108__oh__general.csv', 'Democratic', 'Republican', 'dem2p_sen_2016',
               office='U.S. Senate'),
    medsl_share(OHIO / 'medsl_2018_oh_precinct_senate_governor.csv', 'US SENATE', 'dem2p_sen_2018'),
    medsl_share(OHIO / 'medsl_2018_oh_precinct_senate_governor.csv', 'GOVERNOR', 'dem2p_gov_2018'),
    medsl_share(OHIO / 'medsl_2022_oh_precinct_senate_governor.tab', 'US SENATE', 'dem2p_sen_2022', sep='\t'),
    medsl_share(OHIO / 'medsl_2022_oh_precinct_senate_governor.tab', 'GOVERNOR', 'dem2p_gov_2022', sep='\t'),
    medsl_share(OHIO / 'medsl_2024_oh_precinct_senate_president.csv', 'US SENATE', 'dem2p_sen_2024'),
]
for r in races:
    panel = panel.merge(r, on='county_fips', how='outer', validate='one_to_one')
assert len(panel) == 88 and panel.notna().all().all()
panel.to_csv(OUT / 'ohio_county_panel.csv', index=False)
print(panel.shape)
