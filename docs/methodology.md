# Statistical methodology

## Question and estimands

For a 2015 Freddie Mac loan, how are origination characteristics associated with the timing of its first **reported** 90+ day delinquency, before a recorded zero-balance termination? The primary endpoint is the first performance-month status `03` or higher. It is an operational delinquency proxy, not legal default, foreclosure, charge-off, or realized loss.

We estimate (1) cause-specific hazards for first 90+ delinquency and for any zero-balance termination, and (2) the corresponding cumulative incidence of first 90+ delinquency in the presence of the competing termination. Zero-balance codes remain available individually in the loan-level output. Cause 2 aggregates codes to provide a stable competing endpoint; this does not assert that every code is borrower prepayment.

## Time, entry, and event construction

Time zero is the calendar month of First Payment Date. Analysis time is discrete calendar-month distance: the First Payment Date month ends at month 1. For loan \(i\), let \(M_i^{FPD}\) and \(M_i^{first}\) be the integer calendar-month indexes of FPD and first performance. The implementation sets entry \(e_i=\max(0,M_i^{first}-M_i^{FPD})\); event/exit duration at month \(M_i^{exit}\) is \(T_i=\max(e_i+1,M_i^{exit}-M_i^{FPD}+1)\). At event month \(t\), risk-set membership is exactly `entry < t` and `duration >= t`; a loan with `entry = t` is not at risk for the interval ending at \(t\). Event times use month-end reporting resolution. Loan Age is not the primary clock because it can be redefined after modification. This is left truncation, not right censoring: validity of cohort hazard/CIF interpretation requires appropriate independent-entry/truncation conditions and event-free status through entry. For the 2,736 late entrants, event-free status between First Payment Date and first observed performance cannot be established from this file.

For each loan, the earliest observed `03+` delinquency on or after First Payment Date is the target event unless a zero-balance termination occurs first. Any 90+ rows before the time origin are ignored. Loans whose Zero Balance Effective Date is before First Payment Date are excluded from the at-risk cohort because the competing exit precedes time zero; they are counted in the construction audit. If a 90+ status and termination both appear in the same reporting month, their within-month order cannot be inferred; the primary rule assigns the termination as competing. Zero Balance Effective Date determines the terminal month when available, otherwise the recorded report month is used and flagged.

## Cause-specific Cox models and CIF

Two Cox proportional-hazards models are fit with `lifelines.CoxPHFitter`, each passing delayed entry through `entry_col` and using the same set of origination-time covariates. For a cause-specific fit, other causes are coded as non-events at their exit time for estimation of that cause's hazard. In the audited runtime, lifelines 0.30.3 uses Efron's tie method for the semiparametric partial likelihood and the `CoxPHFitter` default baseline estimation is Breslow. The repository specifies only `lifelines>=0.29`, so the exact runtime version is not pinned for other reproductions. Cause-specific hazards alone do not make the target CIF equal to `1 -` the target model's survival curve.

For covariates \(x\), the code predicts each fitted cause-specific cumulative hazard \(H_k(m\mid x)\) at integer month boundaries \(m=0,1,\ldots,h\). For interval endpoint \(t=1,\ldots,h\), it takes the difference between adjacent boundaries and interprets it as that interval's integrated hazard:

\[
\Delta H_{k,t}(x)=H_k(t\mid x)-H_k(t-1\mid x)
=\int_{t-1}^{t}\lambda_k(u\mid x)\,du,
\qquad k\in\{1,2\}.
\]

The increment is not a monthly event probability. Distributing this fitted increment uniformly over the unit-length month is a prediction interpolation convention; the observed data do not establish that the actual hazard is constant within the month. Under the resulting piecewise-constant cause-specific hazards, let \(\Delta H_{\cdot,t}=\sum_k\Delta H_{k,t}\). For a loan entering at integer time \(e\), initialize \(S_e(e\mid x)=1\) and \(F_{k,e}(e\mid x)=0\); apply only intervals with \(t>e\):

