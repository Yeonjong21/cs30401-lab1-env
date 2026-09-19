"""Generate Hypatia satellite-network state for a set of ground stations (default: Seoul, London).

Uses Hypatia's satgenpy unchanged, except that the all-pairs shortest-path
backend (networkx.floyd_warshall_numpy, O(n^3) in Python/numpy) is swapped for
scipy's Dijkstra, which returns the identical distance matrix much faster.

Usage:
  python3 gen_state.py <out_dir>                                   # Seoul + London, 200 s, 100 ms steps
  python3 gen_state.py <out_dir> --gs "Tokyo,35.68,139.69" --gs "Sydney,-33.87,151.21" --gs "Seoul,37.57,126.98"
  python3 gen_state.py <out_dir> --gs-file my_stations.csv          # one "name,lat,lon" per line
  python3 gen_state.py <out_dir> --orbits 36 --sats-per-orbit 22       # fewer satellites (default 72 x 22 = 1584)
Options: --duration <s> (200)  --step-ms <ms> (100)  --threads <n> (1)
         --orbits <n> (72)  --sats-per-orbit <n> (22)

Output: <out_dir>/state/  (tles.txt, isls.txt, ground_stations.txt, ..., dynamic_state_<step>ms_for_<dur>s/)
Node ids: satellites 0..N-1 (N = orbits x sats-per-orbit; satellite id = orbit * sats-per-orbit + index),
          then the ground stations in the order given: N, N+1, N+2, ...  (default N = 1584)
          (also written to <out_dir>/state/node_ids.txt)
Every ground station can reach every other one; routes use ISLs only (no ground relays).
"""
import math
import os
import sys

import networkx as nx
import numpy as np
from scipy.sparse.csgraph import shortest_path

import types
for _m in ["cartopy", "cartopy.crs"]:  # only needed by satgen's plotting helpers
    sys.modules.setdefault(_m, types.ModuleType(_m))
