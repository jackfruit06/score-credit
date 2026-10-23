# Task 4 — Final statistical audit

## 1. Executive summary

I traced the implemented endpoint, risk sets, Cox fits, CIF prediction, Aalen–Johansen (AJ), concordance, Brier scores, calibration, bootstrap, and calendar split. I reran the primary and calendar-cohort analyses and the existing unit suite. The regenerated metrics match the reported values to rounding; the random and calendar C-index pair counts are distinct and both reconcile to their metric JSON.

**No critical implementation bug was confirmed.** The CIF recursion is mathematically coherent as a piecewise-constant continuous-time competing-hazard approximation over monthly intervals. It is not the discrete-time AJ recursion and should be described as a model-implied monthly CIF under that interpolation assumption. The implementation and methodology document already state this assumption; the final research report should keep it explicit wherever it calls the CIF “exact.”

The central limitations are inferential. First, reverse-KM IPCW requires an appropriate marginal censoring model and conditional independence assumptions that are not supported by deterministic administrative follow-up tied to First Payment Date (FPD). Second, delayed entry requires appropriate left-truncation assumptions and event-free status up to entry; those cannot be verified in this extract. Third, the later-FPD holdout is within the same Freddie Mac sample, mostly 2016, and uses matured 2015 outcomes, so it is not independent external or historical prospective validation.

## 2. Code-to-artifact map

| Quantity / step | Implementation | Inputs and convention | Main artifact |
|---|---|---|---|
| Time origin, event, exit, censor, entry | `build_survival_data()` in `src/survival_pipeline.py:214` | Calendar-month distance from FPD; duration is month-end index `calendar month gap + 1`; entry is `max(0, first performance month − FPD)`; cause 1 is first status `03+` before zero-balance; cause 2 is zero-balance termination; cause 0 is last performance month. | `outputs/survival_dataset.csv`; `reports/data_audit.json` → `survival_cohort_construction` |
| Cox fits / preprocessing | `run_model()` in `src/survival_pipeline.py:762`; `prepare_features()` and feature transforms earlier in the file | Two cause-specific Cox fits with lifelines `entry_col`; other event cause is censored for each cause-specific hazard; preprocessing is estimated on training rows only. | `outputs/models/cause_specific_cox_models.pkl`; `outputs/models/model_metrics.json`; coefficient tables under `reports/tables/` |
| Cause-specific CIF | `competing_cox_cif()` at `:539`; `integrate_competing_cumulative_hazards()` at `:492`; scoring API `score_new_loans()` at `:584` | Cox cumulative hazards evaluated at integer months 0…h; differences supply monthly integrated-hazard increments; increments before or at delayed entry are excluded; prediction is conditional on remaining event-free through entry. | Model CIF and calibration columns in `reports/tables/cif_overall_test_calibration.csv`, `cif_calibration.csv`; model bundle |
| Nonparametric AJ | `aalen_johansen_cif()` at `:393`; `conditional_aj_cif()` at `:426` | Discrete product-limit risk set `(entry < t) & (duration >= t)`; cause events tied at a month update simultaneously; conditional reference is `[F(h)-F(entry)]/S(entry)`. | `reports/tables/aalen_johansen_full.csv`, `aalen_johansen_test.csv`; EDA duplicate full curve `aalen_johansen_cif_full.csv` |
| Concordance | `left_truncated_c_index()` at `:617` | Each cause-1 event is compared with loans that entered before its event time and remain observed beyond it; greater predicted cause-1 risk is concordant; risk ties count one half. | `outputs/models/model_metrics.json`; `reports/tables/test_metric_bootstrap_fixed_model.csv` |
| IPCW Brier | `cif_ipcw_brier()` at `:636`; reverse-KM fitting and aggregation in `run_model()` | Cases are cause 1 by h; competing exits by h are known zeroes; controls are observed beyond h or censored at h; censoring before h is unknown. Uses `G(u−)/G(entry−)` conditionalized weights; denominator is all loans eligible by entry (`entry < h`). | `reports/tables/cif_brier_scores.csv`; `outputs/models/model_metrics.json` |
| Known-status Brier / AJ reference | `administrative_brier_terms()` at `:447`; `conditional_aj_cif()`; paired difference at `:470` | Same test loans and binary target; status is scored only when known by h. AJ reference is trained only on training outcomes and conditioned on each loan’s entry. | `reports/tables/cif_administrative_benchmark.csv` |
| Calibration | `run_model()` at `:844–872` | Mean predicted CIF over entry-eligible loans; observed CIF is IPCW weighted. Grouped calibration uses predicted-CIF quintiles; no calibration intervals. | `reports/tables/cif_overall_test_calibration.csv`, `cif_calibration.csv`, `reports/figures/cif_calibration.png` |
| Bootstrap | `bootstrap_metric_intervals()` at `:732`; `paired_bootstrap_mean_difference()` at `:470` | 100 test-loan resamples, fixed predictions/models and censor KM; paired Cox–AJ differences resample identical test IDs. | `reports/tables/test_metric_bootstrap_fixed_model.csv`, `cif_administrative_benchmark.csv` |
| Calendar holdout | `calendar_cohort_split()` at `:79`; `src/temporal_validation.py:38–95` | Outcome-blind FPD cutoff 201512; same modeling code, train-fitted preprocessing, and horizon scoring. | `outputs/models_temporal_validation/model_metrics.json`; `reports/tables_temporal_validation/` |

