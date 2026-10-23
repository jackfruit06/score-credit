# Cox Survival Analysis với competing risks và delayed entry

Dự án phân tích thời gian đến **lần đầu khoản vay được ghi nhận quá hạn từ 90 ngày trở lên** trong Freddie Mac Single-Family Loan-Level Dataset Sample 2015. Mô hình xử lý đồng thời:

- **Nguyên nhân 1:** tháng đầu tiên ghi nhận trạng thái delinquency dạng số từ `03` đến `99`.
- **Nguyên nhân 2:** khoản vay kết thúc khỏi dataset với zero-balance code được quy định trong hợp đồng phân tích.
- **Kiểm duyệt phải:** chưa quan sát hai nguyên nhân trên trước khi lịch sử dữ liệu kết thúc.
- **Delayed entry:** lịch sử performance của một số khoản vay bắt đầu sau First Payment Date.

Nguyên nhân 2 là trạng thái kết thúc quan sát trong dataset, không đồng nghĩa với vỡ nợ, charge-off hoặc tổn thất. Kết quả là liên hệ dự báo trong mẫu nghiên cứu, không phải tác động nhân quả.

Các định nghĩa toán học và quy tắc tạo cohort được chốt tại [hợp đồng phân tích](docs/analysis_contract.md). Xem thêm [phương pháp](docs/methodology.md), [từ điển dữ liệu](docs/data_dictionary.md), [nguồn dữ liệu](docs/provenance_data.md) và [kết quả chạy lại mới nhất](reports/run_summary.md).

## Pipeline làm gì?

```text
Raw origination + performance
        ↓
Kiểm tra schema và chất lượng dữ liệu
        ↓
Tạo một dòng survival cho mỗi khoản vay: (T, L, J, X)
        ↓
Chia train/test ở cấp khoản vay
        ↓
Học preprocessing chỉ trên train
        ↓
Fit hai cause-specific Cox PH có delayed entry
        ↓
Tính baseline hazard và CIF từ cả hai cause-specific hazards
        ↓
Đánh giá, lưu model, bảng và hình
```

Trong đó:

- `L` là tháng khoản vay đi vào risk set.
- `T` là tháng kết thúc theo dõi, biến cố hoặc competing event.
- `J=0` là kiểm duyệt, `J=1` là quá hạn 90+, `J=2` là zero-balance exit.
- Risk set tại tháng `t` dùng điều kiện `L < t <= T`.
- Hai mô hình Cox được fit riêng cho `J=1` và `J=2`. Khi fit một nguyên nhân, nguyên nhân còn lại kết thúc theo dõi tại thời điểm của nó nhưng không được gán là biến cố của mô hình đang fit.
- CIF được tính bằng cách kết hợp increment hazard của cả hai mô hình theo quy ước hazard hằng trong từng tháng. Pipeline không dùng `1 - S` của riêng mô hình 90+ làm CIF.

## Cấu trúc dự án

| Đường dẫn | Ý nghĩa |
|---|---|
| `src/survival_pipeline.py` | Pipeline chính: audit dữ liệu, tạo cohort, preprocessing, fit hai mô hình Cox, tính CIF, đánh giá, lưu model và vẽ hình. File này cũng cung cấp API dự báo khoản vay mới. |
| `src/temporal_validation.py` | Chạy kiểm định nội bộ theo thời gian: train với FPD đến `2015-12`, test với FPD sau `2015-12`. |
| `src/eda.py` | Tạo thống kê mô tả, phân bố biến cố và các biểu đồ EDA/Aalen–Johansen. |
| `config/analysis_config.json` | Cấu hình nguồn dữ liệu, endpoint, seed, tỷ lệ test, horizons và số bootstrap. |
| `docs/` | Hợp đồng phân tích, phương pháp, từ điển dữ liệu và provenance. |
| `tests/test_survival_pipeline.py` | Test các quy tắc survival, delayed entry, competing risks, CIF, Brier, C-index và model serialization. |
| `tests/test_audit_regressions.py` | Regression test cho baseline hazard, Efron ties, sentinel, sparse AJ, preprocessing và các lỗi phương pháp đã sửa. |
| `outputs/` | Dữ liệu survival đã tạo, model bundle, prediction/metric dạng máy đọc được và kết quả thực nghiệm. |
| `reports/` | Bảng CSV, hình PNG và báo cáo EDA/audit để đọc và đưa vào báo cáo nghiên cứu. |
| `sample_orig_2015.txt` | Dữ liệu khởi tạo khoản vay. |
| `sample_perf_2015.txt` | Lịch sử performance hằng tháng. |
| `sample_2015.zip` | Archive gốc chứa hai tệp dữ liệu trên. |
| `requirements.txt` | Các thư viện Python tối thiểu. |

