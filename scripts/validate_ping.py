"""Step 3 check: ns-3 ping RTT vs. geometric ground truth (path_truth.csv).
Usage: python3 validate_ping.py <path_truth.csv> <ping_run_dir>
Expected: median(ping - truth) is a small positive number (< 1 ms: serialization of the ping on each hop)."""
import csv, sys
truth = {round(float(r["t_s"]), 1): float(r["rtt_prop_ms"]) for r in csv.DictReader(open(sys.argv[1])) if r["rtt_prop_ms"]}
err = []
for r in csv.reader(open(sys.argv[2] + "/logs_ns3/pingmesh.csv")):
    if r[9] != "YES":
        continue
    t = int(r[3]) / 1e9
    k = round(int(t * 10) / 10, 1)
    if k in truth:
        err.append((int(r[5]) - int(r[3])) / 1e6 - truth[k])
err.sort(); n = len(err)
print("pings %d   ping RTT - truth [ms]: min %.3f  median %.3f  p99 %.3f  max %.3f"
      % (n, err[0], err[n // 2], err[int(n * .99)], err[-1]))
