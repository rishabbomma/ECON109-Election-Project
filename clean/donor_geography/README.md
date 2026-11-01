# Donor geography and contribution size (clean)

CSV versions of the FEC JSON files in `raw/donor_geography/`, one CSV per JSON with the same base name.
The values are unchanged; the cleaning only flattened the JSON, renamed columns and added labels. Each file's total matches its JSON source.

**Shared columns:** `candidate`, `party`, `committee_id`, `committee_name`, `cycle` (2026 = 2025–26), `n_contributions`, `amount_usd`.

**by_state files** (itemized individual contributions by donor state, sorted by amount)
- `state`, `state_name`: FEC codes. `ZZ` = foreign, `OT` = other, `AP` = Armed Forces Pacific.
- `state_type`: state / DC / territory / military / foreign / other/unknown. Filter to `state` (or `state` + `DC`) for in-state vs. out-of-state shares.

**by_size files** (all individual contributions by size bucket)
- `size_lower_bound_usd`, `size_bucket`: FEC buckets $200 and under / $200.01–499.99 / $500–999.99 / $1,000–1,999.99 / $2,000+.
- The "$200 and under" row is mostly unitemized money, so FEC gives no count (`n_contributions` is blank).

**Caveat:** FEC processed data lags new filings, and these totals don't match the Form 3 line items in the campaign-finance data (`clean/campaign_finance/`).
Use them for shares (percent from Ohio, percent ≤ $200), not dollar levels.
