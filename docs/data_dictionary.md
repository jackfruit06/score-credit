# Từ điển dữ liệu và quy ước mã hóa

Quy tắc toán/dữ liệu đã chốt: [analysis_contract.md](analysis_contract.md). Nguyên nhân 2 là kết thúc **trong dataset**, không khẳng định khoản nợ của người vay đã chấm dứt sau bán/chuyển giao. `L` là entry, `J` là nguyên nhân, `E=I(J=1)` là chỉ báo biến cố đích.

Các tệp đầu vào được repository khai báo là Freddie Mac Single-Family Loan-Level Dataset (SFLLD) Sample 2015, không có header và phân tách bằng dấu `|`. Tên và thứ tự trường được đối chiếu với schema Release 47 (tháng 7 năm 2026); provenance tải xuống/release gốc của file local chưa được xác minh độc lập. Số thứ tự trường trong bảng bắt đầu từ 1. Xem [manifest provenance](provenance_data.md). Báo cáo kiểm toán phân biệt ô trống với mã sentinel.

## Tệp khởi tạo khoản vay: `sample_orig_2015.txt` (31 trường)

| # | Trường nguồn | Công dụng / cách mã hóa |
|---:|---|---|
| 1 | Classic FICO | Dạng số; `9999` là mã sentinel biểu thị không có giá trị, được xử lý như dữ liệu thiếu. |
| 2 | First Payment Date | Mốc thời gian gốc, chính xác đến tháng lịch. |
| 3 | First-Time Homebuyer Indicator | Biến phân loại. |
| 4 | Maturity Date | Trường mô tả nguồn; không dùng làm đặc trưng mô hình. |
| 5 | Metropolitan Statistical Area | Chỉ dùng mô tả; không đưa vào mô hình. |
| 6 | Mortgage Insurance Percentage | Dạng số; giá trị 0 có ý nghĩa. |
| 7 | Number of Units | Trường nguồn dạng số/phân loại. |
| 8 | Occupancy Status | Biến phân loại. |
| 9 | Original CLTV | Dạng số; đặc trưng phân tích nhạy cảm, xử lý mã sentinel thiếu. |
| 10 | Original DTI | Dạng số; `999` là mã không có giá trị/nằm ngoài phạm vi, được xử lý như dữ liệu thiếu. |
| 11 | Original UPB | Dạng số; lấy log sau khi kiểm tra tính dương. |
| 12 | Original LTV | Dạng số; đặc trưng của mô hình chính, xử lý mã sentinel thiếu. |
| 13 | Original Interest Rate | Dạng số. |
| 14 | Channel | Biến phân loại. |
| 15 | Prepayment Penalty Indicator | Trường mô tả nguồn; không dùng trong mô hình. |
| 16 | Amortization Type | Trường mô tả nguồn; không dùng trong mô hình. |
| 17 | Property State | Trường mô tả nguồn; không dùng trong mô hình. |
| 18 | Property Type | Đặc trưng phân loại của mô hình. |
| 19 | Postal Code | Trường mô tả nguồn; không dùng trong mô hình. |
| 20 | Loan Identifier | Khóa ghép dữ liệu, không dùng làm biến dự báo. |
| 21 | Loan Purpose | Đặc trưng phân loại của mô hình. |
| 22 | Original Loan Term | Đặc trưng dạng số của mô hình, tính bằng tháng. |
| 23 | Number of Borrowers | Trong cấu trúc này, `1` = một người vay, `2` = từ hai người vay trở lên; xử lý như biến phân loại. |
| 24 | Seller Name | Trường mô tả nguồn; không dùng trong mô hình. |
| 25 | Super Conforming Flag | Trường mô tả nguồn; không dùng trong mô hình. |
| 26 | Pre-HARP Loan Sequence Number | Trường mô tả nguồn; không dùng trong mô hình. |
| 27 | Special Eligibility Program | Tên chính thức Release 47; mã quan sát gồm `H` (Home Possible) và `F` (HFA Advantage). Không dùng trong mô hình. |
| 28 | HARP Indicator | Trường mô tả nguồn; không dùng trong mô hình. |
| 29 | Property Valuation Method | Trường mô tả nguồn; không dùng trong mô hình. |
| 30 | Interest-Only Indicator | Trường mô tả nguồn; không dùng trong mô hình. |
| 31 | VantageScore 4.0 | Trường có trong schema; cả 50.000 dòng mẫu chứa sentinel `9999` = Not Available theo Release 47. Không có điểm VantageScore khả dụng và không dùng trong mô hình. |

Pipeline tiền xử lý tạo thêm `log_original_upb` và `has_mortgage_insurance`. Trung vị, hệ số scale, từ vựng giá trị phân loại và quy tắc gộp nhóm hiếm chỉ được học trên khoản vay train rồi lưu cùng mô hình.

## Tệp diễn biến khoản vay theo tháng: `sample_perf_2015.txt` (35 trường)

