# Kết quả chạy lại toàn bộ pipeline — 2026-10-24

Toàn bộ pipeline được chạy lại trên ba tệp dữ liệu local hiện có. Các đầu ra mặc định trong `outputs/` và `reports/` đã được ghi lại bằng code hiện hành.

## Môi trường và dữ liệu

- Python 3.12.7
- pandas 2.2.2, NumPy 1.26.4, SciPy 1.14.1
- lifelines 0.30.3, scikit-learn 1.5.2, matplotlib 3.9.2
- `sample_orig_2015.txt`: SHA-256 `96f19fbbbf7cd76b3f27c74a77b9e24795278c9b0742791d9f497268ba2cec70`
- `sample_perf_2015.txt`: SHA-256 `8ea028b9058fc6f1e87ab7e006271daf1372bea6c6a4188a24209425325b1bca`
- `sample_2015.zip`: SHA-256 `83cd76b9c705dd683d1490a37fb70f954c898a91a4279d09b06a7124f031c1e6`

## Kiểm thử và lệnh đã chạy

`python -B -m unittest discover -s tests -v` chạy 47 test: **47 PASS, 0 FAIL, 0 ERROR, 0 SKIP**. Lần chạy đầu trong sandbox gặp lỗi quyền ở `TemporaryDirectory`; cùng bộ test được chạy lại ngoài giới hạn sandbox và đạt toàn bộ.

Các bước nghiên cứu đã thực thi:

```powershell
python -B src/survival_pipeline.py --bootstrap 100
python -B src/eda.py
python -B src/temporal_validation.py --bootstrap 100
python -B src/survival_pipeline.py --cltv-sensitivity --bootstrap 20
python -B src/survival_pipeline.py --tie-as-event-sensitivity --bootstrap 20
```

Temporal validation được chạy lại với `PYTHONUTF8=1` vì console CP1252 không in được metadata tiếng Việt ở câu lệnh `print` cuối. Lần chạy UTF-8 kết thúc với exit code 0.

## Cohort

- 49.980 khoản vay phân tích.
- 2.019 biến cố 90+.
- 37.305 zero-balance competing exits.
- 10.656 khoản bị kiểm duyệt phải.
- 30 trường hợp 90+ và termination cùng tháng được xếp vào competing event trong phân tích chính.

## Kết quả theo nhánh

| Nhánh | Train | Test | C-index | IPCW Brier 120 tháng | Fit warnings |
|---|---:|---:|---:|---:|---:|
| Primary | 39.984 | 9.996 | 0,751189 | 0,037026 | 0 |
| Temporal | 41.908 | 8.072 | 0,751171 | 0,042966 | 0 |
| CLTV sensitivity | 39.984 | 9.996 | 0,752486 | 0,036978 | 0 |
| Tie sensitivity | 39.984 | 9.996 | 0,753533 | 0,037528 | 0 |

C-index bootstrap 95% của mô hình chính là 0,733294–0,774170 với 100 lần lấy mẫu lại test loans và giữ model cố định.

### Primary IPCW Brier theo horizon

| Horizon | IPCW Brier |
|---:|---:|
| 12 tháng | 0,001234 |
| 24 tháng | 0,004672 |
| 36 tháng | 0,008640 |
| 60 tháng | 0,024188 |
| 120 tháng | 0,037026 |

## Kiểm tra artifact sau chạy

- Bốn model bundle primary, temporal, CLTV và tie đều nạp thành công.
- Mỗi bundle tạo được CIF hữu hạn cho cả hai nguyên nhân ở 12 và 120 tháng trên ba bản ghi kiểm tra.
- Mỗi thư mục model có đủ bundle, metrics, split membership và test predictions.
- Các bảng/hình primary, temporal và sensitivity đã được tạo lại.
- Bốn ảnh `cif_90plus.png` từ tên file cũ đã được xóa; code hiện hành dùng `cif_90plus_cohort.png`.

Kết quả temporal và sensitivity là kiểm tra độ ổn định, không phải cơ sở chọn mô hình theo hiệu năng test. Các giới hạn về proportional hazards, censoring/left truncation và external validation vẫn áp dụng như mô tả trong `docs/methodology.md`.
