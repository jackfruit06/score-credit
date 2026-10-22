Bộ dữ liệu đang dùng là **Freddie Mac Single-Family Loan-Level Dataset — mẫu năm phát hành 2015**. Đây là dữ liệu thực tế về các khoản vay thế chấp nhà ở tại Hoa Kỳ, gồm thông tin ban đầu của khoản vay và lịch sử hiệu năng tín dụng theo từng tháng. Bản mẫu được lấy ngẫu nhiên từ Standard Dataset, với 50.000 khoản vay cho mỗi năm phát hành đầy đủ. [freddiemac](https://www.freddiemac.com/fmac-resources/research/pdf/faq.pdf)

Dưới đây là phần tổng quan, kết hợp tài liệu chính thức với các thống kê bạn vừa cung cấp.

## 1. Thông tin chung

| Nội dung | Mô tả |
|---|---|
| Tên bộ dữ liệu | Freddie Mac Single-Family Loan-Level Dataset |
| Phiên bản nhóm sử dụng | Sample Dataset, năm phát hành 2015 |
| Đơn vị cung cấp | Freddie Mac |
| Thị trường | Tín dụng thế chấp nhà ở tại Hoa Kỳ |
| Loại khoản vay trong Standard Dataset | Các khoản vay thế chấp lãi suất cố định, trả dần toàn bộ gốc theo lịch trả nợ |
| Cách lấy mẫu | Lấy mẫu ngẫu nhiên đơn giản từ Standard Dataset |
| Số khoản vay trong mẫu năm | 50.000 khoản vay |
| Hai nhóm dữ liệu | Origination và Monthly Performance |
| Định dạng tệp | Tệp văn bản phân tách bằng ký tự `|`, không có dòng tiêu đề |
| Khóa liên kết | Loan Sequence Number — mã định danh khoản vay |

Các đặc điểm về phạm vi, cách lấy mẫu và định dạng trên được mô tả trong hướng dẫn chính thức của Freddie Mac. [freddiemac](https://www.freddiemac.com/fmac-resources/research/pdf/faq.pdf)

Lưu ý: “Single-Family” trong tên bộ dữ liệu không có nghĩa tất cả tài sản đều chỉ có đúng một đơn vị nhà ở; từ điển dữ liệu có trường số đơn vị tài sản nhận giá trị từ 1 đến 4. [freddiemac](https://www.freddiemac.com/fmac-resources/research/pdf/user_guide.pdf)

## 2. “Dữ liệu năm 2015” nghĩa là gì?

Năm 2015 là năm phát hành khoản vay, không phải giới hạn thời gian của toàn bộ lịch sử thanh toán.

Cụ thể:

> Nhóm chọn 50.000 khoản vay thuộc năm phát hành 2015, sau đó quan sát lịch sử của từng khoản vay qua các tháng tiếp theo.

Theo tài liệu, mỗi năm mẫu có một tệp thông tin ban đầu và một tệp monthly performance tương ứng. Dữ liệu hiệu năng được báo cáo đến thời điểm kết thúc công bố của phiên bản dữ liệu, hoặc đến khi khoản vay kết thúc theo các điều kiện của bộ dữ liệu. [freddiemac](https://www.freddiemac.com/fmac-resources/research/pdf/faq.pdf)

Vì vậy, cần phân biệt:

- Năm phát hành: 2015.
- Tháng báo cáo đầu tiên và cuối cùng: phải xác định trực tiếp trong tệp đã tải.
- Thời gian theo dõi từng khoản vay: có thể khác nhau vì tất toán, xử lý khoản vay hoặc kết thúc kỳ quan sát.

Hiện chưa thể kết luận tệp hiện dùng đang theo dõi đến tháng nào chỉ từ dòng đầu và bảng tần suất đã gửi.

## 3. Quy mô tệp đang phân tích

Theo kết quả kiểm tra cung cấp:

| Chỉ tiêu | Giá trị |
|---|---:|
| Số bản ghi monthly performance | 3.467.166 |
| Số khoản vay phân biệt | 50.000 |
| Số cột trong tệp performance | 35 |
| Số bản ghi có trạng thái `00` | 3.415.433 |
| Số bản ghi có trạng thái `01` | 23.522 |
| Số bản ghi có trạng thái `02` | 6.686 |
| Số bản ghi có trạng thái `03` | 3.756 |
| Số bản ghi có trạng thái `RA` | 567 |

Các con số trên là thống kê của tệp đang có, không phải thông số cố định cho mọi phiên bản mẫu 2015.

Điểm quan trọng là:

> 3.467.166 bản ghi không tương ứng với 3.467.166 khoản vay. Mỗi bản ghi mô tả một khoản vay tại một tháng báo cáo.

Một khoản vay có thể xuất hiện nhiều lần với trạng thái thay đổi theo thời gian. Do đó, số bản ghi quá hạn không đồng nghĩa với số khoản vay từng quá hạn.

## 4. Hai thành phần của bộ dữ liệu

### 4.1. Origination — thông tin ban đầu

Tên tệp mẫu theo quy ước chính thức:

```text
sample_orig_2015.txt
```

Tệp này ghi nhận đặc điểm ban đầu của khoản vay và người vay. Các trường tiêu biểu gồm: [freddiemac](https://www.freddiemac.com/fmac-resources/research/pdf/user_guide.pdf)

| Nhóm thông tin | Trường tiêu biểu | Ý nghĩa |
|---|---|---|
| Chất lượng tín dụng | Credit Score | Điểm tín dụng của người vay |
| Khả năng đáp ứng nghĩa vụ nợ | Original DTI | Tỷ lệ nghĩa vụ trả nợ hằng tháng trên thu nhập hằng tháng |
| Quy mô khoản vay | Original UPB | Dư nợ gốc ban đầu |
| Mức độ tài trợ so với tài sản | Original LTV, Original CLTV | Tỷ lệ khoản vay hoặc tổng khoản vay trên giá trị tài sản |
| Điều kiện hợp đồng | Original Interest Rate, Original Loan Term | Lãi suất và kỳ hạn ban đầu |
| Mục đích vay | Loan Purpose | Mua nhà hoặc tái cấp vốn |
| Đặc điểm tài sản | Property Type, Occupancy Status, Property State | Loại tài sản, mục đích sử dụng và bang |
| Đặc điểm bên vay | Number of Borrowers, First-Time Homebuyer Flag | Số người cùng chịu nghĩa vụ trả nợ, người mua nhà lần đầu |
| Định danh | Loan Sequence Number | Liên kết với lịch sử monthly performance |

Các trường này là nguồn biến giải thích cho mô hình Cox PH. Không nên tiếp tục dùng nguyên danh sách biến của LendingClub như `annual_inc`, `emp_length` hay `revol_util` mà chưa kiểm tra, vì hai bộ dữ liệu có cấu trúc khác nhau.

### 4.2. Monthly Performance — lịch sử theo tháng

Tên tệp mẫu theo quy ước chính thức:

```text
sample_svcg_2015.txt
```

Tệp này ghi nhận tình trạng khoản vay ở mỗi tháng báo cáo, gồm dư nợ, trạng thái quá hạn, tuổi khoản vay, lãi suất hiện tại, điều chỉnh khoản vay và thông tin kết thúc khoản vay. [freddiemac](https://www.freddiemac.com/fmac-resources/research/pdf/user_guide.pdf)

Các cột đầu của tệp code gửi khớp với cấu trúc chính thức:

| Vị trí | Trường | Nội dung |
|---:|---|---|
| 1 | Loan Sequence Number | Mã khoản vay |
| 2 | Monthly Reporting Period | Tháng báo cáo, định dạng `YYYYMM` |
| 3 | Current Actual UPB | Dư nợ gốc hiện tại |
| 4 | Current Loan Delinquency Status | Trạng thái quá hạn |
| 5 | Loan Age | Tuổi khoản vay theo số kỳ thanh toán |
| 6 | Remaining Months to Legal Maturity | Số tháng còn lại đến đáo hạn |
| 7 | Defect Settlement Date | Ngày xử lý vấn đề liên quan đến khiếm khuyết khoản vay |
| 8 | Modification Flag | Cờ điều chỉnh khoản vay |
| 9 | Zero Balance Code | Lý do dư nợ được đưa về 0 |
| 10 | Zero Balance Effective Date | Thời điểm dư nợ về 0 |
| 11 | Current Interest Rate | Lãi suất hiện tại |

Tên và định nghĩa các trường cần đối chiếu theo tài liệu đi kèm phiên bản tệp; không nên tự gán toàn bộ 35 cột bằng một danh sách tên lấy từ phiên bản khác. [freddiemac](https://www.freddiemac.com/fmac-resources/research/pdf/user_guide.pdf)

## 5. Trạng thái quá hạn — biến quan trọng nhất cho bài toán

Trường `Current Loan Delinquency Status` cho biết mức quá hạn theo các khoảng ngày, không phải số ngày quá hạn chính xác. Freddie Mac tính trường này theo phương pháp của Mortgage Bankers Association, dựa trên kỳ trả nợ cuối đã được thanh toán. [freddiemac](https://www.freddiemac.com/fmac-resources/research/pdf/user_guide.pdf)

| Mã trong tệp | Ý nghĩa |
|---|---|
| `00` | Bình thường hoặc quá hạn dưới 30 ngày |
| `01` | Quá hạn 30–59 ngày |
| `02` | Quá hạn 60–89 ngày |
| `03` | Quá hạn 90–119 ngày |
| `04` | Quá hạn 120–149 ngày |
| Các mã số tiếp theo | Tiếp tục tăng theo khoảng 30 ngày |
| `RA` | REO Acquisition — tài sản được tiếp nhận vào diện bất động sản thuộc sở hữu sau xử lý khoản vay |

Các mã được giải thích trong từ điển dữ liệu chính thức. [freddiemac](https://www.freddiemac.com/fmac-resources/research/pdf/user_guide.pdf)

Ví dụ, nếu lịch sử một khoản vay là:

```text
Tháng 1: 00
Tháng 2: 00
Tháng 3: 00
Tháng 4: 01
Tháng 5: 02
Tháng 6: 00
```

Ta có thể xác định:

- Lần đầu được ghi nhận quá hạn từ 30 ngày là tháng 4.
- Lần đầu được ghi nhận quá hạn từ 60 ngày là tháng 5.
- Khoản vay trở về nhóm dưới 30 ngày quá hạn ở tháng 6.
- Chưa có bản ghi nào cho thấy khoản vay đạt ngưỡng quá hạn từ 90 ngày.

Như vậy, dữ liệu hỗ trợ nghiên cứu cả thời điểm xuất hiện quá hạn lẫn quá trình phục hồi sau quá hạn.

## 6. Các trường hợp khoản vay kết thúc

Một khoản vay dừng xuất hiện không nhất thiết vì vỡ nợ. Trường `Zero Balance Code` cho biết lý do kết thúc, chẳng hạn: [freddiemac](https://www.freddiemac.com/fmac-resources/research/pdf/faq.pdf)

| Mã | Lý do |
|---|---|
| `01` | Tất toán trước hạn hoặc đáo hạn |
| `02` | Bán tài sản cho bên thứ ba |
| `03` | Short sale hoặc charge-off |
| `09` | Xử lý bán tài sản REO |
| `15` | Bán toàn bộ khoản vay |
| `16` | Chứng khoán hóa khoản vay đã phục hồi |
| `96` | Khiếm khuyết khoản vay được xử lý trước sự kiện kết thúc khác |

Lưu ý: mã `01` ở cột trạng thái quá hạn và mã `01` ở cột Zero Balance Code có ý nghĩa hoàn toàn khác nhau. Phải đọc mã cùng tên cột.

Trong bài Cox PH, nhóm cần phân biệt kết thúc quan sát, tất toán và biến cố quá hạn. Không được mặc định mọi khoản vay dừng xuất hiện đều là vỡ nợ.

## 7. Bộ dữ liệu này dùng thế nào trong báo cáo của nhóm?

Có thể mô tả thiết kế nghiên cứu như sau:

1. Dùng monthly performance để xác định tháng đầu tiên mỗi khoản vay đạt ngưỡng quá hạn đã chọn.
2. Xác định mốc bắt đầu theo dõi và thời điểm kết thúc quan sát.
3. Dùng origination để lấy các đặc điểm ban đầu như điểm tín dụng, DTI, LTV, lãi suất và dư nợ ban đầu.
4. Ghép hai tệp theo Loan Sequence Number.
5. Tạo bảng phân tích phục vụ Cox PH.

Nếu nghiên cứu lần đầu quá hạn từ 30 ngày, nên gọi kết quả là “rủi ro xuất hiện quá hạn từ 30 ngày”, không đồng nhất với vỡ nợ mất vốn.

Nếu tất toán được xem là một biến cố cạnh tranh với quá hạn, cần trình bày giới hạn của cách xử lý: Cox cho hazard theo nguyên nhân không tự động cho xác suất quá hạn thực tế bằng cách lấy \(1-S(t)\) khi còn các biến cố cạnh tranh.

## 8. Những hạn chế cần nêu

- Phạm vi đại diện: mẫu đại diện cho Standard Dataset của Freddie Mac, không phải toàn bộ người vay tại Hoa Kỳ hoặc Việt Nam. [freddiemac](https://www.freddiemac.com/fmac-resources/research/pdf/faq.pdf)
- Thông tin người vay không giống LendingClub: phải lựa chọn biến theo từ điển SFLLD.
- Có mã thiếu đặc biệt: chẳng hạn Credit Score dùng `9999`; DTI dùng `999` cho trường hợp không có thông tin hoặc ngoài phạm vi công bố. Không được coi các mã này là giá trị tài chính thực. [freddiemac](https://www.freddiemac.com/fmac-resources/research/pdf/faq.pdf)
- Loan Age có thể thay đổi cách tính sau điều chỉnh khoản vay: không nên dùng trực tiếp mà chưa kiểm tra cờ modification và mốc thời gian. [freddiemac](https://www.freddiemac.com/fmac-resources/research/pdf/faq.pdf)
- Dữ liệu có thể có sai lệch thời điểm báo cáo hoặc lỗi nghiệp vụ; Freddie Mac cũng lưu ý bộ dữ liệu có thể được sửa qua các lần cập nhật. [freddiemac](https://www.freddiemac.com/fmac-resources/research/pdf/faq.pdf)
- Chưa xác định được kỳ quan sát thực tế của tệp: cần thống kê tháng báo cáo nhỏ nhất, lớn nhất và phạm vi theo dõi từng khoản vay.

