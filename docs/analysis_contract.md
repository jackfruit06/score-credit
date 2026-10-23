# Hợp đồng phân tích v1 — chốt trước huấn luyện lại, 2026-10-23

Áp dụng cho phiên bản phân tích hiện hành; thay đổi các quy tắc dưới đây phải tạo phiên bản khác và chạy lại downstream. Đây là quyết định thiết kế dựa trên câu hỏi hiện hành và bằng chứng raw, không phải kết luận các giả định đã được dữ liệu chứng minh.

## Đại lượng đích và dữ liệu

Biến cố đích là **lần đầu quan sát numeric delinquency status 03–99 vào/sau FPD trong lịch sử được cung cấp, trước dataset termination**. Không phải first-ever delinquency, default pháp lý hoặc loss. RA là REO acquisition, không numeric 03+; XX/blank/unknown không được coi là 00. Trên raw có 567 RA, không XX/blank; một loan RA không có prior 03+ vẫn không phải event đích. Dữ liệu đầu vào tương lai có unknown status phải dừng để quyết định policy, không gán nhãn âm tự động.

Nguyên nhân cạnh tranh J=2 là **rời dataset với zero-balance code đã xác nhận**, giữ mã gốc: 01 payoff/maturity, 02 third-party sale, 03 short sale/charge-off, 09 REO disposition, 15 whole-loan sale, 16 resecuritization, 96 confirmed defect. Đây là hợp nhất trạng thái kết thúc quan sát theo dataset. Với nghiên cứu default của người vay sau bán/chuyển giao, các mã này không đủ làm competing terminal sinh học/kinh tế; cần thiết kế khác và dữ liệu tiếp nối. Không dùng kết quả hiện tại cho câu hỏi rộng hơn đó.

Provenance: raw/archive khớp SHA-256 và schema tham chiếu Release 47; nguồn tải, ngày tải và release gốc Unknown. Không suy provenance từ schema.

## T, E, J, L và risk set

M là chỉ số tháng nguyên. Origin là đầu tháng FPD; cuối tháng FPD là t=1.

- L=max(0,M_first−M_FPD), entry tại đầu interval đầu tiên quan sát được. Bản ghi trước FPD không phải lý do loại tự động.
- D=min numeric 03+ reporting month vào/sau origin; Z=zero-balance effective month, dùng report chỉ khi ngày effective thiếu và đếm riêng.
- Áp dụng tuần tự các điều kiện loại trước khi gán nguyên nhân: nếu Z tồn tại và Z<FPD, loại với lý do kết thúc trước origin (20 loan ở raw); nếu không có record từ origin trở đi, loại, không tạo tháng theo dõi giả; nếu Z tồn tại và terminal xảy ra trước interval quan sát đầu tiên, loại có lý do. Quy tắc loại prior 03+ trước origin vẫn áp dụng như dưới đây. Terminal effective muộn hơn report được giữ vì đã có thông tin ngày terminal; 36 trường hợp được gắn cờ, không tự ép về report.
- Sau các điều kiện loại, quyết định theo thứ tự sau; chỉ so sánh D và Z khi cả hai tồn tại:
  1. Nếu D tồn tại và (Z không tồn tại hoặc D<Z): J=1, exit=D.
  2. Nếu chưa thuộc nhánh 1 và Z tồn tại: J=2, exit=Z. Cụ thể, D không tồn tại hoặc cả D và Z tồn tại với Z<=D.
  3. Nếu cả D và Z không tồn tại: J=0, exit=last observed report, với thời gian theo dõi hợp lệ theo điều kiện T>L>=0 bên dưới.
- T=M_exit−M_FPD+1, **không max ép lên L+1**. Phải T>L>=0. E=I(J=1); khi fit nguyên nhân k dùng E_k=I(J=k). Tránh dùng E để gọi entry; entry luôn là L.
- Risk set R(t)={i:L_i<t<=T_i}. Cả partial likelihood, Breslow baseline, AJ, censoring và concordance phải dùng cùng ranh giới.
- Cùng tháng D=Z: J=2 trong chính, J=1 trong sensitivity, giữ nguyên train/test IDs. Đây là quy ước, không phải thứ tự được chứng minh.
- Nhiều tháng 03+ chỉ một event đầu tiên. Gap không nội suy trạng thái. Trước-origin 03+ nếu gặp phải được báo/loại khỏi cohort incident; raw hiện tại không có.

