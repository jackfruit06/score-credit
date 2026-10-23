# Pipeline audit — implementation findings

This audit followed the path `raw origination/performance files -> audit_data() -> build_survival_data() -> train/test split and train-only preprocessing -> two cause-specific Cox fits -> competing_cox_cif() -> IPCW evaluation/bootstrap -> tables, plots and model bundle`. No raw input or remote repository was modified.

## Findings

| Type | Severity | Finding and evidence | Result impact / handling |
|---|---|---|---|
| Confirmed cohort-time bug | High | Twenty zero-balance effective dates occur before First Payment Date. The prior builder forced these pre-origin exits to month 1 using `max(entry + 1, ...)`, even though an exit before the time origin cannot be a post-origin competing event. | Exclude these loans from the risk cohort and report counts/codes. Event definition and time origin remain unchanged. |
| Confirmed IPCW bug | High | The old Brier code silently set weights to zero whenever estimated censor survival was `<= 0.05`. These observations remained in the denominator, which can bias the score downward and hides a lack of support. | Remove the hard cutoff. Retain all finite weights, report maximum weight/effective sample size, and return NaN if required support is zero. |
| Confirmed delayed-entry IPCW defect | Moderate | The old score used `1/G(u-)` but predictions and the target metric are conditional on having entered at `e`; the conditional censor survival is `G(u-)/G(e-)`. | Conditionalize each weight on its entry survival. Validate with a hand-calculated delayed-entry case. |
| Boundary ambiguity | Moderate | The old `duration <= t` event/competing masks overlapped with `duration >= t` controls at exactly `t`. Under the previous code both branches happened to use the same `G(t-)`, so this overlap did not change the current numeric weight, but the group assignment was ambiguous and fragile. | Make mutually exclusive labels; define the reporting-month endpoint convention and test primary event, competing event, and censor at `t`. |
| Coverage gap | Moderate | The model evaluation horizon list stopped at 60 months despite follow-up reaching 134 months and the analysis request including 120 months. | Add the 120-month CIF, Brier/calibration output, and support diagnostics; long-horizon validity remains conditional on censoring assumptions. |
| Data limitation | Moderate | The two raw files contain 50,000 IDs and 3,467,166 monthly performance rows; two loan-month calendar intervals are missing. | Preserve the observed-month endpoint convention and flag the gaps in data audit; no imputation of unobserved statuses. |
| Statistical risk | Moderate | Performance closes at a shared calendar end; relative follow-up and censoring can depend on First Payment Date. Marginal IPCW assumes censoring independent conditional on delayed entry and may not fully capture calendar-dependent administrative censoring. | State the assumption, report support diagnostics, interpret 120-month score cautiously; do not claim external validity. |
| Confirmed PH caveat | Moderate | PH diagnostic is a custom correlation trend of approximate unscaled Schoenfeld residuals; lifelines scaled residual routine does not support the entry-column fit. | Keep diagnostic labeled approximate; no model redesign in this audit. |
| Exploratory scripts | Low | `inspect_events.py` counts any-ever 90+ and any zero-balance code without ordering them; `inspect_data.py` skips short malformed performance rows. | Neither script defines model outcomes. The strict `audit_data()` and `build_survival_data()` implementations are authoritative for the pipeline; the inspection scripts remain quick diagnostics. |
| Artifact / reproducibility | Low | `.gitignore` excludes `outputs/**`, including survival CSV and model pickle, and excludes `reports/tables/**` and figures. CLTV artifacts use sibling names (`tables_cltv`, `figures_cltv`) and are not covered by those exact patterns. | Recreate outputs from commands; identify ignored artifacts in run log and final summary. |

## Statistical calculations checked

For cause (k), the monthly predicted CIF update combines all cause-specific monthly cumulative-hazard increments: total interval failure is (1-e^{-\sum_k\Delta H_k}); each cause receives its share (Delta H_k/\sum_k\Delta H_k). The implementation checks finite/nonnegative increments and the identity (S+\sum_kF_k=1). A separate synthetic test compares the update against the closed form for constant cause hazards.

