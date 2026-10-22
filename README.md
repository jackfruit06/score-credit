# Phân tích rủi ro tín dụng đối với các khoản vay 

## 1. Giới thiệu đề tài

Đề tài tập trung vào việc tìm hiểu và phân tích rủi ro tín dụng của các khoản vay mua nhà thông qua dữ liệu thực tế. Mục tiêu là khám phá mối liên hệ giữa đặc điểm ban đầu của người vay, thông tin khoản vay và tình trạng thanh toán trong suốt thời gian vay.

Thông qua việc nghiên cứu dữ liệu, đề tài hướng đến việc tìm hiểu những yếu tố có liên quan đến nguy cơ vỡ nợ, đồng thời xem xét sự thay đổi của rủi ro tín dụng theo thời gian.

## 2. Bộ dữ liệu

Đề tài sử dụng **Freddie Mac Single-Family Loan-Level Dataset — Sample 2015**, bộ dữ liệu về các khoản vay mua nhà thuộc chương trình cho vay nhà ở đơn lập của Freddie Mac.

Nguồn dữ liệu chính thức:

- [Freddie Mac — Single-Family Loan-Level Dataset](https://www.freddiemac.com/research/datasets/sf-loanlevel-dataset)
- [Freddie Mac — General User Guide](https://www.freddiemac.com/fmac-resources/research/pdf/user_guide.pdf)

Bộ dữ liệu cung cấp thông tin về các khoản vay và lịch sử hoạt động của chúng, tạo cơ sở để nghiên cứu tình trạng thanh toán và rủi ro tín dụng trong thực tế.

### Các nhóm dữ liệu chính

**Dữ liệu khởi tạo khoản vay (Origination Data - sample_orig_2015.txt)**

Chứa thông tin tại thời điểm khoản vay được khởi tạo, bao gồm các đặc điểm của người vay và những thông tin cơ bản về khoản vay.

**Dữ liệu theo dõi khoản vay (Monthly Performance Data - sample_perf_2015.txt)**

Ghi nhận tình trạng hoạt động của khoản vay theo từng tháng, phản ánh diễn biến thanh toán và những thay đổi trong vòng đời khoản vay.

Việc kết hợp hai nhóm dữ liệu giúp xem xét mối liên hệ giữa thông tin ban đầu và tình trạng khoản vay trong các giai đoạn tiếp theo.

## 3. Thống kê dữ liệu đang sử dụng

Bản dữ liệu đang được sử dụng trong dự án có quy mô như sau:

| Đặc điểm | Số lượng |
|---|---:|
| Số khoản vay riêng biệt | 50.000 |
| Số bản ghi theo dõi hằng tháng | 3.467.166 |
| Số cột trong bảng theo dõi hằng tháng | 35 |

*Lưu ý: Các số liệu trên mô tả bản dữ liệu đang sử dụng trong dự án, không đại diện cho toàn bộ dữ liệu do Freddie Mac cung cấp.*


## 4. Nguồn dữ liệu và bản quyền

Bộ dữ liệu được cung cấp bởi Freddie Mac nhằm phục vụ nghiên cứu và phân tích. Người sử dụng cần tuân thủ các điều khoản, điều kiện sử dụng và hướng dẫn được quy định bởi đơn vị cung cấp dữ liệu.

- Trang dữ liệu chính thức: https://www.freddiemac.com/research/datasets/sf-loanlevel-dataset
- Hướng dẫn sử dụng dữ liệu: https://www.freddiemac.com/fmac-resources/research/pdf/user_guide.pdf
- Trang dẫn tới nơi download dữ liệu: https://claritydownload.fmapps.freddiemac.com/CRT/#/sflld
- Chi tiết xem: [Thông tin thêm về data](take_note.md)