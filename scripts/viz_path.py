#!/usr/bin/env python3
"""Animated globe view of the constellation and the path between two ground stations.

Writes one HTML file. Open it in a web browser (double-click; internet connection needed for the
plotting library, no account needed). Play/Pause and the time slider are at the bottom; drag the
globe to rotate it, scroll to zoom. The box at the top left shows the current path and its RTT.

Usage:
  viz_path.py <state_dir> <src> <dst> [--from S] [--to S] [--out FILE]
    state_dir   .../state directory made by gen_state.py (e.g. $STATE_EXAMPLE)
    src, dst    ground-station node ids (see <state_dir>/node_ids.txt)
    --from/--to time window in seconds (default 0 to 60, capped at the state's duration)
    --out       output HTML (default: /work/viz/path_<src>_<dst>_<from>-<to>s.html,
                or ./viz/... outside Docker)

Shown: every satellite (small dots), the two ground stations, and the forward path src -> dst
as it is in the forwarding state at every step (100 ms by default). The RTT shown is the
propagation RTT over the forward and reverse paths, identical to scripts/path_truth.py.
Satellites are drawn at their sub-satellite points (550 km altitude is not drawn).
Inspired by Hypatia's satviz (Kassing et al., IMC 2020).
"""
import argparse
import json
import math
import os
import sys
import types

for _m in ["cartopy", "cartopy.crs"]:  # only needed by satgen's plotting helpers
    sys.modules.setdefault(_m, types.ModuleType(_m))
