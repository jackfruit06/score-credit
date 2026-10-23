# Cox competing-risks analysis of Freddie Mac 2015 loans

This project studies the time to a loan's **first reported 90+ day delinquency status** in Freddie Mac's 2015 Single-Family Loan-Level Dataset sample. It is a research proxy, not a legal default or a realized credit-loss label. Zero-balance terminations are modeled as competing exits, with their source codes retained.

## Run

Use Python 3.10 or newer in the project directory:

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python src/survival_pipeline.py --bootstrap 100
python src/eda.py
```

The pipeline rebuilds the data audit and loan-level survival table, fits cause-specific Cox models, computes competing-risk CIFs and evaluation outputs, and saves a serializable model bundle. `--cltv-sensitivity` runs the prespecified sensitivity model with CLTV in place of LTV, saving to separate `outputs/models_cltv` and `reports/*_cltv` paths. Use `--orig`, `--perf`, `--outputs`, or `--reports` to change paths.

## Main files

- `src/survival_pipeline.py`: validation, event construction, Cox fitting, competing-risk estimation, metrics, bootstrap, plots, and scoring API.
- `src/eda.py`: descriptive analyses and plots.
- `config/analysis_config.json`: cohort, endpoint, time, split, and bootstrap choices.
- `tests/test_survival_pipeline.py`: synthetic tests for endpoint rules, delayed entry, tied events, CIF mathematics, model serialization/scoring, calendar months, and hand-checked concordance.
- `docs/data_dictionary.md`, `docs/methodology.md`: variable and method definitions.
- `reports/research_report.md`: results and interpretation; `reports/data_audit.md` and `reports/eda.md`: data checks and EDA.
- `outputs/survival_dataset.csv`: one row per loan; `outputs/models/cause_specific_cox_models.pkl`: fitted models and training preprocessing.

Scoring new loan origination rows is available through `load_model_bundle()` and `score_new_loans()` in `src/survival_pipeline.py`. Scores are conditional on remaining event-free through each loan's delayed-entry month. Do not apply this model outside the documented 2015 Freddie Mac sample without validation.

## Method in brief

The time origin is First Payment Date, measured in calendar months. Loans enter the risk set when their performance history first becomes observable (delayed entry). Cause 1 is the first monthly status `03` or higher; cause 2 is the first zero-balance termination of any code; right-censoring is cause 0. If the event and zero-balance exit occur in the same reporting month, ordering is unknowable, so the primary analysis treats the termination as competing and reports a tie sensitivity.

Two cause-specific Cox models estimate the event and competing-exit hazards. Their monthly cumulative-hazard increments are combined with an exact competing exponential update to estimate cause-specific CIFs; `1 - S_event` is not used as the event CIF. Evaluation uses delayed-entry Harrell concordance, IPCW Brier scores and calibration at 12, 24, 36, and 60 months, and fixed-model test-loan bootstrap intervals. Full details and assumptions are in `docs/methodology.md`.

## Data and references

The included files are Freddie Mac SFLLD Sample 2015, not LendingClub. Consult Freddie Mac's [dataset page](https://www.freddiemac.com/research/datasets/sf-loanlevel-dataset), [July 2026 General User Guide](https://www.freddiemac.com/fmac-resources/research/pdf/general_user_guide_july_2026.pdf), and [Release 47 disclosure changes](https://www.freddiemac.com/fmac-resources/research/pdf/disclosure-changes-summary.pdf). Follow the dataset's terms of use. Method references are Cox (1972), [Regression Models and Life-Tables](https://rss.onlinelibrary.wiley.com/doi/10.1111/j.2517-6161.1972.tb00899.x), and Aalen and Johansen (1978), [An empirical transition matrix for non-homogeneous Markov chains based on censored observations](https://gwern.net/doc/statistics/survival-analysis/1978-aalen.pdf).
