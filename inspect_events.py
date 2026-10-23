
from collections import Counter
from pathlib import Path
import csv

FILE = Path("sample_perf_2015.txt")

# Mỗi mã khoản vay chỉ lưu một bản tóm tắt.
loans = {}
status_rows = Counter()
zero_code_rows = Counter()

with FILE.open("r", encoding="utf-8", errors="replace", newline="") as f:
    reader = csv.reader(f, delimiter="|")

    for row in reader:
        if len(row) < 9 or not row[0].strip():
            continue

        loan_id = row[0].strip()
        period = row[1].strip()
        status = row[3].strip()
        zero_code = row[8].strip()

        if loan_id not in loans:
            loans[loan_id] = {
                "first_period": period,
                "last_period": period,
                "first_90plus": None,
                "max_numeric_status": None,
                "zero_codes": set(),
                "first_zero_period": None,
            }

        loan = loans[loan_id]

        if period:
            if not loan["first_period"] or period < loan["first_period"]:
                loan["first_period"] = period
            if not loan["last_period"] or period > loan["last_period"]:
                loan["last_period"] = period

        status_rows[status or "<EMPTY>"] += 1

        # Mã số 03 trở lên được xem là từ 90 ngày quá hạn trở lên,
        # theo cách mã hóa delinquency status; cần xác nhận bằng data dictionary.
        if status.isdigit():
            numeric_status = int(status)
            previous = loan["max_numeric_status"]
            if previous is None or numeric_status > previous:
                loan["max_numeric_status"] = numeric_status

            if numeric_status >= 3:
                if loan["first_90plus"] is None:
                    loan["first_90plus"] = period

        if zero_code:
            zero_code_rows[zero_code] += 1
            loan["zero_codes"].add(zero_code)

            if loan["first_zero_period"] is None:
                loan["first_zero_period"] = period

n = len(loans)
loans_90plus = {
    k for k, v in loans.items()
    if v["first_90plus"] is not None
}
loans_with_zero = {
    k for k, v in loans.items()
    if v["zero_codes"]
}
overlap = loans_90plus & loans_with_zero

print("=" * 60)
print("1. TỔNG QUAN")
print("=" * 60)
print(f"Số khoản vay: {n:,}")
print(f"Từng đạt trạng thái 90+ ngày: {len(loans_90plus):,} "
      f"({len(loans_90plus) / max(n, 1):.2%})")
print(f"Có ít nhất một zero balance code: {len(loans_with_zero):,} "
      f"({len(loans_with_zero) / max(n, 1):.2%})")
print(f"Thuộc cả hai nhóm trên: {len(overlap):,}")

print("\n" + "=" * 60)
print("2. ZERO BALANCE CODE — SỐ KHOẢN VAY")
print("=" * 60)
loan_code_counts = Counter()
for loan in loans.values():
    for code in loan["zero_codes"]:
        loan_code_counts[code] += 1

for code, count in loan_code_counts.most_common():
    print(f"Mã {code}: {count:,} khoản vay")

print("\n" + "=" * 60)
print("3. MỨC QUÁ HẠN LỚN NHẤT — SỐ KHOẢN VAY")
print("=" * 60)
max_status_counts = Counter(
    v["max_numeric_status"] for v in loans.values()
    if v["max_numeric_status"] is not None
)

for status, count in sorted(max_status_counts.items()):
    print(f"Mã lớn nhất {status:02d}: {count:,} khoản vay")

print("\n" + "=" * 60)
print("4. VÍ DỤ KHOẢN VAY TỪNG ĐẠT 90+ NGÀY")
print("=" * 60)
shown = 0
for loan_id, loan in loans.items():
    if loan["first_90plus"] is not None:
        print(
            f"{loan_id} | lần đầu 90+: {loan['first_90plus']} | "
            f"zero codes: {sorted(loan['zero_codes']) or 'không có'} | "
            f"kỳ cuối: {loan['last_period']}"
        )
        shown += 1
        if shown == 10:
            break

print("\nLưu ý: đây là thống kê sơ bộ, chưa phải nhãn vỡ nợ.")
print("Cần xác minh ý nghĩa mã kết thúc và cách xử lý tất toán.")
