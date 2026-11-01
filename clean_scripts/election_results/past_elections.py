# Author: Rishab
import pandas as pd
import numpy as np
import openpyxl
import xlrd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw" / "election_results"

OHIO =  RAW / 'ohio_county'
OUT = ROOT /  "clean" / "election_results"




cp = pd.read_csv(RAW / 'county_president' / 'countypres_2000-2024.tab', sep='\t',
                 encoding='latin-1', low_memory=False)
cp = cp[(cp.state_po == 'OH') & cp.party.isin(['DEMOCRAT', 'REPUBLICAN'])].copy()
cp['county_fips'] = cp['county_fips'].astype(int)


fips = (cp[['county_name', 'county_fips']]
        .drop_duplicates()
        .assign(key=lambda d: d['county_name'].str.upper().str.replace(r'[^A-Z]', '', regex=True))
        [['key', 'county_fips']])

def _shares(w, dem, rep, name):
    """Two-party Dem share plus the D+R vote total, used as a regression weight."""
    tag = name.replace('dem2p_', '')
    out = pd.DataFrame(index=w.index)
    out[name] = w[dem] / (w[dem] + w[rep])
    out['votes_' + tag] = w[dem] + w[rep]
    return out


def attach_fips(df, county):
    cols = list(df.columns)
    out = df.reset_index()
    out['key'] = out[county].str.upper().str.replace(r'[^A-Z]', '', regex=True)
    return out.merge(fips, on='key', validate='one_to_one')[['county_fips'] + cols]


def medsl_share(path, office, name, sep=','):
    d = pd.read_csv(path, sep=sep, encoding='latin-1', low_memory=False)
    d = d[(d.office == office) & (~d.writein)
          & d.party_simplified.isin(['DEMOCRAT', 'REPUBLICAN'])]
    w = d.pivot_table(index='county_fips', columns='party_simplified',
                      values='votes', aggfunc='sum')
    return _shares(w, 'DEMOCRAT', 'REPUBLICAN', name).reset_index()


def name_share(path, county, split, dem, rep, name, office=None, sep=','):
    d = pd.read_csv(path, sep=sep, encoding='latin-1', low_memory=False)
    if office is not None:
        d = d[d.office == office]
    w = d.pivot_table(index=county, columns=split, values='votes', aggfunc='sum')
    return attach_fips(_shares(w, dem, rep, name), county)


def wide_share(path, county, dcol, rcol, name):
    d = pd.read_csv(path, encoding='latin-1', low_memory=False)
    w = d.groupby(county)[[dcol, rcol]].sum()
    return attach_fips(_shares(w, dcol, rcol, name), county)

def xls_share(path, sheet, county, dcol, rcol, name, header=1, where=None):
    d = pd.read_excel(path, sheet_name=sheet, header=header)
    d.columns = [str(c).strip() for c in d.columns]
    if where is not None:
        d = where(d)
    w = d.groupby(county)[[dcol, rcol]].sum()
    return attach_fips(_shares(w, dcol, rcol, name), county)

pres = cp.pivot_table(index=['county_fips', 'county_name', 'year'],
                      columns='party', values='candidatevotes',
                      aggfunc='sum').reset_index()
pres['dem2p'] = pres['DEMOCRAT'] / (pres['DEMOCRAT'] + pres['REPUBLICAN'])
pres['votes'] = pres['DEMOCRAT'] + pres['REPUBLICAN']

pres_wide = pres.pivot(index=['county_fips', 'county_name'],
                       columns='year', values=['dem2p', 'votes'])
pres_wide.columns = [(f'dem2p_pres_{y}' if a == 'dem2p' else f'votes_pres_{y}')
                     for a, y in pres_wide.columns]
pres_wide = pres_wide.reset_index()

ohio_sen24 = medsl_share(OHIO / 'medsl_2024_oh_precinct_senate_president.csv',
                    'US SENATE', 'dem2p_sen_2024')
ohio_sen18 = medsl_share(OHIO / 'medsl_2018_oh_precinct_senate_governor.csv',
                    'US SENATE', 'dem2p_sen_2018')
ohio_gov18 = medsl_share(OHIO / 'medsl_2018_oh_precinct_senate_governor.csv',
                    'GOVERNOR', 'dem2p_gov_2018')
ohio_sen22 = medsl_share(OHIO / 'medsl_2022_oh_precinct_senate_governor.tab',
                    'US SENATE', 'dem2p_sen_2022', sep='\t')
ohio_gov22 = medsl_share(OHIO / 'medsl_2022_oh_precinct_senate_governor.tab',
                    'GOVERNOR', 'dem2p_gov_2022', sep='\t')

ohio_sen12 = name_share(OHIO / 'openelections_20121106__oh__general__senate.csv',
                    'county', 'party', 'Democratic', 'Republican', 'dem2p_sen_2012')
ohio_sen16 = name_share(OHIO / 'openelections_20161108__oh__general.csv',
                    'county', 'party', 'Democratic', 'Republican', 'dem2p_sen_2016',
                    office='U.S. Senate')
ohio_gov14 = name_share(OHIO / '20141104__oh__general.csv',
                    'county', 'party', 'D', 'R', 'dem2p_gov_2014',
                    office='Governor')
only_totals = lambda d: d[d.PRECINCT_CODE == 'ZZZ'].drop_duplicates(subset='COUNTY NAME')

ohio_sen10 = xls_share(OHIO / '2010precinct.xlsx', 'AllCounties', 'COUNTY NAME',
                    'U.S. Senate - Fisher, Lee', 'U.S. Senate - Portman, Rob',
                    'dem2p_sen_2010', where=only_totals)
ohio_gov10 = xls_share(OHIO / '2010precinct.xlsx', 'AllCounties', 'COUNTY NAME',
                    'Governor/Lieutenant Governor - Strickland, Ted',
                    'Governor/Lieutenant Governor - Kasich, John',
                    'dem2p_gov_2010', where=only_totals)
ohio_sen04 = xls_share(OHIO / 'precincts.xls', 'Election Results', 'COUNTY NAME',
                    'D_USSEN', 'R_USSEN', 'dem2p_sen_2004')
ohio_sen06 = wide_share(OHIO / 'gen06statewide.csv', 'COUNTY_NAME',
                    'US_SENATE_D_BROWN', 'US_SENATE_R_DEWINE', 'dem2p_sen_2006')
ohio_gov06 = wide_share(OHIO / 'gen06statewide.csv', 'COUNTY_NAME',
                    'GOV_D_STRICKLAND', 'GOV_R_BLACKWELL', 'dem2p_gov_2006')

panel = pres_wide
for f in [ohio_sen04, ohio_sen06, ohio_sen10, ohio_gov06, ohio_gov10, ohio_sen12, ohio_gov14, ohio_sen16,
          ohio_sen18, ohio_gov18, ohio_sen22, ohio_gov22, ohio_sen24]:
    panel = panel.merge(f, on='county_fips', how='outer', validate='one_to_one')
    assert len(panel) == 88 and panel.notna().all().all()

print(panel.info())
print(panel.describe())
print(panel.head(20))
panel.to_csv(OUT / 'ohio_county_panel.csv', index=False)