## 3. CIF mathematical derivation

Let the cause-specific hazards for causes 1 and 2 be constant within monthly interval `(t−1,t]`, with integrated increments

\[
\Delta H_k(t)=\int_{t-1}^{t}\lambda_k(u\mid x)\,du,\qquad
\Delta H_\cdot(t)=\Delta H_1(t)+\Delta H_2(t).
\]

For a subject event-free at the start of the interval, the interval event-free probability is

\[
S(t)=S(t-1)\exp\{-\Delta H_\cdot(t)\}.
\]

Under constant cause-specific hazards in the interval, the probability of cause k during the interval is the integral

\[
S(t-1)\int_0^1 \exp\{-u(\lambda_1+\lambda_2)\}\lambda_k\,du
=S(t-1)\{1-\exp(-\Delta H_\cdot)\}
  \frac{\Delta H_k}{\Delta H_\cdot}.
\]

Thus the code’s update `fail = -expm1(-total)` and `dF_k = S * fail * ΔH_k/total` is the coherent competing-risk recursion for that assumed within-month continuous hazard. At total increment zero it allocates zero CIF increment. The interval increments telescope to `S(t)+F_1(t)+F_2(t)=1`; hazards and CIF increments are nonnegative, survival is nonincreasing, and each CIF is nondecreasing. The implementation checks these invariants at every month. The synthetic constant-hazard test independently calculates the closed-form cause incidence and checks two causes plus delayed entry.

The Cox baseline cumulative hazard is a Breslow step function with event-time jumps. The code evaluates it on integer month boundaries and treats the difference between consecutive boundary values as the integrated hazard for the preceding month. This is an explicit smoothing/interpolation assumption: the monthly data identify the jump by reporting month, not the exact event time within that month. The recursion preserves the fitted total hazard survival `exp(−H_1−H_2)` at the boundaries but allocates cause-specific incidence using the continuous exponential within-month assumption. It is therefore **not** the discrete AJ update `ΔF_k=S(t−1)d_k/Y(t)`, and the two need not agree exactly.

For a loan with entry `e`, `active = (entry < t)` excludes intervals ending at or before e; accumulation starts with conditional survival 1 at entry. The reported CIF is therefore `P(T≤h, J=k | T>e, covariates)` under the fitted hazards and the model’s event-free-through-entry assumption. No incidence before entry is predicted. Calling this unconditional-from-FPD for a delayed entrant would be incorrect.

## 4. Delayed entry, risk sets, and endpoints

