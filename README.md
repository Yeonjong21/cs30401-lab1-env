# CS30401 Lab 1 Environment: TCP over a LEO Satellite Network

This repository provides the simulation environment for Lab 1: **ns-3.48** with the
**Hypatia** LEO satellite modules [1] ported to it, a generator for the constellation state,
and an example state (Seoul–London). What you study in it, and how, is up to your team.

There are two ways to set it up. Both give the same environment.

| | Option A: Docker (recommended) | Option B: Manual install |
|---|---|---|
| Works on | Windows, macOS (Intel / Apple Silicon), Linux | Ubuntu 22.04 / 24.04, or WSL2 |
| Setup time | download once (a few GB), no build | about 10–60 min (building ns-3) |
| TAs check reproducibility with | ✔ this image | — |

TAs regenerate your results with the Docker image. If you use Option B, make sure your
results also reproduce in the image before you submit.

---

## 1. What the environment models

| Item | Setting | Basis |
|---|---|---|
| Constellation | Default: Starlink shell 1, 72 orbits × 22 satellites = 1584, altitude 550 km, inclination 53°, min. elevation angle 25°. The number of orbits and satellites per orbit can be changed (§4.1) | Hypatia [1], from SpaceX's FCC filing |
| Inter-satellite links (ISL) | +Grid: each satellite links to 2 neighbors in its orbit and 1 in each adjacent orbit | Hypatia [1] |
| Ground stations | Any number, anywhere (default: Seoul, London). Traffic between ground stations goes over ISLs only (no ground relays) | |
| Routing | Shortest path by distance, recomputed every 100 ms from satellite positions | Hypatia [1] |
| Links | Point-to-point; propagation delay follows the actual distance at every moment. All ISLs and GSLs share one data rate and one drop-tail device queue size (packets). No queueing discipline | Hypatia [1] |

How the model behaves, so that you can decide what your study needs:

- At every 100 ms routing update, forwarding tables and each ground station's satellite switch
  instantly. There is no link-layer handover procedure, outage, or bit error.
- Packets are lost only when a device queue overflows, or when no satellite is visible.
- Anything else your study requires, you add yourself (and justify, see the handout).

TCP settings applied by Hypatia before your flows start (printed at the top of every run):
initial cwnd 10 segments, segment size 1380 bytes, send/receive buffers 32 MiB, SACK, timestamps,
window scaling on, clock granularity 1 ns. Everything else is the ns-3.48 default.
These live in `contrib/basic-sim/helper/core/tcp-optimizer.cc`; you can override any of them in
`scratch/main_satnet/main_satnet.cc` with `Config::SetDefault(...)` after `TcpOptimizer::OptimizeBasic`.

---

## 2. Option A: Docker

### 2.0 Docker in five minutes

Docker runs a prepared Linux environment on your computer, the same on every OS.

| Term | Meaning here |
|---|---|
| **image** | The packaged environment: Ubuntu + ns-3.48 (built) + LEO modules + scripts. Read-only. You download it once with `docker pull`. |
| **container** | A running copy of the image. You work inside it. With `--rm` it is deleted when you `exit`. |
| **volume** | Storage managed by Docker that survives containers. We keep your ns-3 tree in the volume `cs30401-ns3`. |
| **bind mount** | A folder of your computer made visible inside the container. Your lab folder appears as `/work`. |
| **tag** | The version after `:` in the image name (`2026f-v1`). Report it in your README. |

The command in §2.3, option by option:

| Option | Meaning |
|---|---|
| `docker run` | Start a new container from an image. |
| `-it` | Interactive terminal: you get a shell inside the container. |
| `--rm` | Delete the container on `exit` (your data is in `/work` and in the volume, not in the container). |
| `--name lab1` | Name the container, so that other commands can refer to it. |
| `-v cs30401-ns3:/home/ubuntu/ns-3.48` | Keep ns-3 (your edits and builds) in the volume `cs30401-ns3`. |
| `-v "$PWD":/work` | Show the current folder of your computer as `/work`. |
| `ghcr.io/yeonjong21/cs30401-lab1:2026f-v1` | The image and its tag. |

Other commands you may need (run them on your computer, not inside the container):

| Command | What it does |
|---|---|
| `docker exec -it lab1 bash` | Open a second terminal in the running container `lab1`. |
| `docker ps` | List running containers. |
| `docker stop lab1` | Stop a container (e.g. if its terminal was closed). |
| `docker images` | List downloaded images. |
| `docker volume ls` | List volumes. |
| `docker volume rm cs30401-ns3` | Delete your ns-3 volume (a clean ns-3 on next start; save a patch first, §5.3). |
| `docker system df` | Disk space used by Docker. |