\[
S_e(t\mid x)=S_e(t-1\mid x)\exp(-\Delta H_{\cdot,t}),
\]
\[
F_{k,e}(t\mid x)=F_{k,e}(t-1\mid x)+
\begin{cases}
S_e(t-1\mid x)\left(1-\exp(-\Delta H_{\cdot,t})\right)\dfrac{\Delta H_{k,t}}{\Delta H_{\cdot,t}}, & \Delta H_{\cdot,t}>0,\\[5pt]
0, & \Delta H_{\cdot,t}=0.
\end{cases}
\]

The code implements this update with `-expm1(-total)` and a guarded division (`where=total > 0`); when the total increment is zero, survival is unchanged and each CIF increment is zero. It excludes all intervals ending at or before entry (`entry < t`), which gives the conditional quantities
\[
S_e(h\mid x)=P(T>h\mid T>e,X=x),\qquad
F_{k,e}(h\mid x)=P(e<T\le h,J=k\mid T>e,X=x),\quad h\ge e.
\]
Consequently \(S_e(e\mid x)=1\), \(F_{k,e}(e\mid x)=0\), and survival plus all cause CIFs sum to one, subject to numerical tolerance. The prediction is not unconditional from First Payment Date for a delayed entrant. The exponential competing-hazard update is exact for this assumed within-month interpolation; it is not the discrete monthly Aalen–Johansen update based on event/risk-set fractions.

Predictions at a requested horizon at or before a loan's entry return zero because no post-entry interval has accumulated. Evaluation excludes loans with `entry >= horizon`; such API zeros should not be interpreted as estimated risks at pre-entry horizons.

