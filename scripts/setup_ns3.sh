#!/bin/bash
# Install the Lab 1 LEO modules into an ns-3 source tree, record a git baseline, and build.
# The Docker image is built with exactly this script, so a manual install gives the same environment.
#
# Usage: bash scripts/setup_ns3.sh <path/to/ns-3.48>
set -e
[ -n "$1" ] || { echo "Usage: bash $0 <path/to/ns-3 source tree>"; exit 1; }
NS3=$(cd "$1" && pwd)
REPO=$(cd "$(dirname "$0")/.." && pwd)
[ -x "$NS3/ns3" ] || { echo "Not an ns-3 source tree: $NS3"; exit 1; }

echo "== Copying LEO modules into $NS3"
cp -r "$REPO/ns3/contrib/." "$NS3/contrib/"
cp -r "$REPO/ns3/scratch/." "$NS3/scratch/"

# ns-3 ignores everything under contrib/ and scratch/ by default.
# Track them, so that `git diff` (and scripts/make_patch.sh) also shows your changes there.
echo "# CS30401: everything under contrib/ is tracked" > "$NS3/contrib/.gitignore"
echo "# CS30401: everything under scratch/ is tracked" > "$NS3/scratch/.gitignore"

echo "== Recording the baseline (git tag cs30401-base)"
cd "$NS3"
[ -d .git ] || git init -q
if ! git rev-parse -q --verify cs30401-base >/dev/null; then
  git add -A
  git -c user.name=cs30401 -c user.email=cs30401@localhost \
      commit -q -m "ns-3 + CS30401 Lab 1 LEO modules (baseline)"
  git tag cs30401-base
fi

echo "== Configuring and building ns-3 (takes a while on the first build)"
GEN=""; command -v ninja >/dev/null && GEN="-G Ninja"
# release = optimized without -march=native: the binaries run on any CPU of the same
# architecture, and results do not depend on which CPU compiled them.
./ns3 configure --build-profile=release \
    --enable-modules="satellite-network;flow-monitor" \
    --disable-tests --disable-examples $GEN
./ns3 build
echo "== Done. Set NS3_DIR=$NS3"
