# Task 3 — Robustness and calendar-cohort validation

## Scope

This task evaluates the existing two cause-specific Cox models and their CIF predictions. It does not select new predictors, tune a replacement model, or claim external validation. The primary test remains the seeded, stratified 80/20 loan-level split. Sensitivity analyses retain that split. A separately prespecified cohort split checks later First Payment Date (FPD) cohorts within this same Freddie Mac 2015 extract.

The primary outcome is first recorded 90+ delinquency (`03+`); zero-balance exits are competing events. The endpoint is a reporting proxy, not a legal default or realized loss. The data extend through 2026-03. All 10,656 right-censored loans end at that common reporting cutoff, so follow-up duration is tied to FPD/calendar time. Administrative censoring is therefore a material assumption for ordinary marginal IPCW. Administrative-censoring work documents bias under staggered entry and motivates scores based on known outcomes ([Kvamme & Borgan, 2023](https://www.jmlr.org/papers/volume24/19-1030/19-1030.pdf)); competing-risk prediction validation requires preserving competing outcomes and matching the target population ([van Geloven et al., BMJ 2022](https://www.bmj.com/content/377/bmj-2021-069249/full)).

## Primary holdout and Cox versus training Aalen–Johansen

The random holdout has 9,996 loans: 404 primary events, 7,460 competing exits, and 2,132 right-censored. Left-truncated Harrell C-index is 0.75119 (100-replicate fixed-model test bootstrap 95% interval 0.73329–0.77417). IPCW Brier scores are reported as assumption-dependent because calendar-dependent censoring independence is not established.

The fair reference is a delayed-entry Aalen–Johansen (AJ) curve estimated on training only, conditioned on each test loan's entry month, and scored alongside Cox on the same test loans with known horizon status. The table reports Cox minus this train-AJ reference; negative values favor Cox on squared error. The percentile intervals resample test loan IDs in pairs, with both fitted prediction systems fixed.

| Horizon (months) | Cox Brier, known status | Train-AJ Brier | Cox − AJ (paired 95% CI) | Known / eligible |
|---:|---:|---:|---:|---:|
| 12 | 0.00123357 | 0.00123407 | −0.00000050 [−0.00000406, 0.00000210] | 9,712 / 9,712 |
| 24 | 0.00467203 | 0.00470679 | −0.00003477 [−0.00007189, −0.00001247] | 9,727 / 9,727 |
| 36 | 0.00864022 | 0.00875057 | −0.00011035 [−0.00016928, −0.00005155] | 9,741 / 9,741 |
| 60 | 0.02418603 | 0.02485696 | −0.00067092 [−0.00091904, −0.00037259] | 9,996 / 9,996 |
| 120 | 0.03705184 | 0.03817065 | −0.00111880 [−0.00158403, −0.00070546] | 9,988 / 9,996 |

The random-split Cox score is lower than train-AJ at months 24–120; at month 12 the interval includes zero. This is evidence of better test-set squared error against this covariate-free reference on this split, not a broad superiority claim. Intervals omit model fitting, AJ fitting, split, and cohort uncertainty. The known-status score excludes eight loans censored before month 120.

## Horizon and censoring support

Primary IPCW CIF Brier values at 12/24/36/60/120 months are 0.00123357 / 0.00467203 / 0.00864022 / 0.02418603 / 0.03702374. At months 12–60 the fitted reverse-KM has no pre-horizon censoring; at month 120, `G(120−)=0.998746`, maximum weight is 1.00126, and effective sample size is about 9,988. The modest weights establish numerical support under the fitted marginal censoring model, not the independent-censoring assumption. The full cohort contains 65 loans with potential administrative follow-up under 120 months; the random test set has eight such unknown horizon statuses, and the later-cohort holdout has 20.

Each monthly outcome has at most one observed first event. Events or competing exits by the horizon are known; a censor before the horizon is unknown and excluded from the known-status Brier. A censor recorded at the horizon is known through that month under the project's endpoint convention. Detailed Brier terms and eligibility are in `reports/tables/cif_brier_scores.csv`; benchmark intervals and seeds are in `reports/tables/cif_administrative_benchmark.csv`.

## Calendar-cohort holdout

The cutoff is fixed at FPD 2015-12: train on starts through 2015-12 and test on later starts. This yields 41,908 training loans (1,642 primary events) and 8,072 test loans (377 primary events, 5,928 competing exits, 1,767 censored). Test C-index is 0.75117 over 1,849,210 comparable pairs. No fit warnings were recorded.

| Horizon | Test IPCW Brier* | Cox known-status Brier | Train-AJ reference | Cox − AJ (paired 95% CI) | Known / eligible |
|---:|---:|---:|---:|---:|---:|
| 12 | 0.00200510 | 0.00200510 | 0.00201170 | −0.00000660 [−0.00001118, −0.00000160] | 7,940 / 7,940 |
| 24 | 0.00979420 | 0.00979420 | 0.00986258 | −0.00006838 [−0.00009868, −0.00003983] | 7,959 / 7,959 |
| 36 | 0.01185266 | 0.01185266 | 0.01201432 | −0.00016165 [−0.00022986, −0.00008855] | 7,986 / 7,986 |
| 60 | 0.03807786 | 0.03807786 | 0.03916082 | −0.00108297 [−0.00134899, −0.00079157] | 8,072 / 8,072 |
| 120 | 0.04295835 | 0.04306506 | 0.04446867 | −0.00140362 [−0.00184130, −0.00108221] | 8,052 / 8,072 |

\*IPCW values require the same censoring assumptions. In this later-start cohort, 120-month known-status scoring excludes 20 loans censored before the horizon. All paired intervals use 100 successful test-loan resamples; seeds by horizon are 2028–2032. The score is consistently lower than train-AJ in this cohort, but the cohort is not external: 8,060 of 8,072 test loans have FPD in 2016 and only 12 start in 2017 or later. Further, the model trained on 2015 loans uses their completed outcomes through 2026, so this is not a historical as-of or prospective deployment simulation. Temporal validation methodology distinguishes later-time validation from independent external validation ([TRIPOD explanation](https://pmc.ncbi.nlm.nih.gov/articles/PMC4297220/)).

## Calendar and delayed-entry composition

| FPD group | Loans | 90+ events | Competing exits | Censored | Delayed entry |
|---|---:|---:|---:|---:|---:|
| 2015 | 41,908 | 1,642 | 31,377 | 8,889 | 2,310 |
| 2016 | 8,060 | 377 | 5,918 | 1,765 | 419 |
| 2017+ | 12 | 0 | 10 | 2 | 7 |

Across the full cohort, 47,244 enter at month zero, 1,182 at months 1–2, and 1,554 at month 3 or later. The later-entry strata contain only 45 and 36 primary events, respectively; subgroup comparisons are descriptive and should not be overread. A subgroup known-status Brier by delayed-entry category is saved in `reports/tables_temporal_validation/entry_group_administrative_brier.csv`; that table reports cell counts and point scores only, without intervals. Calendar and entry cell definitions are in `reports/tables_temporal_validation/calendar_entry_summary.csv`.

At 120 months in the calendar test cohort, the subgroup point scores are:

| Delayed-entry group | Known outcomes | 90+ events by 120m | Cox known-status Brier |
|---|---:|---:|---:|
| 0 months | 7,630 | 361 | 0.04367 |
| 1–2 months | 280 | 11 | 0.03758 |
| 3+ months | 142 | 3 | 0.02143 |

The apparent lower error in later-entry groups is based on few events and does not establish better subgroup calibration or transport. These strata are defined by observed performance-history entry, which may itself be selective.

## Existing sensitivity analyses

Both sensitivity runs use the same 39,984/9,996 random train/test split and were rerun with 100 bootstrap replicates.

| Analysis | Test C-index | IPCW Brier at 12 / 24 / 36 / 60 / 120 months |
|---|---:|---|
| Primary LTV; ties assigned to competing exit | 0.75119 | 0.00123357 / 0.00467203 / 0.00864022 / 0.02418603 / 0.03702374 |
| CLTV in place of LTV | 0.75249 | 0.00123350 / 0.00467249 / 0.00863992 / 0.02416842 / 0.03697559 |
| Same-month ties assigned to 90+ event | 0.75353 | 0.00123357 / 0.00477114 / 0.00913230 / 0.02472064 / 0.03752610 |

The CLTV change is small in ranking and scores. Reassigning the 30 ambiguous same-month cases increases test 90+ events from 404 to 410 and reduces competing exits from 7,460 to 7,454; scores rise most at 24–36 and 120 months, while the event definition is explicitly changed. These are robustness checks for those prespecified choices, not independent replications. The sensitivity metrics and paired AJ score files are in `outputs/models_cltv/model_metrics.json`, `outputs/models_tie_sensitivity/model_metrics.json`, `reports/tables_cltv/cif_administrative_benchmark.csv`, and `reports/tables_tie_sensitivity/cif_administrative_benchmark.csv`.

## Interpretation and limits

1. The Cox model improves on the train-only AJ reference in known-status Brier scores from 24 months onward in the random holdout, and at every assessed horizon in the later-cohort holdout. Month 12 random-split performance is effectively tied.
2. The small CLTV sensitivity and somewhat larger tie-rule sensitivity show that the main ranking/scores are not highly sensitive to replacing LTV with CLTV; the tie rule changes the endpoint and produces some score movement.
3. Results do not establish transport to another Freddie Mac vintage, another lender, contemporary lending, or deployment. The later holdout has little calendar separation and uses fully matured training labels.
4. Marginal reverse-KM IPCW cannot by itself correct deterministic administrative censoring by FPD. IPCW results are assumption-dependent; known-status scores target only subjects whose horizon status is observed. Neither score proves performance for all loans at 120 months.
5. Delayed-entry independence and whether loans were event-free before first observed performance remain unverified. Entry-stratum point scores are descriptive, with sparse event cells and no subgroup confidence intervals.
6. Bootstrap intervals are percentile paired resampling of test loan IDs (100 requested and successful per horizon), with Cox predictions and train-AJ curves held fixed. They do not include estimation, split, calendar cohort, or model-selection uncertainty.

## Reproduction and checks

```powershell
python src/survival_pipeline.py --bootstrap 100
python src/survival_pipeline.py --cltv-sensitivity --bootstrap 100
python src/survival_pipeline.py --tie-as-event-sensitivity --bootstrap 100
python src/temporal_validation.py --bootstrap 100
python -m unittest discover -s tests -v
```

The primary configuration and model were not optimized for this task. No commit or push was made. Machine-readable metrics, subgroup summaries, and plots accompany this report under `outputs/models_temporal_validation/`, `reports/tables_temporal_validation/`, and `reports/figures_temporal_validation/`.
