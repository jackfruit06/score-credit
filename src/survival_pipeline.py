"""Phân tích sống còn và biến cố cạnh tranh cho khoản vay Freddie Mac, có thể tái lập."""
from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import pickle
import warnings
from collections import Counter
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from lifelines import CoxPHFitter, KaplanMeierFitter
from scipy.stats import pearsonr, rankdata
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger("survival_pipeline")
ORIG_FIELDS = {
    "classic_fico": 0, "first_payment_date": 1, "first_time_homebuyer": 2,
    "maturity_date": 3, "msa": 4, "mi_percentage": 5, "number_of_units": 6,
    "occupancy_status": 7, "original_cltv": 8, "original_dti": 9,
    "original_upb": 10, "original_ltv": 11, "original_interest_rate": 12,
    "channel": 13, "prepayment_penalty_flag": 14, "amortization_type": 15,
    "property_state": 16, "property_type": 17, "postal_code": 18,
    "loan_id": 19, "loan_purpose": 20, "original_loan_term": 21,
    "number_of_borrowers": 22, "seller_name": 23, "super_conforming_flag": 24,
    "pre_harp_loan_id": 25, "special_eligibility_program": 26, "harp_indicator": 27,
    "property_valuation_method": 28, "interest_only_indicator": 29,
    "vantagescore_4": 30,
}
ORIG_LAYOUT = [
    "Credit Score", "First Payment Date", "First Time Homebuyer Flag", "Maturity Date",
    "Metropolitan Statistical Area (MSA)", "Mortgage Insurance Percentage", "Number of Units",
    "Occupancy Status", "Original Combined Loan-to-Value (CLTV)", "Original Debt-to-Income (DTI)",
    "Original UPB", "Original Loan-to-Value (LTV)", "Original Interest Rate", "Channel",
    "Prepayment Penalty Indicator", "Amortization Type", "Property State", "Property Type",
    "Postal Code", "Loan Sequence Number", "Loan Purpose", "Original Loan Term",
    "Number of Borrowers", "Seller Name", "Super Conforming Flag", "Pre-HARP Loan Sequence Number",
    "Special Eligibility Program", "HARP Indicator", "Property Valuation Method",
    "Interest Only Indicator", "VantageScore 4.0",
]
PERF_LAYOUT = [
    "Loan Sequence Number", "Monthly Reporting Period", "Current Actual UPB",
    "Current Loan Delinquency Status", "Loan Age", "Remaining Months to Legal Maturity",
    "Defect Settlement Date", "Modification Flag", "Zero Balance Code",
    "Zero Balance Effective Date", "Current Interest Rate", "Current Non-Interest Bearing UPB",
    "Due Date of Last Paid Installment", "MI Recoveries", "Net Sales Proceeds",
    "Non-MI Recoveries", "Total Expenses", "Legal Costs", "Maintenance and Preservation Costs",
    "Taxes and Insurance", "Miscellaneous Expenses", "Actual Loss", "Cumulative Modification Costs",
    "Interest Rate Step Indicator", "Payment Deferral Flag", "Estimated Loan-to-Value (ELTV)",
    "Zero Balance Removal UPB", "Delinquent Accrued Interest", "Delinquency Due to Disaster",
    "Borrower Assistance Plan", "Current Period Modification Costs", "Current Interest Bearing UPB",
    "Mortgage Insurance Cancellation Indicator", "Servicer Name", "Bankruptcy Cramdown Costs",
]
ZERO_CODES = {"01", "02", "03", "09", "15", "16", "96"}
NUMERIC = ["classic_fico", "original_ltv", "original_dti", "original_interest_rate",
           "original_loan_term", "mi_percentage", "log_original_upb", "has_mortgage_insurance"]
CATEGORICAL = ["occupancy_status", "loan_purpose", "property_type", "first_time_homebuyer",
               "channel", "number_of_borrowers", "number_of_units"]
SENTINELS = {"classic_fico": {"9999"}, "original_ltv": {"999"}, "original_cltv": {"999"},
             "original_dti": {"999"}, "mi_percentage": {"999"}, "number_of_borrowers": {"99"},
             "number_of_units": {"99"}, "occupancy_status": {"9"},
             "first_time_homebuyer": {"9"}, "loan_purpose": {"9"}, "property_type": {"99"}}


def load_analysis_config() -> dict[str, Any]:
    path = ROOT / "config" / "analysis_config.json"
    return json.loads(path.read_text(encoding="utf-8"))


def calendar_cohort_split(first_payment_date, cutoff: str) -> tuple[np.ndarray, np.ndarray]:
    """Chia chỉ số khoản vay tại cutoff YYYYMM mà không xem kết quả."""
    dates = np.array([month_index(str(v)) for v in first_payment_date])
    cutoff_i = month_index(cutoff)
    train = np.flatnonzero(dates <= cutoff_i)
    test = np.flatnonzero(dates > cutoff_i)
    if not len(train) or not len(test):
        raise ValueError("Phép chia cohort theo lịch phải tạo tập train và test không rỗng")
    return train, test


def month_index(value: str) -> int:
    if len(value) != 6 or not value.isdigit():
        raise ValueError(f"Tháng YYYYMM không hợp lệ: {value!r}")
    year, month = int(value[:4]), int(value[4:])
    if year < 1900 or not 1 <= month <= 12:
        raise ValueError(f"Tháng YYYYMM không hợp lệ: {value!r}")
    return year * 12 + month - 1


def month_string(index: int) -> str:
    year, month0 = divmod(int(index), 12)
    return f"{year:04d}{month0 + 1:02d}"


def _read_rows(path: Path, ncols: int):
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        for row_no, row in enumerate(csv.reader(f, delimiter="|"), start=1):
            if not row:
                continue
            if len(row) != ncols:
                raise ValueError(f"{path.name}:{row_no}: cần {ncols} trường, nhận được {len(row)}")
            yield row_no, [v.strip() for v in row]


