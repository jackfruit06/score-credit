# Independent review: delayed-entry IPCW, competing-risk Brier score, and CIF calibration

## Executive conclusion

The code estimates the first **reported monthly 90+ delinquency status** before a zero-balance termination. Its model prediction is a cause-1 cumulative incidence conditional on a loan being event-free at its observed entry month and on its origination covariates. It is not the cause-specific hazard, the net survival complement, legal default, or realized credit loss.

The implemented IPCW ratio is algebraically correct for a conditional Brier score only under an appropriate independent-censoring model. In the current code, that model is a training-set marginal reverse Kaplan–Meier with delayed-entry risk sets, followed by (G(u^-)/G(L^-)). This requires a common censoring law independent of event time and entry (and relevant covariates), plus valid left-truncation assumptions. The data show administrative censoring at the common 2026-03 file end: a loan's potential follow-up is determined by its First Payment Date. The required independence is therefore not established, and conditional positivity is zero for loans whose administrative follow-up ends before the target horizon. The IPCW score is an assumption-dependent sensitivity measure, not a verified all-cohort score.

The exact-horizon outcome logic, competing-event negative labels, delayed-entry eligibility, and cause-specific CIF integration are coherent for the declared month-end convention. No production defect was found in those calculations. A complementary observed-status Brier score and a training-only delayed-entry Aalen–Johansen reference were added. On the fixed holdout, Cox had lower observed-status Brier scores than the reference at 24–120 months; the 12-month difference was indistinguishable from zero in a paired test-loan bootstrap. These intervals condition on both fitted training predictions.

## 1. Estimand and observation timeline

Let (T_i) be the first terminal event month measured from the First Payment Date calendar month, with the first payment month numbered 1; (J_i=1) denotes the first observed monthly status `03+`, (J_i=2) denotes a qualifying zero-balance termination, and (J_i=0) denotes right censoring at the last available performance month. (L_i) is the number of months from the time origin until first observed performance, with (L_i=0) for first performance at or before the origin. (X_i) contains origination-time predictors.

For (t>L_i), the model's target is

\[
F_{1}(t\mid X_i,L_i)=P(L_i<T_i\le t, J_i=1\mid T_i>L_i, X_i,L_i).
\]

In words: among loans with these origination attributes that are known to be event-free when observation starts at month (L_i), what is the probability of a first reported 90+ status by month (t), before a competing zero-balance exit? This is a conditional real-world CIF because cause 2 is included in the event-free survival depletion and its own cumulative incidence. The validation population at horizon (t) is the held-out loans with (L_i<t); loans with (L_i\ge t) contribute no post-entry risk interval and are excluded.