Các thư mục con trong `outputs/` và `reports/` có ý nghĩa như sau:

| Thư mục | Nội dung |
|---|---|
| `outputs/models/` | Model chính, preprocessing, split, test predictions và metrics. |
| `outputs/models_temporal_validation/` | Model và metrics của temporal validation. |
| `outputs/models_cltv/` | Sensitivity dùng CLTV thay cho LTV. |
| `outputs/models_tie_sensitivity/` | Sensitivity gán trường hợp 90+/termination cùng tháng cho nguyên nhân 1. |
| `outputs/experiments/` | Kết quả các thực nghiệm nghiên cứu đã lưu riêng; không phải đường dẫn mặc định của pipeline. |
| `reports/tables*/` | Hệ số Cox, baseline hazard, CIF, Brier, calibration, bootstrap và chẩn đoán. Hậu tố chỉ nhánh temporal hoặc sensitivity tương ứng. |
| `reports/figures*/` | Đồ thị CIF và calibration của từng nhánh. |

## Kết quả được đưa lên GitHub

`.gitignore` chỉ giữ lại các artifact tổng hợp của lần chạy đầy đủ gần nhất ngày **2026-10-24** để đọc và viết báo cáo:

- `reports/run_summary.md`, `reports/data_audit.*` và `reports/eda.md`.
- Toàn bộ `reports/tables*/` và `reports/figures*/` của primary, temporal validation và hai sensitivity analyses.
- `outputs/survival_dataset_summary.json`.
- `model_metrics.json` của primary, temporal, CLTV và tie sensitivity.

Các file dung lượng lớn hoặc chứa dữ liệu cấp khoản vay không được đưa lên: `survival_dataset.csv`, `test_predictions.csv`, `split_membership.csv`, model pickle và toàn bộ kết quả lịch sử trong `outputs/experiments/`. Các báo cáo ngoài allowlist của lần chạy mới nhất cũng bị loại. Chúng có thể được tạo lại bằng các lệnh bên dưới. Dữ liệu raw được quản lý riêng; `sample_perf_2015.txt` đã được cấu hình bằng Git LFS trong `.gitattributes`.

## Cài đặt

Yêu cầu Python 3.10 trở lên. Từ thư mục gốc của dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Chạy test trước khi fit model:

```powershell
python -m unittest discover -s tests -v
```

Test không thay thế việc đánh giá giả định thống kê trên dữ liệu nghiên cứu, nhưng giúp phát hiện hồi quy trong cách tạo risk set, CIF và metric.

## Chạy mô hình

### 1. Chạy mô hình chính

```powershell
python src/survival_pipeline.py --bootstrap 100
```

Lệnh này dùng hai tệp raw mặc định, seed `2026`, chia ngẫu nhiên 80/20 ở cấp khoản vay và đánh giá tại 12, 24, 36, 60 và 120 tháng.

Đường dẫn mặc định là `outputs/` và `reports/`; chạy lại có thể ghi lại các artifact cùng tên. Để giữ riêng một lần chạy:

```powershell
python src/survival_pipeline.py `
  --outputs outputs/run_20261024 `
  --reports reports/run_20261024 `
  --bootstrap 100
```

Có thể đổi input bằng `--orig` và `--perf`, hoặc đổi seed bằng `--seed`.

### 2. Chạy EDA

EDA cần `survival_dataset.csv` đã được pipeline chính tạo:

```powershell
python src/eda.py
```

Với một thư mục chạy riêng:

```powershell
python src/eda.py `
  --data outputs/run_20261024/survival_dataset.csv `
  --outputs outputs/run_20261024 `
  --reports reports/run_20261024
```

### 3. Temporal validation

```powershell
python src/temporal_validation.py --bootstrap 100
```

