#!/bin/bash
# Write every change you made to the ns-3 tree (including new files under src/, contrib/, scratch/)
# as one patch against the course baseline. Put this patch in your submission's code/ directory.
# Usage: make_patch.sh [output_file]        (default: /work/ns3.patch if /work exists, else ./ns3.patch)
# Apply on a fresh environment:  cd $NS3_DIR && git apply /path/to/ns3.patch && ./ns3 build
set -e
: "${NS3_DIR:?set NS3_DIR to your ns-3 directory}"
DEF=./ns3.patch; [ -d /work ] && DEF=/work/ns3.patch
OUT=$(realpath "${1:-$DEF}")
cd "$NS3_DIR"
git rev-parse -q --verify cs30401-base >/dev/null || { echo "No cs30401-base tag in $NS3_DIR (was it set up with setup_ns3.sh?)"; exit 1; }
git add -A
git diff --cached --binary cs30401-base > "$OUT"
echo "Wrote $OUT"; git diff --cached --stat cs30401-base | tail -n 20