sys.path.insert(0, os.environ.get("SATGENPY", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hypatia", "satgenpy")))
import satgen  # noqa: E402


def _apsp(g, weight="weight"):
    m = nx.to_scipy_sparse_array(g, nodelist=sorted(g.nodes()), weight=weight, format="csr")
    return shortest_path(m, method="D", directed=False)


nx.floyd_warshall_numpy = _apsp  # used by satgen.dynamic_state.fstate_calculation

# Same math as satgen.distance_tools.distance_m_between_satellites, but each satellite's
# (ra, dec, range) is computed once per time step instead of once per ISL endpoint.
import ephem  # noqa: E402
import satgen.dynamic_state.generate_dynamic_state as _gds  # noqa: E402
_cache = {"key": None, "pos": {}}


def _fast_isl_distance(sat1, sat2, epoch_str, date_str):
    key = (epoch_str, date_str)
    if _cache["key"] != key:
        _cache["key"], _cache["pos"] = key, {}
    pos = _cache["pos"]
    for s in (sat1, sat2):
        if id(s) not in pos:
            obs = ephem.Observer()
            obs.epoch, obs.date, obs.lat, obs.lon, obs.elevation = epoch_str, date_str, 0, 0, 0
            s.compute(obs)
            pos[id(s)] = (s.a_ra, s.a_dec, s.range)
    (ra1, de1, r1), (ra2, de2, r2) = pos[id(sat1)], pos[id(sat2)]
    ang = float(repr(ephem.separation((ra1, de1), (ra2, de2))))
    return math.sqrt(r1 ** 2 + r2 ** 2 - 2 * r1 * r2 * math.cos(ang))


_gds.distance_m_between_satellites = _fast_isl_distance

# ---- Starlink shell 1 (as used in Hypatia, IMC'20; from SpaceX FCC filing) ----
EARTH_RADIUS = 6378135.0
NICE_NAME = "Starlink-550"
ECCENTRICITY = 0.0000001
ARG_OF_PERIGEE_DEGREE = 0.0
PHASE_DIFF = True
MEAN_MOTION_REV_PER_DAY = 15.19
ALTITUDE_M = 550000
SATELLITE_CONE_RADIUS_M = 940700          # => min. elevation angle 25 deg
MAX_GSL_LENGTH_M = math.sqrt(SATELLITE_CONE_RADIUS_M ** 2 + ALTITUDE_M ** 2)
MAX_ISL_LENGTH_M = 2 * math.sqrt((EARTH_RADIUS + ALTITUDE_M) ** 2 - (EARTH_RADIUS + 80000) ** 2)
NUM_ORBS = 72               # default; change with --orbits
NUM_SATS_PER_ORB = 22       # default; change with --sats-per-orbit
# Altitude, inclination, mean motion and min. elevation above are those of Starlink shell 1.
# To change them, edit a copy of this file and keep them consistent (mean motion follows from altitude).
INCLINATION_DEGREE = 53


DEFAULT_GS = ["Seoul,37.56826,126.97783", "London,51.50853,-0.12574"]


def parse_args():
    import argparse
    ap = argparse.ArgumentParser(description="Generate Hypatia state (Starlink shell 1) for given ground stations")
    ap.add_argument("out_dir")
    ap.add_argument("--duration", type=int, default=200, help="seconds (default 200)")
    ap.add_argument("--step-ms", type=int, default=100, help="forwarding-state interval in ms (default 100)")
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--orbits", type=int, default=NUM_ORBS, help="number of orbital planes (default 72)")
    ap.add_argument("--sats-per-orbit", type=int, default=NUM_SATS_PER_ORB, help="satellites per plane (default 22)")
    ap.add_argument("--gs", action="append", help='ground station "name,lat,lon" (repeatable)')
    ap.add_argument("--gs-file", help='file with one "name,lat,lon" per line')
    a = ap.parse_args()
    specs = list(a.gs or [])
    if a.gs_file:
        specs += [l.strip() for l in open(a.gs_file) if l.strip() and not l.startswith("#")]
    if not specs:
        specs = DEFAULT_GS
    gss = []
    for x in specs:
        parts = [p.strip() for p in x.split(",")]
        if len(parts) != 3:
            ap.error('ground station must be "name,lat,lon": %r' % x)
        float(parts[1]), float(parts[2])
        gss.append(parts)
    if len(gss) < 2:
        ap.error("need at least 2 ground stations")
    if a.orbits < 3 or a.sats_per_orbit < 3:
        ap.error("+grid ISLs need at least 3 orbits and 3 satellites per orbit")
    return a.out_dir, a.duration, a.step_ms, a.threads, gss, a.orbits, a.sats_per_orbit


def main():
    global NUM_ORBS, NUM_SATS_PER_ORB
    out_root, duration_s, step_ms, threads, gss, NUM_ORBS, NUM_SATS_PER_ORB = parse_args()
    name = "state"
    d = os.path.join(out_root, name)
    os.makedirs(d, exist_ok=True)

    basic = os.path.join(d, "ground_stations.basic.txt")
    with open(basic, "w") as f:
        for gid, (n, lat, lon) in enumerate(gss):
            f.write("%d,%s,%s,%s,0\n" % (gid, n, lat, lon))
    satgen.extend_ground_stations(basic, d + "/ground_stations.txt")
    satgen.generate_tles_from_scratch_manual(
        d + "/tles.txt", NICE_NAME, NUM_ORBS, NUM_SATS_PER_ORB, PHASE_DIFF,
        INCLINATION_DEGREE, ECCENTRICITY, ARG_OF_PERIGEE_DEGREE, MEAN_MOTION_REV_PER_DAY)
    satgen.generate_plus_grid_isls(d + "/isls.txt", NUM_ORBS, NUM_SATS_PER_ORB, isl_shift=0, idx_offset=0)
    satgen.generate_description(d + "/description.txt", MAX_GSL_LENGTH_M, MAX_ISL_LENGTH_M)
    satgen.generate_simple_gsl_interfaces_info(
        d + "/gsl_interfaces_info.txt", NUM_ORBS * NUM_SATS_PER_ORB, len(gss), 1, 1, 1, 1)
    nsat = NUM_ORBS * NUM_SATS_PER_ORB
    with open(d + "/node_ids.txt", "w") as f:
        f.write("# node_id,name,lat,lon   (satellites are 0..%d)\n" % (nsat - 1))
        for i, (n, lat, lon) in enumerate(gss):
            f.write("%d,%s,%s,%s\n" % (nsat + i, n, lat, lon))
    print("Constellation: %d orbits x %d satellites = %d satellites (node ids 0..%d)"
          % (NUM_ORBS, NUM_SATS_PER_ORB, nsat, nsat - 1))
    print("Ground station node ids:", ", ".join("%s=%d" % (g[0], nsat + i) for i, g in enumerate(gss)))
    satgen.help_dynamic_state(out_root, threads, name, step_ms, duration_s,
                              MAX_GSL_LENGTH_M, MAX_ISL_LENGTH_M,
                              "algorithm_free_one_only_over_isls", True)


if __name__ == "__main__":
    main()