### 2.1 Install Docker (once)

- **Windows 10/11, macOS**: Docker Desktop — https://docs.docker.com/desktop/
  (Windows: if Docker Desktop reports that virtualization is disabled, enable it in the BIOS/UEFI.)
- **Linux**: Docker Engine — https://docs.docker.com/engine/install/

Check: `docker run --rm hello-world` prints "Hello from Docker!".

### 2.2 Download the image (once)

```bash
docker pull ghcr.io/yeonjong21/cs30401-lab1:2026f-v1
```

The same command works on Intel/AMD and Apple Silicon machines.

### 2.3 Start the environment

Make a folder for your lab work, open a terminal **in that folder**, and run:

macOS / Linux / WSL:
```bash
docker run -it --rm --name lab1 \
  -v cs30401-ns3:/home/ubuntu/ns-3.48 \
  -v "$PWD":/work \
  ghcr.io/yeonjong21/cs30401-lab1:2026f-v1
```

Windows PowerShell (one line):
```powershell
docker run -it --rm --name lab1 -v cs30401-ns3:/home/ubuntu/ns-3.48 -v "${PWD}:/work" ghcr.io/yeonjong21/cs30401-lab1:2026f-v1
```

You are now in a Linux shell inside the container. Type `exit` to leave.
A second terminal into the same container: `docker exec -it lab1 bash`.

### 2.4 What is kept when you exit

| Location in the container | Kept? | |
|---|---|---|
| `/work` | ✔ | This *is* your folder on your computer. Keep code, states, and results here. |
| `$NS3_DIR` (`/home/ubuntu/ns-3.48`) | ✔ | Stored in the Docker volume `cs30401-ns3`. Your changes to ns-3 and its build survive. |
| everything else (`$LAB`, `~`, installed packages) | ✘ | Reset every time the container starts. |

The first start copies ns-3 from the image into the volume `cs30401-ns3` (a few seconds).
To go back to a clean ns-3, save your changes first (§5.3), then `docker volume rm cs30401-ns3`.

### 2.5 Check the environment (about 1–2 min)

Inside the container:
```bash
check_env.sh
```
It sends pings Seoul → London for 100 simulated seconds and compares their RTT with the
propagation RTT computed independently from satellite positions. The last line should read about
`median 0.672` ms (per-hop transmission delay of the ping packets).

---

## 3. Option B: Manual install

Tested on Ubuntu 24.04 and 22.04 (also inside WSL2). On WSL2, work under your Linux home
directory (`~`), not under `/mnt/c/`.

```bash
# 1. System packages
sudo apt update
sudo apt install -y g++ python3 python3-venv git curl bzip2 cmake ninja-build

# 2. uv (Python package manager); open a new terminal afterwards
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Ubuntu 22.04 only: its cmake (3.22) is too old for ns-3.48 (needs 3.25+)
uv tool install cmake && cmake --version

# 4. This repository, and Hypatia's satgenpy (pinned version) inside it
mkdir -p ~/cs30401 && cd ~/cs30401
git clone https://github.com/yeonjong21/cs30401-lab1-env.git lab
git clone https://github.com/snkas/hypatia.git lab/hypatia
git -C lab/hypatia checkout 0ac531c313eba2335f6344b46347140c3a0d4230

# 5. ns-3.48 source (same source as the Docker image)
curl -L -o ns-3.48.tar.gz https://codeload.github.com/nsnam/ns-3-dev-git/tar.gz/refs/tags/ns-3.48
tar xzf ns-3.48.tar.gz && mv ns-3-dev-git-ns-3.48 ns-3.48

# 6. Install the LEO modules into ns-3 and build (10-60 min depending on your CPU)
bash lab/scripts/setup_ns3.sh ~/cs30401/ns-3.48

# 7. Python packages for satgenpy and the scripts
cd ~/cs30401/lab && uv sync --frozen
```

Then add these lines to `~/.bashrc` (they set up what the Docker image sets up for you) and open
a new terminal:

```bash
export NS3_DIR=~/cs30401/ns-3.48
export LAB=~/cs30401/lab
export STATE_EXAMPLE=$LAB/data/seoul_london/state
export PATH=$LAB/scripts:$PATH
source $LAB/.venv/bin/activate
```

Check the environment with `check_env.sh` as in §2.5.

