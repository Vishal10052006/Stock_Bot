# Fundamental Analysis — Analysis Bot

## Responsibility

This layer converts normalized, point-in-time financial facts into structured
fundamental context. It does not place orders, size positions, set stops, or
override Strategy/Risk/Execution.

## Causal contract

Every observation carries:

- `period_start`
- `period_end`
- `published_at`
- `available_at`
- `symbol`
- `source`
- `source_version`
- normalized financial metrics

For a decision timestamp `T`, the alignment rule is:

`available_at <= T`

The latest eligible observation is selected. Future filings are never
forward-filled into the past, and no fundamental observation is used when no
eligible record exists.

## Normalized metrics

The adapter accepts provider-neutral metric names such as:

- revenue / sales
- gross_profit
- operating_income / EBIT
- net_income / PAT
- total_assets
- total_equity
- total_debt
- cash_and_equivalents
- current_assets
- current_liabilities
- operating_cash_flow / CFO
- free_cash_flow / FCF
- revenue_growth_yoy
- earnings_growth_yoy

Derived analytical metrics include:

- gross margin
- operating margin
- net margin
- ROE
- ROA
- debt/equity
- current ratio
- cash/debt
- CFO margin
- FCF margin
- revenue growth
- earnings growth

Valuation ratios are intentionally separate because they depend on market
observations as well as financial-statement facts:

- P/E
- P/B
- EV/EBITDA
- FCF yield

## Data acquisition boundary

No vendor SDK, credential, or network call is embedded in the Analysis Bot.
A human-operated acquisition process must normalize the source data into the
CSV contract before it enters this layer. The repository provides a deterministic
CSV adapter for that normalized dataset.

For Indian listed companies, NSE publishes financial-results and XBRL filing
interfaces; those source-specific ingestion details belong upstream of this
module.

## Human-required step

Provide or generate the normalized historical fundamental dataset with
trustworthy publication/availability timestamps. Once that dataset exists,
the repository code can ingest, align, analyze and validate it without changing
the analytical contract.
