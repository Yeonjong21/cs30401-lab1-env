"""Ground truth: the path Seoul->London (and back) at every forwarding-state step,
with its propagation-only RTT. Uses satgenpy's own TLE reader and distance functions.

Usage: python3 path_truth.py <state_dir> <dyn_state_subdir> <src_node> <dst_node> <out_csv>
Output columns: t_s, hops_fwd, hops_rev, rtt_prop_ms, path_changed (1 if fwd or rev path differs from previous step), path_fwd
"""
import os
import sys
import types

for _m in ["cartopy", "cartopy.crs"]:
    sys.modules.setdefault(_m, types.ModuleType(_m))
sys.path.insert(0, os.environ.get("SATGENPY", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hypatia", "satgenpy")))
import satgen  # noqa: E402
from astropy import units as u  # noqa: E402

C = 299792458.0


def main():
    state, dyn, src, dst, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
    tles = satgen.read_tles(state + "/tles.txt")
    sats, epoch = tles["satellites"], tles["epoch"]
    gss = satgen.read_ground_stations_extended(state + "/ground_stations.txt")
    nsat = len(sats)
    step_ns = int(dyn.split("_")[2].replace("ms", "")) * 1000000
    files = sorted((int(f[len("fstate_"):-4]) for f in os.listdir(state + "/" + dyn) if f.startswith("fstate_")))
    fstate = {}
    prev = None
    with open(out, "w") as fo:
        fo.write("t_s,hops_fwd,hops_rev,rtt_prop_ms,path_changed,path_fwd\n")
        for t_ns in files:
            with open("%s/%s/fstate_%d.txt" % (state, dyn, t_ns)) as f:
                for line in f:
                    a, d, nh, _, _ = line.strip().split(",")
                    fstate[(int(a), int(d))] = int(nh)
            date = str(epoch + t_ns * u.ns)

            def dist(x, y):
                if x >= nsat:
                    return satgen.distance_m_ground_station_to_satellite(gss[x - nsat], sats[y], str(epoch), date)
                if y >= nsat:
                    return satgen.distance_m_ground_station_to_satellite(gss[y - nsat], sats[x], str(epoch), date)
                return satgen.distance_m_between_satellites(sats[x], sats[y], str(epoch), date)

            def walk(a, b):
                path, cur = [a], a
                while cur != b:
                    cur = fstate.get((cur, b), -1)
                    if cur == -1 or len(path) > 200:
                        return None
                    path.append(cur)
                return path

            pf, pr = walk(src, dst), walk(dst, src)
            if pf is None or pr is None:
                fo.write("%.1f,,,,1,\n" % (t_ns / 1e9))
                prev = None
                continue
            owd = sum(dist(pf[i], pf[i + 1]) for i in range(len(pf) - 1)) / C
            owr = sum(dist(pr[i], pr[i + 1]) for i in range(len(pr) - 1)) / C
            changed = int(prev is not None and prev != (pf, pr))
            prev = (pf, pr)
            fo.write("%.1f,%d,%d,%.3f,%d,%s\n" % (t_ns / 1e9, len(pf) - 1, len(pr) - 1, (owd + owr) * 1000,
                                                   changed, "-".join(map(str, pf))))


if __name__ == "__main__":
    main()
