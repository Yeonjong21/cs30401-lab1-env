#!/bin/bash
# Environment check: ping between two ground stations for 100 s, compared with the
# propagation RTT computed independently from the satellite positions.
# Expected on the example state (Seoul-London): median about 0.67 ms, i.e. ns-3 reproduces the
# geometric RTT up to per-hop transmission delay of the ping packets.
# Usage: check_env.sh [state_dir] [src] [dst]
#   default: example state; src/dst default to the first two ground stations in state/node_ids.txt
#   (state must be at least 100 s long). About 1-2 min.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
STATE=$(cd "${1:-${STATE_EXAMPLE:-$HERE/../data/seoul_london/state}}" && pwd)
GS=($(grep -v '^#' "$STATE/node_ids.txt" | cut -d, -f1))
SRC=${2:-${GS[0]}}; DST=${3:-${GS[1]}}
: "${NS3_DIR:?set NS3_DIR to your ns-3 directory}"
DYN=$(cd "$STATE" && ls -d dynamic_state_*ms_for_*s | head -1)
TRUTH="$STATE/../path_truth_${DYN##*_for_}.csv"
[ "$SRC $DST" = "${GS[0]} ${GS[1]}" ] || TRUTH="${TRUTH%.csv}_${SRC}_${DST}.csv"
if [ ! -f "$TRUTH" ]; then
  echo "Computing propagation RTT from satellite positions -> $TRUTH (a few minutes)"
  python3 "$HERE/path_truth.py" "$STATE" "$DYN" "$SRC" "$DST" "$TRUTH"
fi
R=$(mktemp -d)/check_env
"$HERE/make_run.sh" "$R" "$STATE" TcpNewReno 10 100 100 "$SRC" "$DST" > /dev/null
sed -i '/tcp_flow/d; s/enable_tcp_flow_scheduler=true/enable_tcp_flow_scheduler=false/' "$R/config_ns3.properties"
printf 'enable_pingmesh_scheduler=true\npingmesh_interval_ns=10000000\npingmesh_endpoint_pairs=set(%d->%d)\n' "$SRC" "$DST" >> "$R/config_ns3.properties"
echo "Running ns-3 (100 s simulated)..."
"$HERE/run_sim.sh" "$R" > /dev/null
python3 "$HERE/validate_ping.py" "$TRUTH" "$R"
rm -rf "$(dirname "$R")"