- The analysis clock is calendar month distance from FPD, with first month represented by duration 1. The generated cohort has no row whose last performance month is before FPD; the artificial minimum one-month censor guard in `last_time` therefore does not change this dataset’s cohort results.
- 2,736 retained loans have positive delayed entry. Cox uses `entry_col`; AJ and concordance use the same strict risk condition `entry < t`; CIF starts after the entry month; Brier excludes `entry >= h`. The implementation is internally consistent on these definitions.
- This is left truncation, not evidence of no prior delinquency. For the 2,736 late entrants, the first available performance month is treated as the start of observed risk. The data do not establish that they were event-free between FPD and first performance. Inference requires suitable independent truncation/observation and correct event-free-at-entry assumptions.
- Twenty loans were excluded because their zero-balance effective date precedes FPD: 19 code `01`, one code `96`. Their competing exit precedes the declared time origin; including them as at-risk after FPD would contradict the endpoint clock. This exclusion is recorded in the cohort construction audit.
- Thirty loans have 90+ and zero-balance recorded in the same reporting month. Their order is not identifiable from monthly data. Primary coding assigns all 30 to cause 2; the tie sensitivity assigns them to cause 1. This is transparent sensitivity handling, not a confirmed event ordering.
- AJ risk sets are `entry < t` and `duration >= t`, including event-time subjects in the denominator; simultaneous event causes update together. Competing exits are not treated as target events. Correct interpretation of Cox/AJ with delayed entry still relies on an appropriate truncation mechanism, which cannot be established from these data.

## 5. Numerical reconciliation

### Cohort, splits, and ranking

| Analysis | N train / test | Train causes (censor, 90+, competing) | Test causes (censor, 90+, competing) | C-index | Comparable pairs |
|---|---:|---:|---:|---:|---:|
| Full analysis cohort | 49,980 | — | 10,656 / 2,019 / 37,305 | — | — |
| Seeded random split | 39,984 / 9,996 | 8,524 / 1,615 / 29,845 | 2,132 / 404 / 7,460 | 0.7511890 | 2,277,701 |
| FPD calendar holdout | 41,908 / 8,072 | 8,889 / 1,642 / 31,377 | 1,767 / 377 / 5,928 | 0.7511710 | 1,849,210 |
| CLTV sensitivity | 39,984 / 9,996 | 8,524 / 1,615 / 29,845 | 2,132 / 404 / 7,460 | 0.7524864 | 2,277,701 |
| Tie-as-event sensitivity | 39,984 / 9,996 | 8,524 / 1,639 / 29,821 | 2,132 / 410 / 7,454 | 0.7535333 | 2,324,363 |

The random C-index 100-resample interval is [0.7332938, 0.7741705]; the calendar interval is [0.7350544, 0.7696978]. Both bootstrap CSVs record 100 successful replicates. These intervals quantify test-sample resampling conditional on fixed fitted models, not fit, split, or cohort uncertainty.

### Observed full-cohort AJ at reported horizons

| Month | Event-free survival | CIF 90+ | CIF competing exit |
|---:|---:|---:|---:|
| 12 | 0.934110 | 0.001340 | 0.064550 |
| 24 | 0.831960 | 0.004961 | 0.163079 |
| 36 | 0.745167 | 0.008820 | 0.246012 |
| 60 | 0.523278 | 0.026182 | 0.450541 |
| 120 | 0.221992 | 0.039847 | 0.738162 |

These are full-cohort descriptive AJ estimates, not a holdout benchmark. They agree with the rounded table in `reports/research_report.md`.

### Random holdout Brier and calibration

| Month | IPCW Brier* | Cox known-status Brier | Train-AJ known-status reference | Cox−AJ, paired 95% CI | Known / eligible | Mean predicted / observed CIF IPCW |
|---:|---:|---:|---:|---:|---:|---:|
| 12 | 0.00123357 | 0.00123357 | 0.00123407 | −0.00000050 [−0.00000406, 0.00000210] | 9,712 / 9,712 | 0.001324 / 0.001236 |
| 24 | 0.00467203 | 0.00467203 | 0.00470679 | −0.00003477 [−0.00007189, −0.00001247] | 9,727 / 9,727 | 0.004892 / 0.004729 |
| 36 | 0.00864022 | 0.00864022 | 0.00875057 | −0.00011035 [−0.00016928, −0.00005155] | 9,741 / 9,741 | 0.008630 / 0.008829 |
| 60 | 0.02418603 | 0.02418603 | 0.02485696 | −0.00067092 [−0.00091904, −0.00037259] | 9,996 / 9,996 | 0.026151 / 0.025510 |
| 120 | 0.03702374 | 0.03705184 | 0.03817065 | −0.00111880 [−0.00158403, −0.00070546] | 9,988 / 9,996 | 0.039624 / 0.039737 |

