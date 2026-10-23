# Data dictionary and coding decisions

The inputs are the headerless, pipe-delimited Freddie Mac Single-Family Loan-Level Dataset (SFLLD) Sample 2015. The input physical layouts were checked against Release 47 (July 2026). Raw fields are numbered from 1 in the tables; the data audit report records missingness and observed codes.

## Origination file: `sample_orig_2015.txt` (31 fields)

| # | Field | Use / coding |
|---:|---|---|
| 1 | Classic FICO | Numeric; `9999` is unavailable/sentinel, treated missing. |
| 2 | First Payment Date | Time origin at calendar-month precision. |
| 3 | First-Time Homebuyer Indicator | Categorical. |
| 4 | Maturity Date | Source descriptor; not a model feature. |
| 5 | Metropolitan Statistical Area | Descriptive only; not modeled. |
| 6 | Mortgage Insurance Percentage | Numeric; zero is meaningful. |
| 7 | Number of Units | Numeric/categorical source field. |
| 8 | Occupancy Status | Categorical. |
| 9 | Original CLTV | Numeric; sensitivity feature, missing sentinel handled. |
| 10 | Original DTI | Numeric; `999` is unavailable/out of range, treated missing. |
| 11 | Original UPB | Numeric; log transformed after positivity check. |
| 12 | Original LTV | Numeric; main-model feature, missing sentinel handled. |
| 13 | Original Interest Rate | Numeric. |
| 14 | Channel | Categorical. |
| 15 | Prepayment Penalty Indicator | Source descriptor; not modeled. |
| 16 | Amortization Type | Source descriptor; not modeled. |
| 17 | Property State | Source descriptor; not modeled. |
| 18 | Property Type | Categorical model feature. |
| 19 | Postal Code | Source descriptor; not modeled. |
| 20 | Loan Identifier | Join key, excluded from predictors. |
| 21 | Loan Purpose | Categorical model feature. |
| 22 | Original Loan Term | Numeric model feature, months. |
| 23 | Number of Borrowers | `1` = one borrower, `2` = more than one borrower in this layout; treated categorical. |
| 24 | Seller Name | Source descriptor; not modeled. |
| 25 | Super Conforming Flag | Source descriptor; not modeled. |
| 26 | Pre-HARP Loan Sequence Number | Source descriptor; not modeled. |
| 27 | Program Indicator | Source descriptor; not modeled. |
| 28 | HARP Indicator | Source descriptor; not modeled. |
| 29 | Property Valuation Method | Source descriptor; not modeled. |
| 30 | Interest-Only Indicator | Source descriptor; not modeled. |
| 31 | VantageScore 4.0 | Entirely unavailable in this vintage; excluded. |

The preprocessing pipeline additionally creates `log_original_upb` and `has_mortgage_insurance`. Numeric medians, scales, category vocabularies, and rare-category pooling are learned on training loans only and stored with the model.

## Monthly performance file: `sample_perf_2015.txt` (35 fields)

| # | Field | Use / coding |
|---:|---|---|
| 1 | Loan Identifier | Join key. |
| 2 | Reporting Period | Monthly timeline. |
| 3 | Current Actual UPB | Audited; not a predictor. |
| 4 | Current Loan Delinquency Status | `00` current; `01` 30–59 days; `02` 60–89 days; `03` 90–119 days; progressively higher numeric codes indicate longer delinquency; `RA`/`XX` are not parsed as numeric delinquency. |
| 5 | Loan Age | Audited and compared with calendar duration; not used as the analysis clock because modification can reset its definition. |
| 6 | Remaining Months to Legal Maturity | Audited; not modeled. |
| 7 | Underwriting / Major Servicing Defect Settlement Date | Not modeled. |
| 8 | Modification Flag | Audited; not modeled. |
| 9 | Zero Balance Code | First observed code defines the competing terminal exit. Codes are preserved: `01` voluntary payoff/prepayment, `02` third-party sale, `03` short sale or charge-off, `09` REO disposition, `15` whole-loan sale, `16` reperforming-loan securitization, `96` confirmed underwriting/major servicing defect settlement before another credit event. |
| 10 | Zero Balance Effective Date | Used as the terminal event month when present; missing terminal dates are audited. |
| 11–35 | Interest, UPB, recoveries, expenses, modifications, assistance, disaster, MI cancellation, servicer, and cramdown fields | Audited; post-origination fields excluded from predictors to avoid leakage. |

## Derived loan-level survival table

- Loans with zero-balance effective dates before First Payment Date are excluded because the terminal event precedes the declared time origin; exclusion counts and codes appear in the survival construction audit. Pre-origin 90+ rows are not counted as at-risk events.
- `event_time_months`: calendar month distance from First Payment Date plus one, so the first payment month is month 1; terminal date month is used for zero-balance exits when available.
- `delayed_entry_months`: months from First Payment Date until the first observed performance month. A loan contributes to risk sets only after entry.
- `event_cause`: `0` right-censored at the last observed month, `1` first observed delinquency status `03+`, `2` first zero-balance exit of any code.
- `exit_type` and `zero_balance_code`: retain terminal code detail even though cause 2 is aggregated for the main competing-risk model.
- `same_month_90plus_termination_tie`: a 90+ status and terminal code in the same month; ordering is not identifiable, and the primary conservative rule assigns cause 2.
- Endpoint B (`zero_balance_code` `03` or `09`) is retained for descriptive counts only; there are too few such events for stable adjusted cause-specific modeling.

See the official [SFLLD Release 47 disclosure summary](https://www.freddiemac.com/fmac-resources/research/pdf/disclosure-changes-summary.pdf) and [General User Guide](https://www.freddiemac.com/fmac-resources/research/pdf/general_user_guide_july_2026.pdf) for the authoritative definitions and version changes.
