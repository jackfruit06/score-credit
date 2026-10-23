"""Prespecified calendar-cohort holdout using the existing Cox/AJ pipeline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from survival_pipeline import (ROOT, administrative_brier_terms, calendar_cohort_split,
                               load_analysis_config, load_model_bundle, run_model,
                               score_new_loans)


def calendar_entry_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Descriptive counts only; small late calendar cells remain visible."""
    data = df.copy()
    year = pd.to_numeric(data.first_payment_date, errors="raise").astype(int) // 100
    data["fpd_period"] = year.map(lambda y: str(y) if y < 2017 else "2017+")
    data["entry_group"] = pd.cut(data.delayed_entry_months, [-1, 0, 2, float("inf")],
                                 labels=["0", "1-2", "3+"])
    rows = []
    for dimension, groups in (("first_payment_year", data.groupby("fpd_period", observed=True)),
                              ("delayed_entry_months", data.groupby("entry_group", observed=True))):
        for label, group in groups:
            cause = group.event_cause
            rows.append({"dimension": dimension, "group": str(label), "n_loans": len(group),
                         "primary_events": int((cause == 1).sum()),
                         "competing_events": int((cause == 2).sum()),
                         "right_censored": int((cause == 0).sum()),
                         "delayed_entry_n": int((group.delayed_entry_months > 0).sum()),
                         "median_followup_months": float(group.event_time_months.median()),
                         "max_followup_months": int(group.event_time_months.max())})
    return pd.DataFrame(rows)


def main() -> None:
    config = load_analysis_config()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "outputs" / "survival_dataset.csv")
    parser.add_argument("--outputs", type=Path, default=ROOT / "outputs")
    parser.add_argument("--reports", type=Path, default=ROOT / "reports")
    parser.add_argument("--bootstrap", type=int, default=int(config["model"]["bootstrap_replicates"]))
    args = parser.parse_args()

    df = pd.read_csv(args.dataset)
    cutoff = str(config["model"]["temporal_split_first_payment_cutoff"])
    train_idx, test_idx = calendar_cohort_split(df.first_payment_date, cutoff)
    table_dir = args.reports / "tables_temporal_validation"
    table_dir.mkdir(parents=True, exist_ok=True)
    calendar_entry_summary(df).to_csv(table_dir / "calendar_entry_summary.csv", index=False)

    description = (f"Calendar-cohort holdout by First Payment Date: train <= {cutoff}, "
                   f"test > {cutoff}; test loans are later-starting cohorts within the same source sample. "
                   "This is not external validation and does not emulate a historical as-of training date.")
    metrics = run_model(df, args.outputs / "models_temporal_validation", table_dir,
                        args.reports / "figures_temporal_validation",
                        seed=int(config["model"]["seed"]), bootstrap_n=args.bootstrap,
                        split_indices=(train_idx, test_idx), split_description=description)
    # Descriptive, known-outcome test score by delayed-entry group. No subgroup
    # intervals are reported because later-entry event counts are small.
    test = df.iloc[test_idx].reset_index(drop=True)
    bundle = load_model_bundle(args.outputs / "models_temporal_validation" / "cause_specific_cox_models.pkl")
    predictions = score_new_loans(bundle, test, metrics["horizons_months"])
    test["entry_group"] = pd.cut(test.delayed_entry_months, [-1, 0, 2, float("inf")],
                                 labels=["0", "1-2", "3+"]).astype(str)
    entry_score_rows = []
    for j, horizon in enumerate(metrics["horizons_months"]):
        prediction = predictions[f"predicted_cif_first_90plus_{horizon}m"].to_numpy()
        _, known, outcome, losses = administrative_brier_terms(
            test.event_time_months, test.delayed_entry_months, test.event_cause,
            horizon, prediction)
        for group in ("0", "1-2", "3+"):
            mask = known & (test.entry_group.to_numpy() == group)
            entry_score_rows.append({"horizon_months": int(horizon), "delayed_entry_group": group,
                                     "known_outcomes_scored": int(mask.sum()),
                                     "primary_events_by_horizon": int((mask & (test.event_cause.to_numpy() == 1) &
                                                                         (test.event_time_months.to_numpy() <= horizon)).sum()),
                                     "administrative_brier_cox": float(np.mean(losses[mask])) if mask.any() else float("nan")})
    pd.DataFrame(entry_score_rows).to_csv(table_dir / "entry_group_administrative_brier.csv", index=False)
    metrics["calendar_split_cutoff_first_payment_date"] = cutoff
    metrics["calendar_split_scope"] = description
    (args.outputs / "models_temporal_validation" / "model_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"n_train": len(train_idx), "n_test": len(test_idx),
                      "train_events": int((df.iloc[train_idx].event_cause == 1).sum()),
                      "entry_group_scores": entry_score_rows,
                      "test_cause_counts": {str(k): int((df.iloc[test_idx].event_cause == k).sum()) for k in (0, 1, 2)},
                      "horizons": metrics["cif_brier_scores"],
                      "observed_status_benchmark": pd.read_csv(table_dir / "cif_administrative_benchmark.csv").to_dict("records")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
