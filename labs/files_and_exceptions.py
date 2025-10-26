import pathlib
import datetime
import json
import csv
import sys

# Get today's date
today_str = datetime.date.today().strftime('%Y%m%d')
print(today_str)

# Create a folder with today's date
folder_path = pathlib.Path(today_str)
folder_path.mkdir(parents=True, exist_ok=True)
print(f"Created or using folder: {folder_path}")

# Create two file paths
csv_path = folder_path / f"results-{today_str}.csv"
json_path = folder_path / f"results.json"

# Data
results = [
    {"id": 1, "name": "Alice", "score": 95},
    {"id": 2, "name": "Bob", "score": 87},
]
print(results)

try:
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Saved JSON file to {json_path}")
except OSError as e:
    fail(f"Could not write JSON file: {e}")

if not results:
    fail("No data to write to CSV")

headers = results[0].keys()

try:
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(results)
    print(f"Saved CSV file to {csv_path}")
except OSError as e:
    fail(f"Could not write CSV file: {e}")

try:
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"Read {len(data)} records from JSON.")
    print("First record:", data[0])
except OSError as e:
    fail(f"Could not read JSON file: {e}")

try:
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    print(f"Read {len(rows)} rows from CSV.")
    print("First row:", rows[0])
except OSError as e:
    fail(f"Could not read CSV file: {e}")

print(f"Saved {len(results)} records to folder {folder_path}")