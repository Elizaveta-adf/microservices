import json
from datetime import datetime
from collections import defaultdict
from pathlib import Path
import matplotlib.pyplot as plt


folder = Path(__file__).resolve().parent
interval = 5
records = []

with open(folder / "load-results.json", encoding="utf-8-sig") as file:
    for line in file:
        record = json.loads(line)

        if record["type"] == "Point":
            records.append(record)

start = min(
    datetime.fromisoformat(
        record["data"]["time"].replace("Z", "+00:00")
    ).timestamp()
    for record in records
    if record["metric"] == "http_reqs"
)

requests = defaultdict(int)
durations = defaultdict(list)
errors = defaultdict(list)

for record in records:
    metric = record["metric"]
    data = record["data"]

    timestamp = datetime.fromisoformat(
        data["time"].replace("Z", "+00:00")
    ).timestamp()

    bucket = int((timestamp - start) // interval)
    value = data["value"]

    if metric == "http_reqs":
        requests[bucket] += value

    elif metric == "http_req_duration":
        durations[bucket].append(value)

    elif metric == "http_req_failed":
        errors[bucket].append(value)


def percentile(values, p):
    values = sorted(values)

    if not values:
        return float("nan")

    index = (len(values) - 1) * p / 100
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)

    return values[lower] + (
        values[upper] - values[lower]
    ) * (index - lower)


buckets = list(range(max(requests) + 1))
seconds = [(b + 1) * interval for b in buckets]

rps = [requests[b] / interval for b in buckets]

p50 = [percentile(durations[b], 50) for b in buckets]
p95 = [percentile(durations[b], 95) for b in buckets]
p99 = [percentile(durations[b], 99) for b in buckets]

error_rate = [
    100 * sum(errors[b]) / len(errors[b])
    if errors[b] else float("nan")
    for b in buckets
]


# 1. RPS
plt.figure(figsize=(10, 5))
plt.plot(seconds, rps, marker="o")
plt.title("Requests per Second (RPS)")
plt.xlabel("Time, s")
plt.ylabel("Requests/sec")
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig(folder / "rps.png", dpi=300)


# 2. Latency
plt.figure(figsize=(10, 5))
plt.plot(seconds, p50, marker="o", label="p50")
plt.plot(seconds, p95, marker="o", label="p95")
plt.plot(seconds, p99, marker="o", label="p99")
plt.title("HTTP Request Latency")
plt.xlabel("Time, s")
plt.ylabel("Latency, ms")
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig(folder / "latency.png", dpi=300)


# 3. Error Rate
plt.figure(figsize=(10, 5))
plt.plot(seconds, error_rate, marker="o")
plt.title("HTTP Error Rate")
plt.xlabel("Time, s")
plt.ylabel("Error Rate, %")
plt.ylim(-0.1, 1)
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig(folder / "error_rate.png", dpi=300)


print("Total requests:", sum(requests.values()))
print("Maximum 5-second RPS:", max(rps))
print("Graphs saved successfully")

plt.show()