sys.path.insert(0, os.environ.get("SATGENPY", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hypatia", "satgenpy")))
import ephem  # noqa: E402
import satgen  # noqa: E402
from astropy import units as u  # noqa: E402

C = 299792458.0
PLOTLY = "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@4.1.1/plotly.min.js"
MAX_FRAMES = 300       # at most this many animation frames (plus 2 per path change)

def main():
    ap = argparse.ArgumentParser(description="Animated 3D view of the path between two ground stations")
    ap.add_argument("state_dir")
    ap.add_argument("src", type=int)
    ap.add_argument("dst", type=int)
    ap.add_argument("--from", dest="t0", type=float, default=0.0)
    ap.add_argument("--to", dest="t1", type=float, default=60.0)
    ap.add_argument("--out")
    a = ap.parse_args()

    state = a.state_dir
    dyn = sorted(d for d in os.listdir(state) if d.startswith("dynamic_state_"))
    if not dyn:
        sys.exit("No dynamic_state_* directory in %s" % state)
    dyn = dyn[0]
    step_ms = int(dyn.split("_")[2].replace("ms", ""))
    dur_s = int(dyn.split("_for_")[1].rstrip("s"))
    t0, t1 = max(0.0, a.t0), min(a.t1, dur_s)
    if t1 <= t0:
        sys.exit("Empty time window: --from %g --to %g (state duration %d s)" % (a.t0, a.t1, dur_s))

    tles = satgen.read_tles(state + "/tles.txt")
    sats, epoch = tles["satellites"], tles["epoch"]
    nsat = len(sats)
    gss = satgen.read_ground_stations_extended(state + "/ground_stations.txt")
    for n in (a.src, a.dst):
        if not nsat <= n < nsat + len(gss):
            sys.exit("Node %d is not a ground station (ground stations are %d..%d)" % (n, nsat, nsat + len(gss) - 1))
    gs_pos = {nsat + i: (g["cartesian_x"], g["cartesian_y"], g["cartesian_z"]) for i, g in enumerate(gss)}
    gs_name = {nsat + i: g["name"] for i, g in enumerate(gss)}

    def sat_geo(s, t_s):
        sats[s].compute(ephem.Date((epoch + t_s * u.s).datetime))
        return sats[s].sublat, sats[s].sublong, sats[s].elevation

    # ---- paths at every step (forwarding state files are incremental: replay from t = 0) ----
    def walk(fstate, a_, b_):
        path, cur = [a_], a_
        while cur != b_:
            cur = fstate.get((cur, b_), -1)
            if cur == -1 or len(path) > 500:
                return None
            path.append(cur)
        return path

    steps = []                       # (t_s, forward path, reverse path)
    fstate = {}
    files = sorted(int(f[len("fstate_"):-4]) for f in os.listdir(os.path.join(state, dyn)) if f.startswith("fstate_"))
    for t_ns in files:
        if t_ns / 1e9 >= t1:
            break
        with open(os.path.join(state, dyn, "fstate_%d.txt" % t_ns)) as f:
            for line in f:
                cur, dst, nh = line.strip().split(",")[:3]
                fstate[(int(cur), int(dst))] = int(nh)
        if t_ns / 1e9 + step_ms / 1000 <= t0:
            continue
        steps.append((t_ns / 1e9, walk(fstate, a.src, a.dst), walk(fstate, a.dst, a.src)))

    # propagation RTT (forward + reverse path), computed exactly as scripts/path_truth.py does
    print("Computing path RTTs for %d steps..." % len(steps))
    info = []                        # [t_s, hops, rtt_ms, forward path]
    for t_s, pf, pr in steps:
        if pf is None or pr is None:
            info.append([max(t_s, t0), 0, -1.0, None])
            continue
        date = str(epoch + t_s * u.s)

        def dist(x, y):
            if x >= nsat:
                return satgen.distance_m_ground_station_to_satellite(gss[x - nsat], sats[y], str(epoch), date)
            if y >= nsat:
                return satgen.distance_m_ground_station_to_satellite(gss[y - nsat], sats[x], str(epoch), date)
            return satgen.distance_m_between_satellites(sats[x], sats[y], str(epoch), date)
        d = sum(dist(p[i], p[i + 1]) for p in (pf, pr) for i in range(len(p) - 1))
        info.append([max(t_s, t0), len(pf) - 1, round(d / C * 1000, 3), pf])

    # ---- frames: every FRAME_S, plus the steps right before and at every path change ----
    changes = [round(info[i][0], 1) for i in range(1, len(info)) if info[i][3] != info[i - 1][3]]
    frame_s = max(0.1, math.ceil((t1 - t0) / MAX_FRAMES * 10) / 10)
    ft = set(round(t0 + k * frame_s, 1) for k in range(int((t1 - t0) / frame_s) + 1))
    for c in changes:
        ft.update([round(c - 0.1, 1), c])
    ft = sorted(x for x in ft if t0 <= x < t1 or x == t0)
    step_times = [x[0] for x in info]

    def info_at(t_s):
        k = max(i for i, x in enumerate(step_times) if x <= t_s + 1e-9)
        return info[k]

    print("Computing satellite positions for %d frames..." % len(ft))
    frames = []
    for t_s in ft:
        lat, lon = [], []
        for s in range(nsat):
            la, lo, _ = sat_geo(s, t_s)
            lat.append(round(math.degrees(la), 2))
            lon.append(round(math.degrees(lo), 2))
        _, hops, rtt, path = info_at(t_s)
        frames.append({"t": t_s, "lat": lat, "lon": lon, "hops": hops, "rtt": rtt, "path": path})

    gsd = {n: (float(gss[n - nsat]["latitude_degrees_str"]), float(gss[n - nsat]["longitude_degrees_str"]))
           for n in (a.src, a.dst)}
    # view centre: direction of the sum of the two ground-station position vectors
    x = sum(gs_pos[n][0] for n in gsd); y = sum(gs_pos[n][1] for n in gsd); z = sum(gs_pos[n][2] for n in gsd)
    c_lon, c_lat = math.degrees(math.atan2(y, x)), math.degrees(math.atan2(z, math.hypot(x, y)))
    title = "%s (%d) \u2192 %s (%d), t = %g\u2013%g s" % (gs_name[a.src], a.src, gs_name[a.dst], a.dst, t0, t1)
    data = {"nsat": nsat, "frames": frames, "changes": changes, "title": title,
            "gs": [[n, gs_name[n], gsd[n][0], gsd[n][1]] for n in (a.src, a.dst)],
            "center": [round(c_lon, 2), round(c_lat, 2)]}

    html = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>%(title)s</title>
<script src="%(plotly)s"></script>
<style>html,body{margin:0;height:100%%;font-family:sans-serif}#g{width:100%%;height:100vh}</style>
</head><body><div id="g"></div>
<script>
const D = %(data)s;
const GS = {}; D.gs.forEach(g => GS[g[0]] = [g[2], g[3]]);
function pos(f, n) { return n >= D.nsat ? GS[n] : [f.lat[n], f.lon[n]]; }
function traces(f) {
  const p = f.path || [];
  return [
    {lat: f.lat, lon: f.lon},
    {lat: p.map(n => pos(f, n)[0]), lon: p.map(n => pos(f, n)[1])}
  ];
}
function info(f) {
  return "<b>" + D.title + "</b><br>t = " + f.t.toFixed(1) + " s<br>" +
    (f.hops > 0 ? "hops " + f.hops + ", propagation RTT " + f.rtt.toFixed(2) + " ms" : "no path") +
    "<br>path changes (s): " + (D.changes.length ? D.changes.join(", ") : "none");
}
function annot(f) {
  return [{text: info(f), xref: "paper", yref: "paper", x: 0, y: 1, xanchor: "left", yanchor: "top",
           showarrow: false, align: "left", bgcolor: "rgba(255,255,255,0.9)", font: {family: "monospace", size: 13}}];
}
const f0 = D.frames[0], t0 = traces(f0);
const data = [
  {type: "scattergeo", mode: "markers", lat: t0[0].lat, lon: t0[0].lon, name: "satellites",
   marker: {size: 3, color: "rgba(90,90,90,0.55)"}, hoverinfo: "skip"},
  {type: "scattergeo", mode: "lines+markers", lat: t0[1].lat, lon: t0[1].lon, name: "path",
   line: {width: 3, color: "rgb(230,120,0)"}, marker: {size: 6, color: "rgb(230,120,0)"}},
  {type: "scattergeo", mode: "markers+text", lat: D.gs.map(g => g[2]), lon: D.gs.map(g => g[3]),
   text: D.gs.map(g => g[1] + " (" + g[0] + ")"), textposition: "top center", name: "ground stations",
   marker: {size: 11, color: "rgb(220,30,30)", line: {width: 2, color: "white"}}}
];
const frames = D.frames.map(f => { const t = traces(f);
  return {name: f.t.toFixed(1), traces: [0, 1],
          data: [{lat: t[0].lat, lon: t[0].lon}, {lat: t[1].lat, lon: t[1].lon}],
          layout: {annotations: annot(f)}}; });
const anim = {mode: "immediate", frame: {duration: 0, redraw: true}, transition: {duration: 0}};
const layout = {
  margin: {l: 0, r: 0, t: 0, b: 0}, showlegend: false, annotations: annot(f0),
  geo: {projection: {type: "orthographic", rotation: {lon: D.center[0], lat: D.center[1]}},
        showland: true, landcolor: "rgb(232,228,214)", showocean: true, oceancolor: "rgb(208,227,242)",
        showcountries: true, countrycolor: "rgb(170,170,170)", coastlinecolor: "rgb(120,120,120)",
        lataxis: {showgrid: true, gridcolor: "rgb(215,215,215)"}, lonaxis: {showgrid: true, gridcolor: "rgb(215,215,215)"}},
  updatemenus: [{type: "buttons", direction: "left", x: 0.02, y: 0.02, xanchor: "left", yanchor: "bottom",
    buttons: [{label: "\u25b6 Play", method: "animate",
               args: [null, {mode: "immediate", fromcurrent: true, frame: {duration: 150, redraw: true}, transition: {duration: 0}}]},
              {label: "\u275a\u275a Pause", method: "animate", args: [[null], anim]}]}],
  sliders: [{x: 0.2, len: 0.78, y: 0.02, yanchor: "bottom", currentvalue: {prefix: "t = ", suffix: " s"},
    steps: D.frames.map(f => ({label: f.t.toFixed(1), method: "animate", args: [[f.t.toFixed(1)], anim]}))}]
};
Plotly.newPlot("g", data, layout, {responsive: true}).then(g => Plotly.addFrames(g, frames));
</script></body></html>
""" % {"title": title, "plotly": PLOTLY, "data": json.dumps(data, separators=(",", ":"))}

    out = a.out or os.path.join("/work" if os.path.isdir("/work") else ".", "viz",
                                "path_%d_%d_%g-%gs.html" % (a.src, a.dst, t0, t1))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w") as f:
        f.write(html)
    print("Wrote %s  (%.1f MB)" % (out, os.path.getsize(out) / 1e6))
    print("Path changes in this window (s):", ", ".join(map(str, changes)) or "none")


if __name__ == "__main__":
    main()
