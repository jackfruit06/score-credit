# Kiểm toán mức độ phù hợp giữa đề tài, code và kết quả

## Phạm vi và trạng thái repository

Kiểm tra tập trung vào pipeline thực thi tại `src/survival_pipeline.py`, pipeline holdout cohort tại `src/temporal_validation.py`, `config/analysis_config.json`, model bundle và các JSON/CSV artifacts hiện có, cùng phần mô tả trong `README.md`, `docs/methodology.md` và `reports/research_report.md`. Không fit lại mô hình, chạy toàn pipeline, sửa source hoặc thay đổi artifacts.

Trước khi làm, working tree đã có nhiều thay đổi tracked và untracked từ công việc trước; các thay đổi đó được giữ nguyên. Task này chỉ tạo file audit hiện tại. Không commit hoặc push.

## Bài toán mà code thực sự giải quyết

- **Đơn vị phân tích:** một khoản vay Freddie Mac, ghép từ một dòng khởi tạo và lịch sử báo cáo performance theo tháng. `config/analysis_config.json` chỉ rõ các tệp `sample_orig_2015.txt` và `sample_perf_2015.txt`; nguồn là Freddie Mac Single-Family Loan-Level Dataset Sample 2015. Tên thư mục dự án không phản ánh nguồn dữ liệu thực tế.
- **Thời điểm dự báo và đặc trưng:** pipeline dùng các đặc trưng khởi tạo: FICO, LTV, DTI, lãi suất, thời hạn, mortgage insurance, log dư nợ ban đầu, occupancy, loan purpose, property type, first-time buyer, channel, số borrower và số units. Chúng được lấy từ tệp origination, không phải trạng thái cập nhật sau khi khoản vay đã phát sinh lịch sử. `prepare_features()` học median, mean/scale, nhóm hiếm và vocabulary phân loại trên train rồi áp dụng cùng phép biến đổi lên test (`src/survival_pipeline.py:333–390`).
- **Mốc thời gian và vào risk set:** time origin là tháng lịch First Payment Date; thời lượng tính theo tháng lịch. `entry=max(0, first_performance_month - first_payment_month)`; risk set dùng điều kiện `entry < t` (`src/survival_pipeline.py:261–277`, `395–417`). Với khoản vay có lịch sử bắt đầu sau First Payment Date, mô hình chỉ dùng thời gian sau entry và dự báo là có điều kiện khoản vay còn event-free đến entry. Đây không phải xác suất vô điều kiện từ ngày First Payment Date cho các khoản delayed entry.
- **Endpoint chính:** hàng performance đầu tiên có status số `>=03` từ First Payment Date trở đi, nếu nó xảy ra trước zero-balance termination (`src/survival_pipeline.py:242–246`, `278–289`; `config/analysis_config.json`). Đây là lần đầu ghi nhận quá hạn nghiêm trọng 90+ theo mã báo cáo tháng, một chỉ báo vận hành. Code/config không định nghĩa endpoint này là legal default, foreclosure, charge-off, realized loss hoặc xác suất mất vốn.
- **Biến cố cạnh tranh:** zero-balance effective date là thời điểm kết thúc nếu có; nếu thiếu, dùng reporting month. Bất kỳ mã zero-balance nào trong `{01, 02, 03, 09, 15, 16, 96}` là competing termination; code giữ mã gốc. Tie 90+ và zero-balance trong cùng tháng được xếp vào competing termination vì thứ tự trong tháng không biết (`src/survival_pipeline.py:247–254`, `267–289`). Vì vậy, nhóm này không đồng nghĩa toàn bộ là borrower prepayment.
- **Quy tắc loại trừ và số cohort:** 20 khoản vay có zero-balance effective date trước origin bị loại; artifact `outputs/survival_dataset_summary.json` ghi 49.980 khoản phân tích, 2.019 event chính, 37.305 competing exits, 10.656 right-censored, 2.736 delayed entrants và 30 tie cùng tháng.
- **Chân trời:** 12/24/36/60/120 là tháng tính từ First Payment Date, theo `config/analysis_config.json`. Scoring chỉ tích lũy hazard increments sau entry (`integrate_competing_cumulative_hazards`, `src/survival_pipeline.py:492–536`). Khi horizon nhỏ hơn hoặc bằng entry, hàm hiện trả CIF 0 vì chưa tích lũy interval nào; đó không nên được diễn giải như một xác suất dự báo hợp lệ tại thời điểm trước entry. Trong đánh giá test, các khoản chỉ đủ điều kiện khi `entry < horizon`.