Temporal validation thay cách chia ngẫu nhiên bằng cách chia theo First Payment Date. Đây vẫn là kiểm định nội bộ trong cùng sample, không phải external hoặc prospective validation.

Với thư mục chạy riêng:

```powershell
python src/temporal_validation.py `
  --dataset outputs/run_20261024/survival_dataset.csv `
  --outputs outputs/run_20261024 `
  --reports reports/run_20261024 `
  --bootstrap 100
```

### 4. Sensitivity analyses

Dùng CLTV thay cho LTV:

```powershell
python src/survival_pipeline.py --cltv-sensitivity --bootstrap 20
```

Gán các trường hợp 90+ và zero-balance cùng tháng cho biến cố 90+:

```powershell
python src/survival_pipeline.py --tie-as-event-sensitivity --bootstrap 20
```

Hai tùy chọn phải chạy riêng. Sensitivity dùng để đánh giá độ ổn định của kết luận; không chọn nhánh làm mô hình chính chỉ vì metric test tốt hơn.

## Sử dụng model để dự báo

Model chính được lưu tại:

```text
outputs/models/cause_specific_cox_models.pkl
```

Bundle chứa cả hai mô hình Cox, danh sách feature và preprocessing đã học trên train. Chỉ nạp file pickle do chính dự án tạo hoặc từ nguồn tin cậy.

Ví dụ dự báo một khoản vay mới:

```python
from pathlib import Path

import pandas as pd

from src.survival_pipeline import load_model_bundle, score_new_loans

bundle = load_model_bundle(
    Path("outputs/models/cause_specific_cox_models.pkl")
)

new_loans = pd.DataFrame([
    {
        "loan_id": "example-001",
        "classic_fico": 740,
        "original_ltv": 80,
        "original_cltv": 80,
        "original_dti": 35,
        "original_upb": 250000,
        "original_interest_rate": 4.0,
        "original_loan_term": 360,
        "mi_percentage": 0,
        "occupancy_status": "P",
        "loan_purpose": "P",
        "property_type": "SF",
        "first_time_homebuyer": "N",
        "channel": "R",
        "number_of_borrowers": 2,
        "number_of_units": 1,
        "delayed_entry_months": 0,
    }
])

predictions = score_new_loans(
    bundle,
    new_loans,
    horizons=[12, 24, 36, 60, 120],
)

print(predictions.to_string(index=False))
```

Các cột trả về gồm:

- `predicted_cif_first_90plus_12m`, `..._24m`, ..., `..._120m`: xác suất tích lũy gặp biến cố 90+ trước hoặc tại horizon, khi có competing risk.
- `predicted_cif_any_zero_balance_exit_12m`, `..._120m`: xác suất tích lũy kết thúc zero-balance.
- `delayed_entry_months`: tháng bắt đầu quan sát dùng để điều kiện hóa dự báo.
- `loan_id`: được giữ lại nếu input có cột này.

Nếu không truyền `delayed_entry_months`, API mặc định entry bằng 0. Với `L > 0`, dự báo là xác suất có điều kiện trên việc khoản vay vẫn chưa gặp biến cố đến tháng `L`. Horizon phải nằm trong khoảng follow-up mà model đã học và phải lớn hơn entry để có ý nghĩa dự báo.

Input cần các biến khởi tạo sau:

- Số: `classic_fico`, `original_ltv`, `original_cltv`, `original_dti`, `original_upb`, `original_interest_rate`, `original_loan_term`, `mi_percentage`.
- Phân loại: `occupancy_status`, `loan_purpose`, `property_type`, `first_time_homebuyer`, `channel`, `number_of_borrowers`, `number_of_units`.

Không đưa dữ liệu performance sau thời điểm khởi tạo vào input dự báo. Sentinel và missing được xử lý bằng quy tắc lưu trong bundle; không tự thay đổi schema hoặc mã hóa category trước khi gọi API.

## Đầu ra của pipeline chính

Khi chạy code hiện tại, pipeline chính tạo các nhóm đầu ra sau.

### Dữ liệu cohort

| File | Nội dung |
|---|---|
| `outputs/survival_dataset.csv` | Một dòng mỗi khoản vay, gồm dữ liệu khởi tạo, `delayed_entry_months`, `event_time_months`, `event_cause`, loại exit và cờ tie. |
| `outputs/survival_dataset.exclusions.csv` | Các khoản bị loại và lý do loại. |
| `outputs/survival_dataset_summary.json` | Số khoản vay, số event, competing exit, censoring, delayed entry và các kiểm tra cohort. |

