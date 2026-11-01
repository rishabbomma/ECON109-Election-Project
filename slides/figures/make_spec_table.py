"""Render the specification table as a slide-ready PNG (and a LaTeX source).

Standalone: reads the data directly, refits the six models, writes
    spec_table.png        coefficients through sigma  (what goes on the slide)
    spec_table_full.png   the same plus the 2026 forecast rows
    spec_table.tex        booktabs source, if you'd rather typeset it
Run:  conda run -n sims python make_spec_table.py
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd, numpy as np, statsmodels.formula.api as smf
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
CLEAN = ROOT / 'clean' / 'election_results'

races = pd.read_csv(CLEAN / 'senate_races.csv')
panel = pd.read_csv(CLEAN / 'ohio_county_panel.csv')
INC_MAP = {'dem_elected': 1, 'dem_appointed': 1,
           'rep_elected': -1, 'rep_appointed': -1, 'open': 0}
races['inc'] = races.inc_status.map(INC_MAP)
races['brown'] = ((races.state_po == 'OH')
                  & races.year.isin([2006, 2012, 2018, 2024])).astype(int)
OH_PRES_2024 = ((panel.dem2p_pres_2024 * panel.votes_pres_2024).sum()
                / panel.votes_pres_2024.sum())

GRID = {
 ('(1)', 'pres'):          'dem2p_sen ~ dem2p_pres',
 ('(2)', '+penalty'):      'dem2p_sen ~ dem2p_pres + penalty',
 ('(3)', '+incumbency'):   'dem2p_sen ~ dem2p_pres + penalty + inc',
 ('(4)', '+Brown'):        'dem2p_sen ~ dem2p_pres + penalty + inc + brown',
 ('(5)', '+FE, no Brown'): 'dem2p_sen ~ dem2p_pres + penalty + inc + C(state_po)',
 ('(6)', '+FE +Brown'):    'dem2p_sen ~ dem2p_pres + penalty + inc + brown + C(state_po)',
}
grid = {k: smf.ols(f, races).fit() for k, f in GRID.items()}
ROWS = [('dem2p_pres', 'β   lagged presidential share'),
        ('penalty',    'γ   midterm penalty'),
        ('inc',        'δ   incumbency'),
        ('brown',      'π   Brown premium')]


def ohio_share(fit, inc_val):
    b = fit.params
    return (b['Intercept'] + b['dem2p_pres'] * OH_PRES_2024
            + b.get('C(state_po)[T.OH]', 0.0) + b.get('penalty', 0.0) * (-1)
            + b.get('inc', 0.0) * inc_val + b.get('brown', 0.0))


def build(with_forecast):
    """Return [(label, cells, kind)]; kind drives size/colour/rules."""
    body = []
    for term, lab in ROWS:
        body.append((lab, [f'{f.params[term]:+.4f}' if term in f.params else '–'
                           for f in grid.values()], 'coef'))
        body.append(('', [f'({f.bse[term]:.4f})' if term in f.params else ''
                          for f in grid.values()], 'se'))
    body.append(('State fixed effects',
                 ['Yes' if 'C(state_po)' in f.model.formula else 'No'
                  for f in grid.values()], 'ruled'))
    body.append(('R²', [f'{f.rsquared:.3f}' for f in grid.values()], 'coef'))
    body.append(('σ̂  residual sd',
                 [f'{np.sqrt(f.mse_resid):.4f}' for f in grid.values()], 'coef'))
    if with_forecast:
        body.append(('2026 margin, Husted as incumbent',
                     [f'{(2*ohio_share(f, -1)-1)*100:+.1f}' for f in grid.values()],
                     'ruled'))
        body.append(('2026 margin, Husted as open seat',
                     [f'{(2*ohio_share(f, 0)-1)*100:+.1f}' for f in grid.values()],
                     'coef'))
    return body


SIZE = {'coef': 11.5, 'se': 10.0, 'pval': 9.0, 'ruled': 11.5}
COLOR = {'coef': '#111111', 'se': '#555555', 'pval': '#8a8a8a', 'ruled': '#111111'}


def render(body, out, title):
    # one "line" per row; everything below is in line units, origin top-left.
    # Walk the layout once to find where it ends, so nothing is clipped.
    HEAD = 7.45               # title + equation + note + rules + col heads
    yy = HEAD
    for _, _, kind in body:
        yy += 1.30 if kind == 'se' else 1.0
    total = yy + 0.9
    fig_w, fig_h = 13.6, total * 0.335
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xlim(0, 1); ax.set_ylim(total, 0); ax.axis('off')

    LEFT, RIGHT = 0.008, 0.992
    xs = np.linspace(0.40, RIGHT, len(grid))

    def rule(y, lw, color='#111111'):
        ax.plot([LEFT, RIGHT], [y, y], color=color, lw=lw, solid_capstyle='butt')

    y = 0.9
    ax.text(LEFT, y, title, fontsize=15.5, fontweight='bold', va='baseline')

    # the full specification. Column (6) estimates every term; columns (1)-(5)
    # drop terms from the right, which is what the dashes in the body mean.
    y += 1.20
    ax.text(LEFT, y,
            'dem2p_sen(s,t)  =  \u03b1  +  \u03b2\u00b7dem2p_pres(s,\u03c4(t))  +  \u03b3\u00b7penalty(t)  +  \u03b4\u00b7inc(s,t)  +  \u03c0\u00b7brown(s,t)  +  \u03bc(s)  +  u(s,t)',
            fontsize=12.5, va='baseline', color='#111111')
    y += 1.10
    ax.text(LEFT, y, 'Dependent variable: Democratic two-party Senate share.   '
                     f'OLS, N = {int(list(grid.values())[0].nobs)} races, 2004–2024.   '
                     'Standard errors in parentheses.',
            fontsize=10, va='baseline', color='#555555')

    y += 1.35
    rule(y, 1.6)                                    # top rule
    y += 1.0
    for x, (num, lab) in zip(xs, grid):
        ax.text(x, y - 0.42, num, fontsize=10.5, fontweight='bold',
                ha='right', va='baseline', color='#111111')
        ax.text(x, y + 0.42, lab, fontsize=10.5, ha='right', va='baseline',
                color='#333333')
    y += 1.0
    rule(y, 0.9)                                    # header rule

    y = HEAD
    for lab, cells, kind in body:
        if kind == 'ruled':
            rule(y - 0.72, 0.6, '#bbbbbb')
        if lab:
            ax.text(LEFT, y, lab, fontsize=11.5, va='baseline',
                    fontweight='bold' if kind in ('coef', 'ruled') else 'normal',
                    color='#111111')
        for x, c in zip(xs, cells):
            ax.text(x, y, c, fontsize=SIZE[kind], ha='right', va='baseline',
                    color=COLOR[kind])
        y += 1.30 if kind == 'se' else 1.0          # air after each block

    rule(y - 0.45, 1.6)                             # bottom rule
    fig.subplots_adjust(left=0.012, right=0.988, top=0.995, bottom=0.01)
    fig.savefig(out, dpi=200, facecolor='white')
    plt.close(fig)
    print('wrote', out)


TITLE = 'Building up the Ohio Senate specification'
render(build(False), HERE / 'spec_table.png', TITLE)
render(build(True), HERE / 'spec_table_full.png', TITLE)

# --- LaTeX (booktabs) --------------------------------------------------------
hdr = ' & ' + ' & '.join(f'({i+1})' for i in range(len(grid))) + r' \\'
sub = ' & ' + ' & '.join(lab for _, lab in grid) + r' \\'
tex = [r'\begin{tabular}{l' + 'r' * len(grid) + '}', r'\toprule', hdr, sub,
       r'\midrule']
for lab, cells, kind in build(True):
    tex.append((lab or '') + ' & ' + ' & '.join(c or '' for c in cells) + r' \\')
tex += [r'\bottomrule', r'\end{tabular}']
(HERE / 'spec_table.tex').write_text('\n'.join(tex) + '\n')
print('wrote', HERE / 'spec_table.tex')