For descriptive observed incidence, the implementation uses the discrete-time Aalen–Johansen product-limit estimator with risk set \(Y_t=\#\{i:e_i<t,\ T_i\ge t\}\). At a month with events, all cause counts are applied simultaneously: survival is multiplied by \(1-d_{\cdot t}/Y_t\), and each CIF increases by pre-month survival times \(d_{kt}/Y_t\). These are estimates for the analyzed cohort under its entry and follow-up risk sets. A population interpretation requires suitable independent left truncation and right-censoring assumptions, which are not established here. These AJ estimates are distinct from conditional model predictions for loans entering at different months.

## Features and preprocessing

Predictors are available at origination: classic FICO, LTV, DTI, original interest rate, original term, mortgage-insurance percentage and indicator, log original UPB, occupancy, loan purpose, property type, first-time buyer, channel, borrower-count category, and unit count. The primary model uses LTV; sensitivity replaces LTV with CLTV. No monthly performance information is used as a predictor. Known special numeric values are converted to missing before imputation. Imputation medians, scaling values, and category levels are learned on training data only and saved in the model bundle.

## Validation and uncertainty

Loans are randomly split 80/20 with stratification on the primary event indicator and a fixed seed. This is a within-2015-vintage split, not a temporal or out-of-vintage validation. Ranking uses a delayed-entry Harrell concordance index: for an observed target event, a later-time loan is comparable only if that loan had entered before the event time; higher predicted risk should rank ahead. Ties contribute one half.

A separate outcome-blind calendar holdout trains on loans with First Payment Date through 201512 and evaluates loans after 201512. It is an internal later-cohort holdout within the same Freddie Mac 2015 sample, predominantly 2016 FPD. Training outcomes are observed through the 2026 file cutoff, so this split is neither an as-of historical deployment simulation nor external validation.

CIF prediction error and calibration are evaluated at 12, 24, 36, 60, and 120 months after the FPD time origin. For a horizon \(h\), eligible loans satisfy \(e_i<h\). The target status is \(Y_i(h)=I(T_i\le h,J_i=1)\). The code marks a target event by \(h\) as 1; competing exits by \(h\) and known event-free observations through \(h\) as 0. A right-censor before \(h\) has unknown status and receives zero weight/loss while remaining in the IPCW eligible denominator. Events/competing exits at \(h\) are observed by the monthly cut; a right-censor at exactly \(h\) is known event-free through that reported month.

The training reverse-KM estimates \(G\) with right-censoring (cause 0) as its event and observed causes 1 and 2 censored in that censoring model; the fit uses delayed-entry risk sets. For a known case/competing outcome observed at \(u_i\le h\), the code's weight is \(G(e_i^-)/G(u_i^-)\); for an observed control through \(h\), it is \(G(e_i^-)/G(h^-)\). Thus the implemented score is
\[
\widehat{BS}_{IPCW}(h)=\frac{1}{N_h}\sum_{i:e_i<h}w_i(h)\{Y_i(h)-\widehat F_{1,e_i}(h\mid x_i)\}^2,
\qquad N_h=\#\{i:e_i<h\},
\]
with \(w_i=0\) for censoring strictly before \(h\). Competing exits are known target non-events in the Brier loss; their role as censored observations applies only in fitting the reverse-KM distribution. The code uses left limits at event/horizon/entry boundaries, applies no arbitrary weight cap, and returns NaN if required support is unavailable rather than dropping unsupported statuses. The marginal \(G\) ratio represents post-entry censoring only under appropriate censoring independence and independent-truncation assumptions; here administrative follow-up is tied to calendar FPD, and the marginal model is not conditional on FPD/covariates. The IPCW values are therefore assumption-dependent, not established as unbiased for the full cohort.

As a complementary evaluation, the pipeline reports an unweighted known-status Brier score. Its denominator is the number of loans with `entry < h` and status known by \(h\): target events or competing exits at/before \(h\), observations beyond \(h\), and right-censors exactly at \(h\). Censoring strictly before \(h\) is excluded. This avoids estimating \(G\), but scores only the observed-status subset and is not automatically representative of all eligible loans. The paired reference is a training-only delayed-entry AJ curve conditioned on event-free status at each test loan's entry. At each horizon, Cox and AJ losses use the same known-status test loans; the reported difference is Cox minus AJ. Percentile intervals resample paired test-loan IDs 100 times while keeping fitted Cox predictions and the AJ reference fixed; they do not include training-sample or model-fit uncertainty.

Overall calibration summaries compare the mean predicted conditional CIF among eligible test loans with the ratio of IPCW-weighted target outcomes to the sum of their weights. Quintile summaries group eligible loans by predicted CIF and report group mean predictions and weighted observed proportions; group sizes are about 1,942–2,000 in the random split. These are descriptive point estimates without intervals; closeness overall does not establish calibration across subgroups or other cohorts. At 120 months in the random split, 8 of 9,996 eligible loans are censored before the horizon; the small fitted weight correction does not establish censoring independence. The known-status Brier excludes those eight and uses a different denominator and observed subset.

Bootstrap intervals resample held-out loans while keeping the fitted models, preprocessing, and training censoring model fixed. They describe test-sample uncertainty conditional on the fitted pipeline; they do not include uncertainty from refitting the entire development process.

## Diagnostics, limitations, and reproducibility

The project reports approximate unscaled Schoenfeld residual trends for each cause. In the audited lifelines 0.30.3 runtime, `compute_residuals()` raises `NotImplementedError` whenever `entry_col` is set; the custom delayed-entry/Efron-expectation trend is therefore a screening diagnostic, not a formal definitive PH test. Coefficients are conditional associations, not causal effects. A 2015 Freddie Mac sample, administrative follow-up, unverified independent-entry/event-free-at-entry assumptions, uncertain ordering within a month, and unsupported marginal IPCW censoring assumptions are material limitations. There is no adjusted Cox model for endpoint B because its code-defined event count is small.

Reproduce with `python src/survival_pipeline.py --bootstrap 100`, `python src/eda.py`, and `python -m unittest discover -s tests -v`. The IPCW loss follows the competing-risk event-status scoring approach described by [Schoop et al. (2011)](https://doi.org/10.1002/bimj.201000073) and guidance on competing-risk model validation by [van Geloven et al. (2022)](https://www.bmj.com/content/377/bmj-2021-069249); censoring-weight estimation follows the IPCW Brier formulation of [Gerds & Schumacher (2006)](https://doi.org/10.1002/bimj.200610301). Administrative censoring can affect IPCW Brier scores in important ways ([Kvamme & Borgan, 2023](https://www.jmlr.org/papers/volume24/19-1030/19-1030.pdf)). The Cox formulation follows [Cox (1972)](https://doi.org/10.1111/j.2517-6161.1972.tb00899.x); competing-risk estimation follows Aalen–Johansen product integration ([Aalen & Johansen, 1978](https://www.jstor.org/stable/4615704)).