### Model và dự báo

| File | Nội dung |
|---|---|
| `outputs/models/cause_specific_cox_models.pkl` | Hai mô hình Cox đã fit cùng preprocessing train-only. |
| `outputs/models/model_metrics.json` | C-index, Brier, số event, horizons, chẩn đoán thiết kế và metadata phương pháp. |
| `outputs/models/split_membership.csv` | Loan ID thuộc train hay test. |
| `outputs/models/test_predictions.csv` | Outcome của test và CIF 90+ dự báo tại từng horizon. |

### Bảng kết quả

| Nhóm file trong `reports/tables/` | Nội dung |
|---|---|
| `cox_*_coefficients.csv` | Hệ số, hazard ratio, khoảng tin cậy và p-value cho từng nguyên nhân. |
| `baseline_cumulative_hazard_*.csv` | Baseline cumulative hazard đã tính lại với delayed-entry risk set. |
| `aalen_johansen_*.csv` | CIF phi tham số cho toàn cohort và test. |
| `cif_brier_scores.csv` | IPCW Brier theo horizon. |
| `cif_administrative_benchmark.csv` | Brier trên outcome đã biết và so sánh với AJ fit trên train. |
| `cif_calibration.csv` | Calibration theo nhóm xác suất. |
| `cif_overall_test_calibration.csv` | Calibration-in-the-large theo horizon. |
| `test_metric_bootstrap_fixed_model.csv` | Khoảng bootstrap cho metric với model giữ cố định. |
| `schoenfeld_trend_approx.csv` | Screening xu hướng phần dư Schoenfeld cho giả định PH. |

### Hình và báo cáo dữ liệu

| File | Nội dung |
|---|---|
| `reports/figures/cif_90plus_cohort.png` | CIF Aalen–Johansen của biến cố 90+. |
| `reports/figures/cif_calibration.png` | Predicted CIF so với observed CIF trên test. |
| `reports/data_audit.json` và `reports/data_audit.md` | Schema, dữ liệu thiếu, mã trạng thái và kiểm tra tạo cohort. |

Chạy `src/eda.py` bổ sung `reports/eda.md`, thống kê mô tả trong `reports/tables/` và các hình `followup_duration.png`, `aalen_johansen_cif.png`, `cif_by_occupancy.png` cùng `km_net_survival_90plus.png`.

## Đọc kết quả đánh giá

- **C-index:** đo khả năng xếp hạng rủi ro; cao hơn cho thấy thứ hạng tốt hơn. Nó không đánh giá trực tiếp độ chính xác của xác suất.
- **Brier score:** sai số bình phương của dự báo xác suất; thấp hơn tốt hơn khi so sánh trên cùng cohort, horizon và công thức đánh giá.
- **Calibration:** mean predicted CIF nên gần observed CIF; cần xem cả tổng thể và từng nhóm rủi ro.
- **Bootstrap interval:** mô tả bất định do lấy mẫu lại các khoản test khi model giữ cố định; không bao gồm bất định do fit lại hoặc chọn split.
- **Hazard ratio:** cho biết liên hệ giữa feature và cause-specific hazard khi giữ các biến khác cố định. HR không phải tỷ lệ xác suất CIF và không chứng minh quan hệ nhân quả.
- **Schoenfeld screening:** giúp phát hiện dấu hiệu vi phạm proportional hazards, nhưng chẩn đoán hiện tại chỉ là screening xấp xỉ.

Một metric tốt hơn không tự chứng minh code hoặc lý thuyết đúng. Cần đọc đồng thời discrimination, Brier, calibration, giả định PH, giả định censoring/truncation và kết quả sensitivity.

## Giới hạn sử dụng

Model được phát triển trên Freddie Mac Sample 2015. Chưa có external validation trên vintage hoặc nguồn dữ liệu khác. Dự báo dài hạn phụ thuộc hỗ trợ follow-up, quy ước hazard theo tháng, proportional hazards và giả định về censoring/left truncation. Không dùng model như quyết định tín dụng tự động hoặc suy luận nhân quả nếu chưa có validation và governance phù hợp.