`setup_ns3.sh` does exactly what the Docker image build does: copy `ns3/contrib` and
`ns3/scratch` into ns-3, record a git baseline (tag `cs30401-base`, used in §5.3), and build with
`./ns3 configure --build-profile=release --enable-modules="satellite-network;flow-monitor"`.
(`release` is `optimized` without `-march=native`, so binaries and results do not depend on the CPU
that compiled them.)

---

## 4. Using the environment

From here on, commands are the same for Docker and manual installs.

### 4.1 Constellation state

A simulation needs a *state*: satellite orbits, ISLs, ground stations, and the forwarding tables
for every 100 ms step. The example state is at `$STATE_EXAMPLE` (Seoul = node 1584,
London = node 1585, 200 s). To use other ground stations or a longer time span:

```bash
python3 $LAB/scripts/gen_state.py /work/mystate --threads 4 --duration 200 \
    --gs "Seoul,37.56826,126.97783" --gs "London,51.50853,-0.12574" --gs "Tokyo,35.6895,139.69171"
```

- Number of satellites: `--orbits` (default 72) and `--sats-per-orbit` (default 22), e.g.
  `--orbits 36 --sats-per-orbit 22` for half the planes. Altitude, inclination, and minimum
  elevation stay those of Starlink shell 1; to change them, edit the constants in a copy of
  `gen_state.py` and keep them consistent (the mean motion follows from the altitude).
  With fewer satellites, a ground station may at times see no satellite; packets are then dropped.
- Node ids: with N satellites, satellites are 0 … N−1 (satellite id = orbit × sats-per-orbit +
  index in orbit) and ground stations follow in the order given: N, N+1, … For the default
  N = 1584 that is 1584, 1585, 1586, … Always check `state/node_ids.txt`.
- Many stations: `--gs-file stations.txt` with one `name,lat,lon` per line.
- Time: about 25 min per 200 s of state on one thread for 1584 satellites; `--threads` scales it down.
- The state is written to `/work/mystate/state/`; use that path below.

(Manual install: replace `/work/...` with any directory of yours; `viz_path.py` then writes to `./viz/`.)

### 4.2 One simulation

```bash
make_run.sh /work/runs/r1 $STATE_EXAMPLE TcpCubic 100 1000 60 1584 1585
#           run_dir       state          cc       Mbit/s  queue(pkts)  sim(s)  src  dst
run_sim.sh  /work/runs/r1
```

- `make_run.sh` writes `config_ns3.properties` and `schedule.csv` into the run directory:
  one bulk TCP flow src → dst from t = 0, every ISL/GSL at the given rate and queue size.
  Several flows: `FLOWS="1584>1585,1586>1585" make_run.sh ...` (flow ids 0, 1, …).
- Both files are plain text. Edit them for anything `make_run.sh` does not cover
  (flow sizes and start times in `schedule.csv`, seed, …). The format is documented in
  `$NS3_DIR/contrib/basic-sim/doc/`.
- `run_sim.sh` calls `./ns3 run`, so any change you made to ns-3 is rebuilt first.
- Simulated time must not exceed the state's duration. Wall-clock time grows with
  data rate × simulated time (roughly minutes for 100 Mbit/s × 60 s).
- `TcpBbr` gets pacing enabled automatically (`tcp_enable_pacing=true` in the config).

### 4.3 Seeing the constellation and the path

```bash
viz_path.py $STATE_EXAMPLE 1584 1585 --from 20 --to 30
# -> /work/viz/path_1584_1585_20-30s.html
```

Open the HTML file in a web browser on your computer by double-clicking it (Windows: your lab
folder, or `\\wsl$\Ubuntu\home\<user>\...` for a folder inside WSL). It shows a globe with every
satellite, the two ground stations, and the path between them. Play/Pause and the time slider are
at the bottom; drag to rotate the globe, scroll to zoom. The box at the top left shows the time,
hop count, propagation RTT, and the times at which the path changed. Satellites are drawn at the
point on the ground directly below them. Needs an internet connection (the plotting library is
loaded online); no account needed. Works with any state from `gen_state.py`, including other
ground stations or satellite counts. Generating takes about 30 s per 100 frames (at most 300 frames,
plus two per path change); a 200 s window gives a file of about 6 MB.

The same path data as a table: `python3 $LAB/scripts/path_truth.py <state_dir> <dynamic_state_dir> <src> <dst> out.csv`.

### 4.4 Output files (`<run_dir>/logs_ns3/`)