def audit_data(orig_path: Path, perf_path: Path, out_dir: Path) -> dict[str, Any]:
    """Kiểm toán cấu trúc/liên kết theo luồng; không sửa đổi tệp thô."""
    orig_ids, orig_missing = set(), Counter()
    orig_rows = 0
    for row_no, row in _read_rows(orig_path, 31):
        orig_rows += 1
        loan_id = row[19]
        if not loan_id or loan_id in orig_ids:
            raise ValueError(f"Loan Sequence Number trong tệp khởi tạo bị trống hoặc trùng tại dòng {row_no}")
        orig_ids.add(loan_id)
        orig_missing.update(i for i, v in enumerate(row) if not v)

    perf_ids, perf_missing = set(), Counter()
    status_counts, zero_counts, first_period_counts, first_age_counts = Counter(), Counter(), Counter(), Counter()
    perf_rows, duplicates, global_id_decrease = 0, 0, 0
    previous_key = ("", -1)
    per_loan_prev: dict[str, int] = {}
    gaps = []
    min_month, max_month = None, None
    first_seen = set()
    for row_no, row in _read_rows(perf_path, 35):
        perf_rows += 1
        loan_id, period = row[0], row[1]
        if not loan_id:
            raise ValueError(f"Loan Sequence Number trong tệp performance bị trống tại dòng {row_no}")
        pm = month_index(period)
        key = (loan_id, pm)
        if key == previous_key:
            duplicates += 1
        if loan_id < previous_key[0]:
            global_id_decrease += 1
        previous_key = key
        perf_ids.add(loan_id)
        perf_missing.update(i for i, v in enumerate(row) if not v)
        status_counts[row[3] or "<EMPTY>"] += 1
        if row[8]:
            zero_counts[row[8]] += 1
            if row[8] not in ZERO_CODES:
                LOG.warning("Mã zero-balance chưa có trong danh mục %s tại dòng %d", row[8], row_no)
        min_month = pm if min_month is None else min(min_month, pm)
        max_month = pm if max_month is None else max(max_month, pm)
        prev = per_loan_prev.get(loan_id)
        if prev is None:
            first_period_counts[period] += 1
            first_age_counts[row[4] or "<EMPTY>"] += 1
            first_seen.add(loan_id)
        elif pm <= prev:
            raise ValueError(f"Tháng performance không được sắp xếp/tăng dần với khoản vay {loan_id} tại dòng {row_no}")
        elif pm - prev > 1:
            gaps.append({"loan_id": loan_id, "from": month_string(prev), "to": period, "missing_months": pm - prev - 1})
        per_loan_prev[loan_id] = pm

    only_orig, only_perf = sorted(orig_ids - perf_ids), sorted(perf_ids - orig_ids)
    if duplicates:
        raise ValueError(f"Có dòng trùng cặp (loan_id, reporting_period): {duplicates}")
    col_missing_orig = [{"index": i + 1, "name": ORIG_LAYOUT[i], "missing": orig_missing[i],
                         "missing_pct": orig_missing[i] / max(orig_rows, 1)} for i in range(31)]
    col_missing_perf = [{"index": i + 1, "name": PERF_LAYOUT[i], "missing": perf_missing[i],
                         "missing_pct": perf_missing[i] / max(perf_rows, 1)} for i in range(35)]
    result = {
        "source": "Declared Freddie Mac SFLLD Sample 2015; schema reference Release 47 (July 2026); local download provenance unverified",
        "origination": {"path": str(orig_path), "rows": orig_rows, "columns": 31,
                        "unique_loan_ids": len(orig_ids), "missing_by_column": col_missing_orig},
        "performance": {"path": str(perf_path), "rows": perf_rows, "columns": 35,
                        "unique_loan_ids": len(perf_ids), "missing_by_column": col_missing_perf,
                        "report_period_min": month_string(min_month), "report_period_max": month_string(max_month),
                        "reporting_months": max_month - min_month + 1,
                        "status_row_counts": dict(status_counts), "zero_balance_code_row_counts": dict(zero_counts),
                        "first_period_loan_counts": dict(sorted(first_period_counts.items())),
                        "first_observed_loan_age_counts": dict(sorted(first_age_counts.items()))},
        "join": {"matched_loan_ids": len(orig_ids & perf_ids), "origination_only": len(only_orig),
                 "performance_only": len(only_perf), "origination_only_examples": only_orig[:20],
                 "performance_only_examples": only_perf[:20]},
        "duplicates_loan_period": duplicates, "global_loan_id_order_decreases": global_id_decrease,
        "loans_with_calendar_gaps": len(gaps), "missing_calendar_month_intervals": sum(x["missing_months"] for x in gaps),
        "gap_examples": gaps[:20],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "data_audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Kiểm toán dữ liệu", "", f"Nguồn/schema: {result['source']}", "",
             f"- Origination: {orig_rows:,} rows, 31 columns, {len(orig_ids):,} unique loans.",
             f"- Performance: {perf_rows:,} rows, 35 columns, {len(perf_ids):,} unique loans.",
             f"- Matched IDs: {len(orig_ids & perf_ids):,}; origination only: {len(only_orig):,}; performance only: {len(only_perf):,}.",
             f"- Reporting window: {month_string(min_month)}–{month_string(max_month)} ({max_month-min_month+1} calendar months).",
             f"- Duplicate loan-month rows: {duplicates}; per-loan calendar gaps: {len(gaps)} intervals across {len({x['loan_id'] for x in gaps})} loans.",
             "- Raw files are pipe-delimited, headerless; audit streamed rows without editing inputs.", "",
             "## Giá trị thiếu theo cột", "", "### Khởi tạo", "", "| # | Trường | Thiếu |", "|---:|---|---:|"]
    lines += [f"| {x['index']} | {x['name']} | {x['missing']:,} ({x['missing_pct']:.3%}) |" for x in col_missing_orig]
    lines += ["", "### Performance", "", "| # | Trường | Thiếu |", "|---:|---|---:|"]
    lines += [f"| {x['index']} | {x['name']} | {x['missing']:,} ({x['missing_pct']:.3%}) |" for x in col_missing_perf]
    lines += ["", "## Số dòng theo mã trạng thái quá hạn", "", "| Mã | Số dòng |", "|---|---:|"]
    lines += [f"| {k} | {v:,} |" for k, v in status_counts.most_common()]
    lines += ["", "## Số dòng theo mã zero-balance", "", "| Mã | Số dòng |", "|---|---:|"]
    lines += [f"| {k} | {v:,} |" for k, v in zero_counts.most_common()]
    lines += ["", "Missing counts above are raw blanks only, not sentinel counts or post-cleaning missingness.",
              f"Calendar gaps total {sum(x['missing_months'] for x in gaps)} missing months in {len(gaps)} intervals.",
              "See docs/provenance_data.md for raw/archive identity; schema compatibility does not verify download provenance."]
    (out_dir / "data_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def build_survival_data(orig_path: Path, perf_path: Path, out_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    loans: dict[str, dict[str, Any]] = {}
    for row_no, row in _read_rows(orig_path, 31):
        loan_id, fp = row[19], row[1]
        if not loan_id or loan_id in loans:
            raise ValueError(f"ID khoản vay khởi tạo bị trống hoặc trùng tại dòng {row_no}")
        loans[loan_id] = {name: row[idx] for name, idx in ORIG_FIELDS.items()}
        loans[loan_id].update({"first_payment_month": month_index(fp), "first_period_month": None,
                               "last_period_month": None, "first_age": None, "first_mod": "",
                               "first_event_month": None, "first_event_period": "", "first_event_status": "",
                               "zero_code": "", "zero_effective_month": None, "zero_effective_date": "",
                               "zero_report_period": "", "n_perf_rows": 0, "pre_origin_event": False})
    status_rows = Counter()
    zero_loans = Counter()
    pre_origin_90plus_rows = 0
    for row_no, row in _read_rows(perf_path, 35):
        loan_id, period, status, zero_code, zero_date = row[0], row[1], row[3], row[8], row[9]
        if loan_id not in loans:
            raise ValueError(f"ID performance không có trong tệp khởi tạo tại dòng {row_no}: {loan_id}")
        pmonth = month_index(period)
        loan = loans[loan_id]
        if loan["last_period_month"] is not None and pmonth <= loan["last_period_month"]:
            raise ValueError(f"Dòng tháng bị trùng hoặc sai thứ tự với khoản vay {loan_id}: {period}")
        loan["n_perf_rows"] += 1
        if loan["first_period_month"] is None:
            loan["first_period_month"], loan["first_age"], loan["first_mod"] = pmonth, row[4], row[7]
        loan["last_period_month"] = pmonth
        status_rows[status or "<EMPTY>"] += 1
        if status != "RA" and not (len(status) == 2 and status.isdigit() and 0 <= int(status) <= 99):
            raise ValueError(f"Unknown delinquency status {status!r} for {loan_id}; cohort policy required")
        if status.isdigit() and int(status) >= 3 and loan["first_event_month"] is None:
            if pmonth >= loan["first_payment_month"]:
                loan["first_event_month"], loan["first_event_period"], loan["first_event_status"] = pmonth, period, status
            else:
                pre_origin_90plus_rows += 1
                loan["pre_origin_event"] = True
        if zero_code:
            if loan["zero_code"]:
                raise ValueError(f"Có nhiều dòng mã zero-balance cho khoản vay {loan_id}")
            if zero_code not in ZERO_CODES:
                raise ValueError(f"Mã zero-balance {zero_code} không hợp lệ với khoản vay {loan_id}")
            loan["zero_code"], loan["zero_effective_date"], loan["zero_report_period"] = zero_code, zero_date, period
            loan["zero_effective_month"] = month_index(zero_date) if zero_date else pmonth
            zero_loans[zero_code] += 1

    records, event_a, competing, censored, ambiguous = [], 0, Counter(), 0, 0
    event_b = Counter()
    excluded_pre_origin_terminal = Counter()
    other_exclusions = Counter()
    exclusion_rows = []
    first_performance_relative_to_origin = Counter()
    entry_age_mismatch = 0
    for loan_id, loan in loans.items():
        if loan["n_perf_rows"] == 0:
            raise ValueError(f"Khoản vay khởi tạo không có dòng performance: {loan_id}")
        first_m, last_m = loan["first_period_month"], loan["last_period_month"]
        first_performance_relative_to_origin["before" if first_m < loan["first_payment_month"] else
                                             "at" if first_m == loan["first_payment_month"] else "after"] += 1
        if loan["zero_effective_month"] is not None and loan["zero_effective_month"] < loan["first_payment_month"]:
            excluded_pre_origin_terminal[loan["zero_code"]] += 1
            exclusion_rows.append({"loan_id": loan_id, "reason": "terminal_before_origin"})
            continue
        exclusion = ("pre_origin_90plus" if loan["pre_origin_event"] else
                     "no_post_origin_observation" if last_m < loan["first_payment_month"] else
                     "terminal_before_entry" if loan["zero_effective_month"] is not None
                     and loan["zero_effective_month"] < first_m else None)
        if exclusion:
            other_exclusions[exclusion] += 1
            exclusion_rows.append({"loan_id": loan_id, "reason": exclusion})
            continue
        entry = max(0, first_m - loan["first_payment_month"])
        first_age = int(loan["first_age"]) if str(loan["first_age"]).isdigit() else None
        expected_age = max(0, first_m - loan["first_payment_month"] + 1)
        if first_age is not None and not loan["first_mod"] and first_age != expected_age:
            entry_age_mismatch += 1
        terminal = loan["zero_effective_month"]
        e_month = loan["first_event_month"]
        last_time = last_m - loan["first_payment_month"] + 1
        tie = e_month is not None and terminal is not None and e_month == terminal
        if e_month is not None and (terminal is None or e_month < terminal):
            duration = e_month - loan["first_payment_month"] + 1
            cause, exit_type = 1, "first_90plus"
            event_a += 1
        elif terminal is not None:
            duration = terminal - loan["first_payment_month"] + 1
            cause, exit_type = 2, f"zero_balance_{loan['zero_code']}"
            competing[loan["zero_code"]] += 1
            ambiguous += int(tie)
        else:
            duration, cause, exit_type = last_time, 0, "right_censored_at_last_observation"
            censored += 1
        if duration <= entry:
            raise ValueError(f"Khoảng quan sát không dương với {loan_id}: entry={entry}, duration={duration}")
        code = loan["zero_code"]
        if code in {"03", "09"}:
            event_b[code] += 1
        record = {k: loan[k] for k in ORIG_FIELDS}
        record.update({"first_observed_period": month_string(first_m), "last_observed_period": month_string(last_m),
                       "first_observed_loan_age": loan["first_age"], "delayed_entry_months": entry,
                       "n_performance_rows": loan["n_perf_rows"], "first_90plus_period": loan["first_event_period"],
                       "first_90plus_status": loan["first_event_status"], "zero_balance_code": code,
                       "zero_balance_effective_date": loan["zero_effective_date"],
                       "zero_balance_report_period": loan["zero_report_period"],
                       "event_time_months": duration, "event_cause": cause, "event_a_90plus": int(cause == 1),
                       "exit_type": exit_type, "same_month_90plus_termination_tie": int(tie),
                       "duration_b_credit_disposition_months": terminal - loan["first_payment_month"] + 1
                       if code in {"03", "09"} and terminal is not None else last_time,
                       "event_b_credit_disposition": int(code in {"03", "09"}),
                       "time_origin": "first_payment_date_calendar_month"})
        records.append(record)
    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError("No eligible loans after cohort exclusions")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8")
    pd.DataFrame(exclusion_rows, columns=["loan_id", "reason"]).to_csv(
        out_path.with_suffix(".exclusions.csv"), index=False)
    summary = {"n_loans": len(df), "primary_90plus_events": event_a,
               "competing_zero_balance_exits": int(sum(competing.values())),
               "competing_exit_codes": dict(competing), "right_censored": censored,
               "same_month_ambiguities_treated_as_competing": ambiguous,
               "endpoint_b_code_03_or_09_counts": dict(event_b),
               "endpoint_b_total_events": int(sum(event_b.values())),
               "loans_with_delayed_entry": int((df.delayed_entry_months > 0).sum()),
               "first_performance_month_relative_to_time_origin": dict(first_performance_relative_to_origin),
               "pre_origin_90plus_rows_ignored": pre_origin_90plus_rows,
               "loans_excluded_terminal_before_time_origin": int(sum(excluded_pre_origin_terminal.values())),
               "excluded_pre_origin_terminal_codes": dict(excluded_pre_origin_terminal),
               "loans_excluded_terminal_before_entry": other_exclusions["terminal_before_entry"],
               "other_exclusion_reasons": dict(other_exclusions),
               "entry_clock_mismatch_vs_first_loan_age_unmodified": entry_age_mismatch,
               "zero_balance_effective_date_missing_fallback_to_report_month": int(
                   (df.zero_balance_code.ne("") & df.zero_balance_effective_date.eq("")).sum()),
               "terminal_effective_after_last_report": int(
                   (df.zero_balance_effective_date.ne("") &
                    (df.zero_balance_effective_date > df.last_observed_period)).sum()),
               "status_row_counts": dict(status_rows), "time_origin": "First Payment Date calendar month",
               "terminal_time": "Zero Balance Effective Date; reporting month fallback only if missing",
               "event_month_rule": "event recorded at month end; same-month terminal handled as competing exit",
               "output": str(out_path)}
    return df, summary


def _clean_original(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    numeric_cols = ["classic_fico", "original_ltv", "original_cltv", "original_dti", "original_upb",
                    "original_interest_rate", "original_loan_term", "mi_percentage"]
    for col, codes in SENTINELS.items():
        if col in out and col not in numeric_cols:
            values = out[col].astype("string").str.strip()
            if col in ("number_of_borrowers", "number_of_units"):
                values = values.str.replace(r"\.0+$", "", regex=True)
            # Normalize only declared sentinel tokens, leaving other categories intact.
            sentinel_tokens = values.str.replace(r"\.0+$", "", regex=True)
            out[col] = values.mask(sentinel_tokens.isin(codes) | values.eq("")).astype(object)
            out[col] = out[col].where(pd.notna(out[col]), np.nan)
    for col in numeric_cols:
        out[col] = pd.to_numeric(out[col], errors="coerce")
        if col in SENTINELS:
            out[col] = out[col].mask(out[col].isin([float(v) for v in SENTINELS[col]]))
    if (out.original_upb.notna() & (out.original_upb <= 0)).any():
        raise ValueError("Original UPB must be positive when available")
    out["log_original_upb"] = np.log1p(out.original_upb.clip(lower=0))
    out["has_mortgage_insurance"] = (out.mi_percentage.fillna(0) > 0).astype(float)
    return out


def prepare_features(df: pd.DataFrame, train_idx: np.ndarray, test_idx: np.ndarray):
    clean = _clean_original(df)
    train, test = clean.iloc[train_idx].copy(), clean.iloc[test_idx].copy()
    transform: dict[str, Any] = {"numeric": {}, "categorical": {}, "dropped": []}
    tx, vx = pd.DataFrame(index=train.index), pd.DataFrame(index=test.index)
    for col in NUMERIC:
        med = train[col].median()
        if pd.isna(med):
            transform["dropped"].append({"field": col, "reason": "all missing in training"})
            continue
        tr_missing, te_missing = train[col].isna(), test[col].isna()
        trval, teval = train[col].fillna(med), test[col].fillna(med)
        mean, sd = float(trval.mean()), float(trval.std(ddof=0))
        if not np.isfinite(sd) or sd == 0:
            transform["dropped"].append({"field": col, "reason": "constant in training"})
            continue
        tx[col], vx[col] = (trval - mean) / sd, (teval - mean) / sd
        add_missing = int(tr_missing.sum()) >= 30
        transform["numeric"][col] = {"median": float(med), "mean": mean, "sd": sd,
                                      "missing_indicator": add_missing, "train_missing": int(tr_missing.sum())}
        if add_missing:
            tx[col + "_missing"], vx[col + "_missing"] = tr_missing.astype(float), te_missing.astype(float)
    for col in CATEGORICAL:
        tr = train[col].replace("", np.nan).fillna("Unknown").astype(str)
        te = test[col].replace("", np.nan).fillna("Unknown").astype(str)
        counts = tr.value_counts()
        rare = set(counts[counts < 100].index)
        tr = tr.where(~tr.isin(rare), "Other")
        te = te.where(~te.isin(rare), "Other")
        levels = sorted(tr.unique())
        if len(levels) < 2:
            transform["dropped"].append({"field": col, "reason": "constant in training"})
            continue
        transform["categorical"][col] = {"levels": levels, "reference": levels[0], "rare_cutoff": 100,
                                          "rare_values": sorted(rare)}
        tr_d = pd.get_dummies(pd.Categorical(tr, categories=levels), prefix=col, drop_first=True, dtype=float)
        te = te.where(te.isin(levels), levels[0])
        te_d = pd.get_dummies(pd.Categorical(te, categories=levels), prefix=col, drop_first=True, dtype=float)
        tr_d.index, te_d.index = tx.index, vx.index
        tx = pd.concat([tx, tr_d], axis=1)
        vx = pd.concat([vx, te_d], axis=1)
    vx = vx.reindex(columns=tx.columns, fill_value=0)
    tx = tx.astype(float).reset_index(drop=True)
    vx = vx.astype(float).reset_index(drop=True)
    return tx, vx, transform, clean


def aalen_johansen_cif(duration: np.ndarray, entry: np.ndarray, cause: np.ndarray,
                       times: np.ndarray | None = None, n_causes: int = 2) -> pd.DataFrame:
    """Ước lượng product-limit Aalen–Johansen rời rạc theo tháng, có delayed entry.

    Mỗi khoảng kết thúc tại tháng nguyên tương ứng. Các nguyên nhân đồng hạng được cập nhật đồng thời:
    S(t)=S(t-1)*(1-d_all/Y), F_k(t)=F_k(t-1)+S(t-1)*d_k/Y.
    """
    duration, entry, cause = np.asarray(duration, float), np.asarray(entry, float), np.asarray(cause, int)
    if not (len(duration) == len(entry) == len(cause)):
        raise ValueError("Độ dài duration, entry và cause không khớp")
    if np.any(duration <= entry) or np.any(duration <= 0) or np.any(cause < 0) or np.any(cause > n_causes):
        raise ValueError("Dữ liệu competing risks có delayed entry không hợp lệ")
    requested = None if times is None else np.asarray(times)
    if requested is not None and (requested.ndim != 1 or not len(requested)
            or np.any(~np.isfinite(requested)) or np.any(requested != requested.astype(int))
            or np.any(requested < 1) or np.any(np.diff(requested) <= 0)
            or requested.max() > np.max(duration)):
        raise ValueError("AJ output times must be increasing supported positive integer months")
    grid = np.arange(1, int(np.max(duration)) + 1)
    survival, cif = 1.0, np.zeros(n_causes, dtype=float)
    results = []
    event_times = set(duration[cause > 0].astype(int))
    for t in grid:
        if int(t) in event_times:
            risk = int(np.sum((entry < t) & (duration >= t)))
            d = np.array([np.sum((duration == t) & (cause == k)) for k in range(1, n_causes + 1)], dtype=float)
            if risk <= 0 or d.sum() > risk:
                raise ValueError(f"Risk set không hợp lệ tại tháng {t}: Y={risk}, events={d.sum()}")
            old_survival = survival
            cif += old_survival * d / risk
            survival *= 1.0 - d.sum() / risk
        results.append([int(t), float(survival), *cif.tolist()])
        if not np.isfinite(survival) or np.any(~np.isfinite(cif)) or survival < -1e-12 or np.any(cif < -1e-12):
            raise ArithmeticError("Xác suất không hữu hạn hoặc âm trong ước lượng Aalen–Johansen")
        if np.any(cif > 1 + 1e-12) or survival > 1 + 1e-12 or abs(survival + cif.sum() - 1) > 1e-8:
            raise ArithmeticError("Các bất biến xác suất Aalen–Johansen không được thỏa mãn")
    result = pd.DataFrame(results, columns=["time_months", "survival_all"] + [f"cif_cause_{k}" for k in range(1, n_causes + 1)])
    return result if requested is None else result[result.time_months.isin(requested)].reset_index(drop=True)


def conditional_aj_cif(aj: pd.DataFrame, entry: np.ndarray, horizon: int,
                      cause: int = 1) -> np.ndarray:
    """Conditional train AJ CIF at explicitly available calendar months.

    Sparse rows do not identify values at omitted months. Require both horizon
    and every positive entry month explicitly; month zero has S=1 and CIF=0.
    """
    entry = np.asarray(entry, int)
    if horizon <= 0 or np.any(entry < 0) or np.any(entry >= horizon):
        raise ValueError("Horizon hoặc entry không hợp lệ")
    col = f"cif_cause_{cause}"
    if col not in aj or "survival_all" not in aj or "time_months" not in aj:
        raise ValueError("Đường AJ không có nguyên nhân và survival được yêu cầu")
    times = aj.time_months.to_numpy(float)
    if (not len(times) or np.any(~np.isfinite(times)) or np.any(times < 1)
            or np.any(times != times.astype(int)) or np.any(np.diff(times) <= 0)):
        raise ValueError("AJ time_months must be increasing positive integer months")
    positions = {int(t): i + 1 for i, t in enumerate(times)}
    positions[0] = 0
    required = {horizon, *entry.tolist()}
    missing = required.difference(positions)
    if missing:
        raise ValueError(f"Missing AJ months {sorted(missing)}; provide explicit months or a full monthly grid")
    survival = np.r_[1.0, aj.survival_all.to_numpy(float)]
    cif = np.r_[0.0, aj[col].to_numpy(float)]
    entry_positions = np.array([positions[int(t)] for t in entry], dtype=int)
    denom = survival[entry_positions]
    numer = cif[positions[horizon]] - cif[entry_positions]
    out = np.divide(numer, denom, out=np.full(len(entry), np.nan), where=denom > 0)
    if np.any(np.isfinite(out) & ((out < -1e-10) | (out > 1 + 1e-10))):
        raise ArithmeticError("CIF AJ có điều kiện nằm ngoài [0, 1]")
    return out


def administrative_brier_terms(duration, entry, cause, horizon: int,
                               pred_cif) -> tuple[float, np.ndarray, np.ndarray, np.ndarray]:
    """Brier score competing risks không trọng số trên khoản test được quan sát đầy đủ đến h.

    Cách này tránh ước lượng G khi có kiểm duyệt hành chính. Score nhắm đến
    nhóm có entry < h và trạng thái biến cố đã biết đến h (kể cả kiểm duyệt tại h).
    Loại kiểm duyệt trước h vì trạng thái tại horizon chưa biết.
    """
    duration, entry, cause, pred = map(np.asarray, (duration, entry, cause, pred_cif))
    if not (len(duration) == len(entry) == len(cause) == len(pred)):
        raise ValueError("Độ dài duration, entry, cause và pred_cif không khớp")
    if np.any(~np.isfinite(pred)) or np.any((pred < 0) | (pred > 1)):
        raise ValueError("pred_cif phải chứa xác suất hữu hạn trong [0, 1]")
    eligible = entry < horizon
    known = eligible & (((cause > 0) & (duration <= horizon)) |
                        (duration > horizon) | ((duration == horizon) & (cause == 0)))
    y = ((cause == 1) & (duration <= horizon)).astype(float)
    losses = np.zeros(len(duration), dtype=float)
    losses[known] = (y[known] - pred[known]) ** 2
    score = float(np.mean(losses[known])) if known.any() else float("nan")
    return score, known, y, losses


def paired_bootstrap_mean_difference(model_loss, reference_loss, valid,
                                     n_boot: int, seed: int) -> dict[str, float | int]:
    """Khoảng percentile của loss mô hình trừ loss tham chiếu, lấy mẫu lại theo cặp khoản vay."""
    model_loss, reference_loss, valid = np.asarray(model_loss, float), np.asarray(reference_loss, float), np.asarray(valid, bool)
    if not (model_loss.shape == reference_loss.shape == valid.shape):
        raise ValueError("Các loss ghép cặp và mặt nạ hợp lệ phải có cùng kích thước")
    if n_boot <= 0:
        raise ValueError("n_boot phải là số dương")
    ids = np.flatnonzero(valid)
    if not len(ids):
        return {"difference": float("nan"), "ci_2_5": float("nan"), "ci_97_5": float("nan"),
                "n_valid": 0, "successful_replicates": 0}
    delta = model_loss[ids] - reference_loss[ids]
    if np.any(~np.isfinite(delta)):
        raise ValueError("Các loss ghép cặp hợp lệ phải hữu hạn")
    rng = np.random.default_rng(seed)
    draws = np.array([np.mean(delta[rng.integers(0, len(delta), len(delta))]) for _ in range(n_boot)])
    return {"difference": float(np.mean(delta)), "ci_2_5": float(np.quantile(draws, .025)),
            "ci_97_5": float(np.quantile(draws, .975)), "n_valid": int(len(ids)),
            "successful_replicates": int(np.isfinite(draws).sum())}


def integrate_competing_cumulative_hazards(increments: dict[int, np.ndarray],
                                           entry: np.ndarray, horizons: list[int]) -> np.ndarray:
    """Tích phân cumulative-hazard increment theo nguyên nhân và tháng để tính CIF.

    Mỗi giá trị trong increments[k] là Delta H_k cho một khoản vay trong một tháng.
    Trong mỗi khoảng, hazard được giả định hằng từng đoạn nên xác suất chưa biến cố
    được nhân với exp(-sum Delta H); mỗi nguyên nhân nhận phần tỷ lệ tương ứng
    trong tổng xác suất biến cố của khoảng.
    """
    raw_entry = np.asarray(entry, float)
    if (np.any(~np.isfinite(raw_entry)) or np.any(raw_entry < 0)
            or np.any(raw_entry != raw_entry.astype(int))):
        raise ValueError("Entry must be nonnegative integer months")
    if not len(horizons) or any(not np.isfinite(h) or int(h) != h or h <= 0 for h in horizons) or len(set(horizons)) != len(horizons):
        raise ValueError("Horizons must be distinct positive integer months")
    entry = raw_entry.astype(int)
    max_t = max(horizons)
    if not increments:
        raise ValueError("Cần có ít nhất một cause-specific hazard")
    n = len(entry)
    if any(np.asarray(h).shape != (n, max_t) for h in increments.values()):
        raise ValueError("Mảng hazard increment theo nguyên nhân phải có kích thước (n_loans, max_horizon)")
    if any(np.any(~np.isfinite(h)) or np.any(np.asarray(h) < -1e-10) for h in increments.values()):
        raise ValueError("Hazard increment theo nguyên nhân phải hữu hạn và không âm")
    survival = np.ones(n, dtype=float)
    cif = {cause: np.zeros(n, dtype=float) for cause in increments}
    out = np.full((n, len(horizons), len(increments)), np.nan)
    h_to_col = {int(h): j for j, h in enumerate(horizons)}
    for t in range(1, max_t + 1):
        active = entry < t
        total = np.sum(np.vstack([increments[k][:, t - 1] for k in increments]), axis=0)
        fail = -np.expm1(-total)
        for k, dh_grid in increments.items():
            dh = dh_grid[:, t - 1]
            frac = np.divide(dh, total, out=np.zeros_like(dh), where=total > 0)
            dk = survival * fail * frac
            cif[k][active] += dk[active]
        survival[active] *= np.exp(-total[active])
        current_sum = survival + np.sum(np.vstack([cif[k] for k in cif]), axis=0)
        if (np.any(survival < -1e-10) or np.any(survival > 1 + 1e-10)
                or np.any(current_sum < 1 - 1e-9) or np.any(current_sum > 1 + 1e-9)):
            raise ArithmeticError("Các bất biến xác suất CIF/survival không được thỏa mãn")
        if t in h_to_col:
            for cause_pos, cause in enumerate(increments):
                out[:, h_to_col[t], cause_pos] = cif[cause]
    if np.any((out[np.isfinite(out)] < -1e-10) | (out[np.isfinite(out)] > 1 + 1e-10)):
        raise ArithmeticError("CIF dự báo nằm ngoài [0, 1]")
    # Survival chưa biến cố cộng với incidence của mọi nguyên nhân phải bằng 1
    # khi theo dõi khoản vay từ thời điểm 0; với delayed entry, chủ ý loại các
    # increment trước entry và đẳng thức vẫn đúng theo điều kiện.
    return out


def competing_cox_cif(cause_models: dict[int, CoxPHFitter], features: pd.DataFrame,
                      entry: np.ndarray, horizons: list[int]) -> np.ndarray:
    """CIF có điều kiện suy ra từ cumulative hazard Cox nguyên nhân cụ thể đã fit."""
    entry = np.asarray(entry, float)
    max_t = max(horizons)
    times = np.arange(0, max_t + 1, dtype=float)
    cumulative = {}
    for cause, model in cause_models.items():
        raw = model.predict_cumulative_hazard(features, times=times)
        cumulative[cause] = raw.to_numpy(dtype=float).T
        if cumulative[cause].shape != (len(features), len(times)):
            raise ValueError("Kích thước cumulative hazard dự báo không như dự kiến")
        if np.any(np.diff(cumulative[cause], axis=1) < -1e-9):
            raise ArithmeticError("Cumulative hazard nguyên nhân cụ thể dự báo không đơn điệu")
    increments = {k: np.maximum(0.0, h[:, 1:] - h[:, :-1]) for k, h in cumulative.items()}
    all_cif = integrate_competing_cumulative_hazards(increments, entry, horizons)
    cause_order = list(cumulative)
    # Metric công khai đánh giá nguyên nhân 1; hàm trả CIF tại từng horizon.
    return all_cif[:, :, cause_order.index(1)]


def transform_new_features(new_df: pd.DataFrame, transform: dict[str, Any],
                           feature_columns: list[str], use_cltv: bool = False) -> pd.DataFrame:
    """Áp dụng tiền xử lý đã fit trên train cho bản ghi khởi tạo mới."""
    raw = new_df.copy()
    if use_cltv and "original_cltv" in raw:
        raw["original_ltv"] = raw["original_cltv"]
    clean = _clean_original(raw)
    out = pd.DataFrame(index=np.arange(len(clean)))
    for col, info in transform["numeric"].items():
        vals = clean[col].fillna(info["median"])
        out[col] = (vals.to_numpy(float) - info["mean"]) / info["sd"]
        if info["missing_indicator"]:
            out[col + "_missing"] = clean[col].isna().to_numpy(float)
    for col, info in transform["categorical"].items():
        levels, rare_values = info["levels"], set(info.get("rare_values", []))
        vals = clean[col].replace("", np.nan).fillna("Unknown").astype(str)
        vals = vals.where(~vals.isin(rare_values), "Other")
        vals = vals.where(vals.isin(levels), info["reference"])
        dummies = pd.get_dummies(pd.Categorical(vals, categories=levels), prefix=col, drop_first=True, dtype=float)
        dummies.index = out.index
        out = pd.concat([out, dummies], axis=1)
    return out.reindex(columns=feature_columns, fill_value=0).astype(float)


def score_new_loans(bundle: dict[str, Any], new_loans: pd.DataFrame,
                    horizons: list[int] = (12, 24, 36, 60, 120)) -> pd.DataFrame:
    """Trả dự báo CIF theo nguyên nhân, có điều kiện theo tháng entry của từng dòng."""
    features = transform_new_features(new_loans, bundle["transform"], bundle["feature_columns"],
                                      bundle.get("use_cltv_sensitivity", False))
    entry = (pd.to_numeric(new_loans["delayed_entry_months"], errors="raise").to_numpy(float)
             if "delayed_entry_months" in new_loans else np.zeros(len(new_loans), dtype=int))
    max_t = max(horizons)
    for model in bundle["models"].values():
        if hasattr(model, "baseline_cumulative_hazard_") and max_t > model.baseline_cumulative_hazard_.index.max():
            raise ValueError("Prediction horizon exceeds training follow-up support")
    times = np.arange(0, max_t + 1, dtype=float)
    cumulative = {k: model.predict_cumulative_hazard(features, times=times).to_numpy(float).T
                  for k, model in bundle["models"].items()}
    increments = {k: np.maximum(0.0, h[:, 1:] - h[:, :-1]) for k, h in cumulative.items()}
    all_cif = integrate_competing_cumulative_hazards(increments, entry, list(horizons))
    names = {1: "predicted_cif_first_90plus", 2: "predicted_cif_any_zero_balance_exit"}
    result = pd.DataFrame({"delayed_entry_months": entry})
    if "loan_id" in new_loans:
        result.insert(0, "loan_id", new_loans["loan_id"].astype(str).to_numpy())
    for pos, cause in enumerate(bundle["models"]):
        for j, horizon in enumerate(horizons):
            result[f"{names.get(cause, f'predicted_cif_cause_{cause}')}_{horizon}m"] = all_cif[:, j, pos]
    return result


def load_model_bundle(path: Path) -> dict[str, Any]:
    """Tải các mô hình nguyên nhân cụ thể đã fit và tiền xử lý đã fit trên train."""
    with path.open("rb") as f:
        bundle = pickle.load(f)
    required = {"models", "feature_columns", "transform", "use_cltv_sensitivity"}
    if not required.issubset(bundle):
        raise ValueError(f"Model bundle thiếu khóa: {sorted(required - set(bundle))}")
    return bundle


def left_truncated_c_index(duration, entry, event, risk) -> tuple[float, int]:
    duration, entry, event, risk = map(np.asarray, (duration, entry, event, risk))
    concordant, comparable = 0.0, 0
    for i in np.flatnonzero(event == 1):
        controls = (entry < duration[i]) & (duration > duration[i])
        controls[i] = False
        diffs = risk[i] - risk[controls]
        concordant += float(np.sum(diffs > 1e-12)) + .5 * float(np.sum(np.abs(diffs) <= 1e-12))
        comparable += int(len(diffs))
    return (concordant / comparable if comparable else float("nan"), comparable)


def _km_survival_before(km: KaplanMeierFitter, time: float) -> float:
    if time <= 0:
        return 1.0
    v = km.survival_function_at_times([max(0, time - 1e-7)]).to_numpy()
    return float(v[0])


def fit_monthly_censoring(duration, entry, cause) -> KaplanMeierFitter:
    """Reverse product-limit: cause events precede end-of-month censoring."""
    duration, entry, cause = map(np.asarray, (duration, entry, cause))
    km = KaplanMeierFitter().fit(duration, event_observed=(cause == 0), entry=entry)
    survival, values = 1.0, [1.0]
    times = np.arange(0, int(np.max(duration)) + 1)
    for t in times[1:]:
        risk = int(np.sum((entry < t) & (duration >= t)))
        events = int(np.sum((duration == t) & (cause > 0)))
        censors = int(np.sum((duration == t) & (cause == 0)))
        remaining = risk - events
        if remaining < censors or remaining < 0:
            raise ValueError("Invalid monthly censoring risk set")
        if remaining:
            survival *= 1 - censors / remaining
        values.append(survival)
    # Only this step function is used by IPCW; KM confidence intervals are not used.
    km.survival_function_ = pd.DataFrame({"KM_estimate": values}, index=times)
    return km


def delayed_entry_baseline(duration, entry, event, partial_hazard) -> pd.DataFrame:
    """Breslow increments at the training mean, with R(t)={L<t<=T}."""
    duration, entry, event, risk = map(np.asarray, (duration, entry, event, partial_hazard))
    if not (duration.shape == entry.shape == event.shape == risk.shape):
        raise ValueError("Baseline inputs must have matching shapes")
    if (np.any(~np.isfinite(duration)) or np.any(~np.isfinite(entry)) or
            np.any(duration <= entry) or np.any(entry < 0) or
            np.any(duration != duration.astype(int)) or np.any(entry != entry.astype(int)) or
            np.any(~np.isfinite(risk)) or np.any(risk <= 0)):
        raise ValueError("Invalid monthly baseline inputs")
    grid = np.arange(0, int(duration.max()) + 1, dtype=float)
    increments = np.zeros(len(grid))
    for t in np.unique(duration[event == 1]):
        denominator = risk[(entry < t) & (duration >= t)].sum()
        increments[int(t)] = np.sum((duration == t) & (event == 1)) / denominator
    return pd.DataFrame({"baseline hazard": increments}, index=grid)


def correct_delayed_entry_baseline(model, features, duration, entry, event) -> None:
    """Replace lifelines' entry-blind baseline, preserving fitted Efron coefficients."""
    baseline = delayed_entry_baseline(duration, entry, event,
                                      model.predict_partial_hazard(features).to_numpy())
    # CoxPHFitter delegates prediction to its fitted internal model.
    fitted = model._model
    fitted.baseline_hazard_ = baseline
    fitted.baseline_cumulative_hazard_ = baseline.cumsum().rename(
        columns={"baseline hazard": "baseline cumulative hazard"})
    fitted.baseline_survival_ = np.exp(-fitted.baseline_cumulative_hazard_).rename(
        columns={"baseline cumulative hazard": "baseline survival"})


def cif_ipcw_brier(duration, entry, cause, horizon: int, pred_cif,
                   censor_km: KaplanMeierFitter) -> tuple[float, np.ndarray, np.ndarray]:
    """Brier score IPCW theo nguyên nhân, có điều kiện theo delayed entry.

    Quy ước theo tháng xem kết quả ghi nhận tại tháng t (kể cả kiểm duyệt phải
    cuối tháng đã quan sát) là đã biết đến hết tháng đó. Trọng số kiểm duyệt dùng
    G(t-) và được điều kiện hóa theo việc đã được quan sát tại entry:
    G(t-)/G(entry). Không cắt trọng số theo ngưỡng tùy ý. Nếu phân phối kiểm duyệt
    không có support cho trạng thái cần chấm, trả NaN thay vì âm thầm bỏ trạng thái đó.
    """
    duration, entry, cause, pred = map(np.asarray, (duration, entry, cause, pred_cif))
    if not (len(duration) == len(entry) == len(cause) == len(pred)):
        raise ValueError("Độ dài duration, entry, cause và pred_cif không khớp")
    if horizon <= 0 or np.any(duration <= entry) or np.any(entry < 0):
        raise ValueError("Horizon hoặc dữ liệu survival có delayed entry không hợp lệ")
    if np.any((cause < 0) | (cause > 2)):
        raise ValueError("cause phải là 0 (kiểm duyệt), 1 (đích) hoặc 2 (cạnh tranh)")
    if np.any(~np.isfinite(pred)) or np.any((pred < 0) | (pred > 1)):
        raise ValueError("pred_cif must contain finite probabilities in [0, 1]")
    eligible = entry < horizon
    y = np.zeros(len(duration), dtype=float)
    weight = np.zeros(len(duration), dtype=float)
    case = eligible & (cause == 1) & (duration <= horizon)
    comp = eligible & (cause > 1) & (duration <= horizon)
    # Kết quả biến cố/cạnh tranh tại t đã biết ở mốc chốt báo cáo nên không được
    # xếp đồng thời vào nhóm event-free. Kiểm duyệt tại t có bản ghi đến cuối tháng.
    control = eligible & ((duration > horizon) | ((duration == horizon) & (cause == 0)))
    y[case] = 1.0
    known = case | comp | control
    unsupported = False
    for i in np.flatnonzero(known):
        g_entry = float(censor_km.survival_function_at_times([entry[i]]).iloc[0])
        endpoint = duration[i] if case[i] or comp[i] else horizon
        g_endpoint = _km_survival_before(censor_km, endpoint)
        if not np.isfinite(g_entry) or not np.isfinite(g_endpoint) or g_entry <= 0 or g_endpoint <= 0:
            unsupported = True
            continue
        conditional_g = g_endpoint / g_entry
        if conditional_g > 1 + 1e-9:
            raise ArithmeticError("Xác suất censor survival có điều kiện tăng sau entry")
        weight[i] = 1.0 / min(conditional_g, 1.0)
    # Kiểm duyệt trước t khiến trạng thái đích chưa biết. Nếu censor-survival đã
    # bằng 0 tại t thì không thể khôi phục trạng thái còn thiếu đó.
    unknown = eligible & (cause == 0) & (duration < horizon)
    for i in np.flatnonzero(unknown):
        g_entry = float(censor_km.survival_function_at_times([entry[i]]).iloc[0])
        g_h = _km_survival_before(censor_km, horizon)
        if not np.isfinite(g_entry) or not np.isfinite(g_h) or g_entry <= 0 or g_h <= 0:
            unsupported = True
    if not eligible.any() or not known.any() or unsupported:
        score = float("nan")
        if unsupported:
            weight[:] = 0.0
    else:
        score = float(np.sum(weight * (y - pred) ** 2) / eligible.sum())
    return score, y, weight


def schoenfeld_trend(model: CoxPHFitter, x: pd.DataFrame, duration, entry, event, cause_name: str) -> pd.DataFrame:
    """Xu hướng Schoenfeld xấp xỉ, chưa scale, với risk set delayed entry và kỳ vọng Efron khi có tie."""
    arr, duration, entry, event = x.to_numpy(float), np.asarray(duration, float), np.asarray(entry, float), np.asarray(event, int)
    beta = model.params_.reindex(x.columns).to_numpy(float)
    eta = np.clip(arr @ beta, -500, 500)
    w = np.exp(eta - np.max(eta))
    residuals, rtimes = [], []
    for t in np.unique(duration[event == 1]):
        deaths = np.flatnonzero((duration == t) & (event == 1))
        risk = np.flatnonzero((entry < t) & (duration >= t))
        d = len(deaths)
        sw, swx = w[risk].sum(), (w[risk, None] * arr[risk]).sum(axis=0)
        dw, dwx = w[deaths].sum(), (w[deaths, None] * arr[deaths]).sum(axis=0)
        expected = np.zeros(arr.shape[1])
        for ell in range(d):
            f = ell / d
            denom = sw - f * dw
            if denom > 0:
                expected += (swx - f * dwx) / denom
        expected /= d
        residuals.extend(arr[deaths] - expected)
        rtimes.extend([t] * d)
    if not residuals:
        return pd.DataFrame(columns=["cause", "term", "n_event_residuals", "correlation", "p_value", "p_value_bh"])
    mat = np.asarray(residuals)
    rt = rankdata(rtimes) / len(rtimes)
    rows = []
    for j, col in enumerate(x.columns):
        corr, p = pearsonr(mat[:, j], rt) if np.std(mat[:, j]) else (0.0, 1.0)
        rows.append({"cause": cause_name, "term": col, "n_event_residuals": len(mat), "correlation": corr, "p_value": p})
    out = pd.DataFrame(rows).sort_values("p_value").reset_index(drop=True)
    m = len(out)
    q = out.p_value.to_numpy() * m / np.arange(1, m + 1)
    out["p_value_bh"] = np.minimum.accumulate(q[::-1])[::-1].clip(max=1.0)
    return out


def bootstrap_metric_intervals(duration, entry, cause, risk, horizons, brier_terms,
                              n_boot: int, seed: int) -> pd.DataFrame:
    """Bootstrap theo khoản vay test; giữ mô hình/dự báo cố định, chỉ lượng hóa bất định metric của mẫu test."""
    rng = np.random.default_rng(seed)
    n = len(duration)
    samples = []
    for b in range(n_boot):
        ix = rng.integers(0, n, size=n)
        cidx, pairs = left_truncated_c_index(np.asarray(duration)[ix], np.asarray(entry)[ix],
                                               (np.asarray(cause)[ix] == 1).astype(int), np.asarray(risk)[ix])
        if np.isfinite(cidx):
            samples.append({"replicate": b, "metric": "left_truncated_c_index", "horizon_months": None, "value": cidx})
        for h in horizons:
            # Trọng số đã điều chỉnh kiểm duyệt; lấy mẫu lại ID khoản vay và giữ mẫu số đủ điều kiện.
            losses, eligible = brier_terms[h]
            denominator = int(np.sum(eligible[ix]))
            score = float(np.sum(losses[ix]) / denominator) if denominator else float("nan")
            if np.isfinite(score):
                samples.append({"replicate": b, "metric": "cif_ipcw_brier", "horizon_months": h, "value": score})
    raw = pd.DataFrame(samples)
    rows = []
    if not raw.empty:
        for (metric, horizon), g in raw.groupby(["metric", "horizon_months"], dropna=False):
            rows.append({"metric": metric, "horizon_months": horizon, "successful_replicates": len(g),
                         "bootstrap_mean": g.value.mean(), "ci_2_5": g.value.quantile(.025),
                         "ci_97_5": g.value.quantile(.975),
                         "scope": "giữ cố định mô hình đã fit; chỉ lấy mẫu lại khoản vay test"})
    return pd.DataFrame(rows)


def run_model(df: pd.DataFrame, output_dir: Path, tables_dir: Path, figures_dir: Path,
              seed: int = 2026, test_fraction: float | None = None, bootstrap_n: int = 100,
              use_cltv: bool = False, split_stratification: np.ndarray | None = None,
              split_indices: tuple[np.ndarray, np.ndarray] | None = None,
              split_description: str | None = None) -> dict[str, Any]:
    """Fit Cox cho biến cố và kết thúc cạnh tranh; tính CIF có điều kiện và metric trên test."""
    config = load_analysis_config()
    if test_fraction is None:
        test_fraction = float(config["model"]["test_fraction"])
    output_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    if use_cltv:
        df = df.copy()
        df["original_ltv"] = df["original_cltv"]
    y = df[["event_time_months", "delayed_entry_months", "event_cause"]].copy()
    indices = np.arange(len(df))
    if split_indices is None:
        stratification = (df.event_cause.to_numpy() == 1) if split_stratification is None else np.asarray(split_stratification)
        if len(stratification) != len(df):
            raise ValueError("split_stratification length does not match analysis cohort")
        train_idx, test_idx = train_test_split(indices, test_size=test_fraction, random_state=seed,
                                               stratify=stratification)
        split_label = split_description or "Stratified loan-level 80/20 random split within 2015 sample; not out-of-vintage validation."
    else:
        train_idx, test_idx = (np.asarray(ix, dtype=int) for ix in split_indices)
        if (len(train_idx) == 0 or len(test_idx) == 0 or
                len(np.unique(np.r_[train_idx, test_idx])) != len(train_idx) + len(test_idx) or
                not np.array_equal(np.sort(np.r_[train_idx, test_idx]), indices)):
            raise ValueError("Explicit train/test indices must partition the analysis cohort exactly once")
        split_label = split_description or "Explicit loan-level train/test split."
    x_train, x_test, transform, _ = prepare_features(df, train_idx, test_idx)
    y_train, y_test = y.iloc[train_idx].reset_index(drop=True), y.iloc[test_idx].reset_index(drop=True)
    pd.DataFrame({"loan_id": df.loan_id.astype(str),
                  "split": np.where(np.isin(indices, train_idx), "train", "test")}).to_csv(
                      output_dir / "split_membership.csv", index=False)
    if any(int((y_train.event_cause == k).sum()) < 20 for k in (1, 2)):
        raise ValueError("Insufficient training events for both cause-specific models")
    models = {}
    model_summaries = []
    fit_warnings = []
    for cause, name in ((1, "event_90plus"), (2, "any_zero_balance_exit")):
        fit_df = x_train.copy()
        fit_df["_duration"] = y_train.event_time_months.to_numpy(float)
        fit_df["_entry"] = y_train.delayed_entry_months.to_numpy(float)
        fit_df["_event"] = (y_train.event_cause.to_numpy() == cause).astype(int)
        cph = CoxPHFitter()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            cph.fit(fit_df, duration_col="_duration", event_col="_event", entry_col="_entry",
                    show_progress=False, batch_mode=True)
        fit_warnings.extend([f"{name}: {w.message}" for w in caught])
        correct_delayed_entry_baseline(cph, x_train, y_train.event_time_months,
                                       y_train.delayed_entry_months, fit_df["_event"])
        models[cause] = cph
        summary = cph.summary.copy().reset_index().rename(columns={"covariate": "term"})
        summary.insert(0, "cause", name)
        summary["hazard_ratio"] = np.exp(summary["coef"])
        summary.to_csv(tables_dir / f"cox_{name}_coefficients.csv", index=False)
        model_summaries.append(summary)
    pd.concat(model_summaries, ignore_index=True).to_csv(tables_dir / "cox_coefficients_all_causes.csv", index=False)
    risk_test = models[1].predict_partial_hazard(x_test).to_numpy().ravel()
    cindex, comparable = left_truncated_c_index(y_test.event_time_months, y_test.delayed_entry_months,
                                                (y_test.event_cause == 1).astype(int), risk_test)
    horizon_candidates = [int(h) for h in config["model"]["evaluation_horizons_months"]]
    max_h = min(int(y_train.event_time_months.max()), max(horizon_candidates))
    horizons = [h for h in horizon_candidates if h <= max_h]
    if not horizons:
        raise ValueError("No supported evaluation horizons in training follow-up")
    pred_cif = competing_cox_cif(models, x_test, y_test.delayed_entry_months.to_numpy(), horizons)
    predictions = y_test.copy()
    predictions.insert(0, "loan_id", df.iloc[test_idx].loan_id.to_numpy())
    for j, h in enumerate(horizons):
        predictions[f"cif_90plus_{h}m"] = pred_cif[:, j]
    predictions.to_csv(output_dir / "test_predictions.csv", index=False)
    design_diagnostics = {"rank": int(np.linalg.matrix_rank(x_train.to_numpy())),
                          "n_features": x_train.shape[1],
                          "condition_number": float(np.linalg.cond(x_train.to_numpy()))}
    censor_km = fit_monthly_censoring(y_train.event_time_months,
                                     y_train.delayed_entry_months, y_train.event_cause)
    brier_rows, brier_terms = [], {}
    cal_rows, cal_summary_rows = [], []
    for j, h in enumerate(horizons):
        score, outcome, weight = cif_ipcw_brier(y_test.event_time_months, y_test.delayed_entry_months,
                                                 y_test.event_cause, h, pred_cif[:, j], censor_km)
        eligible = y_test.delayed_entry_months.to_numpy() < h
        losses = weight * (outcome - pred_cif[:, j]) ** 2
        if not np.isfinite(score):
            losses[:] = np.nan
        brier_terms[h] = (losses, eligible)
        positive = weight[weight > 0]
        ess = float(positive.sum() ** 2 / np.sum(positive ** 2)) if positive.size else 0.0
        g_entry = censor_km.survival_function_at_times(y_test.delayed_entry_months.to_numpy()).to_numpy()
        g_h = _km_survival_before(censor_km, h)
        conditional_g = np.divide(g_h, g_entry, out=np.zeros_like(g_entry), where=g_entry > 0)
        brier_rows.append({"horizon_months": h, "cif_ipcw_brier": score,
                           "eligible_test_loans": int(eligible.sum()),
                           "test_event_90plus_by_horizon": int(((y_test.event_cause == 1) & (y_test.event_time_months <= h) & eligible).sum()),
                           "test_competing_exits_by_horizon": int(((y_test.event_cause == 2) & (y_test.event_time_months <= h) & eligible).sum()),
                           "censor_survival_at_horizon_pre_horizon": g_h,
                           "minimum_conditional_censor_survival": float(np.min(conditional_g[eligible])) if eligible.any() else float("nan"),
                           "maximum_ipcw_weight": float(weight.max()) if weight.size else 0.0,
                           "ipcw_effective_sample_size": ess,
                           "test_censors_before_horizon": int((eligible & (y_test.event_cause == 0) & (y_test.event_time_months < h)).sum()),
                           "ipcw_score_defined": bool(np.isfinite(score))})
        # Calibration IPCW theo ngũ phân vị CIF dự báo, có điều kiện theo entry và horizon.
        p = pred_cif[:, j]
        cal_summary_rows.append({"horizon_months": h, "eligible_test_loans": int(eligible.sum()),
                                 "mean_predicted_cif": float(np.mean(p[eligible])) if eligible.any() else float("nan"),
                                 "observed_cif_ipcw": float(np.sum(weight * outcome) / np.sum(weight)) if np.sum(weight) else float("nan")})
        groups = pd.qcut(pd.Series(p[eligible]), q=5, duplicates="drop")
        elig_idx = np.flatnonzero(eligible)
        for grp in groups.unique():
            local = groups == grp
            ids = elig_idx[np.asarray(local)]
            ww = weight[ids]
            observed = float(np.sum(ww * outcome[ids]) / np.sum(ww)) if np.sum(ww) else float("nan")
            cal_rows.append({"horizon_months": h, "risk_group": str(grp), "n": len(ids),
                             "mean_predicted_cif": float(np.mean(p[ids])), "observed_cif_ipcw": observed})
    pd.DataFrame(brier_rows).to_csv(tables_dir / "cif_brier_scores.csv", index=False)
    pd.DataFrame(cal_rows).to_csv(tables_dir / "cif_calibration.csv", index=False)
    pd.DataFrame(cal_summary_rows).to_csv(tables_dir / "cif_overall_test_calibration.csv", index=False)
    # Đường tham chiếu AJ phi tham số trên mẫu holdout, với risk set delayed entry.
    aj_test = aalen_johansen_cif(y_test.event_time_months.to_numpy(), y_test.delayed_entry_months.to_numpy(),
                                  y_test.event_cause.to_numpy(), times=np.arange(1, int(y_test.event_time_months.max()) + 1))
    aj_test.to_csv(tables_dir / "aalen_johansen_test.csv", index=False)
    aj_full = aalen_johansen_cif(y.event_time_months.to_numpy(), y.delayed_entry_months.to_numpy(), y.event_cause.to_numpy())
    aj_full.to_csv(tables_dir / "aalen_johansen_full.csv", index=False)
    # Đường AJ biên chỉ fit trên train, điều kiện hóa theo từng khoản test chưa
    # gặp biến cố tại delayed entry. Chỉ chấm các kết quả horizon đã quan sát.
    aj_train = aalen_johansen_cif(y_train.event_time_months.to_numpy(),
                                  y_train.delayed_entry_months.to_numpy(),
                                  y_train.event_cause.to_numpy())
    admin_rows = []
    for j, h in enumerate(horizons):
        eligible = y_test.delayed_entry_months.to_numpy() < h
        baseline = np.full(len(y_test), np.nan)
        baseline[eligible] = conditional_aj_cif(
            aj_train, y_test.delayed_entry_months.to_numpy()[eligible], h)
        if not np.isfinite(baseline[eligible]).all():
            raise ArithmeticError(f"Training AJ reference has no support at month {h}")
        model_score, valid, outcome, model_losses = administrative_brier_terms(
            y_test.event_time_months, y_test.delayed_entry_months, y_test.event_cause,
            h, pred_cif[:, j])
        base_score, valid_base, _, base_losses = administrative_brier_terms(
            y_test.event_time_months, y_test.delayed_entry_months, y_test.event_cause,
            h, np.nan_to_num(baseline, nan=0.0))
        if not np.array_equal(valid, valid_base):
            raise ArithmeticError("Administrative benchmark eligibility mismatch")
        paired = paired_bootstrap_mean_difference(model_losses, base_losses, valid,
                                                  bootstrap_n, seed + 2 + j)
        admin_rows.append({"horizon_months": h, "administrative_brier_model": model_score,
                           "administrative_brier_training_aj_reference": base_score,
                           "model_minus_reference": paired["difference"],
                           "paired_test_bootstrap_ci_2_5": paired["ci_2_5"],
                           "paired_test_bootstrap_ci_97_5": paired["ci_97_5"],
                           "known_outcomes_scored": int(valid.sum()),
                           "eligible_by_entry": int(eligible.sum()),
                           "unknown_censored_before_horizon": int((eligible & (y_test.event_cause.to_numpy() == 0) &
                                                                     (y_test.event_time_months.to_numpy() < h)).sum()),
                           "reference": "Aalen–Johansen delayed entry trên tập train, có điều kiện chưa biến cố tại entry",
                           "bootstrap_replicates_requested": int(bootstrap_n),
                           "bootstrap_replicates_successful": paired["successful_replicates"],
                           "bootstrap_seed": int(seed + 2 + j),
                           "bootstrap_method": "lấy mẫu ghép cặp percentile theo ID khoản vay test; giữ cố định dự báo đã fit",
                           "uncertainty_scope": "bootstrap ghép cặp khoản vay test; giữ cố định AJ train và Cox đã fit"})
    pd.DataFrame(admin_rows).to_csv(tables_dir / "cif_administrative_benchmark.csv", index=False)
    trend_tables = []
    for cause, name in ((1, "event_90plus"), (2, "any_zero_balance_exit")):
        event_train = (y_train.event_cause.to_numpy() == cause).astype(int)
        trend_tables.append(schoenfeld_trend(models[cause], x_train, y_train.event_time_months,
                                              y_train.delayed_entry_months, event_train, name))
    ph = pd.concat(trend_tables, ignore_index=True)
    ph.to_csv(tables_dir / "schoenfeld_trend_approx.csv", index=False)
    bootstrap = bootstrap_metric_intervals(y_test.event_time_months.to_numpy(), y_test.delayed_entry_months.to_numpy(),
                                           y_test.event_cause.to_numpy(), risk_test, horizons,
                                           brier_terms, bootstrap_n, seed + 1)
    bootstrap.to_csv(tables_dir / "test_metric_bootstrap_fixed_model.csv", index=False)
    # Lưu baseline hazard và mô hình/tiền xử lý đã fit ở dạng máy đọc được để tái lập.
    bundle_path = output_dir / "cause_specific_cox_models.pkl"
    with bundle_path.open("wb") as f:
        pickle.dump({"models": models, "feature_columns": list(x_train.columns), "transform": transform,
                     "causes": {1: "lần đầu ghi nhận quá hạn 90+", 2: "mọi trường hợp kết thúc zero-balance"},
                     "use_cltv_sensitivity": use_cltv}, f)
    reloaded = load_model_bundle(bundle_path)
    smoke_predictions = score_new_loans(reloaded, df.iloc[test_idx[:5]].copy(), horizons)
    smoke_cif_cols = [c for c in smoke_predictions if c.startswith("predicted_cif_")]
    if not np.isfinite(smoke_predictions[smoke_cif_cols].to_numpy(float)).all():
        raise ArithmeticError("Loaded-model scoring smoke test produced non-finite CIF values")
    if np.any(smoke_predictions[smoke_cif_cols].to_numpy(float) < -1e-10) or np.any(smoke_predictions[smoke_cif_cols].to_numpy(float) > 1 + 1e-10):
        raise ArithmeticError("Loaded-model scoring smoke test violated CIF bounds")
    for cause, name in ((1, "event_90plus"), (2, "any_zero_balance_exit")):
        models[cause].baseline_cumulative_hazard_.to_csv(tables_dir / f"baseline_cumulative_hazard_{name}.csv")
    metrics = {"n_train": len(train_idx), "n_test": len(test_idx),
               "train_cause_counts": {str(k): int((y_train.event_cause == k).sum()) for k in (0, 1, 2)},
               "test_cause_counts": {str(k): int((y_test.event_cause == k).sum()) for k in (0, 1, 2)},
               "left_truncated_harrell_c_index_event_90plus": cindex, "comparable_pairs": comparable,
               "cif_brier_scores": brier_rows, "horizons_months": horizons,
               "fit_warnings": fit_warnings, "bootstrap_replicates_requested": bootstrap_n,
               "baseline_method": "Breslow with L<t<=T; full integer monthly grid including H(0)=0",
               "analysis_contract": "docs/analysis_contract.md v1 (2026-10-23)",
               "design_diagnostics": design_diagnostics,
               "bootstrap_scope": "lấy mẫu lại khoản vay test; giữ cố định mô hình, tiền xử lý và KM kiểm duyệt IPCW",
               "diagnostic_scope": "xu hướng Schoenfeld xấp xỉ, chưa scale; lifelines không hỗ trợ residual đã scale với entry_col.",
               "model_save_load_scoring_smoke_test": "đạt trên năm dòng đặc trưng khoản vay holdout; không dùng dự báo để chọn mô hình",
               "cif_method": "Hai Cox nguyên nhân cụ thể; cumulative-hazard increment theo tháng được nội suy thành hazard hằng từng đoạn trong tháng; cập nhật competing-exponential chính xác có điều kiện trên phép nội suy này; dự báo có điều kiện khoản vay sống không biến cố đến delayed entry.",
               "censoring_assumption": "Monthly reverse product-limit on training with L<t<=T; cause events precede end-of-month censoring; weights G(L)/G(u-). Independent censoring/truncation assumptions remain unverified. Known-status Brier scores only observed outcomes and is not the administrative Brier estimator of Kvamme-Borgan.",
               "split": split_label,
               "features": list(x_train.columns), "preprocessing": transform, "use_cltv_sensitivity": use_cltv}
    (output_dir / "model_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _plot_cif(aj_full, aj_test, cal_summary_rows, figures_dir)
    return metrics


def _plot_cif(aj_full, aj_test, calibration, figures_dir):
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.step(aj_full.time_months, aj_full.cif_cause_1, where="post", label="Aalen-Johansen, full cohort")
    ax.step(aj_test.time_months, aj_test.cif_cause_1, where="post", label="Aalen-Johansen, test")
    ax.set(xlabel="Months from First Payment Date", ylabel="Aalen-Johansen CIF estimate",
           title="Observed 90+ delinquency incidence in analysis cohort")
    ax.set_ylim(0, max(.02, float(aj_full.cif_cause_1.max()) * 1.15))
    ax.grid(alpha=.25); ax.legend(); fig.tight_layout()
    fig.savefig(figures_dir / "cif_90plus_cohort.png", dpi=160); plt.close(fig)
    fig, ax = plt.subplots(figsize=(6, 6))
    pred = [r["mean_predicted_cif"] for r in calibration]
    obs = [r["observed_cif_ipcw"] for r in calibration]
    upper = max(.01, max(pred + obs) * 1.15)
    ax.plot([0, upper], [0, upper], "k--", linewidth=1, label="Ideal calibration")
    ax.plot(pred, obs, "o-", label="Test set, IPCW")
    for r in calibration:
        ax.annotate(f"{r['horizon_months']}m", (r["mean_predicted_cif"], r["observed_cif_ipcw"]),
                    xytext=(4, 4), textcoords="offset points")
    ax.set(xlim=(0, upper), ylim=(0, upper), xlabel="Mean predicted CIF (conditional on entry)",
           ylabel="Observed CIF (IPCW, conditional on entry)", title="Overall test-set CIF calibration")
    ax.grid(alpha=.25); ax.legend(); fig.tight_layout()
    fig.savefig(figures_dir / "cif_calibration.png", dpi=160); plt.close(fig)


def main() -> None:
    config = load_analysis_config()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--orig", type=Path, default=ROOT / config["data"]["origination"])
    parser.add_argument("--perf", type=Path, default=ROOT / config["data"]["performance"])
    parser.add_argument("--outputs", type=Path, default=ROOT / "outputs")
    parser.add_argument("--reports", type=Path, default=ROOT / "reports")
    parser.add_argument("--bootstrap", type=int, default=int(config["model"]["bootstrap_replicates"]))
    parser.add_argument("--seed", type=int, default=int(config["model"]["seed"]))
    parser.add_argument("--cltv-sensitivity", action="store_true")
    parser.add_argument("--tie-as-event-sensitivity", action="store_true",
                        help="fit lại cùng mô hình sau khi gán trường hợp 90+/zero-balance cùng tháng cho nguyên nhân 1")
    args = parser.parse_args()
    if args.cltv_sensitivity and args.tie_as_event_sensitivity:
        parser.error("hãy chạy riêng phân tích độ nhạy CLTV và tie cùng tháng")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    audit = audit_data(args.orig, args.perf, args.reports)
    LOG.info("Audit complete: %d origination loans, %d performance rows", audit["origination"]["rows"], audit["performance"]["rows"])
    df, summary = build_survival_data(args.orig, args.perf, args.outputs / "survival_dataset.csv")
    (args.outputs / "survival_dataset_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    audit["survival_cohort_construction"] = summary
    (args.reports / "data_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    audit_md = args.reports / "data_audit.md"
    with audit_md.open("a", encoding="utf-8") as f:
        f.write("\n## Survival cohort construction\n\n")
        f.write(f"- Loans in source origination/performance files: {audit['origination']['unique_loan_ids']:,}.\n")
        f.write(f"- Loans excluded because zero-balance effective date precedes First Payment Date: {summary['loans_excluded_terminal_before_time_origin']:,} ({summary['excluded_pre_origin_terminal_codes']}).\n")
        f.write(f"- Analysis loans: {summary['n_loans']:,}; first 90+ events: {summary['primary_90plus_events']:,}; competing exits: {summary['competing_zero_balance_exits']:,}; right-censored: {summary['right_censored']:,}.\n")
        f.write(f"- First performance month relative to First Payment Date (before/at/after): {summary['first_performance_month_relative_to_time_origin']}.\n")
        f.write(f"- Pre-origin 90+ status rows ignored: {summary['pre_origin_90plus_rows_ignored']:,}; same-month 90+/termination ties assigned to competing exit: {summary['same_month_ambiguities_treated_as_competing']:,}.\n")
    LOG.info("Survival dataset: %s", json.dumps({k: summary[k] for k in ["n_loans", "primary_90plus_events", "competing_zero_balance_exits", "right_censored", "same_month_ambiguities_treated_as_competing", "endpoint_b_total_events"]}))
    if args.tie_as_event_sensitivity:
        primary_split_stratification = df.event_cause.to_numpy() == 1
        ties = df.same_month_90plus_termination_tie.astype(int).eq(1)
        if int(ties.sum()) != summary["same_month_ambiguities_treated_as_competing"]:
            raise ArithmeticError("Tie sensitivity mask disagrees with the survival construction audit")
        df.loc[ties, "event_cause"] = 1
        df.loc[ties, "event_a_90plus"] = 1
        df.loc[ties, "exit_type"] = "first_90plus_tie_sensitivity"
    output_tag = "models_tie_sensitivity" if args.tie_as_event_sensitivity else "models_cltv" if args.cltv_sensitivity else "models"
    table_tag = "tables_tie_sensitivity" if args.tie_as_event_sensitivity else "tables_cltv" if args.cltv_sensitivity else "tables"
    figure_tag = "figures_tie_sensitivity" if args.tie_as_event_sensitivity else "figures_cltv" if args.cltv_sensitivity else "figures"
    metrics = run_model(df, args.outputs / output_tag,
                        args.reports / table_tag,
                        args.reports / figure_tag,
                        seed=args.seed, test_fraction=float(config["model"]["test_fraction"]),
                        bootstrap_n=args.bootstrap, use_cltv=args.cltv_sensitivity,
                        split_stratification=primary_split_stratification if args.tie_as_event_sensitivity else None)
    if args.tie_as_event_sensitivity:
        metrics["tie_sensitivity"] = {"same_month_ties_assigned_to_event": int(ties.sum()),
                                      "primary_rule": "assign same-month zero-balance termination to competing cause"}
        (args.outputs / output_tag / "model_metrics.json").write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    LOG.info("Model complete: C-index=%s; test CIF scores=%s", metrics["left_truncated_harrell_c_index_event_90plus"], metrics["cif_brier_scores"])


if __name__ == "__main__":
    main()
