# Phương pháp thống kê

Hợp đồng phân tích được chốt tại [analysis_contract.md](analysis_contract.md). Kết quả hiện hành nằm trong [báo cáo thực nghiệm](../outputs/experiments/cox_theory_20261023_2dc0b4ff6893/theory_review.md).

## Câu hỏi nghiên cứu và đại lượng đích

Với khoản vay Freddie Mac năm 2015, các đặc điểm tại thời điểm khởi tạo liên hệ như thế nào với thời điểm lần đầu **được báo cáo** quá hạn 90+ ngày, trước khi có ghi nhận kết thúc zero-balance? Endpoint chính là status `03` trở lên trong tháng performance đầu tiên đáp ứng điều kiện. Đây là proxy vận hành cho tình trạng quá hạn, không phải vỡ nợ pháp lý, foreclosure, charge-off hay tổn thất đã thực hiện.

Chúng tôi ước tính (1) cause-specific hazard cho lần quá hạn 90+ đầu tiên và cho mọi kết thúc zero-balance, và (2) cumulative incidence tương ứng của lần quá hạn 90+ đầu tiên khi có kết thúc cạnh tranh. Các mã zero-balance vẫn được giữ riêng trong đầu ra cấp khoản vay. Nguyên nhân 2 gộp các mã để tạo endpoint cạnh tranh ổn định; điều này không có nghĩa mọi mã đều là khoản vay được người vay trả trước.

## Thời gian, entry và cách tạo biến cố

Thời điểm 0 là tháng lịch của First Payment Date. Thời gian phân tích là số tháng lịch rời rạc; tháng First Payment Date kết thúc ở tháng 1. Với khoản vay \(i\), gọi \(M_i^{FPD}\) và \(M_i^{first}\) là chỉ số tháng lịch nguyên của FPD và tháng performance đầu tiên. Code đặt entry là \(e_i=\max(0,M_i^{first}-M_i^{FPD})\); thời lượng đến biến cố/kết thúc ở tháng \(M_i^{exit}\) là \(T_i=M_i^{exit}-M_i^{FPD}+1\). Tại tháng biến cố \(t\), điều kiện vào risk set chính xác là `entry < t` và `duration >= t`; khoản vay có `entry = t` không thuộc risk set của interval kết thúc tại \(t\). Thời điểm biến cố được xác định theo độ phân giải báo cáo cuối tháng. Loan Age không phải đồng hồ chính vì định nghĩa có thể thay đổi sau khi sửa đổi khoản vay. Đây là left truncation, không phải right censoring: để diễn giải hazard/CIF cho cohort cần giả định phù hợp về entry/truncation độc lập và khoản vay còn event-free đến entry. Với 2.736 khoản delayed entry, tệp này không xác nhận được khoản vay không có biến cố trong khoảng từ First Payment Date đến performance đầu tiên được quan sát.

Với mỗi khoản vay, status `03+` sớm nhất được quan sát vào hoặc sau First Payment Date là biến cố đích, trừ khi zero-balance termination xảy ra trước. Loại khoản có 90+ trước origin khỏi cohort incident; raw hiện tại không có trường hợp này. Loại terminal trước entry và các khoản chỉ có quan sát trước origin; không ép duration lên entry+1. Loại khỏi cohort có nguy cơ các khoản vay có Zero Balance Effective Date trước First Payment Date vì kết thúc cạnh tranh xảy ra trước thời điểm 0; số lượng bị loại được ghi trong kiểm toán tạo cohort. Nếu status 90+ và termination cùng xuất hiện trong một tháng báo cáo thì không suy ra được thứ tự trong tháng; quy tắc chính xếp termination vào nhóm competing. Khi có Zero Balance Effective Date, dùng ngày đó xác định tháng kết thúc; nếu thiếu thì dùng tháng báo cáo và đánh dấu trường hợp này.

## Mô hình Cox nguyên nhân cụ thể và CIF

Hai mô hình Cox proportional hazards được fit bằng `lifelines.CoxPHFitter`; cả hai truyền delayed entry qua `entry_col` và dùng cùng tập biến giải thích tại thời điểm khởi tạo. Trong mỗi mô hình nguyên nhân cụ thể, các nguyên nhân khác được mã hóa là không phải biến cố tại thời điểm kết thúc của chúng khi ước tính hazard nguyên nhân đang xét. Trong môi trường đã kiểm tra, lifelines 0.30.3 dùng phương pháp Efron cho tie trong partial likelihood bán tham số và ước tính baseline hazard mặc định của `CoxPHFitter` theo Breslow. Baseline mặc định của lifelines 0.30.3 bỏ qua entry: pipeline tính lại Breslow với mẫu số sum exp((x−xbar)beta) trên L<t<=T, lưu đầy đủ tháng 0..max(T) và H(0)=0 trước mọi dự báo. Repository chỉ khai báo `lifelines>=0.29`, nên không khóa chính xác phiên bản môi trường cho lần tái lập khác. Chỉ dùng cause-specific hazard không làm CIF của endpoint bằng `1 -` đường sống còn của mô hình nguyên nhân đích.

