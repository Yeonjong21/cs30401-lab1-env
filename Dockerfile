# CS30401 Lab 1 environment: ns-3.48 + Hypatia LEO modules (ported) + satgenpy + example state
#
# Build:  docker build -t cs30401-lab1:dev .
# Run:    see README.md ("Option A: Docker")

FROM ubuntu:24.04

ARG NS3_VERSION=3.48
# Pinned Hypatia commit (only satgenpy is used from it)
ARG HYPATIA_COMMIT=0ac531c313eba2335f6344b46347140c3a0d4230
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        g++ python3 python3-venv cmake ninja-build git curl ca-certificates bzip2 \
        less nano vim \
    && rm -rf /var/lib/apt/lists/*

# uv (Python package manager)
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /usr/local/bin/

# ./ns3 refuses to run as root, so everything below runs as the image's default user (uid 1000)
USER ubuntu
WORKDIR /home/ubuntu
ENV LAB=/home/ubuntu/lab
ENV NS3_DIR=/home/ubuntu/ns-${NS3_VERSION}

# ---- Python environment (satgenpy dependencies) ----
COPY --chown=ubuntu:ubuntu pyproject.toml uv.lock ${LAB}/
RUN cd ${LAB} && uv sync --frozen --no-install-project
ENV VIRTUAL_ENV=${LAB}/.venv
ENV PATH=${LAB}/.venv/bin:${PATH}

# ---- satgenpy (from Hypatia) ----
RUN git clone -q https://github.com/snkas/hypatia.git && cd hypatia && git checkout -q ${HYPATIA_COMMIT}
ENV SATGENPY=/home/ubuntu/hypatia/satgenpy

# ---- ns-3 + LEO modules, built with the same script as a manual install ----
RUN curl -fsSL -o ns3.tgz https://codeload.github.com/nsnam/ns-3-dev-git/tar.gz/refs/tags/ns-${NS3_VERSION} \
    && tar xzf ns3.tgz && mv ns-3-dev-git-ns-${NS3_VERSION} ${NS3_DIR} && rm ns3.tgz
COPY --chown=ubuntu:ubuntu ns3/ ${LAB}/ns3/
COPY --chown=ubuntu:ubuntu scripts/ ${LAB}/scripts/
RUN chmod +x ${LAB}/scripts/*.sh ${LAB}/scripts/*.py
RUN bash ${LAB}/scripts/setup_ns3.sh ${NS3_DIR}

# ---- example state ----
COPY --chown=ubuntu:ubuntu data/ ${LAB}/data/
ENV STATE_EXAMPLE=${LAB}/data/seoul_london/state
ENV PATH=${LAB}/scripts:${PATH}

# Welcome message
COPY --chown=ubuntu:ubuntu docker/welcome.txt ${LAB}/welcome.txt
RUN echo 'cat $LAB/welcome.txt' >> /home/ubuntu/.bashrc

# Students keep their own files in /work (a folder shared with the host)
USER root
RUN mkdir -p /work && chown ubuntu:ubuntu /work
USER ubuntu
WORKDIR /work
CMD ["bash"]
