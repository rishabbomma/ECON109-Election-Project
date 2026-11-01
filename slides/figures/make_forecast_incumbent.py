"""Single-panel waterfalls for the 2026 forecast, one per incumbency coding.

Standalone -- refits the headline model (state FE, OLS) from the CSVs.
Writes forecast_incumbent.png  (titled) and forecast_open_seat.png (no titles).
Run:  conda run -n sims python make_forecast_incumbent.py
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd, numpy as np, statsmodels.formula.api as smf
import re, datetime as dt
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLEAN = HERE.parent.parent / 'clean' / 'election_results'

races = pd.read_csv(CLEAN / 'senate_races.csv')
panel = pd.read_csv(CLEAN / 'ohio_county_panel.csv')
INC_MAP = {'dem_elected': 1, 'dem_appointed': 1,
           'rep_elected': -1, 'rep_appointed': -1, 'open': 0}
races['inc'] = races.inc_status.map(INC_MAP)
races['brown'] = ((races.state_po == 'OH')
                  & races.year.isin([2006, 2012, 2018, 2024])).astype(int)

m = smf.ols('dem2p_sen ~ dem2p_pres + penalty + inc + brown + C(state_po)',
            races).fit()
OH_PRES_2024 = ((panel.dem2p_pres_2024 * panel.votes_pres_2024).sum()
                / panel.votes_pres_2024.sum())
SILVER = 0.4830 / (0.4830 + 0.4500)          # Silver 48.3 / 45.0, two-party

# --- the five most recent polls ---------------------------------------------
# The file gives field dates without a year. Nearly all are 2026; a date that
# would fall after today must belong to 2025, which is how Emerson's Dec 6-8
# is dated correctly rather than being treated as the most recent poll.
POLLS_CSV = HERE.parent.parent / 'raw' / 'polls' / 'ohio_senate_polls2025.csv'
TODAY = dt.date(2026, 10, 27)
MON = {m: i + 1 for i, m in enumerate(
    ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct',
     'Nov', 'Dec'])}


def end_date(txt):
    """Last day of the field period, e.g. 'Sep 29-Oct 9' -> 2026-10-09."""
    txt = txt.replace('\u2013', '-').replace('\u2014', '-')
    last = txt.split('-')[-1].strip()
    m = re.match(r'([A-Z][a-z]{2})\s+(\d+)', last)
    mon, day = ((m.group(1), int(m.group(2))) if m else
                (re.match(r'([A-Z][a-z]{2})', txt.strip()).group(1), int(last)))
    cand = dt.date(2026, MON[mon], day)
    return cand if cand <= TODAY else dt.date(2025, MON[mon], day)


polls = pd.read_csv(POLLS_CSV, encoding='utf-8-sig')
polls['end'] = polls['Field dates (as shown)'].map(end_date)
polls['dem2p'] = polls['Brown (%)'] / (polls['Brown (%)'] + polls['Husted (%)'])
recent = polls.sort_values('end', ascending=False).head(5)
print(recent[['Pollster', 'end', 'Brown (%)', 'Husted (%)', 'dem2p']].to_string(index=False))


def panel(inc_2026, inc_label, title, out):
    b = m.params
    parts = [('baseline\n(pres + Ohio effect)',
              b['Intercept'] + b['dem2p_pres'] * OH_PRES_2024
              + b.get('C(state_po)[T.OH]', 0.0)),
             ('midterm penalty\n(R president)', b['penalty'] * -1),
             (inc_label, b['inc'] * inc_2026),
             ('Brown premium', b['brown'])]
    vals = [v for _, v in parts]
    labels = [lab for lab, _ in parts] + ['2026\nforecast']
    cum = np.cumsum(vals)
    starts = np.concatenate([[0], cum[:-1]])
    total = cum[-1]
    print(f'{out}: forecast {total:.4f}  margin {(2*total-1)*100:+.1f}')

    fig, ax = plt.subplots(figsize=(10.2, 6.4))
    cols = ['#5b6b7a'] + ['#4a90c4' if v >= 0 else '#c0392b' for v in vals[1:]]
    for i, (s, v, c) in enumerate(zip(starts, vals, cols)):
        ax.bar(i, v * 100, bottom=s * 100, color=c, edgecolor='#1b3a5c',
               linewidth=.7, width=.62)
        ax.annotate(f'{v*100:+.1f}', (i, (s + v) * 100), ha='center',
                    va='bottom' if v >= 0 else 'top', fontsize=11.5,
                    fontweight='bold',
                    xytext=(0, 5 if v >= 0 else -5), textcoords='offset points')
        if i < len(vals) - 1:
            ax.plot([i + .31, i + 1 - .31], [cum[i] * 100] * 2, color='#8c9aa8',
                    lw=1.0, ls=':')
    ax.bar(len(vals), total * 100, color='#1b3a5c', edgecolor='#1b3a5c',
           linewidth=.7, width=.62)
    ax.annotate(f'{total*100:.1f}', (len(vals), total * 100), ha='center',
                va='bottom', fontsize=13, fontweight='bold',
                xytext=(0, 5), textcoords='offset points')

    ax.axhline(50, color='#c0392b', lw=1.4, ls='--', zorder=0)
    ax.annotate('50% = tie', (-0.45, 50), fontsize=10, color='#c0392b',
                va='bottom', xytext=(0, 3), textcoords='offset points')

    # the five most recent polls, as points over the forecast bar, plus Silver
    # placed in a narrow column clear of the bar so nothing overlaps the
    # bar's own value label or disappears against the dark fill
    xf = len(vals) + 0.56
    jitter = np.linspace(-0.13, 0.13, len(recent))
    ax.scatter(xf + jitter, recent.dem2p * 100, s=62, marker='o',
               facecolor='white', edgecolor='#1b6ca8', linewidth=1.7,
               zorder=6, label='5 most recent polls')
    ax.scatter([xf], [SILVER * 100], s=140, marker='D', facecolor='#1b6ca8',
               edgecolor='#0d3b5c', linewidth=1.0, zorder=7,
               label=f'Silver average ({SILVER*100:.1f}%)')
    ax.set_xlim(-0.62, len(vals) + 1.05)
    ax.legend(frameon=False, fontsize=10, loc='upper left')

    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=10.5)
    ax.set_ylim(38, 54)
    ax.set_ylabel('Democratic two-party share (%)', fontsize=11.5)
    if title:
        ax.set_title('The 2026 forecast turns on one coding decision\n'
                     f'{title}: forecast {total*100:.1f}% '
                     f'(margin {(2*total-1)*100:+.1f})',
                     fontsize=14, fontweight='bold')
    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(axis='y', labelsize=10.5)
    fig.tight_layout()
    fig.savefig(HERE / out, dpi=200, facecolor='white')
    plt.close(fig)
    print('wrote', HERE / out)


panel(-1, 'incumbency\n(Husted, R)',
      'Husted counted as incumbent', 'forecast_incumbent.png')
panel(0, 'incumbency', None, 'forecast_open_seat.png')
