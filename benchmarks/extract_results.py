import csv
import sys

def extract(csv_path):
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        print(f"{'Endpoint':<40} {'RPS':>8} {'P50':>8} {'P95':>8} {'P99':>8} {'Err%':>8}")
        print("-" * 80)
        for row in reader:
            name = row.get("Name", "")
            if not name:
                continue
            rps = row.get("Requests/s", "0")
            p50 = row.get("50%", "0")
            p95 = row.get("95%", "0")
            p99 = row.get("99%", "0")
            total = int(row.get("Request Count", 0))
            fails = int(row.get("Failure Count", 0))
            err_pct = f"{fails/total*100:.1f}%" if total > 0 else "0%"
            print(f"{name:<40} {rps:>8} {p50:>8} {p95:>8} {p99:>8} {err_pct:>8}")

if __name__ == "__main__":
    extract(sys.argv[1] if len(sys.argv) > 1 else "benchmarks/results/baseline/data_stats.csv")