**Theo code hiện tại, dự án đang giải quyết bài toán dự báo có điều kiện thời gian đến lần đầu ghi nhận trạng thái quá hạn 90+ của khoản vay trong mẫu Freddie Mac 2015, có tính đến mọi zero-balance termination như một nguyên nhân cạnh tranh và có xử lý delayed entry; endpoint này là proxy quá hạn báo cáo, không phải nhãn tổn thất tín dụng đã xác minh.**

## Vai trò của Cox PH và đường đi đến dự báo

`run_model()` fit hai `lifelines.CoxPHFitter` (`src/survival_pipeline.py:762–817`): cause 1 là first reported 90+; cause 2 là any first zero-balance termination. Cả hai fit truyền `event_time_months` làm duration, `event_cause == cause` làm event indicator và `delayed_entry_months` qua `entry_col`. Các nguyên nhân khác là non-event tại thời điểm exit trong từng cause-specific fit. Đây là hai mô hình Cox PH nguyên nhân cụ thể; không có mô hình Cox riêng cho endpoint phụ mã zero-balance `03/09`.

Đặc trưng đều đến từ origination và được tiền xử lý theo train. Hệ số và hazard ratios được lưu trong các bảng hệ số. `predict_partial_hazard()` từ mô hình cause 1 tạo risk ranking dùng cho C-index. Để dự báo xác suất, `competing_cox_cif()` gọi cumulative hazard từ từng mô hình Cox; code lấy chênh lệch giữa các tháng, biểu diễn các increment bằng hazard hằng trong từng khoảng tháng và dùng competing-exponential update (`src/survival_pipeline.py:539–557`, `492–536`). Do đó CIF đánh giá là đầu ra suy ra từ hai Cox models đã fit, không phải chỉ số phụ trợ không liên quan đến Cox. Cập nhật exponential chính xác có điều kiện trên nội suy hazard hằng trong tháng; nó không phải cập nhật AJ rời rạc.

Ngược lại, các đường `aalen_johansen_full.csv` và biểu đồ cohort được tạo bởi `aalen_johansen_cif()` từ event counts/risk sets, không dùng đặc trưng loan-level và không phải dự báo Cox (`src/survival_pipeline.py:393–423`, `873–883`, `962–970`). Chúng là ước tính mô tả AJ của cohort/split tương ứng. Không dùng đường AJ làm bằng chứng rằng mô hình Cox đã tạo CIF cá nhân.

| Đầu ra | Trạng thái | Bằng chứng trong code/artifact |
|---|---|---|
| Hệ số Cox và hazard ratio | Có | `run_model()` fit hai Cox; ghi `cox_*_coefficients.csv`, trong đó có `coef` và `hazard_ratio` (`src/survival_pipeline.py:800–817`). |
| Risk score cấp khoản vay | Có, dưới dạng partial hazard nội bộ | `predict_partial_hazard()` tạo risk cho C-index (`src/survival_pipeline.py:818–820`). `score_new_loans()` không trả riêng cột risk score. |
| Cumulative hazard cấp khoản vay | Có, tính nội bộ | Hai fitted models được gọi bằng `predict_cumulative_hazard()` trong `competing_cox_cif()` và `score_new_loans()` (`src/survival_pipeline.py:547`, `593–596`); scoring API không trả bảng cumulative hazard riêng. |
| Event-free survival | Có, tính nội bộ | Được cập nhật trong competing-hazard integrator và dùng kiểm tra tổng xác suất (`src/survival_pipeline.py:510–535`); không được trả riêng bởi `score_new_loans()`. |
| CIF theo đặc trưng, có điều kiện theo entry | Có | `score_new_loans()` áp dụng preprocessing đã lưu, đọc entry nếu có và dùng hai Cox cumulative hazards (`src/survival_pipeline.py:560–604`). |
| Xác suất tại các chân trời cụ thể | Có | Mặc định 12/24/36/60/120 tháng; đầu ra gồm `predicted_cif_first_90plus_*` và `predicted_cif_any_zero_balance_exit_*` (`src/survival_pipeline.py:584–604`). Chỉ diễn giải horizon sau entry. |
| Scoring từ mô hình đã lưu | Có, smoke test thành công | Model bundle `outputs/models/cause_specific_cox_models.pkl`; hàm `load_model_bundle()`/`score_new_loans()`. Smoke test đọc ba dòng từ `outputs/survival_dataset.csv`, không fit và không ghi file. |