Với các biến giải thích \(x\), code dự báo cumulative hazard nguyên nhân cụ thể đã fit \(H_k(m\mid x)\) tại các ranh giới tháng nguyên \(m=0,1,\ldots,h\). Với endpoint interval \(t=1,\ldots,h\), code lấy hiệu giữa hai ranh giới kề nhau và xem đó là integrated hazard của interval:

\[
\Delta H_{k,t}(x)=H_k(t\mid x)-H_k(t-1\mid x)
=\int_{t-1}^{t}\lambda_k(u\mid x)\,du,
\qquad k\in\{1,2\}.
\]

Increment này không phải xác suất biến cố trong tháng. Phân bổ đều increment đã fit trên một tháng có độ dài đơn vị là quy ước nội suy để dự báo; dữ liệu quan sát không xác lập rằng hazard thực tế không đổi trong tháng. Với cause-specific hazard hằng từng đoạn theo quy ước này, đặt \(\Delta H_{\cdot,t}=\sum_k\Delta H_{k,t}\). Với khoản vay entry tại thời điểm nguyên \(e\), khởi tạo \(S_e(e\mid x)=1\) và \(F_{k,e}(e\mid x)=0\); chỉ cập nhật các interval có \(t>e\):

\[
S_e(t\mid x)=S_e(t-1\mid x)\exp(-\Delta H_{\cdot,t}),
\]
\[
F_{k,e}(t\mid x)=F_{k,e}(t-1\mid x)+
\begin{cases}
S_e(t-1\mid x)\left(1-\exp(-\Delta H_{\cdot,t})\right)\dfrac{\Delta H_{k,t}}{\Delta H_{\cdot,t}}, & \Delta H_{\cdot,t}>0,\\[5pt]
0, & \Delta H_{\cdot,t}=0.
\end{cases}
\]

Code thực hiện cập nhật bằng `-expm1(-total)` và phép chia có điều kiện (`where=total > 0`); khi tổng increment bằng 0, survival không đổi và increment của từng CIF bằng 0. Code loại mọi interval kết thúc tại hoặc trước entry (`entry < t`), tạo ra các đại lượng có điều kiện
\[
S_e(h\mid x)=P(T>h\mid T>e,X=x),\qquad
F_{k,e}(h\mid x)=P(e<T\le h,J=k\mid T>e,X=x),\quad h\ge e.
\]
Do đó \(S_e(e\mid x)=1\), \(F_{k,e}(e\mid x)=0\), và survival cộng các CIF nguyên nhân bằng 1, trong sai số số học cho phép. Với khoản delayed entry, đây không phải dự báo vô điều kiện từ First Payment Date. Cập nhật exponential hazard cạnh tranh là chính xác có điều kiện trên quy ước nội suy trong tháng này; nó không phải cập nhật Aalen–Johansen tháng rời rạc dựa trên tỷ lệ biến cố/risk set.

Nếu horizon yêu cầu nằm tại hoặc trước entry của khoản vay, đầu ra là 0 vì chưa tích lũy interval nào sau entry. Phần đánh giá loại các khoản có `entry >= horizon`; không diễn giải số 0 mà API trả ở các horizon trước entry như ước lượng rủi ro tại thời điểm đó.