The observed estimator is discrete monthly Aalen–Johansen with risk set (Y(t)=\#\{i:E_i<t\leq T_i\}); all tied cause counts are updated simultaneously. Test coverage checks exact tied-event values, left-truncation exclusion, monotonic CIFs, and probability sum invariants. Full-cohort AJ and conditional model predictions are not interchangeable: AJ is a cohort-level nonparametric estimate, while model outputs condition on surviving event-free to each loan's delayed-entry month.

For target cause 1, the evaluated binary status is (Y_i(t)=I(T_i\leq t,J_i=1)). Competing exits by (t) are observed negatives. Right-censoring strictly before (t) has unknown status and no direct loss. Under the code's month-end convention, primary/competing events at (t) are known by (t), and a right-censor at the end of a month (t) is known event-free through that month. The IPCW score is

\[
\widehat{BS}(t)=\frac{1}{n_t}\sum_{i:E_i<t} W_i(t)\{Y_i(t)-\hat F_{1i}(t)\}^2,
\]

where (W_i=G(E_i^-)/G(T_i^-)) for an observed primary/competing event by (t), (W_i=G(E_i^-)/G(t^-)) for a loan known event-free through (t), and (W_i=0) for censoring before (t). (G) is the reverse-Kaplan–Meier censor-survival estimate fitted on training loans with delayed entry. This targets the eligible test-loan average under independent censoring conditional on entry. It is not robust to dependent censoring or unsupported horizons. This follows cause-specific competing-risk prediction-error formulations such as [Schoop et al. (2011)](https://doi.org/10.1002/bimj.201000073), [van Geloven et al. (2022)](https://www.bmj.com/content/377/bmj-2021-069249), and IPCW Brier methodology in [Gerds & Schumacher (2006)](https://doi.org/10.1002/bimj.200610301). The score is not silently clipped at an arbitrary minimum survival probability.

## Brier synthetic checks

The 10 Brier tests in `tests/test_survival_pipeline.py` use explicit expected statuses and weights (all weights conditionalized on entry):

| Case | Input and horizon | Expected target labels | Expected weights | Expected score |
|---|---|---|---|---:|
| Target event and known control | (T=(2,4), J=(1,0), t=3, p=(.8,.2), G=1) | (1,0) | (1,1) | .0400 |
| Competing event and control | (T=(2,4), J=(2,0), t=3, p=(.2,.3), G=1) | (0,0) | (1,1) | .0650 |
| Censor before horizon | Test (T=(3,4,2),J=(1,0,0),t=3,p=(.8,.2,.9)); train reverse-KM (G(3-)=.5) | (1,0,0) | (2,2,0) | .05333 |
| Target at horizon | (T=3,J=1,t=3,p=.7,G=1) | (1) | (1) | .0900 |
| Competing at horizon | (T=3,J=2,t=3,p=.7,G=1) | (0) | (1) | .4900 |
| Censor at horizon | (T=3,J=0,t=3,p=.3,G=1); observed month-end status is known | (0) | (1) | .0900 |
| No event by horizon | (T=(4,5),J=(0,2),t=3,p=(.1,.2),G=1) | (0,0) | (1,1) | .0250 |
| Delayed entry | (E=(2,2), T=(3,5),J=(1,0),t=4,p=(.8,.2), G(2-)=G(3-)=.5) | (1,0) | (1,1) | .0400 |
| No censor support | all reverse-KM support exhausted before required status | — | — | NaN |
| Large but finite weights | train has 24/25 censor events at 2, so (G(4-)=.04); (T=(4,6),J=(1,0),t=4,p=(.8,.2)) | (1,0) | (25,25) | 1.0000 |

No expected value is computed by calling the function under test. The final test command reported 16 tests, all passing.

## Empirical result comparison

| Run | Cohort / split | C-index | Brier 12m | 24m | 36m | 60m | 120m |
|---|---|---:|---:|---:|---:|---:|---:|
| Previously reported pipeline | 50,000 loans; previous seed-2026 80/20 split | 0.751509 | 0.001234 | 0.004675 | 0.008646 | 0.024242 | not calculated |
| Audited primary | 49,980 loans after excluding 20 pre-origin terminations; 80/20 split | 0.751189 | 0.001234 | 0.004672 | 0.008640 | 0.024186 | 0.037024 |
| CLTV sensitivity | Same audited cohort and split; CLTV replaces LTV | 0.752486 | 0.001233 | 0.004672 | 0.008640 | 0.024168 | 0.036976 |
| Tie-as-event sensitivity | Same audited cohort and exact primary train/test IDs; all 30 ties assigned cause 1 | 0.753533 | 0.001234 | 0.004771 | 0.009132 | 0.024721 | 0.037526 |

The old-vs-new primary differences combine the corrected cohort and updated evaluation implementation; they are not a clean isolated estimate of the effect of any one code change. At 12–60 months in the audited run, all conditional censor-survival weights are 1, so removing the old 0.05 cutoff does not alter those observed scores; the correction prevents silent bias at unsupported/lower-support horizons. At 120 months, (G(120^-)=0.998746), maximum weight is 1.00126, eight test loans were censored before the horizon, and all 100 bootstrap replicates were successful. The CLTV run used 20 bootstrap replicates; the tie sensitivity also used 20. The primary used 100.

## Executed commands and artifact provenance

- `python -m py_compile src/survival_pipeline.py src/eda.py`: exit code 0.
- `python -m unittest discover -s tests -v`: final run, 16 passed, 0 failed.
- `python src/survival_pipeline.py --bootstrap 100`: exit code 0; rebuilt the strict data audit, primary loan-level survival CSV/summary, primary Cox models/model bundle, metrics, bootstrap, tables and plots.
- `python src/survival_pipeline.py --cltv-sensitivity --bootstrap 20`: exit code 0; rebuilt the CLTV model bundle and `reports/tables_cltv/`, `reports/figures_cltv/` outputs.
- `python src/survival_pipeline.py --tie-as-event-sensitivity --bootstrap 20`: exit code 0; rebuilt same-split tie sensitivity outputs under `outputs/models_tie_sensitivity/`, `reports/tables_tie_sensitivity/`, and `reports/figures_tie_sensitivity/`.
- `python src/eda.py`: exit code 0; rebuilt EDA tables and figures from the audited 49,980-loan CSV.
- `git diff --check`: exit code 0 (only line-ending warnings were observed in earlier runs).

The raw input files are regular local files and are already tracked; they are not Git LFS pointers. `.gitignore` excludes `outputs/**`, `reports/tables/**`, and `reports/figures/**`, so the main regenerated survival CSV, fitted bundles, tables, and figures are present locally but ignored by Git. Sibling CLTV/tie folders are not matched by those exact ignore patterns. No commit or remote operation was performed.

