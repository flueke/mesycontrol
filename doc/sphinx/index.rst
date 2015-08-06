.. mesycontrol documentation master file, created by
   sphinx-quickstart on Mon Sep 15 09:48:17 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

*mesycontrol* documentation
===========================

Introduction
------------
*mesycontrol* is a remote control solution for detector readout systems by
mesytec. *mesycontrol* makes use of the mesytec RC bus controllers (MRC-1/MRCC)
to communicate with the actual devices. For user interaction a GUI application
is provided.

Features
^^^^^^^^
* MRC-1/MRCC connectivity via USB, serial port and network.
* Client-server architecture using plain TCP as the transport. This enables the
  graphical frontend to run and operate on machines without direct access to
  the mesytec hardware.
* Storing and loading of single device configurations and complete setups
  (multiple devices and multiple MRCs).
* Tabular view/editing of device memory.
* Custom GUIs for MHV-4, MSCF-16, STM-16 and MCFD-16.
* Polling of frequently changing parameters (e.g. voltage or current)
* Cross-platform: both client and server work on Linux and Windows
* Offline editing: setups can be created/edited without access to the hardware.

Installation and dependencies
-----------------------------
Linux
^^^^^
*mesycontrol* requires the Qt libraries >= 4.8 to be installed on your system.
Also be sure to pick the right archive for your distribution and architecture
as trying to run the 32 bit version of the software on a 64 bit linux
installation will most likely result in errors about missing libraries. 

The installation itself is simple: unpack the tar.bz2 archive and execute the
*mesycontrol_gui* binary to get started:::

  $ tar xf mesycontrol-0.5.tar.bz2
  $ ./mesycontrol-0.5/bin/mesycontrol_gui

Note: so far *mesycontrol* has only been tested on Debian Wheezy, Ubuntu 12.04
and OpenSUSE 12.1 but it should work on other distributions and versions as
long as the C++ and Qt libraries stay binary compatible.

Windows
^^^^^^^
*mesycontrol* does not require any additional dependencies on Windows. Running
the supplied installer and following the wizard should correctly install the
software and create a start menu entry for the GUI application.

Architecture Overview
---------------------
.. image:: architecture.png

*mesycontrol* is divided into two parts: *mesycontrol_server* handling MRC
connectivity and communication, and the client part (*mesycontrol_gui*)
connecting to running server processes via TCP.

The GUI client will transparently spawn its own server process if the user
requests a MRC connection via serial port or USB.

In case the client PC has no direct (USB, Serial) connection to an MRC-1/MRCC
the server can be run stand-alone on a machine with direct access to the
hardware. The GUI client then connects via the network to the remotely running
server process.

The client supports connections to multiple servers and is thus able to control
multiple MRC-1/MRCCs.

Using mesycontrol
-----------------

GUI overview
^^^^^^^^^^^^
.. image:: treeview-unlinked.png
   :width: 12cm

The GUI shows hardware and config trees side-by-side. On the left side active
MRC connections and their connected devices are shown. On the right side the
currently opened setup with its MRC and device configurations is displayed.

At startup the two sides will not be linked together. This means hardware and
setup can be separately edited without affecting each other.

Using the *link mode* button in the center of the tree view **linked-mode** can
be activated. In this mode the hardware and setup trees are compared against
each other, differences and conflicts are highlighted and devices missing on
either side are also shown. In linked-mode it is possible to have changes to
device parameters apply to both the hardware and the config side keeping both
trees in sync.

.. image:: treeview-linked.png
   :width: 12cm

Devices with a red background have conflicting device types (their IDCs don't
match). A green background means hardware and config parameters are equal. No
background color indicates that the hardware vs. config state is unknown
meaning hardware parameters have not been read yet.

Using the arrow buttons on the center bar device state can be copied from
hardware to config and vice-versa. Pressing the checkmark icon will fetch any
missing parameters from the hardware and compare them against the
configuration.

Device GUIs
^^^^^^^^^^^

Stand-alone server operation
----------------------------
* Binary location:

  * Linux: bin/mesycontrol_server
  * Windows: mesycontrol_server.exe in the installation path

* Handles all MRC communication
* Opens a listening socket and waits for mesycontrol clients to connect
* An overview of all options is available by running::

  $ ./mesycontrol_server --help

* Common use cases:

  * Using a local serial port and listening on all network interfaces:::

      $ ./mesycontrol_server --mrc-serial-port=/dev/ttyUSB0

  * Local serial port as above but limit the listening socket to a certain IP
    address and using a different listening port:::

      $ ./mesycontrol_server --mrc-serial-port=/dev/ttyUSB0 \
        --listen-address=192.168.168.202 --listen-port=23023

  * Connection to a serial server:::

      $ ./mesycontrol_server --mrc-host=example.com --mrc-port=42000

* To stop a running server instance hit *CTRL-C* in the terminal or send the
  termination signal to the process (e.g. via the *kill* command)

TODOS
=====
.. todolist::

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

