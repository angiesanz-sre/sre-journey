import argparse

def calculate_burn_rate(log_file):
    total = 0
    errors = 0

    with open(log_file) as f:
        for line in f:
            total += 1
            if "500" in line or "ERROR" in line:
                errors += 1

    if total == 0:
        return 0

    error_rate = errors / total
    slo_target = 0.001   # 99.9% reliability target
    burn_rate = error_rate / slo_target
    return burn_rate

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", help="path to the log file", required=True)
    args = parser.parse_args()

    rate = calculate_burn_rate(args.log)
    print("Burn rate:", round(rate, 2))
