# Ghi chú dự án

## Dataset

- Freddie Mac Single-Family Loan-Level Dataset, Sample 2015; dữ liệu này không phải LendingClub.
- Hai tệp nguồn: `sample_orig_2015.txt` (khởi tạo) và `sample_perf_2015.txt` (tháng), ghép bằng Loan Identifier.
- Định dạng gốc pipe-delimited, không có header. Mẫu có 50.000 khoản vay, 3.467.166 bản ghi performance.
- Dữ liệu được đối chiếu theo schema Release 47 (July 2026). Kiểm tra số dòng, IDs, duplicates, tháng, trạng thái delinquency, zero-balance codes và missingness nằm trong `reports/data_audit.md`.

## Định nghĩa phân tích

- Thời gian gốc: First Payment Date; đơn vị tháng lịch.
- Delayed entry: thời điểm bắt đầu lịch sử performance của từng khoản vay.
- Event A: tháng đầu ghi Current Loan Delinquency Status `03+` (90+ ngày), là proxy báo cáo chứ không khẳng định legal default/loss.
- Competing exit: zero-balance termination bất kỳ; giữ nguyên code gốc. Trong mẫu phần lớn là code `01`.
- Cùng tháng có event/termination: không biết thứ tự nên xếp termination là competing trong phân tích chính; có 30 trường hợp.
- Endpoint B mã `03` hoặc `09`: 73 trường hợp, chỉ mô tả; không fit Cox đa biến.

## Kết quả đã chạy

- Cohort: 50.000; event A: 2.019; competing exits: 37.325; kiểm duyệt: 10.656.
- Cox hai nguyên nhân + tích phân CIF cạnh tranh; 40k train / 10k holdout cùng vintage, seed 2026.
- C-index holdout có delayed entry: 0,7515; bootstrap 100 mẫu test-loan, mô hình giữ cố định, KTC 95% xấp xỉ 0,7298–0,7778.
- Brier CIF/IPCW tại 12/24/36/60 tháng: 0,00123 / 0,00468 / 0,00865 / 0,02424.
- Sensitivity thay LTV bằng CLTV: C-index 0,7524; chỉ cải thiện khoảng 0,0009.
- Test tổng hợp: 6 test passed; kiểm tra Aalen–Johansen tied events, competing hazards vs nghiệm đóng, delayed entry, event tie rules, scoring/load model, calendar-month boundaries và C-index đối chiếu tay.

## Chạy lại

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python src/survival_pipeline.py --bootstrap 100
python src/survival_pipeline.py --cltv-sensitivity --bootstrap 20
python src/eda.py
```

Diễn giải, giả định, bảng và giới hạn nằm trong `reports/research_report.md`, `docs/methodology.md` và `docs/data_dictionary.md`. Mô hình có thể chấm điểm dòng origination mới thông qua `load_model_bundle()` và `score_new_loans()`; dự báo có điều kiện khoản vay còn event-free tới delayed entry.