### Smoke test scoring chỉ đọc

Đã tải bundle hiện có `outputs/models/cause_specific_cox_models.pkl` và gọi `score_new_loans()` trên ba dòng khoản vay sẵn có. Hàm trả 10 cột CIF: hai nguyên nhân tại năm horizon. Tất cả giá trị hữu hạn, nằm trong [0,1] và không giảm theo horizon; dự báo 90+ tại 120 tháng khác nhau giữa các hồ sơ (khoảng 0,00781–0,02995). Một dòng có entry tháng 48 cho CIF 0 tại horizon 12, 24 và 36, rồi giá trị dương ở 60/120 tháng. Điều này xác nhận chức năng tạo dự báo có phụ thuộc đặc trưng và horizon, nhưng cũng cho thấy phải bỏ qua hoặc xử lý riêng horizon không sau entry. Smoke test không đánh giá độ chính xác hay khả năng tổng quát.

## Mức độ “vỡ nợ” được endpoint hỗ trợ

README, methodology và research report hiện nói rõ endpoint là first reported 90+ delinquency, proxy vận hành chứ không phải legal default hay realized credit loss (`README.md:3`; `docs/methodology.md:5`; `reports/research_report.md:5`, `19`). Report cũng bảo lưu các mã zero-balance và không gọi mọi competing termination là prepayment (`reports/research_report.md:19–23`). Trong các phần đã đọc, không thấy kết luận rằng endpoint đo foreclosure, charge-off, realized loss hay xác suất mất vốn.

Kết luận riêng: thuật ngữ **“rủi ro vỡ nợ” được hỗ trợ thông qua một chỉ báo vận hành đã công khai**, với điều kiện người đọc được thông báo rõ rằng biến cố là lần đầu báo cáo status 03+ trong mẫu tháng. Nếu “vỡ nợ” được hiểu là một nhãn pháp lý/tổn thất tín dụng, code hiện không đo trực tiếp khái niệm đó. Dùng CIF đúng cho competing risks không biến endpoint 90+ thành xác suất default pháp lý hay mất vốn.

## Bằng chứng dự đoán ngoài mẫu và giới hạn

Pipeline có hai đánh giá loan-level holdout. Model metrics hiện có ghi:

| Đánh giá | Train / test | C-index và cặp so sánh | Brier/đánh giá xác suất | Diễn giải |
|---|---:|---:|---|---|
| Random 80/20 cùng vintage | 39.984 / 9.996 | 0,751189; 2.277.701 cặp | IPCW CIF Brier tại 12/24/36/60/120 tháng: 0,001234 / 0,004672 / 0,008640 / 0,024186 / 0,037024. Known-status Brier tại 120 tháng là 0,037052 trên 9.988 trạng thái biết; train-AJ benchmark có paired comparison. | Holdout nội bộ cùng sample/vintage. C-index là discrimination; Brier là squared probability error. IPCW dựa vào giả định censoring chưa được xác nhận; known-status chỉ dùng subset có outcome biết. |
| Calendar holdout, FPD đến 201512 so với sau 201512 | 41.908 / 8.072 | 0,751171; 1.849.210 cặp | Known-status Brier 0,043065 trên 8.052/8.072 ở 120 tháng; train-AJ benchmark có paired comparison. | Holdout nội bộ cohort muộn cùng sample, trong đó 8.060/8.072 test loans có FPD 2016; không phải external validation. |