Ví dụ FPD=201501, first=201502, event=201503: L=1,T=3; risk ở t=2,3, không t=1. First=FPD và exit cùng tháng: L=0,T=1 hợp lệ. Terminal trước first interval không được biến thành T=L+1.

Đối với delayed entry, dự báo F_k(h|L,x) có điều kiện event-free đến L trong mô hình. Đây là giả định không xác minh được trước cửa sổ quan sát; không diễn giải first-ever risk. Horizon<=L không có interval dự báo (API 0, không dùng trong evaluation).

## Mô hình và xác suất

Giữ hai cause-specific Cox PH, hệ số bằng Efron partial likelihood. Với r_i=exp((x_i−xbar_train)'beta), baseline tháng dH0k(t)=d_k(t)/sum_{i in R(t)}r_i. Tính baseline riêng có entry; lưu toàn bộ tháng 0..max(T), H0(0)=0. Không dùng baseline mặc định thiếu entry của lifelines 0.30.3.

CIF dự báo dùng competing-exponential trên increment từng tháng, không 1−S_1: dF_k=S_previous*(1−exp(−sum dH))*dH_k/sum dH, S_new=S_previous*exp(−sum dH). Giả định nội suy hazard hằng trong từng tháng, khác product-limit AJ. AJ dùng Y=|R(t)|, tăng F_k bằng S_previous*d_k/Y và nhân S với 1−sum d_k/Y. Sparse output grid không được bỏ biến cố trung gian.

Các đặc trưng khởi tạo có trong data dictionary, không performance. Sentinel numeric phải giống nhau với input chuỗi/int/float; missing categorical giữ missing. Median, scaling, missing-indicator selection và vocab chỉ học train. Không chọn mô hình từ kết quả test.

## Đánh giá và giả định

Giữ split ngẫu nhiên loan-level seed 2026, 80/20, stratify E; temporal holdout FPD<=201512 so với >201512 là nội bộ, không triển vọng. CLTV và tie là sensitivity đã định trước. Horizons 12/24/36/60/120.

Censor cuối tháng u cho biết event-free qua u. Event được xử lý trước censor cùng tháng. Censor survival G(t)=P(C>t): hazard censor tháng u là d0/(Y−d1−d2), trên risk trước tháng, không gồm entrants L=u. Nếu không ai còn để censor thì hazard=0. IPCW với entry L: numerator G(L), denominator G(u−) cho event trước/tại h và G(h−) cho outcome known qua h. Censor trước h có loss=0 trong estimator, vẫn trong mẫu số eligible; thiếu support -> NaN, không cắt weight. Đây vẫn là phân tích phụ thuộc independent censoring/truncation chưa được chứng minh.

Known-status Brier là loss trung bình chỉ trên outcomes biết tại h, Cox và AJ train dùng cùng IDs; không gọi là score toàn cohort không chệch hoặc gán đúng phương pháp administrative Brier trong bài Kvamme–Borgan. Concordance kiểu Harrell với quy ước thời gian tháng nghiêm ngặt: L<t và T_control>t, tie risk=1/2. Loại mọi cặp có cùng exit month vì thứ tự trong tháng không rõ; không đồng nhất các implementation Harrell xử lý event/censor đồng thời theo quy ước khác. Bootstrap 100 test-loan cho chính/temporal, 20 cho sensitivity; mô hình và nuisance fit giữ cố định. PH correlation là screening; không gán p-value này là bằng chứng PH chuẩn hoặc HR nhân quả. Không tuning theo screening sau khi xem test.

Nguồn định nghĩa mã và tháng: [Freddie Mac guide](https://www.freddiemac.com/fmac-resources/research/pdf/general_user_guide_july_2026.pdf). Tài liệu cập nhật chu kỳ báo cáo từ tháng 10/2025: month là độ phân giải vận hành, không ngày xảy ra chính xác. Các giả định chưa kiểm chứng và bằng chứng kiểm tra hiện hành ghi ở [báo cáo lý thuyết và thực nghiệm](../outputs/experiments/cox_theory_20261023_2dc0b4ff6893/theory_review.md).
