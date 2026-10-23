# Task 5 — Nhật ký hoàn thiện báo cáo

## Các thay đổi nội dung

1. **CIF do Cox và delayed entry:** Làm rõ cumulative-hazard increments được diễn giải qua giả định cause-specific hazard hằng trong từng tháng. Cập nhật competing-exponential là chính xác có điều kiện trên phép nội suy đó; đây không phải cập nhật Aalen–Johansen rời rạc theo tháng. Dự báo cho delayed entrants được mô tả là có điều kiện trên việc event-free qua entry, không phải xác suất vô điều kiện từ FPD. Chú thích hình CIF phân biệt đường cong AJ quan sát với CIF dự báo Cox.
2. **Brier và censoring:** Giữ nguyên các số đã kiểm toán; trình bày IPCW Brier và known-status Brier thành hai đại lượng riêng. Nêu mẫu số eligible của IPCW, mẫu số known outcomes của điểm không trọng số, và việc censor trước horizon bị loại khỏi known-status score. Nêu rõ marginal reverse-KM phụ thuộc giả định censoring không được xác lập trong dữ liệu administrative censoring theo lịch FPD; trọng số gần 1 không chứng minh giả định và IPCW không được gọi là không chệch cho toàn cohort.
3. **Phạm vi holdout theo lịch:** Bổ sung bảng và mô tả holdout FPD sau 201512, gồm sample size, event counts, C-index, số cặp và Brier theo các horizon 12/24/36/60/120. Ghi rõ test chủ yếu là FPD năm 2016, outcomes huấn luyện 2015 đã trưởng thành đến cutoff dữ liệu 2026; vì vậy đây là validation nội bộ cùng sample, không phải mô phỏng deployment as-of lịch sử hay external validation. Pair counts của holdout ngẫu nhiên và calendar được gắn riêng.
4. **Metrics và bất định:** Phân biệt C-index là discrimination, Brier là squared probability prediction error, và calibration summaries là so sánh mô tả giữa incidence dự báo và quan sát. Ghi rõ calibration chỉ là point estimates không có intervals; bootstrap 100 lần giữ model/predictions cố định và không bao gồm bất định fitting, split hoặc cohort.
5. **Giới hạn và nhất quán:** Giữ các giới hạn delayed entry, ties cùng tháng, Schoenfeld diagnostics xấp xỉ, administrative censoring, và thiếu external validation; bổ sung nội suy hazard tháng và phạm vi bootstrap. Hiệu chỉnh lại metadata trang Cox (187–202) và thay liên kết Aalen–Johansen bằng bản JSTOR ổn định sau khi đối chiếu nguồn.
6. **Phương pháp:** Đồng bộ `docs/methodology.md` với report về ý nghĩa “exact” có điều kiện, dự báo delayed-entry, phạm vi calendar holdout và calibration point estimates. Các định nghĩa endpoint, cohort, pipeline, và kết quả số không đổi.

## Kiểm tra số liệu

Các giá trị holdout ngẫu nhiên và calendar được đối chiếu với `outputs/models/model_metrics.json`, `outputs/models_temporal_validation/model_metrics.json`, `reports/tables/cif_brier_scores.csv`, `reports/tables/cif_overall_test_calibration.csv`, `reports/tables/cif_administrative_benchmark.csv` và các bảng cùng tên trong `reports/tables_temporal_validation/`. CIF AJ toàn cohort được đối chiếu với `reports/tables/aalen_johansen_full.csv`; sensitivities, counts và diagnostics với báo cáo audit Task 4 cùng các artifact liên quan. Không phát hiện mismatch số nguồn cần sửa.

## Lệnh kiểm tra

- `python -m unittest discover -s tests -v` — 24 tests passed.
- Inline `python -c` consistency assertions — passed: checked random/calendar C-index pair counts, split sizes, horizon list, Brier eligible denominators, calibration row count and required interpretation language against source JSON/CSV/report.
- `python -c` local-link check — passed: all four linked audit, methodology, and figure targets resolve from `reports/research_report.md`.
- `git diff --check -- reports/research_report.md docs/methodology.md reports/task5_finalization_log.md` — passed; Git displayed only an LF-to-CRLF working-copy notice for the report.

## Giới hạn còn lại

Kết luận vẫn bị giới hạn bởi cohort Freddie Mac 2015, delayed-entry/independent-truncation assumptions chưa kiểm chứng, thời điểm chỉ xác định theo tháng và 30 ties chưa phân thứ tự, administrative censoring gắn với FPD, diagnostics Schoenfeld xấp xỉ, bootstrap điều kiện trên fitted predictions, và không có external validation.
