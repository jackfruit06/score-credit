
from collections import Counter, defaultdict
from pathlib import Path
import csv

ORIG_FILE = Path("sample_orig_2015.txt")
PERF_FILE = Path("sample_perf_2015.txt")


def check_file(path):
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {path.resolve()}")


def inspect_origination():
    """Kiểm tra file thông tin khoản vay tại thời điểm ban đầu."""
    print("\n" + "=" * 65)
    print("1. ORIGINATION FILE")
    print("=" * 65)

    check_file(ORIG_FILE)

    total_rows = 0
    field_counts = Counter()
    nonempty_by_col = Counter()
    loan_ids = set()
    examples = []

    with ORIG_FILE.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f, delimiter="|")

        for row in reader:
            if not row:
                continue

            total_rows += 1
            field_counts[len(row)] += 1

            if row[0].strip():
                loan_ids.add(row[19].strip())

            for i, value in enumerate(row):
                if value.strip():
                    nonempty_by_col[i + 1] += 1

            if len(examples) < 3:
                examples.append(row)

    print(f"Tổng số bản ghi: {total_rows:,}")
    print(f"Số mã khoản vay duy nhất: {len(loan_ids):,}")
    print(f"Số lượng cột theo từng bản ghi: {dict(field_counts)}")
    print("\nTỷ lệ giá trị không rỗng theo cột:")

    for col in sorted(field_counts):
        n = nonempty_by_col[col]
        print(f"  Cột {col:02d}: {n:,}/{total_rows:,} "
              f"({n / total_rows:.1%})")

    print("\n3 bản ghi mẫu (các cột đánh số từ 1):")
    for row in examples:
        print(row)

    return loan_ids


def inspect_performance(orig_ids):
    """Đọc file theo từng dòng, không nạp toàn bộ file vào RAM."""
    print("\n" + "=" * 65)
    print("2. PERFORMANCE FILE")
    print("=" * 65)

    check_file(PERF_FILE)

    total_rows = 0
    field_counts = Counter()
    status_counts = Counter()
    zero_balance_counts = Counter()
    report_period_counts = Counter()
    nonempty_by_col = Counter()

    # loan_id -> [số bản ghi, kỳ đầu, kỳ cuối, số kỳ duy nhất]
    loan_stats = {}
    seen_periods = defaultdict(set)
    perf_ids = set()
    examples = []

    with PERF_FILE.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.reader(f, delimiter="|")

        for row in reader:
            if not row:
                continue

            total_rows += 1
            field_counts[len(row)] += 1

            # Bỏ qua dòng không đủ cột để phân tích.
            if len(row) < 9:
                continue

            loan_id = row[0].strip()
            period = row[1].strip()
            delinquency_status = row[3].strip()
            zero_balance_code = row[8].strip()

            if loan_id:
                perf_ids.add(loan_id)

                if loan_id not in loan_stats:
                    loan_stats[loan_id] = [0, period, period, 0]

                stats = loan_stats[loan_id]
                stats[0] += 1

                if period:
                    if not stats[1] or period < stats[1]:
                        stats[1] = period
                    if not stats[2] or period > stats[2]:
                        stats[2] = period

                    seen_periods[loan_id].add(period)

            status_counts[delinquency_status or "<EMPTY>"] += 1
            zero_balance_counts[zero_balance_code or "<EMPTY>"] += 1

            if period:
                report_period_counts[period] += 1

            for i, value in enumerate(row):
                if value.strip():
                    nonempty_by_col[i + 1] += 1

            if len(examples) < 3:
                examples.append(row)

            if total_rows % 500_000 == 0:
                print(f"Đã đọc {total_rows:,} dòng...")

    print(f"\nTổng số bản ghi: {total_rows:,}")
    print(f"Số mã khoản vay duy nhất: {len(perf_ids):,}")
    print(f"Số lượng cột theo từng bản ghi: {dict(field_counts)}")

    print("\nTần suất delinquency status (cột 4):")
    for code, count in status_counts.most_common():
        print(f"  {code}: {count:,} ({count / max(total_rows, 1):.2%})")

    print("\nTần suất zero balance code (cột 9):")
    for code, count in zero_balance_counts.most_common():
        print(f"  {code}: {count:,} ({count / max(total_rows, 1):.2%})")

    print("\nKhoảng thời gian báo cáo:")
    if report_period_counts:
        periods = sorted(report_period_counts)
        print(f"  Kỳ đầu: {periods[0]}")
        print(f"  Kỳ cuối: {periods[-1]}")
        print(f"  Số kỳ báo cáo khác nhau: {len(periods)}")

    matched = orig_ids & perf_ids
    print("\nĐối chiếu hai file:")
    print(f"  Mã khoản vay trong origination: {len(orig_ids):,}")
    print(f"  Mã khoản vay trong performance: {len(perf_ids):,}")
    print(f"  Mã xuất hiện ở cả hai file: {len(matched):,}")
    print(f"  Chỉ có trong origination: {len(orig_ids - perf_ids):,}")
    print(f"  Chỉ có trong performance: {len(perf_ids - orig_ids):,}")

    if loan_stats:
        row_counts = [v[0] for v in loan_stats.values()]
        unique_period_counts = [len(seen_periods[k]) for k in loan_stats]

        print("\nSố kỳ theo dõi mỗi khoản vay:")
        print(f"  Ít nhất: {min(row_counts)} bản ghi")
        print(f"  Trung vị: {sorted(row_counts)[len(row_counts) // 2]} bản ghi")
        print(f"  Nhiều nhất: {max(row_counts)} bản ghi")
        print(f"  Trung vị số kỳ khác nhau: "
              f"{sorted(unique_period_counts)[len(unique_period_counts) // 2]}")

        print("\n5 khoản vay mẫu: loan ID | số bản ghi | kỳ đầu | kỳ cuối")
        for loan_id in list(loan_stats)[:5]:
            stats = loan_stats[loan_id]
            print(f"  {loan_id} | {stats[0]} | {stats[1]} | {stats[2]}")

    print("\n3 bản ghi mẫu:")
    for row in examples:
        print(row)

    print("\nLưu ý: mã trạng thái mới chỉ được thống kê, chưa được")
    print("diễn giải thành vỡ nợ hay tất toán. Cần đối chiếu data dictionary.")


if __name__ == "__main__":
    orig_ids = inspect_origination()
    inspect_performance(orig_ids)

    print("\n" + "=" * 65)
    print("HOÀN TẤT KIỂM TRA SƠ BỘ")
    print("=" * 65)