| File | Columns |
|---|---|
| `tcp_flow_<id>_cwnd.csv` | flow id, time (ns), cwnd (byte) — one line per change |
| `tcp_flow_<id>_rtt.csv` | flow id, time (ns), smoothed RTT (ns) — one line per change |
| `tcp_flow_<id>_progress.csv` | flow id, time (ns), bytes acknowledged so far |
| `tcp_flows.csv`, `tcp_flows.txt` | per-flow summary |
| `pingmesh.csv` | ping results (if enabled) |

Analysis and plotting are yours to write. The path and its propagation RTT at every step:
§4.3 (`viz_path.py`, `path_truth.py`).

---

## 5. Modifying things

You may change anything: the scenario, TCP, the satellite modules, the state generator.

### 5.1 Where things are

| To change | Edit | Kept across restarts (Docker) |
|---|---|---|
| Scenario program (what gets installed, traced, logged) | `$NS3_DIR/scratch/main_satnet/main_satnet.cc`, or your own program in `$NS3_DIR/scratch/` | ✔ |
| TCP itself, other ns-3 models | `$NS3_DIR/src/...` (e.g. `src/internet/model/`) | ✔ |
| Satellite network model (links, routing, ground stations) | `$NS3_DIR/contrib/satellite-network/`, `contrib/basic-sim/` | ✔ |
| Constellation or state generation | copy `$LAB/scripts/gen_state.py` to `/work` and edit the copy | ✔ (in `/work`) |
| Course scripts | copy `$LAB/scripts/` to `/work` and edit the copies | ✔ (in `/work`) |

After editing ns-3, `run_sim.sh` rebuilds automatically, or run `cd $NS3_DIR && ./ns3 build`.
To enable more ns-3 modules, re-run `./ns3 configure` with a longer `--enable-modules` list.

### 5.2 Extra Python packages

Docker: packages installed inside the container are lost on exit. Keep a
`requirements.txt` in `/work` and install it after each start:
`uv pip install -r /work/requirements.txt` (a few seconds).
Your submission's `code/requirements.txt` should list them anyway (see the handout).

### 5.3 Saving your ns-3 changes as a patch

The handout asks for a patch file instead of a modified ns-3 tree. One command:

```bash
make_patch.sh            # -> /work/ns3.patch (Docker) or ./ns3.patch
```

It contains every change and every new file in the ns-3 tree relative to the course baseline.
To reproduce from scratch (what the TAs will do):

```bash
cd $NS3_DIR && git apply /path/to/ns3.patch && ./ns3 build
```

Test this once on a clean ns-3 before you submit: in Docker, use a second volume name, e.g.
`-v cs30401-ns3-clean:/home/ubuntu/ns-3.48`.

### 5.4 When a new image version is announced

1. In the old container: `make_patch.sh` (your changes are now in `/work/ns3.patch`).
2. `docker volume rm cs30401-ns3` and `docker pull` the new tag.
3. Start the new image, then `cd $NS3_DIR && git apply /work/ns3.patch && ./ns3 build`.

---

## 6. Reproducibility checklist

- Report the image tag (e.g. `2026f-v1`) and ns-3 version in your README and report.
- Put your run directories' `config_ns3.properties` and `schedule.csv` (or the commands that
  generate them) in `code/`. The random seed is `simulation_seed` in the config.
- If you generated your own state, include the exact `gen_state.py` command. Do not submit the
  state itself (it can be large).

---

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| `permission denied` on `/work` (Linux host) | The container user has uid 1000. If `id -u` on your host is not 1000, run `chmod a+rwx` on your lab folder. |
| `docker: command not found` / cannot connect to the Docker daemon | Start Docker Desktop (or `sudo systemctl start docker` on Linux). |
| Build or run killed without a message | Out of memory. Docker Desktop → Settings → Resources: give it at least 4 GB. |
| `cmake` version error (manual install) | Ubuntu 22.04: step 3 of §3. |
| `NS3_DIR` / `set NS3_DIR` error (manual install) | The `~/.bashrc` lines in §3 are missing, or you did not open a new terminal. |

Questions: Classum, "Lab" tag. Include your OS, the exact command, and the full error message.

---

## References

[1] S. Kassing, D. Bhattacherjee, A. B. Aguas, J. E. Saethre, and A. Singla, "Exploring the
'Internet from space' with Hypatia," *Proceedings of the ACM Internet Measurement Conference
(IMC)*, 2020. https://github.com/snkas/hypatia

See `NOTICE` and `LICENSE` for the origin and license of the included modules.