The construction uses calendar month of First Payment Date as origin and month-end reporting resolution. First observed performance sets (L_i). A termination uses Zero Balance Effective Date when available, otherwise the reporting month. A same-month `03+` and termination tie is coded cause 2 because within-month order is unavailable. Twenty pre-origin zero-balance cases are excluded. These rules are in [`build_survival_data()`](../src/survival_pipeline.py#L201) and the dictionary at [`docs/data_dictionary.md`](data_dictionary.md#L61).

Delayed entry is a data-availability rule, not proof that entry was random or that the loan was known event-free before its first record. Cause-specific Cox fitting and AJ risk sets properly omit loans before (L_i), conditional on the usual left-truncation assumptions. Whether the late first-record process is independent of latent event risk is not identifiable from these files.

## 2. IPCW derivation and applicability

For the binary target (Y_i(t)=I(T_i\le t,J_i=1)), the target Brier risk in the eligible evaluation sample is

\[
BS(t)=\frac{1}{n_t}\sum_{i:L_i<t}\{Y_i(t)-\widehat F_{1,i}(t\mid X_i,L_i)\}^2.
\]

Suppose a subject is observed at entry (L_i), and let (C_i) be the censoring time on the same origin-month scale. For a status observed at endpoint (u\le t), the probability it is observable after entry is

\[
q_i(u\mid L_i,Z_i)=P(C_i\ge u\mid C_i\ge L_i,L_i,Z_i),
\]

where (Z_i) must include all variables needed to make censoring independent of the event process. For an event or competing event at (u\), use (1/q_i(u\mid L_i,Z_i)); for an event-free control observed through (t), use (1/q_i(t\mid L_i,Z_i)). A censored-before-(t) row has unknown (Y_i(t)) and contributes no direct loss. In the discrete month-end convention, a censor at (t) is known through that month, and the pre-jump probability uses (C_i\ge t).

If censoring has a common survival (G(u)), independent of (L,X,T,J), then

\[
q_i(u\mid L_i)=G(u^-)/G(L_i^-),\qquad w_i(u)=G(L_i^-)/G(u^-).
\]

This is exactly what [`cif_ipcw_brier()`](../src/survival_pipeline.py#L599) applies: reverse-KM (G) is fit on training durations with `event_observed=(cause==0)` and delayed entry, then event/competing endpoint weights use (G(L^-)/G(U^-)), while controls use (G(L^-)/G(t^-)). The loss is divided by the number with (L_i<t), not by the sum of weights. An unsupported zero (G) yields `NaN`; there is no arbitrary weight truncation.

That ratio is **not universal**. If (G) depends on entry/calendar date or covariates, the corresponding probability must be conditional:

\[
q_i(u\mid L_i,Z_i)=G(u^-\mid L_i,Z_i)/G(L_i^-\mid L_i,Z_i).
\]

The code does not estimate this conditional function. A marginal reverse-KM plus delayed-entry risk sets does not by itself adjust for censoring informative about entry or predictors. In the actual data, every right-censored loan is observed through the common final reporting month 202603, and its potential censor duration is that calendar cutoff minus its First Payment Date. Thus administrative follow-up is a deterministic function of the origin calendar date. If that date is conditioned on, some loans have zero chance of being observed through 120 months. IPCW cannot recover their unknown status without extrapolating assumptions. At 120 months, 20 of 49,980 cohort loans and 8 of 9,996 test loans are censored before the horizon; reverse-KM weights remain near one only because the marginal censor fraction is small. This is not evidence for independent censoring.

**Finding:** no formula coding defect was confirmed, but the assumption supporting the reported all-eligible IPCW estimand is unjustified for administrative censoring tied to calendar origin. The former report statement that independence conditional on entry suffices was too strong: the implemented model is marginal and does not condition (G) on entry/covariates.

## 3. Cause-specific Brier labels and exact month convention

For eligible loans, code assigns (Y_i(t)=1) when cause 1 occurs by (t); a cause-2 event by (t) is a known (Y=0); a cause-0 loan observed after (t), or censored at the end of month (t), is a known (Y=0). Cause-0 censoring strictly before (t) has unknown status and weight zero. The score is

\[
\widehat{BS}(t)=\frac{1}{n_t}\sum_{i:L_i<t}W_i(t)\{Y_i(t)-\widehat F_{1,i}(t\mid X_i,L_i)\}^2,
\]

with (W_i(t)=0) for unknown rows and the observed endpoint-specific inverse probabilities above for known rows. The competing event is censored only for estimating (G), never treated as censoring in the target label. Entry at or after (t) is excluded. This makes the exact-time categories disjoint.

Selected monthly rules:

| Record at month (t) | Status at (t) | Brier label | Direct loss |
|---|---|---:|---|
| First 90+ status | Observed target case | 1 | Yes, event-endpoint weight |
| Zero-balance termination | Known target negative | 0 | Yes, competing-endpoint weight |
| Censor at end of month | Known event-free through month end | 0 | Yes, horizon weight |
| Censor before month (t) | Unknown at (t) | not imputed | No direct loss; eligible denominator remains under IPCW |
| Entry at or after (t) | Not eligible for a post-entry interval | — | Excluded |
| Same-month 90+ and termination | Order unavailable | 0, cause 2 under repository rule | Yes, once |

If the source had within-month censoring/event order, this month-end convention could be wrong. The files provide only monthly reports, so no finer ordering is inferred. `T` includes the event month and `L<t` means the first at-risk interval is after entry. The implementation uses (G(t^-)) consistently for outcomes through month (t).

## 4. Synthetic verification

The expected values below were derived from the labels, probabilities, and risk-set counts shown; they are not produced by the function under test. Tests are in [`tests/test_survival_pipeline.py`](../tests/test_survival_pipeline.py).

| Case | Synthetic record(s), horizon (t) | Hand expectation | Code verification |
|---:|---|---|---|
| 1 | (T=2,J=1,L=0,t=3,p=.8); plus known control (T=4,J=0,p=.2), (G=1) | Labels (1,0), weights (1,1); score ((.04+.04)/2=.04) | `test_brier_only_primary_event_hand_calculation` |
| 2 | (T=2,J=2,L=0,t=3,p=.2); plus control (p=.3), (G=1) | Competing event is known negative; score ((.04+.09)/2=.065) | `test_brier_only_competing_event_is_known_target_nonevent` |
| 3 | (T=4,J=0,L=0,t=3,p=.1) | Known event-free, (Y=0,w=1), loss .01 | `test_brier_no_event_before_horizon_including_competing_after_horizon` |
| 4 | (T=2,J=0,L=0,t=3,p=.9) | Unknown outcome; (Y) not inferred, direct weight 0 | `test_brier_drops_censor_before_horizon_from_loss_not_denominator` |
| 5 | (T=3,J=1,L=0,t=3,p=.7) | Exact-horizon target event is case; loss .09 | `test_brier_event_exactly_at_horizon_is_a_case_not_a_control` |
| 6 | (T=3,J=2,L=0,t=3,p=.7) | Exact-horizon competitor is known negative; loss .49 | `test_brier_competing_event_exactly_at_horizon_is_a_nonevent` |
| 7 | (T=3,J=0,L=0,t=3,p=.3) | Censor at month-end is known through (t); loss .09 | `test_brier_censor_exactly_at_horizon_is_known_through_observed_month` |
| 8 | (L=2,T=3,J=1,t=4), and a control through 4; (G(2^-)=G(4^-)=.5) | Both conditional weights (1/(.5/.5)=1); score .04 | `test_brier_delayed_entry_uses_conditional_censor_survival_ratio` |
| 9 | (L=t=3) or (L=4,t=3) | Excluded; no eligible loans, score `NaN` | `test_brier_entry_at_or_after_horizon_is_ineligible` |
| 10 | Reverse-KM support (G(t^-)=0) with required known controls | Score is undefined (`NaN`), not silently zero | `test_brier_returns_undefined_when_censoring_support_is_zero` |
| 11 | Reverse-KM (G(4^-)=1/25); one case and one control | Each finite weight 25; Brier 1.0 for p=(.8,.2) | `test_brier_keeps_large_finite_ipcw_weights_without_arbitrary_cutoff` |
| 12 | One loan has 90+ and zero-balance termination in same report month | Within-month order unknown; tie coded once as cause 2 | `test_dataset_builder_handles_event_competing_tie_and_delayed_entry` |
| 13 | (h=3); administrative cutoffs (C=(5,2)), both (L=0), p=(.2,.9) | First loan's known-status inverse probability conditional on its known cutoff is 1; second status is unknown and excluded. Marginal reverse-KM instead assigns observed first loan weight 2, demonstrating the additional independence assumption | `test_marginal_censor_survival_does_not_recover_known_admin_followup`; admin-score test returns .04 on its one known row |
| 14 | Four subjects: (T=(1,1,2,2), J=(1,2,1,0), L=0) | Month 1: risk 4, (S=.5,F_1=.25,F_2=.25). Month 2: risk 2, (S=.25,F_1=.5,F_2=.25) | `test_aalen_johansen_exact_monthly_ties_and_probability_invariants`; independent expected values are literal constants |

The existing constant-hazard check also verifies the closed-form competing exponential CIF, while a duplicate loan-month is rejected so records cannot silently change the loan as the statistical unit. Properties verified include nonnegative/nondecreasing CIFs, total probability at most one, finite probability bounds, zero support transparency, and deterministic arithmetic.

## 5. CIF prediction construction and support

Each cause-specific Cox model estimates a cause-specific hazard, treating the other cause as censored for that fit. The CIF is not (1-S_1(t)). For monthly integrated hazard increments (\Delta H_k), (H_\cdot=\sum_k\Delta H_k), and prior event-free probability (S), the code uses the competing exponential update

\[
\Delta F_k=S\{1-\exp(-H_\cdot)\}\frac{\Delta H_k}{H_\cdot},\qquad S_{new}=S\exp(-H_\cdot).
\]

It starts accumulation after each subject's entry, thereby returning a conditional CIF. This represents piecewise-constant within-month cause-specific hazards; it is a modeling approximation for monthly discrete observations, while the AJ reference uses discrete product-limit updates. Across causes, CIFs remain nonnegative and nondecreasing, each is at most one, and (S+\sum_kF_k=1). Those invariants are checked in [`integrate_competing_cumulative_hazards()`](../src/survival_pipeline.py#L455); the direct cause-specific prediction path is [`competing_cox_cif()`](../src/survival_pipeline.py#L502).

Horizons are clipped to the largest training duration and the configured maximum. The selected 120-month horizon is within observed training duration; this is only a coarse support check and does not prove adequate covariate-specific tail support. The model uses the fitted Breslow baseline hazard and makes no explicit extrapolation beyond the maximum configured horizon.

## 6. Aalen–Johansen populations and fair comparison

`aalen_johansen_cif()` uses risk sets (Y(t)=\#\{i:L_i<t,T_i\ge t\}) and simultaneous tied-cause updates (S(t)=S(t-1)(1-d_{all}/Y)), (F_k(t)=F_k(t-1)+S(t-1)d_k/Y). It handles delayed entry in the observed risk sets, provided the left-truncation mechanism is independent enough for the intended source population.

The repository writes (a) a full-cohort descriptive AJ curve, which includes both training and test outcomes; and (b) a test-set AJ curve. The mean Cox CIF is instead individual-specific, conditional on each test loan's entry and covariates. Those curves do not share a population or conditioning set and should not be expected to match pointwise. The full-cohort AJ curve is descriptive, not a holdout benchmark. The added benchmark estimates AJ from training only and predicts each test loan's conditional risk from entry using

\[
\widehat F_{1,AJ}(t\mid L=e)=\{\widehat F_1(t)-\widehat F_1(e)\}/\widehat S(e),\quad e<t,
\]

then scores Cox and AJ on the same known-outcome test loans. This is a covariate-free reference, and it inherits the truncation and censoring assumptions of training AJ. It avoids outcome leakage from test predictions.

## 7. Calibration and 120-month interpretation

Test eligibility is (L<t). Predicted group averages are arithmetic means within quintiles of predicted conditional CIF; observed values are weighted positive proportions ΣwY/Σw. With nonnegative weights and binary outcomes, an observed value outside [0,1] would signal an implementation/data error; it cannot occur under this estimator. Current output contains five groups per horizon, each with 1,942–2,000 loans, and all observed group proportions are between 0 and 1. No calibration uncertainty interval is produced, so these are point summaries only.

At 120 months, the primary IPCW Brier is 0.0370237 over 9,996 eligible test loans, with 8 censored before the horizon; (G(120^-)=0.998746), maximum weight 1.00126, ESS 9,988. This confirms numerical support under the fitted marginal KM, not independent censoring. The known-outcome score is 0.0370518 over 9,988 test loans and excludes eight unknown statuses. Its training-AJ reference is 0.0381706. The confidence interval for Cox-minus-reference is [-0.0016438, -0.0006939], from 100 paired test-resamples with both fitted prediction systems fixed. Do not treat this result as out-of-vintage validation or as an unbiased all-cohort score absent the assumptions above.

## 8. Scores and benchmark results

| Horizon | IPCW Brier (assumption-dependent) | Known-status Cox Brier | Training-AJ reference | Cox minus AJ, paired 95% test bootstrap CI | N known |
|---:|---:|---:|---:|---:|---:|
| 12 | 0.00123357 | 0.00123357 | 0.00123407 | -0.00000050 [-0.00000406, 0.00000210] | 9,712 |
| 24 | 0.00467203 | 0.00467203 | 0.00470679 | -0.00003477 [-0.00007189, -0.00001247] | 9,727 |
| 36 | 0.00864022 | 0.00864022 | 0.00875057 | -0.00011035 [-0.00016928, -0.00005155] | 9,741 |
| 60 | 0.02418603 | 0.02418603 | 0.02485696 | -0.00067092 [-0.00091904, -0.00037259] | 9,996 |
| 120 | 0.03702374 | 0.03705184 | 0.03817065 | -0.00111880 [-0.00158403, -0.00070546] | 9,988 |

The Brier values rise with horizon because the target event becomes more common; magnitude alone does not establish quality. The training-AJ comparison indicates lower held-out squared error for Cox at 24–120 months on this random split. At 12 months, the difference is negligible and the interval covers zero. It is a modest reference model, not a no-information or calibrated oracle benchmark. Test-only bootstrap intervals omit training AJ uncertainty, model fitting, and split uncertainty.

## 9. Censoring and truncation evidence

- The file's last reported month is 202603. All 10,656 right-censored loans have that same last observation month; none stop earlier. This supports administrative rather than observed loss-to-follow-up in the constructed cohort.
- First Payment Date ranges from 201502 to 202004. Thus (C_i\), measured from First Payment Date to the common file end, varies deterministically with calendar origin. This directly violates the simple story of a common censor distribution independent of entry/calendar date. No censoring model conditional on origin date or covariates was fit.
- There are 20 cohort loans with administrative follow-up shorter than 120 months; the random test set contains 8. These are precisely rows whose status by 120 is unavailable; a conditional model that knows their calendar cutoff has no positivity at 120.
- The 2,736 delayed entries arise because first performance records occur after the declared time origin. Observed counts alone cannot establish that entry is independent of latent event risk, or that unobserved pre-entry months are known event-free.
- Covariate-conditional censoring independence, independent truncation, within-month event ordering, and transport to other origination vintages are not verifiable from this single extract.

An internal later-FPD cohort check is now reported in [`task3_robustness_validation.md`](task3_robustness_validation.md); it does not provide external or historical prospective validation. The next analysis should use an independent vintage or lender and, if overlap/positivity permits, a censoring model that uses calendar entry date and other predictors of follow-up. In this one-cutoff dataset, retain the known-status score as a transparent complement and present IPCW as assumption-dependent. Do not use a conditional IPCW model to claim a full population horizon score when the known calendar cutoff implies zero observation probability for some subjects.

## 10. Findings by severity and code evidence

| Severity | Classification | Finding |
|---|---|---|
| High | Unjustified assumption / reporting | Marginal reverse-KM IPCW is not justified for deterministic calendar administrative censoring by First Payment Date. The weight ratio itself is conditionally correct under the marginal independent-censoring model; the project data do not verify that model. |
| Moderate | Estimand / comparison | Full-cohort AJ and test conditional model predictions represent different populations. The report now labels that distinction and adds a train-only AJ reference scored on the same test subjects. |
| Moderate | Limitation | Delayed-entry independence, monthly within-period order, and calendar transport cannot be verified from this dataset. |
| Low | Reporting correction | Calibration has no reported intervals; test-only paired benchmark intervals exclude training uncertainty. These limitations are now explicit. |
| None found | Implementation check | Competing outcomes are known negatives; pre-horizon censoring is never labeled zero; exact-horizon rules are mutually exclusive; zero support returns `NaN`; CIF probability invariants hold. |

Key paths: construction and event coding [`src/survival_pipeline.py:201-315`](../src/survival_pipeline.py#L201); AJ and conditional AJ [`:380-433`](../src/survival_pipeline.py#L380); CIF integration [`:455-522`](../src/survival_pipeline.py#L455); censor survival and Brier [`:592-654`](../src/survival_pipeline.py#L592); reverse-KM fit and calibration [`:778-824`](../src/survival_pipeline.py#L778); AJ and benchmark outputs [`:826-869`](../src/survival_pipeline.py#L826); edge-case tests [`tests/test_survival_pipeline.py:93-280`](../tests/test_survival_pipeline.py#L93).

## 11. Literature

- Schoop, R., Beyersmann, J., Schumacher, M., & Binder, H. (2011). *Quantifying the predictive accuracy of time-to-event models in the presence of competing risks*. **Biometrical Journal, 53**(1), 88–112. https://doi.org/10.1002/bimj.201000073. Competing-risk prediction-error formulation; it does not by itself establish the left-truncation/calendar-censoring assumptions in this project.
- Gerds, T. A., & Schumacher, M. (2006). *Consistent estimation of the expected Brier score in general survival models with right-censored event times*. **Biometrical Journal, 48**(6), 1029–1040. https://doi.org/10.1002/bimj.200610301. Shows censoring-regression weighting when censoring depends on predictors; ordinary marginal weights require stronger assumptions.
- van Geloven, N., et al. (2022). *Validation of prediction models in the presence of competing risks: a guide through modern methods*. **BMJ, 377**, e069249. https://doi.org/10.1136/bmj-2021-069249. Practical competing-risk model validation guidance.
- Kvamme, H., & Borgan, Ø. (2023). *The Brier Score under Administrative Censoring: Problems and a Solution*. **Journal of Machine Learning Research, 24**(2), 1–26. https://www.jmlr.org/papers/volume24/19-1030/19-1030.pdf. Shows marginal IPCW can be biased with staggered/calendar entry and administrative censoring and proposes a score on subjects with known outcomes. Its original setup is single-event; the repository applies the same known-binary-status logic to the cause-1 CIF outcome.
- Stegherr, R., Allignol, A., Meister, R., Schaefer, C., & Beyersmann, J. (2020). *Estimating cumulative incidence functions in competing risks data with dependent left-truncation*. **Statistics in Medicine, 39**(4), 481–493. https://doi.org/10.1002/sim.8421. Standard AJ with left truncation relies on random truncation; dependent entry needs additional assumptions or methods.

## 12. Reproduction and remaining limits

Commands executed after changes:

```text
python -m unittest discover -s tests -v       # 24 tests passed
python -m py_compile src/survival_pipeline.py src/temporal_validation.py src/eda.py
python src/survival_pipeline.py --bootstrap 100
python src/temporal_validation.py --bootstrap 100
git diff --check
```

The primary pipeline regenerated the loan table, model artifacts, metrics, CIF calibration, bootstrap output, and `reports/tables/cif_administrative_benchmark.csv`. Primary outputs remain C-index 0.7511890 and IPCW Brier [0.00123357, 0.00467203, 0.00864022, 0.02418603, 0.03702374]. No Cox fit warnings were recorded. The only intentional behavior addition is the train-AJ comparison and known-status score; existing IPCW values are unchanged.

Remaining limitations: no conditional censoring model was fit; independent out-of-vintage validation is unavailable; delayed-entry independence is unverified; calibration uncertainty is absent; and the 100-replicate bootstrap is conditional on fitted development. These results should be reported as within-vintage validation and sensitivity analysis, not deployment evidence.
