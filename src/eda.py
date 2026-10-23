"""Exploratory tables and plots for the loan-level survival cohort."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lifelines import KaplanMeierFitter

from survival_pipeline import ROOT, SENTINELS, aalen_johansen_cif


def run_eda(data_path: Path, reports: Path, outputs: Path) -> None:
    reports.mkdir(parents=True, exist_ok=True)
    table_dir, figure_dir = reports / "tables", reports / "figures"
    table_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(data_path, dtype=str, keep_default_na=False)
    # Apply documented special codes before numeric summaries.
    for col, sentinels in SENTINELS.items():
        if col in df:
            df[col] = df[col].replace(list(sentinels), "")
    num = ["classic_fico", "original_ltv", "original_cltv", "original_dti", "original_upb",
           "original_interest_rate", "original_loan_term", "mi_percentage"]
    for col in num:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    numeric_summary = df[num].describe(percentiles=[.01, .25, .5, .75, .99]).T
    numeric_summary["missing_pct"] = df[num].isna().mean().values
    numeric_summary.to_csv(table_dir / "origination_numeric_summary.csv")
    df[num].corr(method="spearman").to_csv(table_dir / "origination_spearman.csv")
    categorical = ["occupancy_status", "loan_purpose", "property_type", "first_time_homebuyer",
                   "channel", "number_of_borrowers", "number_of_units"]
    cat_rows = []
    for col in categorical:
        for level, n in df[col].replace("", "<MISSING>").value_counts(dropna=False).items():
            cat_rows.append({"variable": col, "level": level, "n": int(n), "share": float(n / len(df))})
    pd.DataFrame(cat_rows).to_csv(table_dir / "categorical_distributions.csv", index=False)
    df["event_cause"] = pd.to_numeric(df.event_cause).astype(int)
    df["event_time_months"] = pd.to_numeric(df.event_time_months).astype(int)
    df["delayed_entry_months"] = pd.to_numeric(df.delayed_entry_months).astype(int)
    df["event_a_90plus"] = pd.to_numeric(df.event_a_90plus).astype(int)
    summary = {"n_loans": len(df), "cause_counts": {str(k): int(v) for k, v in df.event_cause.value_counts().sort_index().items()},
               "event_a_count": int(df.event_a_90plus.sum()), "delayed_entry_n": int((df.delayed_entry_months > 0).sum()),
               "followup_months": {"median": float(df.event_time_months.median()), "p25": float(df.event_time_months.quantile(.25)),
                                   "p75": float(df.event_time_months.quantile(.75)), "max": int(df.event_time_months.max())},
               "missing_pct_after_sentinel_conversion": {c: float(df[c].isna().mean()) for c in num}}
    (table_dir / "eda_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    construction_path = outputs / "survival_dataset_summary.json"
    construction = json.loads(construction_path.read_text(encoding="utf-8")) if construction_path.exists() else {}
    # Follow-up distribution.
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(df.event_time_months, bins=np.arange(0, df.event_time_months.max() + 6, 6), color="#477998", edgecolor="white")
    ax.set(xlabel="Months from First Payment Date", ylabel="Loans", title="Observed follow-up duration")
    ax.grid(axis="y", alpha=.25); fig.tight_layout(); fig.savefig(figure_dir / "followup_duration.png", dpi=160); plt.close(fig)
    # Cause-specific net KM, censoring competing exits; label its interpretation.
    km = KaplanMeierFitter()
    km.fit(df.event_time_months, event_observed=df.event_a_90plus, entry=df.delayed_entry_months, label="Cause-specific net survival")
    fig, ax = plt.subplots(figsize=(8, 5))
    km.plot_survival_function(ax=ax, ci_show=True)
    ax.set(xlabel="Months from First Payment Date", ylabel="Net survival", title="90+ status: cause-specific Kaplan–Meier")
    ax.text(.02, .03, "Competing terminations are censored; 1−S is not the real-world CIF.", transform=ax.transAxes, fontsize=8)
    ax.grid(alpha=.25); fig.tight_layout(); fig.savefig(figure_dir / "km_net_survival_90plus.png", dpi=160); plt.close(fig)
    # Nonparametric AJ CIF, retaining a single composite terminal cause for the CIF target.
    aj = aalen_johansen_cif(df.event_time_months.to_numpy(), df.delayed_entry_months.to_numpy(), df.event_cause.to_numpy())
    aj.to_csv(table_dir / "aalen_johansen_cif_full.csv", index=False)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.step(aj.time_months, aj.cif_cause_1, where="post", label="First 90+ status")
    ax.step(aj.time_months, aj.cif_cause_2, where="post", label="Any zero-balance termination")
    ax.step(aj.time_months, aj.survival_all, where="post", label="Event-free survival")
    ax.set(xlabel="Months from First Payment Date", ylabel="Probability", title="Aalen–Johansen estimates with delayed entry")
    ax.set_ylim(0, 1); ax.grid(alpha=.25); ax.legend(); fig.tight_layout()
    fig.savefig(figure_dir / "aalen_johansen_cif.png", dpi=160); plt.close(fig)
    # Descriptive occupancy-specific CIFs; groups are not causal comparisons.
    fig, ax = plt.subplots(figsize=(8, 5))
    for occupancy, group in df.groupby("occupancy_status"):
        ajg = aalen_johansen_cif(group.event_time_months.to_numpy(), group.delayed_entry_months.to_numpy(), group.event_cause.to_numpy())
        ax.step(ajg.time_months, ajg.cif_cause_1, where="post", label=f"{occupancy} (n={len(group):,})")
    ax.set(xlabel="Months from First Payment Date", ylabel="CIF: first 90+ status", title="Descriptive CIF by occupancy")
    ax.set_ylim(0, None); ax.grid(alpha=.25); ax.legend(); fig.tight_layout()
    fig.savefig(figure_dir / "cif_by_occupancy.png", dpi=160); plt.close(fig)
    by_cause = df.groupby("event_cause").size().rename("n").to_frame()
    by_cause["share"] = by_cause.n / len(df)
    by_cause.to_csv(table_dir / "event_cause_distribution.csv")
    text = ["# Exploratory data analysis", "",
            f"The cohort contains {len(df):,} loans. Event causes are coded 0=right-censored, 1=first 90+ delinquency, and 2=zero-balance termination.",
            f"Cause counts: {summary['cause_counts']}. Delayed entry applies to {summary['delayed_entry_n']:,} loans.",
            f"Loans excluded for zero-balance effective dates before First Payment Date: {construction.get('loans_excluded_terminal_before_time_origin', 'not recorded')}.",
            f"First performance month relative to First Payment Date: {construction.get('first_performance_month_relative_to_time_origin', 'not recorded')}.",
            f"Median observed follow-up is {summary['followup_months']['median']:.0f} months; maximum is {summary['followup_months']['max']} months.",
            "Special codes were converted to missing only for documented fields. VantageScore 4.0 is entirely unavailable in this cohort.",
            "The Kaplan–Meier plot treats competing exits as censored and describes cause-specific net survival. The Aalen–Johansen plot estimates observed CIFs under delayed-entry risk sets.",
            "Occupancy-specific curves are descriptive and do not imply causal effects.", "",
            "![Follow-up](figures/followup_duration.png)", "", "![Aalen–Johansen CIF](figures/aalen_johansen_cif.png)", "",
            "![CIF by occupancy](figures/cif_by_occupancy.png)", ""]
    (reports / "eda.md").write_text("\n".join(text), encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data", type=Path, default=ROOT / "outputs" / "survival_dataset.csv")
    p.add_argument("--reports", type=Path, default=ROOT / "reports")
    p.add_argument("--outputs", type=Path, default=ROOT / "outputs")
    a = p.parse_args()
    run_eda(a.data, a.reports, a.outputs)


if __name__ == "__main__":
    main()