| # | Trường nguồn | Công dụng / cách mã hóa |
|---:|---|---|
| 1 | Loan Identifier | Khóa ghép dữ liệu. |
| 2 | Reporting Period | Mốc thời gian theo tháng. |
| 3 | Current Actual UPB | Đã kiểm toán; không dùng làm biến dự báo. |
| 4 | Current Loan Delinquency Status | `00` là hiện hành; `01` là quá hạn 30–59 ngày; `02` là 60–89 ngày; `03` là 90–119 ngày; mã số lớn hơn biểu thị quá hạn lâu hơn; `RA`/`XX` không được đọc thành mã quá hạn số. |
| 5 | Loan Age | Đã kiểm toán và đối chiếu với thời lượng theo lịch; không dùng làm đồng hồ phân tích vì định nghĩa có thể được đặt lại sau khi sửa đổi khoản vay. |
| 6 | Remaining Months to Legal Maturity | Đã kiểm toán; không đưa vào mô hình. |
| 7 | Underwriting / Major Servicing Defect Settlement Date | Không dùng trong mô hình. |
| 8 | Modification Flag | Đã kiểm toán; không đưa vào mô hình. |
| 9 | Zero Balance Code | Mã quan sát đầu tiên xác định lần kết thúc cạnh tranh. Giữ nguyên mã: `01` tất toán/trả trước tự nguyện; `02` bán cho bên thứ ba; `03` bán khống hoặc charge-off; `09` xử lý REO; `15` bán toàn bộ khoản vay; `16` chứng khoán hóa khoản vay đã phục hồi khả năng trả nợ; `96` xác nhận dàn xếp lỗi thẩm định/lỗi dịch vụ lớn trước một biến cố tín dụng khác. |
| 10 | Zero Balance Effective Date | Dùng làm tháng biến cố kết thúc khi có giá trị; các ngày kết thúc bị thiếu được kiểm toán. |
| 11 | Current Interest Rate | Không dùng làm predictor khởi tạo. |
| 12 | Current Non-Interest Bearing UPB | Không dùng làm predictor. |
| 13 | Due Date of Last Paid Installment | Không dùng làm predictor. |
| 14 | MI Recoveries | Hậu nghiệm; không dùng predictor. |
| 15 | Net Sales Proceeds | Hậu nghiệm; không dùng predictor. |
| 16 | Non-MI Recoveries | Hậu nghiệm; không dùng predictor. |
| 17 | Total Expenses | Hậu nghiệm; không dùng predictor. |
| 18 | Legal Costs | Hậu nghiệm; không dùng predictor. |
| 19 | Maintenance and Preservation Costs | Hậu nghiệm; không dùng predictor. |
| 20 | Taxes and Insurance | Hậu nghiệm; không dùng predictor. |
| 21 | Miscellaneous Expenses | Hậu nghiệm; không dùng predictor. |
| 22 | Actual Loss | Không dùng làm nhãn 90+ hoặc predictor. |
| 23 | Cumulative Modification Costs | Không dùng predictor. |
| 24 | Interest Rate Step Indicator | Không dùng predictor. |
| 25 | Payment Deferral Indicator | Không dùng predictor. |
| 26 | Estimated LTV | Sentinel 999; không dùng predictor. |
| 27 | Zero Balance Removal UPB | Không dùng predictor. |
| 28 | Delinquent Accrued Interest | Không dùng predictor. |
| 29 | Delinquency Due to Disaster | Không dùng predictor. |
| 30 | Borrower Assistance Plan | Không dùng predictor. |
| 31 | Current Period Modification Costs | Không dùng predictor. |
| 32 | Current Interest Bearing UPB | Không dùng predictor. |
| 33 | Mortgage Insurance Cancellation Indicator | Không dùng predictor. |
| 34 | Servicer Name | Không dùng predictor. |
| 35 | Bankruptcy Cramdown Costs | Không dùng predictor. |

## Bảng sống còn suy dẫn ở cấp khoản vay

- Loại các khoản vay có ngày hiệu lực zero-balance trước First Payment Date vì biến cố kết thúc xảy ra trước mốc thời gian gốc đã chọn; số lượng và mã bị loại được ghi trong báo cáo tạo cohort sống còn. Không tính các hàng 90+ trước origin là biến cố trong risk set.
- `event_time_months`: khoảng cách tháng lịch từ First Payment Date cộng 1; do đó tháng First Payment Date là tháng 1. Với zero-balance exit, dùng tháng của ngày hiệu lực kết thúc nếu có.
- `delayed_entry_months`: số tháng từ First Payment Date đến tháng performance đầu tiên được quan sát. Khoản vay chỉ tham gia risk set sau thời điểm entry.
- `event_cause`: `0` là kiểm duyệt phải tại tháng cuối quan sát; `1` là status quá hạn `03+` đầu tiên được quan sát; `2` là lần zero-balance exit đầu tiên, bất kể mã.
- `exit_type` và `zero_balance_code`: giữ chi tiết mã kết thúc dù nguyên nhân 2 được gộp trong mô hình rủi ro cạnh tranh chính.
- `same_month_90plus_termination_tie`: status 90+ và mã kết thúc cùng tháng; không xác định được thứ tự nên quy tắc chính thận trọng xếp trường hợp này vào nguyên nhân 2.
- Endpoint B (mã `zero_balance_code` `03` hoặc `09`) chỉ được giữ để đếm mô tả; số biến cố quá ít để fit mô hình nguyên nhân cụ thể hiệu chỉnh ổn định.

Xem [tóm tắt thay đổi công bố SFLLD Release 47](https://www.freddiemac.com/fmac-resources/research/pdf/disclosure-changes-summary.pdf) và [General User Guide](https://www.freddiemac.com/fmac-resources/research/pdf/general_user_guide_july_2026.pdf) để tra định nghĩa có thẩm quyền và các thay đổi theo phiên bản.
