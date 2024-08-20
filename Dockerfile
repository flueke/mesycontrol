# syntax=docker/dockerfile:1.5
# vim:ft=dockerfile

# Dockerfile for building mesycontrol_server and a frozen/binary version of
# mesycontrol_script_runner.

# Image creation:
#   docker build  -f ./Dockerfile.debian-stable . -t mesycontrol:latest

# Running the server:
#   docker run --rm mesycontrol:latest /dev/ttyUSB0

# Using the script runner:

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND="noninteractive"
ENV TZ="Etc/UTC"

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates build-essential git cmake python3-venv \
    libboost-all-dev libprotobuf-dev protobuf-compiler \
    libglib2.0-0 libgl1

COPY . /mesycontrol-source

# Use pip to install the python client package, its dependencies and
# pyinstaller.
RUN python3 -m venv /mesycontrol-venv
ENV PATH="/mesycontrol-venv/bin:$PATH"
RUN python3 -m pip install --upgrade pip
WORKDIR /mesycontrol-source/src/client
RUN --mount=type=cache,target=/root/.cache \
    pip3 install . pyinstaller

RUN pip3 list

# Run cmake to build both the server and frozen client packages.
WORKDIR /mesycontrol-build
RUN cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/mesycontrol \
    -DMESYCONTROL_BUILD_CLIENT=ON /mesycontrol-source \
    && make -j && make install

# Try to start the server and import the mesycontrol python package.
ENV PATH="/mesycontrol/bin:$PATH"
WORKDIR /mesycontrol
RUN ./bin/mesycontrol_server --help
RUN python3 -c 'import mesycontrol'
RUN python3 -c 'from mesycontrol.mesycontrol_script_runner import script_runner_main; script_runner_main()'

# Default entrypoint is the server binary.
ENTRYPOINT ["/mesycontrol/bin/mesycontrol_server"]
