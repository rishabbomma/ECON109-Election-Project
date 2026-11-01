# ECON109 election project — Ohio Senate 2026

## Where the raw data lives

`raw/` is **not** in this repository. It is a symlink to a Google Drive folder:

    My Drive/ECON109DATA        (~708 MB, 114 files)

The data is too large for GitHub, so it syncs through Google Drive instead.
To set the link up on another machine, point `raw` at your own local copy of
that Drive folder:

    ln -s "/path/to/My Drive/ECON109DATA" raw

Everything under `clean/` and `output/` is small and is committed, so the
analysis can be read without the raw files. Re-running the cleaning scripts
needs `raw/` present.

## Layout

    raw/            source data, by what it measures (symlink, see above)
    clean_scripts/  cleaning code: election_results/, campaign_finance/
    clean/          cleaned data, same topic folders
    notebooks/      forecast/baseline.ipynb, campaign_finance/descriptive_v2.ipynb
    output/         tables and figures
    slides/         presentation and the scripts that build its figures
    write-up/       LaTeX write-up

Authorship is recorded in a comment at the top of each code file.
`REORG_LOG_2026-11-01.txt` lists the file moves from the 2026-11-01 cleanup.
