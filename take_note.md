# Ghi chú dự án

## Dataset

- Freddie Mac Single-Family Loan-Level Dataset, Sample 2015; dữ liệu này không phải LendingClub.
- Hai tệp nguồn: `sample_orig_2015.txt` (khởi tạo) và `sample_perf_2015.txt` (tháng), ghép bằng Loan Identifier.
- Định dạng gốc pipe-delimited, không có header. Mẫu có 50.000 khoản vay, 3.467.166 bản ghi performance.
- Dữ liệu được đối chiếu theo schema Release 47 (July 2026). Kiểm tra số dòng, IDs, duplicates, tháng, trạng thái delinquency, zero-balance codes và missingness nằm trong `reports/data_audit.md`.

## Định nghĩa phân tích

- Thời gian gốc: First Payment Date; đơn vị tháng lịch.
- 43.823 loan có performance trước FPD, 3.441 bắt đầu đúng FPD và 2.736 sau FPD; pre-origin history được coi là đã biết tại time zero, nhóm bắt đầu sau dùng delayed entry.
- Delayed entry: thời điểm bắt đầu lịch sử performance sau First Payment Date.
- Event A: tháng đầu ghi Current Loan Delinquency Status `03+` (90+ ngày), là proxy báo cáo chứ không khẳng định legal default/loss.
- Competing exit: zero-balance termination bất kỳ; giữ nguyên code gốc. Trong mẫu phần lớn là code `01`.
- Cùng tháng có event/termination: không biết thứ tự nên xếp termination là competing trong phân tích chính; có 30 trường hợp.
- Endpoint B mã `03` hoặc `09`: 73 trường hợp, chỉ mô tả; không fit Cox đa biến.

## Kết quả đã chạy

- Cohort phân tích: 49.980; 20 khoản vay có zero-balance date trước First Payment Date bị loại; event A: 2.019; competing exits: 37.305; kiểm duyệt: 10.656.
- Cox hai nguyên nhân + tích phân CIF cạnh tranh; chia 80/20 theo khoản vay, seed 2026. C-index holdout có delayed entry: 0,75119; bootstrap 100 mẫu test-loan, mô hình giữ cố định, KTC 95%: 0,73329–0,77417.
- Brier CIF/IPCW tại 12/24/36/60/120 tháng: 0,001234 / 0,004672 / 0,008640 / 0,024186 / 0,037024. Tại 120 tháng support được ước lượng (G=0,99875, max IPCW=1,00126), nhưng phụ thuộc giả định censoring độc lập.
- Sensitivity thay LTV bằng CLTV: C-index 0,75249, tăng khoảng 0,00130 so với mô hình chính; cùng split theo loan ID.
- Tie sensitivity (30 same-month ties recoded as event; exact same test IDs): C-index 0,75353; Brier changes are reported in `reports/pipeline_audit.md`.
- Test tổng hợp: 16 test passed; gồm 10 phép thử Brier với expected weights/loss tính tay, Aalen–Johansen ties, hazard CIF nghiệm đóng, pre-origin exclusion, delayed entry, serialization/scoring, lịch tháng và C-index đối chiếu tay.

## Chạy lại

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python src/survival_pipeline.py --bootstrap 100
python src/survival_pipeline.py --cltv-sensitivity --bootstrap 20
python src/survival_pipeline.py --tie-as-event-sensitivity --bootstrap 20
python src/eda.py
```

Diễn giải, giả định, bảng và giới hạn nằm trong `reports/research_report.md`, `docs/methodology.md` và `docs/data_dictionary.md`. Mô hình có thể chấm điểm dòng origination mới thông qua `load_model_bundle()` và `score_new_loans()`; dự báo có điều kiện khoản vay còn event-free tới delayed entry.
