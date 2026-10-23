# Statistical methodology

## Question and estimands

For a 2015 Freddie Mac loan, how are origination characteristics associated with the timing of its first **reported** 90+ day delinquency, before a recorded zero-balance termination? The primary endpoint is the first performance-month status `03` or higher. It is an operational delinquency proxy, not legal default, foreclosure, charge-off, or realized loss.

We estimate (1) cause-specific hazards for first 90+ delinquency and for any zero-balance termination, and (2) the corresponding cumulative incidence of first 90+ delinquency in the presence of the competing termination. Zero-balance codes remain available individually in the loan-level output. Cause 2 aggregates codes to provide a stable competing endpoint; this does not assert that every code is borrower prepayment.

## Time, entry, and event construction

Time zero is the calendar month of First Payment Date. Analysis time is discrete calendar-month distance; the first payment month is month 1. Performance often starts after the time origin, so delayed entry is set to the first observed performance month. Every risk set includes only loans with entry before the month at risk and not yet exited. Event times use month-end reporting resolution. Loan Age is not the primary clock because it can be redefined after modification.

For each loan, the earliest observed `03+` delinquency is the target event unless a zero-balance termination occurs first. If both appear in the same reporting month, their within-month order cannot be inferred; the conservative primary rule assigns the termination as competing. The data builder also reports the number of these ties and the alternative count if all ties were assigned to the target event. Zero Balance Effective Date determines the terminal month when available, otherwise the recorded report month is used and flagged.

## Cause-specific Cox models and CIF

Two Cox proportional-hazards models are fit with `lifelines.CoxPHFitter`, each using delayed entry and the same set of origination-time covariates. For a cause-specific fit, other causes are treated as censored at their exit time for estimation of that cause's hazard. This gives cause-specific hazards, but the target CIF is not `1 -` the target model's survival curve.

For loan covariates (x), let (dH_k(t\mid x)) be the monthly cumulative-hazard increment for cause (k\in\{1,2\}). Within each month, the pipeline assumes constant cause-specific hazards. With (dH_\cdot=\sum_k dH_k), it updates survival and cause incidence as:

\[
S(t+1)=S(t)e^{-dH_\cdot},\qquad
F_k(t+1)=F_k(t)+S(t)(1-e^{-dH_\cdot})\frac{dH_k}{dH_\cdot}.
\]

This competing exponential update retains both causes and checks that CIFs are bounded/monotone and that survival plus all CIFs sums to one. Predictions are conditional on surviving event-free until delayed entry; the API does not extrapolate incidence before entry.

For descriptive observed incidence, the implementation uses the discrete-time Aalen–Johansen product-limit estimator with left-truncated risk sets and tied monthly events. It reports population curves; those curves are distinct from conditional model predictions for loans entering at different months.

## Features and preprocessing

Predictors are available at origination: classic FICO, LTV, DTI, original interest rate, original term, mortgage-insurance percentage and indicator, log original UPB, occupancy, loan purpose, property type, first-time buyer, channel, borrower-count category, and unit count. The primary model uses LTV; sensitivity replaces LTV with CLTV. No monthly performance information is used as a predictor. Known special numeric values are converted to missing before imputation. Imputation medians, scaling values, and category levels are learned on training data only and saved in the model bundle.

## Validation and uncertainty

Loans are randomly split 80/20 with stratification on the primary event indicator and a fixed seed. This is a within-2015-vintage split, not a temporal or out-of-vintage validation. Ranking uses a delayed-entry Harrell concordance index: for an observed target event, a later-time loan is comparable only if that loan had entered before the event time; higher predicted risk should rank ahead. Ties contribute one half.

CIF prediction error is evaluated at 12, 24, 36, and 60 months with IPCW Brier scores. The censoring survival distribution is estimated from training loans with delayed entry; competing exits are known target non-events, while right-censored loans are weighted while under observation. Calibration reports an overall mean prediction against an IPCW observed fraction, plus prediction quintiles, among test loans eligible at each horizon. Horizon-specific eligible counts are included.

Bootstrap intervals resample held-out loans while keeping the fitted models, preprocessing, and training censoring model fixed. They describe test-sample uncertainty conditional on the fitted pipeline; they do not include uncertainty from refitting the entire development process.

## Diagnostics, limitations, and reproducibility

The project reports approximate unscaled Schoenfeld residual trends for each cause. `lifelines` scaled-residual PH routines do not support the delayed-entry fit used here; the custom diagnostic is explicitly approximate and should be treated as a screening signal, not a definitive PH test. Coefficients are associations, not causal effects. A 2015 sample, administrative follow-up, uncertain event ordering within a month, and dependent censoring are material limitations. There is no adjusted Cox model for endpoint B because its code-defined event count is small.

Reproduce with `python src/survival_pipeline.py --bootstrap 100`, `python src/eda.py`, and `python -m unittest discover -s tests -v`. The Cox formulation follows [Cox (1972)](https://rss.onlinelibrary.wiley.com/doi/10.1111/j.2517-6161.1972.tb00899.x); competing-risk estimation follows Aalen–Johansen product integration ([Aalen & Johansen, 1978](https://gwern.net/doc/statistics/survival-analysis/1978-aalen.pdf)).