\*IPCW uses the eligible denominator and inverse censoring weights. At 12–60 months, fitted `G(h−)=1`; at 120 months `G(h−)=0.998746`, maximum weight 1.00126, effective sample size 9,987.997, and eight test censors precede h. `G≈1` is numerical support under the fitted marginal reverse-KM, **not** evidence that censoring is independent.

### Calendar holdout Brier reconciliation

| Month | IPCW Brier* | Cox known-status Brier | Train-AJ reference | Cox−AJ, paired 95% CI | Known / eligible |
|---:|---:|---:|---:|---:|---:|
| 12 | 0.00200510 | 0.00200510 | 0.00201170 | −0.00000660 [−0.00001118, −0.00000160] | 7,940 / 7,940 |
| 24 | 0.00979420 | 0.00979420 | 0.00986258 | −0.00006838 [−0.00009868, −0.00003983] | 7,959 / 7,959 |
| 36 | 0.01185266 | 0.01185266 | 0.01201432 | −0.00016165 [−0.00022986, −0.00008855] | 7,986 / 7,986 |
| 60 | 0.03807786 | 0.03807786 | 0.03916082 | −0.00108297 [−0.00134899, −0.00079157] | 8,072 / 8,072 |
| 120 | 0.04295835 | 0.04306506 | 0.04446867 | −0.00140362 [−0.00184130, −0.00108221] | 8,052 / 8,072 |

\*The training reverse-KM has no censoring before these horizons in this later cohort’s analysis times. At 120 months, 20 test loans are censored before h. Consequently IPCW and known-status Brier differ in their denominator/estimand; this is a useful diagnostic of the unsupported administrative-censoring assumption, not a reason to select the smaller value.

### Sensitivity numbers

| Model / event rule | C-index | IPCW Brier at 12 / 24 / 36 / 60 / 120 months |
|---|---:|---|
| Primary LTV; same-month ties competing | 0.751189 | 0.00123357 / 0.00467203 / 0.00864022 / 0.02418603 / 0.03702374 |
| CLTV instead of LTV | 0.752486 | 0.00123350 / 0.00467249 / 0.00863992 / 0.02416842 / 0.03697559 |
| 30 ties assigned to cause 1 | 0.753533 | 0.00123357 / 0.00477114 / 0.00913230 / 0.02472064 / 0.03752610 |

The research report’s rounded counts, AJ values, primary and sensitivity point estimates, prediction averages, and paired intervals agree with regenerated files. The Task 3 calendar metrics also agree. The distinct comparable-pair counts above are verified from their respective `model_metrics.json` files. Differences between IPCW and known-status scores are intentional because their weighting/denominators differ, especially at 120 months.

## 6. Validation claims, confirmed bugs, and limitations

### Critical

- None found that invalidates the implemented cohort counts, Cox ranking, CIF recursion under its stated hazard interpolation, AJ point estimates, or score arithmetic.

### Major

- **CIF estimand / within-month interpolation (methodological assumption, not an arithmetic defect):** Cox baseline hazard jumps occur at reported event months. Treating each monthly difference as a constant continuous hazard over the interval yields a coherent model-based CIF, but it is not the discrete-time AJ probability update. Final prose should call it a piecewise-constant within-month hazard approximation and avoid implying that the model-based CIF is the unique exact monthly event probability.
- **Marginal IPCW and administrative censoring (methodological limitation):** Reverse-KM IPCW requires censoring independent of event time conditional on the risk-entry structure assumed by the model. With all 10,656 censored subjects ending at 2026-03, follow-up from FPD is mechanically tied to calendar entry. The near-unit weights do not validate that assumption. Label all IPCW values assumption-dependent and show known-status scores alongside them.
- **Temporal-validation scope (interpretation):** Later FPD cohorts are almost entirely 2016 and remain in the same source sample. The 2015 training outcomes use follow-up through 2026. Do not call this external validation or a historical deployment simulation.

