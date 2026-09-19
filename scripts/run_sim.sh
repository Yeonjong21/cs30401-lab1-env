#!/bin/bash
# Run main_satnet on a run directory made by make_run.sh.
# `./ns3 run` first rebuilds anything you changed in ns-3, then runs the simulation.
# Output: <run_dir>/logs_ns3/ (see README "Output files"); console output also in <run_dir>/out.txt
# Usage: run_sim.sh <run_dir>
set -e
[ -n "$1" ] || { echo "Usage: $0 <run_dir>"; exit 1; }
: "${NS3_DIR:?set NS3_DIR to your ns-3 directory}"
RUN=$(cd "$1" && pwd)
[ -f "$RUN/config_ns3.properties" ] || { echo "No config_ns3.properties in $RUN"; exit 1; }
cd "$NS3_DIR" && ./ns3 run "main_satnet --run_dir=$RUN" 2>&1 | tee "$RUN/out.txt"
exit ${PIPESTATUS[0]}
