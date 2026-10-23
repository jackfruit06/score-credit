"""Tạo bảng và biểu đồ thăm dò cho cohort sống còn cấp khoản vay."""
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
    # Áp dụng các mã đặc biệt đã được tài liệu hóa trước khi tóm tắt số liệu.
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
    # Phân bố thời gian theo dõi.
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(df.event_time_months, bins=np.arange(0, df.event_time_months.max() + 6, 6), color="#477998", edgecolor="white")
    ax.set(xlabel="Số tháng từ First Payment Date", ylabel="Số khoản vay", title="Thời lượng theo dõi quan sát được")
    ax.grid(axis="y", alpha=.25); fig.tight_layout(); fig.savefig(figure_dir / "followup_duration.png", dpi=160); plt.close(fig)
    # KM net theo nguyên nhân, kiểm duyệt các lần kết thúc cạnh tranh; ghi rõ cách diễn giải.
    km = KaplanMeierFitter()
    km.fit(df.event_time_months, event_observed=df.event_a_90plus, entry=df.delayed_entry_months, label="Survival net theo nguyên nhân")
    fig, ax = plt.subplots(figsize=(8, 5))
    km.plot_survival_function(ax=ax, ci_show=True)
    ax.set(xlabel="Số tháng từ First Payment Date", ylabel="Survival net", title="Trạng thái 90+: Kaplan–Meier theo nguyên nhân")
    ax.text(.02, .03, "Các lần kết thúc cạnh tranh được kiểm duyệt; 1−S không phải CIF thực tế.", transform=ax.transAxes, fontsize=8)
    ax.grid(alpha=.25); fig.tight_layout(); fig.savefig(figure_dir / "km_net_survival_90plus.png", dpi=160); plt.close(fig)
    # CIF AJ phi tham số, giữ một nguyên nhân kết thúc tổng hợp cho kết quả CIF đích.
    aj = aalen_johansen_cif(df.event_time_months.to_numpy(), df.delayed_entry_months.to_numpy(), df.event_cause.to_numpy())
    aj.to_csv(table_dir / "aalen_johansen_cif_full.csv", index=False)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.step(aj.time_months, aj.cif_cause_1, where="post", label="Lần đầu trạng thái 90+")
    ax.step(aj.time_months, aj.cif_cause_2, where="post", label="Mọi lần kết thúc zero-balance")
    ax.step(aj.time_months, aj.survival_all, where="post", label="Survival chưa gặp biến cố")
    ax.set(xlabel="Số tháng từ First Payment Date", ylabel="Xác suất", title="Ước lượng Aalen–Johansen có delayed entry")
    ax.set_ylim(0, 1); ax.grid(alpha=.25); ax.legend(); fig.tight_layout()
    fig.savefig(figure_dir / "aalen_johansen_cif.png", dpi=160); plt.close(fig)
    # CIF mô tả theo tình trạng cư trú; các nhóm không phải so sánh nhân quả.
    fig, ax = plt.subplots(figsize=(8, 5))
    for occupancy, group in df.groupby("occupancy_status"):
        ajg = aalen_johansen_cif(group.event_time_months.to_numpy(), group.delayed_entry_months.to_numpy(), group.event_cause.to_numpy())
        ax.step(ajg.time_months, ajg.cif_cause_1, where="post", label=f"{occupancy} (n={len(group):,})")
    ax.set(xlabel="Số tháng từ First Payment Date", ylabel="CIF: lần đầu trạng thái 90+", title="CIF mô tả theo tình trạng cư trú")
    ax.set_ylim(0, None); ax.grid(alpha=.25); ax.legend(); fig.tight_layout()
    fig.savefig(figure_dir / "cif_by_occupancy.png", dpi=160); plt.close(fig)
    by_cause = df.groupby("event_cause").size().rename("n").to_frame()
    by_cause["share"] = by_cause.n / len(df)
    by_cause.to_csv(table_dir / "event_cause_distribution.csv")
    text = ["# Phân tích dữ liệu thăm dò", "",
            f"Cohort gồm {len(df):,} khoản vay. Nguyên nhân biến cố được mã hóa 0=kiểm duyệt phải, 1=lần đầu quá hạn 90+, và 2=kết thúc zero-balance.",
            f"Số lượng theo nguyên nhân: {summary['cause_counts']}. Delayed entry áp dụng cho {summary['delayed_entry_n']:,} khoản vay.",
            f"Số khoản vay bị loại vì ngày zero-balance effective date trước First Payment Date: {construction.get('loans_excluded_terminal_before_time_origin', 'không có thông tin')}.",
            f"Tháng performance đầu tiên so với First Payment Date: {construction.get('first_performance_month_relative_to_time_origin', 'không có thông tin')}.",
            f"Trung vị thời gian theo dõi quan sát là {summary['followup_months']['median']:.0f} tháng; tối đa {summary['followup_months']['max']} tháng.",
            "Chỉ chuyển mã đặc biệt thành thiếu dữ liệu ở các trường đã được tài liệu hóa. VantageScore 4.0 hoàn toàn không có trong cohort này.",
            "Biểu đồ Kaplan–Meier coi các lần kết thúc cạnh tranh là kiểm duyệt và mô tả survival net theo nguyên nhân. Biểu đồ Aalen–Johansen ước lượng CIF quan sát bằng risk set delayed entry.",
            "Các đường cong theo tình trạng cư trú mang tính mô tả, không hàm ý quan hệ nhân quả.", "",
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
