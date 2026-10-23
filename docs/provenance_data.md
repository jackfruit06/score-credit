# Provenance dữ liệu Freddie Mac SFLLD Sample 2015

Ngày lập manifest: **2026-10-23**.

## Nguồn và chuẩn schema

| Thuộc tính | Giá trị | Trạng thái |
|---|---|---|
| Dataset được khai báo | Freddie Mac Single-Family Loan-Level Dataset (SFLLD) Sample 2015 | Khai báo trong `config/analysis_config.json` và tên archive local |
| Schema dùng đối chiếu | Freddie Mac Release 47, July 2026 | Đã đối chiếu theo tài liệu chính thức; không chứng minh release gốc của raw data |
| User Guide | [Release 47, July 2026 PDF](https://www.freddiemac.com/fmac-resources/research/pdf/general_user_guide_july_2026.pdf) | Đã đọc; glossary theo thứ tự file, tệp không có header |
| Disclosure Changes | [SFLLD Disclosure Changes PDF](https://www.freddiemac.com/fmac-resources/research/pdf/disclosure-changes-summary.pdf) | Đã đọc; bảng vị trí/tên và enumeration Release 47 |
| Trang dataset | [Freddie Mac SFLLD](https://www.freddiemac.com/research/datasets/sf-loanlevel-dataset) | Trang chính thức tham chiếu |
| Ngày tải raw/archive | Unknown | Không có metadata tải hoặc chứng từ nguồn trong repository |
| Release gốc của archive local | Not verified | Config khai báo Release 47, nhưng không đủ xác nhận provenance tải xuống |

Freddie Mac mô tả SFLLD là dataset có thể được cập nhật. Vì vậy, checksum dưới đây chỉ định danh và kiểm tra tính toàn vẹn của các file hiện có trong workspace; **không chứng minh nhà phát hành, URL tải, ngày tải hoặc release gốc**.

## File local và checksum

SHA-256 tính trực tiếp trên byte của các file hiện có. Các thành viên trong ZIP được đọc streaming, không giải nén hoặc ghi đè dữ liệu.

| File | Kích thước byte | SHA-256 | Kiểm tra archive |
|---|---:|---|---|
| `sample_2015.zip` | 55,381,655 | `83cd76b9c705dd683d1490a37fb70f954c898a91a4279d09b06a7124f031c1e6` | ZIP chứa hai file raw bên dưới |
| `sample_orig_2015.txt` | 6,237,206 | `96f19fbbbf7cd76b3f27c74a77b9e24795278c9b0742791d9f497268ba2cec70` | SHA-256 thành viên ZIP trùng file local; 6,237,206 byte |
| `sample_perf_2015.txt` | 386,828,102 | `8ea028b9058fc6f1e87ab7e006271daf1372bea6c6a4188a24209425325b1bca` | SHA-256 thành viên ZIP trùng file local; 386,828,102 byte |

So khớp SHA-256 giữa thành viên ZIP và file raw local xác nhận các bản raw trong workspace giống nội dung tương ứng trong archive hiện có. Không xác nhận archive này được tải từ Freddie Mac nếu không có manifest/chứng từ bên ngoài.

## Cấu hình sử dụng

`config/analysis_config.json` khai báo:

- `data.origination`: `sample_orig_2015.txt`
- `data.performance`: `sample_perf_2015.txt`
- `data.source`: Freddie Mac Single-Family Loan-Level Dataset Sample 2015
- `data.release_layout`: Release 47, July 2026

Pipeline mặc định phân giải tên tệp tương đối từ root repository. Các bản raw local có 31 trường Origination và 35 trường Performance, không có header; định danh và kết quả kiểm tra cấu trúc được ghi tại [data audit](../reports/data_audit.md). Schema dùng làm chuẩn đối chiếu được phân biệt với nguồn/release thực tế của archive như nêu ở trên.