Để mô tả incidence quan sát, code dùng ước lượng product-limit Aalen–Johansen rời rạc theo tháng với risk set \(Y_t=\#\{i:e_i<t,\ T_i\ge t\}\). Trong tháng có biến cố, số lượng theo mọi nguyên nhân được cập nhật đồng thời: survival nhân với \(1-d_{\cdot t}/Y_t\), còn mỗi CIF tăng thêm survival đầu tháng nhân \(d_{kt}/Y_t\). Đây là các ước tính cho cohort phân tích theo risk set entry và theo dõi thực tế. Diễn giải ở mức quần thể đòi hỏi giả định phù hợp về left truncation độc lập và right censoring; các giả định này chưa được xác lập ở đây. Các ước tính AJ này khác với dự báo mô hình có điều kiện cho khoản vay vào mẫu ở các tháng khác nhau.

## Đặc trưng và tiền xử lý

Các biến dự báo có sẵn lúc khởi tạo gồm classic FICO, LTV, DTI, lãi suất ban đầu, thời hạn ban đầu, tỷ lệ và chỉ báo bảo hiểm khoản vay, log UPB ban đầu, loại hình cư trú, mục đích vay, loại tài sản, người mua nhà lần đầu, kênh, nhóm số người vay và số đơn vị. Mô hình chính dùng LTV; phân tích nhạy cảm thay LTV bằng CLTV. Không dùng thông tin performance theo tháng làm biến dự báo. Các giá trị số đặc biệt đã biết được chuyển thành thiếu trước khi bù. Trung vị bù thiếu, giá trị scale và các mức phân loại chỉ được học trên train và lưu cùng model bundle.

## Đánh giá mô hình và bất định

Khoản vay được chia ngẫu nhiên 80/20, phân tầng theo chỉ báo biến cố chính và dùng seed cố định. Đây là tập giữ lại trong vintage 2015, không phải đánh giá theo thời gian hay ngoài vintage. Xếp hạng dùng Harrell concordance có delayed entry: với một biến cố đích quan sát được, khoản vay có thời điểm muộn hơn chỉ được so sánh nếu đã vào mẫu trước thời điểm biến cố; nguy cơ dự báo cao hơn cần được xếp trước. Cặp hòa điểm đóng góp một nửa.

Một tập giữ lại theo lịch, độc lập với kết quả, dùng các khoản có First Payment Date đến hết 201512 để huấn luyện và đánh giá các khoản sau 201512. Đây là kiểm định nội bộ trên cohort muộn trong cùng mẫu Freddie Mac 2015, phần lớn có FPD năm 2016. Kết quả huấn luyện được quan sát đến mốc kết thúc dữ liệu năm 2026, vì vậy phép chia này không mô phỏng thông tin có sẵn tại thời điểm triển khai lịch sử và cũng không phải đánh giá bên ngoài.

Sai số dự báo CIF và calibration được đánh giá tại 12, 24, 36, 60 và 120 tháng tính từ FPD. Với horizon \(h\), khoản vay đủ điều kiện phải thỏa \(e_i<h\). Trạng thái đích là \(Y_i(h)=I(T_i\le h,J_i=1)\). Code gán 1 cho biến cố đích đến thời điểm \(h\); gán 0 cho competing exit đến \(h\) và quan sát đã biết event-free qua \(h\). Right censor trước \(h\) có trạng thái chưa biết và nhận trọng số/tổn thất bằng 0, nhưng vẫn nằm trong mẫu số đủ điều kiện của IPCW. Biến cố/competing exit tại \(h\) được quan sát ở mốc chốt dữ liệu tháng; right censor đúng tại \(h\) được xem là đã biết event-free đến hết tháng báo cáo đó.

Reverse product-limit theo tháng trên train (event trước censor cùng tháng; censor denominator Y−d1−d2) ước tính \(G\), xem right censor (nguyên nhân 0) là biến cố và kiểm duyệt các nguyên nhân quan sát 1 và 2 trong mô hình censoring đó; phép fit dùng risk set có delayed entry. Với ca đích/competing outcome đã biết tại \(u_i\le h\), trọng số trong code là \(G(e_i)/G(u_i^-)\); với đối chứng được quan sát qua \(h\), trọng số là \(G(e_i)/G(h^-)\). Do đó, điểm số triển khai là
\[
\widehat{BS}_{IPCW}(h)=\frac{1}{N_h}\sum_{i:e_i<h}w_i(h)\{Y_i(h)-\widehat F_{1,e_i}(h\mid x_i)\}^2,
\qquad N_h=\#\{i:e_i<h\},
\]
với \(w_i=0\) khi bị kiểm duyệt nghiêm ngặt trước \(h\). Competing exit là trạng thái âm đã biết của endpoint trong Brier loss; chỉ khi fit reverse-KM thì chúng mới được xem là đã kết thúc quan sát cho mô hình censoring. Code dùng giới hạn trái tại biến cố/horizon và giá trị sau cập nhật tại entry, không áp trần trọng số tùy tiện và trả NaN nếu thiếu support cần thiết thay vì âm thầm loại các trạng thái không được hỗ trợ. Tỷ số \(G\) biên chỉ biểu diễn censoring sau entry khi các giả định phù hợp về censoring độc lập và truncation độc lập được thỏa mãn; ở đây thời gian theo dõi hành chính gắn với FPD theo lịch, còn mô hình biên không điều kiện theo FPD/hiệp biến. Vì vậy, các giá trị IPCW phụ thuộc giả định và chưa được chứng minh là không chệch cho toàn cohort.

Để bổ sung, pipeline báo cáo Brier không trọng số trên các trạng thái đã biết. Mẫu số là số khoản vay có `entry < h` và trạng thái được biết đến \(h\): biến cố đích hoặc competing exit tại/trước \(h\), quan sát vượt quá \(h\), và right censor đúng tại \(h\). Loại các khoản bị censor nghiêm ngặt trước \(h\). Cách này không cần ước tính \(G\), nhưng chỉ chấm điểm tập con có trạng thái quan sát được và không mặc nhiên đại diện cho mọi khoản đủ điều kiện. Đường tham chiếu ghép cặp là AJ có delayed entry, chỉ fit trên train, có điều kiện event-free tại entry của từng khoản test. Ở mỗi horizon, Cox và AJ dùng cùng các khoản test có trạng thái đã biết; chênh lệch báo cáo là Cox trừ AJ. Khoảng percentile lấy mẫu lại ID khoản vay test theo cặp 100 lần, giữ cố định dự báo Cox và đường AJ đã fit; không bao gồm bất định từ mẫu train hay quá trình fit mô hình.

Tóm tắt calibration tổng thể so sánh CIF dự báo trung bình có điều kiện của các khoản test đủ điều kiện với tỷ lệ tổng các outcome đích có trọng số IPCW trên tổng trọng số. Tóm tắt theo quintile nhóm các khoản đủ điều kiện theo CIF dự báo, rồi báo cáo trung bình dự báo và tỷ lệ quan sát có trọng số trong nhóm; mỗi nhóm có khoảng 1.942–2.000 khoản trong split ngẫu nhiên. Đây là các ước lượng điểm mô tả, không có khoảng; độ gần nhau tổng thể không chứng minh calibration ở các nhóm con hay cohort khác. Tại 120 tháng trong split ngẫu nhiên, 8/9.996 khoản đủ điều kiện bị censor trước horizon; hiệu chỉnh trọng số ước tính nhỏ không xác lập giả định censoring độc lập. Brier trạng thái đã biết loại tám khoản này và dùng tập quan sát cùng mẫu số khác.

Khoảng bootstrap lấy mẫu lại các khoản vay held-out, giữ cố định mô hình đã fit, tiền xử lý và mô hình censoring trên train. Chúng mô tả bất định của mẫu test có điều kiện trên pipeline đã fit, không gồm bất định khi fit lại toàn bộ quy trình phát triển mô hình.

## Chẩn đoán, giới hạn và khả năng tái lập

Project báo cáo xu hướng phần dư Schoenfeld xấp xỉ, chưa scale, cho từng nguyên nhân. Trong môi trường lifelines 0.30.3 đã kiểm tra, `compute_residuals()` phát sinh `NotImplementedError` mỗi khi đặt `entry_col`; do đó xu hướng tùy chỉnh có delayed entry/Efron expectation chỉ là chẩn đoán sàng lọc, không phải kiểm định PH chính thức mang tính kết luận. Hệ số là liên hệ có điều kiện, không phải tác động nhân quả. Các giới hạn đáng kể gồm mẫu Freddie Mac năm 2015, theo dõi hành chính, giả định entry độc lập và event-free tại entry chưa được xác minh, thứ tự biến cố trong tháng không rõ, và giả định censoring của IPCW biên chưa được hỗ trợ. Không fit Cox hiệu chỉnh cho endpoint B vì số biến cố theo định nghĩa code nhỏ.

Tái lập bằng `python src/survival_pipeline.py --bootstrap 100`, `python src/eda.py` và `python -m unittest discover -s tests -v`. Loss IPCW theo cách chấm điểm trạng thái biến cố cạnh tranh được mô tả trong [Schoop và cộng sự (2011)](https://doi.org/10.1002/bimj.201000073), cùng hướng dẫn validation mô hình rủi ro cạnh tranh của [van Geloven và cộng sự (2022)](https://www.bmj.com/content/377/bmj-2021-069249); ước tính trọng số censoring theo công thức IPCW Brier của [Gerds và Schumacher (2006)](https://doi.org/10.1002/bimj.200610301). Censoring hành chính có thể ảnh hưởng đáng kể đến điểm IPCW Brier ([Kvamme và Borgan, 2023](https://www.jmlr.org/papers/volume24/19-1030/19-1030.pdf)). Công thức Cox dựa trên [Cox (1972)](https://doi.org/10.1111/j.2517-6161.1972.tb00899.x); ước lượng rủi ro cạnh tranh dựa trên tích phân product Aalen–Johansen ([Aalen và Johansen, 1978](https://www.jstor.org/stable/4615704)).