Các con số được đối chiếu với `outputs/models/model_metrics.json`, `outputs/models_temporal_validation/model_metrics.json`, `reports/tables/cif_brier_scores.csv`, `reports/tables/cif_administrative_benchmark.csv`, các bảng tương ứng trong `reports/tables_temporal_validation/`, và phân bố năm FPD tính từ `outputs/survival_dataset.csv`. Khoảng C-index random bootstrap 95% là 0,733294–0,774170; calendar là 0,735054–0,769698. Bootstrap resamples test loans, giữ fitted model/predictions cố định và không bao gồm model-fitting/split/cohort uncertainty.

Vì follow-up train được quan sát đến cutoff dữ liệu 2026 và thời gian censoring hành chính liên hệ với FPD/calendar time, calendar split không tái tạo thông tin sẵn có tại một thời điểm triển khai trong quá khứ. Cả hai đánh giá vẫn thuộc cùng Freddie Mac Sample 2015, không chứng minh hiệu năng ngoài nguồn/vintage. Calibration summaries là so sánh mô tả; không có intervals. Trọng số IPCW gần 1 không chứng minh giả định độc lập censoring đúng. Vì vậy có bằng chứng holdout nội bộ về ranking và sai số xác suất trên các tập đánh giá đã nêu, nhưng chưa có bằng chứng đủ mạnh về hiệu năng population-level hoặc khả năng tổng quát.

Ba mức bằng chứng cần tách biệt:

1. **Có chức năng tạo dự báo:** có; đã smoke test bundle và scoring API.
2. **Có đánh giá ngoài mẫu:** có holdout nội bộ loan-level (random cùng vintage và calendar cohort muộn), kèm C-index, Brier và calibration summaries với các giới hạn nêu trên.
3. **Có bằng chứng đủ mạnh về chất lượng và khả năng tổng quát:** chưa. Không có external validation; censoring, delayed entry, monthly event ties, proxy endpoint, PH diagnostics và uncertainty scope giới hạn cách diễn giải.

## Đối chiếu với tên đề tài

| Thành phần trong tên đề tài | Implementation thực tế | Bằng chứng: file/hàm/artifact | Mức phù hợp | Giới hạn |
|---|---|---|---|---|
| “Ứng dụng mô hình Cox PH” | Hai Cox proportional-hazards nguyên nhân cụ thể được fit cho 90+ và any zero-balance termination. | `src/survival_pipeline.py:800–817`; hai bảng hệ số. | Phù hợp | Đặc tả Cox PH là mô hình dự đoán liên hệ có điều kiện; chẩn đoán PH chỉ là screening approximation. |
| “Dự đoán” | Scoring bundle tạo CIF theo khoản vay và horizon; được dùng trong đánh giá held-out. | `score_new_loans()` ở `src/survival_pipeline.py:584–604`; smoke test; test metric CSV/JSON. | Phù hợp có điều kiện/giới hạn | Horizon trước hoặc tại entry cho output 0 và không có ý nghĩa dự báo sau entry; chỉ có kiểm định nội bộ. |
| “Rủi ro vỡ nợ” | Endpoint là first reported monthly status 03+, một proxy quá hạn nghiêm trọng; không đo trực tiếp legal default/loss. | `build_survival_data()` `src/survival_pipeline.py:242–246`; README, methodology, research report. | Phù hợp có điều kiện/giới hạn | Cần gọi rõ là rủi ro lần đầu ghi nhận 90+; không diễn giải như xác suất mất vốn. |
| “Theo thời gian” | Thời gian tháng lịch từ First Payment Date, có delayed entry, competing exits và CIF theo horizon. | `config/analysis_config.json`; `src/survival_pipeline.py:261–289`, `492–604`. | Phù hợp | Prediction cho delayed entrant conditional trên event-free đến entry; resolution theo tháng, cùng tháng không xác định thứ tự. |
| “Của khoản vay” | Một đơn vị quan sát/đầu vào scoring là một khoản vay với origination features và history outcome của khoản vay đó. | `build_survival_data()` `src/survival_pipeline.py:214–330`; smoke test scoring. | Phù hợp | Phạm vi dữ liệu là Freddie Mac Sample 2015, không phải mọi khoản vay hay các nguồn/vintage khác. |

