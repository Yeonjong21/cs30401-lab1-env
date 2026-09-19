#!/bin/bash
# Create one Hypatia run directory: config_ns3.properties + schedule.csv.
#
# Usage: make_run.sh <run_dir> <state_dir> <cc> <rate_mbps> <queue_pkts> <sim_s> <src> <dst>
#   state_dir   the .../state directory made by gen_state.py (e.g. $STATE_EXAMPLE)
#   cc          ns-3 TCP class name: TcpNewReno, TcpCubic, TcpBbr, TcpVegas, ...
#   rate_mbps   data rate of every ISL and GSL (Mbit/s)
#   queue_pkts  device queue size of every ISL and GSL (packets)
#   sim_s       simulated time (s); must not exceed the duration of the state (200 s for the example)
#   src dst     ground-station node ids (see <state_dir>/node_ids.txt)
#
# One bulk TCP flow src -> dst starts at t = 0.
# Several flows: set FLOWS instead (src/dst arguments are then ignored), e.g.
#   FLOWS="1584>1585,1586>1585" make_run.sh ...     (flow ids 0, 1, ... in that order)
# Pacing is enabled automatically for TcpBbr; override with PACING=true|false.
#
# The generated config_ns3.properties is a plain text file: edit it for anything not covered here.
# Run the simulation with scripts/run_sim.sh <run_dir>.
set -e
[ $# -eq 8 ] || { sed -n '2,19p' "$0"; exit 1; }
RUN=$1; STATE=$2; CC=$3; RATE=$4; Q=$5; SIM=$6; SRC=$7; DST=$8
[ -f "$STATE/tles.txt" ] || { echo "Not a state directory (no tles.txt): $STATE"; exit 1; }
DYN=$(cd "$STATE" && ls -d dynamic_state_*ms_for_*s 2>/dev/null | head -1)
[ -n "$DYN" ] || { echo "No dynamic_state_* directory in $STATE"; exit 1; }
DUR=${DYN##*_for_}; DUR=${DUR%s}
[ "$SIM" -le "$DUR" ] || { echo "sim_s=$SIM exceeds the state duration ($DUR s)"; exit 1; }
STEP_MS=${DYN#dynamic_state_}; STEP_MS=${STEP_MS%%ms_*}
if [ -z "$PACING" ]; then PACING=false; [ "$CC" = TcpBbr ] && PACING=true; fi

mkdir -p "$RUN"
# Hypatia resolves these paths relative to the run directory
REL=$(realpath --relative-to="$RUN" "$STATE")
if [ -n "$FLOWS" ]; then PAIRS=$(echo "$FLOWS" | tr ',' ' '); else PAIRS="$SRC>$DST"; fi
NF=$(echo $PAIRS | wc -w)
IDS=$(seq -s, 0 $((NF-1)))

cat > "$RUN/config_ns3.properties" <<CFG
simulation_end_time_ns=$((SIM*1000000000))
simulation_seed=123456789
satellite_network_dir="$REL"
satellite_network_routes_dir="$REL/$DYN"
dynamic_state_update_interval_ns=$((STEP_MS*1000000))
isl_data_rate_megabit_per_s=$RATE
gsl_data_rate_megabit_per_s=$RATE
isl_max_queue_size_pkts=$Q
gsl_max_queue_size_pkts=$Q
enable_isl_utilization_tracking=false
tcp_socket_type=$CC
tcp_enable_pacing=$PACING
enable_tcp_flow_scheduler=true
tcp_flow_schedule_filename="schedule.csv"
tcp_flow_enable_logging_for_tcp_flow_ids=set($IDS)
CFG

# id,from,to,size_byte,start_ns,additional,metadata   (100 GB = effectively an infinite bulk flow)
: > "$RUN/schedule.csv"
i=0
for p in $PAIRS; do
  echo "$i,${p%%>*},${p##*>},100000000000,$((i*1000000)),," >> "$RUN/schedule.csv"; i=$((i+1))
done
echo "Run directory ready: $RUN  ($NF flow(s), $CC, $RATE Mbit/s, queue $Q pkts, $SIM s)"