### Minor

- **Calibration uncertainty:** Global and quintile calibration are point estimates; no confidence intervals are produced. Brier is a squared-probability error metric, not a calibration statistic by itself. Describe discrimination (C-index), probability accuracy (Brier), and calibration summaries separately.
- **Bootstrap scope:** The 100-replicate intervals hold the model and preprocessing fixed (and hold the AJ reference fixed for paired comparisons); they do not capture fitting, selection, or split uncertainty. This scope is stated in generated CSVs and should remain in the report.
- **Scoring API horizons before delayed entry:** `integrate_competing_cumulative_hazards()` returns zero for a requested horizon at or before a loan’s entry, because no post-entry interval has accumulated. Evaluation excludes `entry >= h`, and the production evaluation horizons exceed observed entries, so this does not alter current metrics. Callers should not interpret a pre-entry zero as an estimated risk; input validation/documentation could make this edge case clearer.

### Limitations

- Independent left truncation and no unobserved target/competing event before first observed performance are unverified.
- Monthly timestamps cannot identify the order of the 30 same-month 90+ / zero-balance pairs.
- A single 2015 sample cannot establish external or vintage transport. Only 12 loans in the temporal test start in 2017 or later.
- Schoenfeld trend output is explicitly approximate; the standard scaled-residual test is unavailable for this delayed-entry fit. It is a screening diagnostic, not proof of proportional hazards.

## 7. Files changed and tests run

Task 4 adds this audit report. No model code, event definition, configuration, or tests were changed in this audit. Reproducibility runs regenerated the existing primary outputs under `outputs/models/`, `outputs/survival_dataset.csv`, `reports/tables/`, and `reports/data_audit.*`; the calendar run regenerated `outputs/models_temporal_validation/` and `reports/tables_temporal_validation/`. Existing Task 1–3 workspace changes were preserved. No commit or push was made.

Commands actually run for this audit:

```text
python src/survival_pipeline.py --bootstrap 100             # completed; primary metrics reproduced
python src/temporal_validation.py --bootstrap 100            # completed; calendar metrics reproduced
python -m unittest discover -s tests -v                      # 24 passed
python -m py_compile src/survival_pipeline.py src/temporal_validation.py src/eda.py
python -m json.tool config/analysis_config.json
git diff --check                                             # passed; Git emitted line-ending notices only
```

The existing synthetic tests already cover the mathematical properties required here: `test_piecewise_competing_hazards_match_constant_hazard_analytic_solution` derives both cause CIFs from constant cause-specific hazards and checks probability conservation with a delayed entrant; `test_aalen_johansen_exact_monthly_ties_and_probability_invariants` independently hand-computes tied monthly AJ updates; `test_conditional_training_aj_reference_hand_calculation` hand-checks conditioning; `test_left_truncated_concordance_hand_calculation` hand-checks comparable pairs; and Brier tests hand-check event, censor, competing-event, horizon, and delayed-entry boundaries. No additional synthetic test was necessary, and no test was removed or weakened.

## 8. Residual items before finalizing the research report

1. Keep the continuous-time within-month hazard conversion explicit in the CIF method and figure captions; reserve “exact” for the exponential update **conditional on that interpolation assumption**.
2. Keep IPCW and known-status Brier results separate and visibly label IPCW as assumption-dependent. Do not treat the IPCW score as unbiased for the full cohort merely because `G` and weights are close to one.
3. Keep the calendar analysis labeled as internal later-cohort validation. External/vintage validation and a historical as-of development design remain unavailable in the current data.
4. State that calibration values are descriptive point summaries and that the bootstrap does not refit the model or account for split uncertainty.
5. No code correction or artifact regeneration beyond the executed reproducibility runs is required by this audit. If the above interpretation/claim wording is retained, the central reported statistical results can be finalized with their assumptions and limitations visible.