## Kết luận và đề xuất tối thiểu

**Kết luận tổng thể: B. Phù hợp có điều kiện.** Code thực sự fit Cox PH và tạo dự báo CIF theo thời gian ở cấp khoản vay, có tính đến competing zero-balance exits và điều kiện delayed entry. Phần “rủi ro vỡ nợ” chỉ được hỗ trợ khi hiểu và trình bày như proxy first reported 90+ delinquency; model và endpoint không cho phép kết luận về default pháp lý hoặc tổn thất tín dụng. Có kết quả đánh giá holdout nội bộ, nhưng chưa có external validation hoặc bằng chứng tổng quát đủ mạnh.

Đề xuất tối thiểu, không đổi thiết kế nghiên cứu:

- Trong mục tiêu/phạm vi và mọi bản nộp, viết rõ “vỡ nợ” được vận hành hóa bằng **lần đầu ghi nhận quá hạn 90+ (status 03+)** trong Freddie Mac SFLLD Sample 2015.
- Có thể thêm phụ đề giải nghĩa endpoint, chẳng hạn: *“Dự báo thời gian đến lần đầu ghi nhận quá hạn 90+ ngày trong mô hình competing risks”*. Đây là làm rõ phạm vi, không phải đổi endpoint.
- Khi dùng `score_new_loans()` cho delayed entrant, chỉ diễn giải các horizon lớn hơn entry; nếu muốn API an toàn hơn cho người dùng cuối, một thay đổi riêng có thể đánh dấu/raise lỗi với horizon `<= entry` thay vì trả số 0. Task này không sửa code.
- External validation hoặc endpoint tổn thất/default pháp lý sẽ cần dữ liệu/thiết kế nghiên cứu khác; đây không phải chỉnh sửa diễn giải đơn thuần và không được thêm trong Task 9.

## Tệp đã đọc và kiểm tra

Đã đọc/truy nguyên các phần thực thi liên quan trong `src/survival_pipeline.py` (cohort, feature preprocessing, AJ, CIF, scoring, fitting, metrics, bundle và figures), `src/temporal_validation.py` (calendar validation), `config/analysis_config.json`, `README.md`, `docs/methodology.md`, `reports/research_report.md`, `outputs/survival_dataset.csv`, `outputs/survival_dataset_summary.json`, model bundle `outputs/models/cause_specific_cox_models.pkl`, model metric JSON cho random/calendar split, cùng Brier, paired benchmark, bootstrap và Cox coefficient CSV artifacts.

| Check | Kết quả |
|---|---|
| Git status trước/sau | Working tree đã dirty trước Task 9; không có thao tác trên thay đổi sẵn có. Chỉ thêm audit này. |
| Model bundle scoring smoke test | Thành công trên 3 dòng sẵn có; không fit lại, không ghi output. |
| CIF cơ bản | Hữu hạn, nằm trong [0,1], không giảm theo các horizon đã trả; giá trị thay đổi giữa hồ sơ. |
| Holdout metrics/artifacts | Random và calendar metric JSON/CSV đọc được, khớp các mẫu số/chỉ số nêu trên. |
| Full pipeline/tests | Không chạy; không cần cho mục tiêu truy nguyên, và không fit lại theo phạm vi task. |

### Chưa xác minh được

- Không xác minh độc lập các giả định independent truncation/entry, event-free status trước first observed performance, censoring độc lập có điều kiện, hay diễn giải population-level.
- Không có external dataset/holdout vintage để kiểm tra transportability; holdout calendar trong cùng sample không thay thế được.
- Smoke test chứng minh đường đi kỹ thuật của inference trên vài dòng, không chứng minh calibration, độ chính xác hay chất lượng dự báo ngoài các metric artifacts hiện có.
- Không chạy lại pipeline để tái tạo toàn bộ artifacts; số liệu báo cáo được đối chiếu với artifacts hiện hữu, không phải kết quả fit mới.

**Trạng thái Git cuối:** các thay đổi tracked/untracked có sẵn vẫn còn; `reports/topic_alignment_audit.md` là file mới được tạo bởi Task 9. Không commit hoặc push.
