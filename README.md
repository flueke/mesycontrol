# mesycontrol - Remote control for mesytec NIM devices.

See https://mesytec.com/products/mesycontrol/mesycontrol.html for info and downloads.

Binary releases are available from https://mesytec.com/downloads/mesycontrol/ .
This includes a precompiled `mesycontrol_server` binary to run the server on
Raspberry Pi machines.

# Installation

Either use the precompiled binaries from the mesytec website or build the
software yourself according to the steps below.

## Build requirements

These packages are required to build the server binary and install and run the
`mesycontrol_gui` python package via pip:
```
  ca-certificates build-essential git cmake python3 python3-pip
  libboost-all-dev libprotobuf-dev protobuf-compiler libqt5widgets5
```

If you want to create the standalone binary distribution of the client software `pyinstaller` is needed:
  `pip3 install pyinstaller`

## Build steps

mesycontrol uses cmake for the configuration and build steps. If building under
windows msys2 is needed and `-G"MSYS Makefiles"` has to be added to the cmake
command lines.

* server

```shell
   git clone --recurse-submodules https://github.com/flueke/mesycontrol
   mkdir -p mesycontrol/build
   cd mesycontrol/build
   cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=~/local/mesycontrol ..
   make -j install
```

* client python package and gui

```shell
   git clone --recurse-submodules https://github.com/flueke/mesycontrol
   mkdir -p mesycontrol/build
   cd mesycontrol/build
   # The cmake step is required to generate a python file containing version information.
   cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=~/local/mesycontrol ..
   cd ../src/client
   python3 setup.py generate_py_protobufs   # Generate python protbuf code.
   pip3 install --user src/client           # Install for the local user.
```

The above uses pip to fetch dependencies of the client package and install it
for the local user. After the above steps `mesycontrol_gui` should be in your
path and you should be able to `import mesycontrol` from python.

* client binary/exe package

These commands build the server and - with the help of `pyinstaller` - a
deployable binary package of the `mesycontrol_gui` client. These packages are
stand-alone runnable as they contain the Qt and python .so/.dll files.

```shell
   pip3 install pyinstaller
   git clone --recurse-submodules https://github.com/flueke/mesycontrol
   mkdir -p mesycontrol/build
   cd mesycontrol/build
   cmake -DCMAKE_BUILD_TYPE=Release -DMESYCONTROL_BUILD_CLIENT=ON ..
   make -j package
```
